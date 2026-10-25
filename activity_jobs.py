"""Save-bound independent seated breaks; acceptance is never completion.

Two native slots are a protocol capacity, not a population scheduler limit.
Leases survive held jobs until native release is proved and acknowledged.
"""
import copy
import hashlib
import json
import math
import secrets
from rest import rest_opportunities, FATIGUE_PER_GAME_HOUR
from activity_leases import activity_leases, reserved_activity_actors, reserved_activity_targets
from activity_plan_sources import find_activity_plan, independent_plan_authorized

CAPACITY = 2
IDENTITY = ('actor', 'target', 'slot', 'session', 'epoch')
REST_POLICY = {'version': 'independent-rest-v1', 'rest_minutes': 30,
               'fatigue_recovery': .35, 'fatigue_per_game_hour': FATIGUE_PER_GAME_HOUR,
               'next_review_minutes': 60}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _safe(value):
    if isinstance(value, float) and not math.isfinite(value):return None
    if isinstance(value, dict):return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, list):return [_safe(item) for item in value]
    return value


def _matches(receipt, job):
    if isinstance(receipt, dict) and 'job_session' in receipt:
        receipt = {**receipt, 'session': receipt['job_session']}
    return isinstance(receipt, dict) and receipt.get('job_id') == job['id'] and all(
        type(receipt.get(key)) is type(job[key]) and receipt.get(key) == job[key] for key in IDENTITY)


def _command(job, acknowledge=False):
    command = {'id': ('activity-ack-' if acknowledge else 'activity-start-') + job['id'],
            'kind': 'activity_ack_receipt' if acknowledge else 'activity_start_rest',
            'job_id': job['id'], **{key: job[key] for key in IDENTITY},
            'rest_minutes': job['policy']['rest_minutes']}
    if 'actor_base_id' in job:command['actor_base_id'] = job['actor_base_id']
    return command


def _orphan_key(receipt):
    """Only exact bounded native terminal identities may enter reconciliation."""
    if not isinstance(receipt, dict) or receipt.get('status') not in ('applied', 'held'):return None
    for key in ('job_id', 'session', 'epoch'):
        if not isinstance(receipt.get(key), str) or not 1 <= len(receipt[key]) <= 128:return None
    if any(type(receipt.get(key)) is not int or receipt[key] <= 0 for key in ('actor', 'target')):return None
    if type(receipt.get('slot')) is not int or not 0 <= receipt['slot'] < CAPACITY:return None
    evidence = receipt.get('rest')
    if not isinstance(evidence, dict):return None
    if any(type(evidence.get(key)) is not int or evidence[key] != receipt[key] for key in ('actor', 'target')):return None
    if type(evidence.get('release_verified')) is not bool:return None
    identity = {key: receipt[key] for key in ('job_id', *IDENTITY)}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _receipt_record(receipt):
    safe = _safe(copy.deepcopy(receipt))
    return safe, hashlib.sha256(json.dumps(safe, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class ActivityJobs:
    def activity_status(self):
        state = self.active or {}
        def view(job):
            projected = {'id': job['id'], **{key: job[key] for key in IDENTITY},
                    'rest_minutes': job['policy']['rest_minutes'],
                    **{key: copy.deepcopy(job.get(key)) for key in (
                        'source_plan', 'phase', 'created_day', 'accepted_day', 'settled_day',
                        'release_verified', 'receipt_acknowledged', 'outcome', 'error', 'receipt_hash', 'no_effects_issued',
                        'orphan', 'received_session', 'recovery_applied')}}
            if type(job.get('actor_base_id')) is int:projected['actor_base_id'] = job['actor_base_id']
            return projected
        history = [*state.get('activity_jobs', {}).values(), *state.get('activity_orphans', {}).values()]
        return {'epoch': state.get('activity_job_epoch'), 'capacity': CAPACITY,
                'jobs': [view(job) for job in activity_leases(state)],
                'history': [view(job) for job in history if job.get('receipt_acknowledged')][-32:]}

    def delegate_rest(self, plan, observation):
        independent = (isinstance(plan, dict) and
                       (self.active or {}).get('independent_plans', {}).get(plan.get('id')) is plan)
        if independent:
            self._agency_guard(observation, allow_routines=True)
            if not independent_plan_authorized(self.active, plan, 'ready_to_rest'):
                raise ValueError('Delegation requires an exact accepted independent rest review')
            from resident_goals import occupied
            if plan['actor'] in occupied(self.active, observation):
                raise ValueError('Independent rest resident has a foreground or activity conflict')
            actor = next((row for row in observation.get('residents', []) if row.get('id') == plan['actor']), {})
            if plan.get('session') != self.session or plan.get('actor_base_id') != actor.get('baseId'):
                raise ValueError('Independent rest review session or resident identity changed')
        else:
            self._agency_guard(observation)
            if plan is not self.agency_plan() or plan.get('phase') != 'ready_to_rest':
                raise ValueError('Delegation requires the current accepted rest intention')
        capability = observation.get('activity_jobs') or {}
        if capability.get('available') is not True or type(capability.get('capacity')) is not int or capability['capacity'] != CAPACITY:
            raise ValueError('Two independent native activity slots are unavailable')
        day = observation.get('gameDays')
        if not _finite(day) or day < 0:raise ValueError('A finite activity clock is required')
        leases = activity_leases(self.active)
        native_leases = capability.get('jobs', []) + capability.get('receipts', [])
        slots = {job.get('slot') for job in leases + native_leases if type(job.get('slot')) is int}
        if len(leases) >= CAPACITY or all(slot in slots for slot in range(CAPACITY)):
            raise ValueError('Independent activity capacity is leased')
        if (plan['actor'] in reserved_activity_actors(self.active, observation)
            or plan['rest_target'] in reserved_activity_targets(self.active, observation)):
            raise ValueError('The resident or selected seat already has an activity lease')
        if plan['rest_target'] not in [site['id'] for site in rest_opportunities(self.active, observation, plan['actor'])]:
            raise ValueError('The selected rest site is no longer eligible')
        actor = next(row for row in observation['residents'] if row['id'] == plan['actor'])
        state = copy.deepcopy(self.active)
        epoch = state.setdefault('activity_job_epoch', secrets.token_hex(12))
        job_id = 'rest-' + hashlib.sha256((epoch + ':' + plan['id']).encode()).hexdigest()[:24]
        jobs = state.setdefault('activity_jobs', {})
        if job_id in jobs:raise ValueError('An accepted activity may not be redelegated')
        slot = next(slot for slot in range(CAPACITY) if slot not in slots)
        job = {'id': job_id, 'source_plan': plan['id'], 'kind': 'rest', 'actor': plan['actor'],
               'target': plan['rest_target'], 'slot': slot, 'session': self.session, 'epoch': epoch,
               'phase': 'prepared', 'created_day': day, 'policy': copy.deepcopy(REST_POLICY),
               'receipt_acknowledged': False, 'release_verified': False}
        if type(actor.get('baseId')) is int:job['actor_base_id'] = actor['baseId']
        jobs[job_id] = job
        saved = find_activity_plan(state, plan['id'])
        if saved is None:raise ValueError('Accepted rest source plan is missing')
        saved.update(phase='delegated', activity_job=job_id)
        person = state['people'][str(plan['actor'])]
        person['agency'].update(state='activity_delegated', event_id=plan['id'],
                                reason='Independent seated break awaiting native attendance')
        return {'checkpoint': self._write(state, 'rest job and exclusive actor seat slot leases persisted'), 'job_id': job_id}

    def activity_pending_command(self):
        if not self.active or self.transition or self.error:return None
        jobs = activity_leases(self.active)
        for job in jobs:
            if job.get('receipt_hash') and job.get('release_verified'):
                command = _command(job, acknowledge=True)
                if job['session'] != self.session:command.update(session=self.session, job_session=job['session'])
                return command
        for job in jobs:
            if job['session'] == self.session and job['phase'] == 'prepared':return _command(job)
        return None

    def observe_activity_jobs(self, observation):
        if not self.active or self.transition or self.error:return False
        native = observation.get('activity_jobs') or {}
        ack = observation.get('ack') or {}
        for original in activity_leases(self.active):
            receipt = next((r for r in native.get('receipts', []) if _matches(r, original)), None)
            if original.get('orphan'):
                if receipt and not original.get('release_verified') and _orphan_key(receipt) == original['orphan_key'] and receipt['rest']['release_verified'] is True:
                    state = copy.deepcopy(self.active);record = state['activity_orphans'][original['orphan_key']]
                    safe, digest = _receipt_record(receipt)
                    record.update(release_verified=True, release_receipt=safe, release_receipt_hash=digest)
                    self._write(state, 'orphan activity release proof persisted without importing any simulated effect');return True
                if (_matches(ack, original) and ack.get('id') == _command(original, True)['id']
                    and ack.get('status') == 'applied' and ack.get('acknowledged') is True and original.get('release_verified')):
                    state = copy.deepcopy(self.active);state['activity_orphans'][original['orphan_key']]['receipt_acknowledged'] = True
                    self._write(state, 'orphan terminal receipt acknowledged; quarantine released without recovery');return True
                continue
            session_changed = original['session'] != self.session or observation.get('session') != original['session']
            epoch_changed = (original['phase'] != 'prepared' and isinstance(native.get('epoch'), str)
                             and native['epoch'] != original['epoch'])
            if (session_changed or epoch_changed) and not original.get('reset_held') and not original.get('receipt_hash'):
                state = copy.deepcopy(self.active);job = state['activity_jobs'][original['id']]
                job.update(phase='held', reset_held=True, error='Activity session or epoch changed; no recovery or replay permitted')
                self._hold_activity_plan(state, job, job['error'])
                self._write(state, 'independent activity reset held with lease retained');return True
            # A stale-session receipt can prove release, but cannot grant recovery.
            if receipt and not original.get('receipt_hash'):
                return self._settle_activity_receipt(original, receipt, observation)
            if (receipt and original.get('receipt_hash') and not original.get('release_verified')
                and (receipt.get('rest') or {}).get('release_verified') is True):
                # Native release can later succeed after a held terminal receipt.
                # The previous failed attendance remains failed permanently.
                state = copy.deepcopy(self.active);job = state['activity_jobs'][original['id']]
                job.update(release_verified=True, release_receipt=_safe(copy.deepcopy(receipt)))
                self._hold_activity_plan(state, job, job.get('error', 'Independent rest remained held'))
                self._write(state, 'held independent activity release subsequently verified');return True
            if not _matches(ack, original):continue
            if ack.get('id') == _command(original, True)['id'] and ack.get('status') == 'applied' and ack.get('acknowledged') is True and original.get('receipt_hash') and original.get('release_verified'):
                state = copy.deepcopy(self.active);state['activity_jobs'][original['id']]['receipt_acknowledged'] = True
                self._write(state, 'native terminal receipt acknowledged; activity leases released');return True
            if original['phase'] == 'prepared' and ack.get('id') == _command(original)['id']:
                state = copy.deepcopy(self.active);job = state['activity_jobs'][original['id']]
                if ack.get('status') == 'applied' and ack.get('accepted') is True:
                    accepted_day = observation.get('gameDays')
                    job.update(phase='running', accepted_day=accepted_day if _finite(accepted_day) else None)
                else:
                    job.update(phase='held', error='Native independent activity start was not accepted')
                    if ack.get('accepted') is False and ack.get('no_effects_issued') is True:
                        job.update(receipt_acknowledged=True, no_effects_issued=True)
                    self._hold_activity_plan(state, job, job['error'])
                self._write(state, 'independent activity start acknowledgement recorded');return True
        # A rollback can leave a native terminal job absent from this saved
        # lineage. Persist its release evidence before sending an exact ack;
        # never infer an old resident intention or import its fatigue effects.
        for receipt in native.get('receipts', []):
            key = _orphan_key(receipt)
            if key is None or key in self.active.get('activity_orphans', {}):continue
            if any(_matches(receipt, job) for job in self.active.get('activity_jobs', {}).values()):continue
            state = copy.deepcopy(self.active);safe, digest = _receipt_record(receipt)
            record = {'id': receipt['job_id'], **{field: receipt[field] for field in IDENTITY},
                      'kind': 'rest', 'orphan': True, 'orphan_key': key, 'phase': 'held',
                      'outcome': 'orphan_activity_held', 'received_session': self.session,
                      'policy': copy.deepcopy(REST_POLICY), 'receipt': safe, 'receipt_hash': digest,
                      'release_verified': receipt['rest']['release_verified'], 'receipt_acknowledged': False,
                      'recovery_applied': False,
                      'error': 'Native terminal activity has no matching saved intention; only release reconciliation is permitted'}
            if type(receipt.get('actor_base_id')) is int and receipt['actor_base_id'] > 0:
                record['actor_base_id'] = receipt['actor_base_id']
            state.setdefault('activity_orphans', {})[key] = record
            self._write(state, 'orphan native terminal identity and release evidence durably quarantined');return True
        return False

    @staticmethod
    def _hold_activity_plan(state, job, reason):
        plan = find_activity_plan(state, job['source_plan'])
        if plan:plan.update(phase='held', outcome='independent_rest_held', error=reason,
                            activity_release_required=not (job.get('release_verified') or job.get('no_effects_issued')), remembered=True)
        for event in state.get('town', {}).get('daily', {}).get('queue', []):
            if event['id'] == job['source_plan']:
                event.update(status='held', outcome='independent_rest_held')

    def _settle_activity_receipt(self, original, receipt, observation):
        state = copy.deepcopy(self.active);job = state['activity_jobs'][original['id']]
        evidence = receipt.get('rest') or {};day = observation.get('gameDays')
        safe, digest = _receipt_record(receipt)
        job.update(receipt=safe, receipt_hash=digest, release_verified=evidence.get('release_verified') is True)
        actor = next((r for r in observation.get('residents', []) if r.get('id') == job['actor'] and r.get('isPerson') is True), None)
        minutes = evidence.get('rested_minutes');policy = job['policy']
        valid = (not job.get('reset_held') and job['session'] == self.session and observation.get('session') == job['session']
                 and receipt.get('status') == 'applied' and type(evidence.get('actor')) is int and evidence.get('actor') == job['actor']
                 and type(evidence.get('target')) is int and evidence.get('target') == job['target']
                 and job['release_verified'] and evidence.get('exact_furniture_verified') is True
                 and type(evidence.get('seated_samples')) is int and evidence['seated_samples'] >= 2
                 and _finite(minutes) and policy['rest_minutes'] <= minutes <= policy['rest_minutes'] + 1
                 and _finite(day) and day >= job['created_day'] + policy['rest_minutes'] / 1440 - 1e-7
                 and actor is not None and ('actor_base_id' not in job or actor.get('baseId') == job['actor_base_id']))
        person = state['people'].get(str(job['actor']))
        resident = state.get('town', {}).get('residents', {}).get(str(job['actor']), {})
        clocks = [person.get('needs_clock', resident.get('observed_game_day', day)), person.get('fatigue_clock', 0)] if person else []
        baseline = max(clocks) if clocks and all(_finite(clock) for clock in clocks) else None
        valid = valid and _finite(baseline) and day >= baseline
        if not valid:
            job.update(phase='held', error='Independent rest attendance, identity, clock or release was not verified; no recovery applied')
            self._hold_activity_plan(state, job, job['error'])
        else:
            before = min(1, person['needs']['fatigue'] + (day - baseline) * 24 * policy['fatigue_per_game_hour'])
            person['needs']['fatigue'] = round(max(0, before - policy['fatigue_recovery']), 6);person['fatigue_clock'] = day
            job.update(phase='complete', outcome='rested_at_bench', settled_day=day,
                       fatigue_before=before, fatigue_after=person['needs']['fatigue'])
            person['memories'] = (person.get('memories', []) + [{'event_id': job['id'], 'kind': 'rested_at_bench',
                'bench': job['target'], 'minutes': policy['rest_minutes'], 'receipt_hash': digest,
                'fatigue_before': before, 'fatigue_after': person['needs']['fatigue'],
                'source': 'Independent native seated attendance and verified release; authored recovery'}])[-32:]
            state.setdefault('rests', []).append({'id': job['id'], 'status': 'committed', 'evidence': safe,
                'receipt_hash': digest, 'fatigue_before': before, 'fatigue_after': person['needs']['fatigue']})
            plan = find_activity_plan(state, job['source_plan'])
            if plan:plan.update(phase='complete', outcome='rested_at_bench', remembered=True, activity_release_required=False)
            for event in state.get('town', {}).get('daily', {}).get('queue', []):
                if event['id'] == job['source_plan']:event.update(status='complete', outcome='rested_at_bench', settled_day=day)
            person['agency'].update(state='quiet_interval', reason='Independent seated break verified',
                                    next_review_day=day + policy['next_review_minutes'] / 1440)
        self._write(state, 'independent rest terminal receipt persisted exactly once');return True
