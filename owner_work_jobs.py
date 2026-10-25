"""Independent owner attendance followed by one serialized native recipe.

Attendance proves stationary game time, not productive animation. Only an
exact single-use native commit receipt and observed inventories earn output.
"""
import copy
import hashlib
import json
import math
import secrets
import time
from activity_leases import owner_work_leases, activity_conflict, work_account_conflict
from activity_plan_sources import find_activity_plan, independent_plan_authorized
from enterprises import production_policy
from entrepreneurship import learn_recipe
from owner_production import owner_work_opportunities
from economy_catalog import (commodity_ids, recipe_spec, recipe_hash, catalog_hash, apply_recipe,
                             native_catalog_matches, MAX_STOCK)

SCHEMA = 'owner-work-jobs-v1'
DEFAULT_CAPACITY = 4
IDENTITY = ('actor', 'slot', 'session', 'epoch', 'business_id', 'business_revision',
            'recipe_id', 'policy_version', 'work_minutes', 'catalog_hash', 'recipe_hash')
PHASES = ('attendance_verified', 'recipe_committed', 'complete', 'held')


def _finite(value):return type(value) in (int, float) and math.isfinite(value)


def _safe(value):
    if isinstance(value, float) and not math.isfinite(value):return None
    if isinstance(value, dict):return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, list):return [_safe(item) for item in value]
    return value


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _matches(receipt, job):
    if not isinstance(receipt, dict):return False
    actual = {**receipt, 'session': receipt.get('job_session', receipt.get('session'))}
    return (actual.get('job_id') == job['id'] and all(
            type(actual.get(k)) is type(job[k]) and actual.get(k) == job[k] if k in job else actual.get(k) is None for k in IDENTITY)
            and ('actor_base_id' not in job or type(actual.get('actor_base_id')) is int and actual['actor_base_id'] == job['actor_base_id']))


def _identity(job):
    result = {'job_id': job['id'], **{key: job[key] for key in IDENTITY if key in job}}
    if 'actor_base_id' in job:result['actor_base_id'] = job['actor_base_id']
    return result


def _command(job, acknowledge=False):
    return {'id': ('owner-work-ack-' if acknowledge else 'owner-work-start-') + job['id'],
            'kind': 'owner_work_ack_receipt' if acknowledge else 'owner_work_start', **_identity(job)}


def _record(state, job):
    return state['work_orphans'][job['orphan_key']] if job.get('orphan') else state['work_jobs'][job['id']]


def _current_business(state, job):
    business = state.get('town', {}).get('businesses', {}).get(job['business_id'])
    try:
        return bool(business and business.get('active', True) is True and business.get('owner') == job['actor']
            and business.get('custodian') == job['actor'] and business.get('revision', 0) == job['business_revision']
            and job['recipe_id'] in business.get('capabilities', []) and production_policy(business,job['recipe_id']) == job['policy'])
    except (ValueError,KeyError,TypeError):return False


def _current_catalog(job):
    try:return job.get('catalog_hash')==catalog_hash() and job.get('recipe_hash')==recipe_hash(job['recipe_id'])
    except (KeyError,ValueError):return False


def _native_identity_supported(job):
    return (type(job.get('actor_base_id')) is int and job['actor_base_id']>0
        and all(isinstance(job.get(key),str) and len(job[key])==64 and all(c in '0123456789abcdef' for c in job[key])
                for key in ('catalog_hash','recipe_hash')))


def _inventory(observation, job):
    actor = next((r for r in observation.get('residents', []) if r.get('id') == job['actor'] and r.get('isPerson') is True), None)
    if not actor or 'actor_base_id' in job and actor.get('baseId') != job['actor_base_id']:return None
    inventory = actor.get('inventory', {})
    items=commodity_ids()
    if any(type(inventory.get(k)) is not int or not 0<=inventory[k]<=MAX_STOCK for k in items):return None
    return {'owner': {k: inventory[k] for k in items}}


def _attendance_valid(receipt, job, day):
    evidence = receipt.get('attendance') or {};ready = evidence.get('ready_at');expires = evidence.get('expires_at')
    minutes = evidence.get('worked_minutes');anchor = evidence.get('anchor');token = evidence.get('token')
    return (receipt.get('phase') == 'attendance_verified' and receipt.get('effects_issued') is False
        and isinstance(token, str) and 1 <= len(token) <= 256
        and type(evidence.get('slot')) is int and evidence.get('slot') == job['slot']
        and type(evidence.get('serial')) is int and 1 <= evidence['serial'] <= 16777215
        and type(evidence.get('expected_package')) is int and evidence.get('expected_package') == job['expected_package']
        and isinstance(anchor, list) and len(anchor) == 3 and all(_finite(v) for v in anchor)
        and type(evidence.get('samples')) is int and evidence['samples'] >= 2
        and _finite(minutes) and job['work_minutes'] <= minutes <= job['work_minutes'] + 1
        and _finite(ready) and _finite(expires) and ready <= time.time() * 1000 < expires and expires > ready
        and _finite(day) and day >= job['created_day'] + job['work_minutes'] / 1440 - 1e-7)


def _orphan_key(receipt):
    if not isinstance(receipt, dict) or receipt.get('phase') not in PHASES:return None
    for key in ('job_id', 'session', 'epoch', 'business_id', 'recipe_id', 'policy_version'):
        if not isinstance(receipt.get(key), str) or not 1 <= len(receipt[key]) <= 256:return None
    if type(receipt.get('actor')) is not int or receipt['actor'] <= 0:return None
    if type(receipt.get('slot')) is not int or not 0 <= receipt['slot'] < 128:return None
    if type(receipt.get('business_revision')) is not int or receipt['business_revision'] < 0:return None
    if type(receipt.get('work_minutes')) is not int or not 5 <= receipt['work_minutes'] <= 120:return None
    if type(receipt.get('release_verified')) is not bool:return None
    for key in ('catalog_hash','recipe_hash'):
        if key in receipt and (not isinstance(receipt[key],str) or len(receipt[key])!=64 or any(c not in '0123456789abcdef' for c in receipt[key])):return None
    return _hash({key: receipt[key] for key in ('job_id', *IDENTITY) if key in receipt})


class OwnerWorkJobs:
    def owner_work_status(self):
        state = self.active or {}
        def view(job):
            return {**_identity(job), 'id': job['id'], 'kind': 'owner_production', 'custodian': job['actor'],
                    'account_actor': job['actor'], 'productive_animation_verified': False,
                    **{key: copy.deepcopy(job.get(key)) for key in (
                        'source_plan', 'phase', 'created_day', 'accepted_day', 'attendance_verified_day',
                        'recipe_prepared_day', 'committed_day', 'settled_day', 'attendance', 'attendance_receipt_hash',
                        'settlement', 'release_verified', 'receipt_acknowledged', 'receipt_hash', 'outcome',
                        'error', 'orphan', 'received_session', 'cancel_requested', 'no_effects_issued',
                        'effect_unreconciled', 'input_reservation','recipe_definition','catalog_held','capability_source')}}
        records = [*state.get('work_jobs', {}).values(), *state.get('work_orphans', {}).values()]
        return {'schema_version': SCHEMA, 'pool_id': 'citizen-owner-work',
                'capacity': state.get('work_job_capacity', DEFAULT_CAPACITY), 'epoch': state.get('work_job_epoch'),
                'jobs': [view(job) for job in owner_work_leases(state)],
                'history': [view(job) for job in records if job.get('receipt_acknowledged')][-32:]}

    def delegate_owner_work(self, plan, observation):
        if not isinstance(self.active, dict) or not isinstance(plan, dict):
            raise ValueError('Owner delegation requires a saved society and accepted plan')
        independent = independent_plan_authorized(self.active, plan, 'ready_to_self_work')
        if (plan.get('kind') == 'independent_review' or 'independent_review' in plan
                or plan.get('id') in self.active.get('independent_plans', {})) and not independent:
            raise ValueError('Independent owner decision is not an exact accepted saved review')
        if independent:
            self._agency_guard(observation, allow_routines=True)
            from resident_goals import occupied
            from resident_identity import resident_identity_status
            if plan.get('actor') in occupied(self.active, observation):
                raise ValueError('Independent owner actor is occupied by foreground or routine activity')
            identity = resident_identity_status(self.active, observation, plan.get('actor'))
            if (not identity['qualified'] or identity['base_id'] != plan.get('actor_base_id')
                    or plan.get('session') != self.session):
                raise ValueError('Independent owner requires a current bound resident identity')
        else:
            self._agency_guard(observation)
        if not independent and (plan is not self.agency_plan() or plan.get('phase') != 'ready_to_self_work'):
            raise ValueError('Independent owner work requires the current accepted owner decision')
        capability = observation.get('owner_work_jobs') or {};capacity = capability.get('capacity')
        if capability.get('available') is not True or type(capacity) is not int or not 1 <= capacity <= 128:
            raise ValueError('Independent owner work capacity is unavailable')
        if len(owner_work_leases(self.active)) >= capacity:raise ValueError('Independent owner work capacity is leased')
        terms = plan['own_work_terms'];actor_id = plan['actor']
        if (terms.get('catalog_hash')!=catalog_hash() or terms.get('recipe_hash')!=recipe_hash(terms.get('recipe_id'))
            or not native_catalog_matches(observation,terms.get('recipe_id'))):
            raise ValueError('Independent owner work requires the matching resolved native catalog')
        if activity_conflict(self.active, actors=(actor_id,), observation=observation) or work_account_conflict(
                self.active, actors=(actor_id,), business_ids=(terms['business_id'],), observation=observation):
            raise ValueError('Owner account or enterprise is already leased')
        if terms not in owner_work_opportunities(self.active, observation, actor_id, require_owned=False):
            raise ValueError('Owner production opportunity changed before delegation')
        actor = next(r for r in observation['residents'] if r['id'] == actor_id)
        if type(actor.get('baseId')) is not int or actor['baseId']<=0:
            raise ValueError('Independent owner work requires an observed native base identity')
        control = next((r for r in (observation.get('resident_control') or {}).get('activities', []) if r.get('actor') == actor_id), {})
        slot = control.get('slot');day = observation.get('gameDays')
        if type(slot) is not int or not 0 <= slot < 128 or not _finite(day) or day < 0:
            raise ValueError('Owner mailbox slot or game clock is unavailable')
        native_rows = capability.get('jobs', []) + capability.get('receipts', [])
        leased_slots = {j.get('slot') for j in [*owner_work_leases(self.active), *native_rows]}
        if slot in leased_slots or len(leased_slots) >= capacity:raise ValueError('Owner work mailbox capacity is leased')
        state = copy.deepcopy(self.active);epoch = state.setdefault('work_job_epoch', secrets.token_hex(12))
        state['work_job_capacity'] = capacity
        job_id = 'owner-work-' + hashlib.sha256((epoch + ':' + plan['id']).encode()).hexdigest()[:24]
        if job_id in state.get('work_jobs', {}):raise ValueError('Owner intention may not be delegated twice')
        policy = copy.deepcopy(terms['policy']);recipe=recipe_spec(terms['recipe_id'])
        job = {'id': job_id, 'kind': 'owner_production', 'source_plan': plan['id'], 'actor': actor_id,
               'custodian': actor_id, 'account_actor': actor_id, 'slot': slot, 'session': self.session, 'epoch': epoch,
               'business_id': terms['business_id'], 'business_revision': terms['revision'], 'recipe_id': terms['recipe_id'],
               'catalog_hash':terms['catalog_hash'],'recipe_hash':terms['recipe_hash'],'recipe_definition':recipe,
               'capability_source':terms['capability_source'],
               'policy_version': 'owner-production-v1:' + _hash(policy)[:16], 'policy': policy,
               'work_minutes': policy['work_minutes'], 'expected_package': terms['expected_package'],
               'input_reservation': copy.deepcopy(recipe['inputs']), 'phase': 'prepared', 'created_day': day,
               'settlement': {'phase': 'not_prepared', 'committed_inventory_verified': False},
               'release_verified': False, 'receipt_acknowledged': False}
        if type(actor.get('baseId')) is int:job['actor_base_id'] = actor['baseId']
        state.setdefault('work_jobs', {})[job_id] = job
        find_activity_plan(state, plan['id']).update(phase='delegated', work_job=job_id)
        state['people'][str(actor_id)]['agency'].update(state='work_delegated', event_id=plan['id'],
            reason='Independent owner attendance; no inventory effect yet')
        return {'checkpoint': self._write(state, 'owner attendance and exclusive account lease persisted'), 'job_id': job_id}

    def owner_work_pending_command(self):
        if not self.active or self.transition or self.error:return None
        for job in owner_work_leases(self.active):
            if (_native_identity_supported(job) and job.get('receipt_hash') and job.get('release_verified')
                and not job.get('effect_unreconciled')):
                command = _command(job, True)
                if job['session'] != self.session:command.update(session=self.session, job_session=job['session'])
                return command
        for job in owner_work_leases(self.active):
            if job['session'] == self.session and job['phase'] == 'prepared' and _current_catalog(job):return _command(job)
        return None

    @staticmethod
    def _hold_owner_job(state, job, reason, *, unreconciled=False):
        job.update(phase='held', error=reason, cancel_requested=True, effect_unreconciled=unreconciled)
        if job.get('orphan'):return
        plan = find_activity_plan(state, job['source_plan'])
        if plan:plan.update(phase='held', outcome='independent_owner_work_held', error=reason, remembered=True)
        for event in state.get('town', {}).get('daily', {}).get('queue', []):
            if event['id'] == job['source_plan']:event.update(status='held', outcome='independent_owner_work_held')

    @staticmethod
    def _complete_owner_job(state, job, day):
        job.update(phase='complete', outcome='owner_work_completed', settled_day=day)
        plan = find_activity_plan(state, job['source_plan'])
        if plan:plan.update(phase='complete', outcome='owner_work_completed', remembered=True)
        for event in state.get('town', {}).get('daily', {}).get('queue', []):
            if event['id'] == job['source_plan']:event.update(status='complete', outcome='owner_work_completed', settled_day=day)
        person = state['people'].get(str(job['actor']))
        if person and _finite(day):person['agency'].update(state='quiet_interval', reason='Owner recipe and release verified', next_review_day=day + 1 / 24)

    def observe_owner_work_jobs(self, observation):
        if not self.active or self.transition or self.error or self.active.get('pending'):return False
        native = observation.get('owner_work_jobs') or {};ack = observation.get('ack') or {};day = observation.get('gameDays')
        for original in owner_work_leases(self.active):
            receipt = next((r for r in native.get('receipts', []) if _matches(r, original)), None)
            if not original.get('orphan') and not _current_catalog(original) and not original.get('catalog_held'):
                state=copy.deepcopy(self.active);job=_record(state,original);job['catalog_held']=True
                self._hold_owner_job(state,job,'Owner catalog or recipe identity is missing or changed; historical proof cannot authorize new work',
                    unreconciled=job.get('settlement',{}).get('phase') in ('prepared','held'))
                self._write(state,'old or unknown owner recipe held without recertifying its catalog');return True
            if (not original.get('orphan') and not original.get('reset_held') and original['session'] != self.session
                and original['phase'] not in ('complete',)):
                state = copy.deepcopy(self.active);job = _record(state, original);job['reset_held'] = True
                ambiguous = job.get('settlement', {}).get('phase') in ('prepared', 'held')
                self._hold_owner_job(state, job, 'Owner attendance session changed; never replay work or recipe', unreconciled=ambiguous)
                self._write(state, 'owner work reset quarantined without importing labour or output');return True
            if receipt:
                if original.get('orphan'):
                    if receipt.get('release_verified') is True and not original.get('release_verified'):
                        state = copy.deepcopy(self.active);job = _record(state, original)
                        job.update(release_verified=True, release_receipt=_safe(receipt), release_receipt_hash=_hash(_safe(receipt)))
                        self._write(state, 'orphan owner task release verified without production credit');return True
                elif (receipt.get('phase') == 'attendance_verified' and original['phase'] in ('prepared', 'running')):
                    state = copy.deepcopy(self.active);job = _record(state, original)
                    if (_attendance_valid(receipt, job, day) and job['session'] == self.session and not job.get('reset_held')
                        and _current_catalog(job) and native_catalog_matches(observation,job['recipe_id'])):
                        job.update(phase='attendance_verified', attendance=copy.deepcopy(receipt['attendance']),
                            attendance_receipt=_safe(receipt), attendance_receipt_hash=_hash(_safe(receipt)), attendance_verified_day=day)
                    else:self._hold_owner_job(state, job, 'Owner attendance evidence or token is not current and valid')
                    self._write(state, 'owner attendance proof persisted; no recipe effect yet');return True
                elif receipt.get('phase') in ('held', 'complete'):
                    digest = _hash(_safe(receipt))
                    if digest != original.get('receipt_hash'):
                        state = copy.deepcopy(self.active);job = _record(state, original)
                        job.update(receipt=_safe(receipt), receipt_hash=digest, release_verified=receipt.get('release_verified') is True)
                        committed = job.get('settlement', {}).get('committed_inventory_verified') is True
                        if (committed and job['release_verified'] and receipt.get('commit_id') == job['settlement'].get('commit_id')
                            and receipt.get('committed_inventory_verified') is True):
                            self._complete_owner_job(state, job, day)
                        elif committed and job['release_verified']:
                            self._hold_owner_job(state, job, 'Released owner receipt does not identify its committed recipe', unreconciled=True)
                        elif not committed:
                            self._hold_owner_job(state, job, receipt.get('error') or 'Owner work ended without verified inventory commitment',
                                unreconciled=receipt.get('effects_issued') is not False and not job.get('orphan'))
                        self._write(state, 'owner terminal receipt recorded independently of production ledger');return True
            if not _matches(ack, original):continue
            if (ack.get('id') == _command(original, True)['id'] and ack.get('status') == 'applied'
                and ack.get('acknowledged') is True and original.get('release_verified') and not original.get('effect_unreconciled')):
                state = copy.deepcopy(self.active);_record(state, original)['receipt_acknowledged'] = True
                self._write(state, 'owner work terminal receipt acknowledged; account lease released');return True
            if original['phase'] == 'prepared' and ack.get('id') == _command(original)['id']:
                state = copy.deepcopy(self.active);job = _record(state, original)
                if ack.get('status') == 'applied' and ack.get('accepted') is True:
                    job.update(phase='running', accepted_day=day if _finite(day) else None)
                else:
                    self._hold_owner_job(state, job, 'Independent owner attendance was not admitted')
                    if ack.get('accepted') is False and ack.get('no_effects_issued') is True:
                        job.update(no_effects_issued=True, receipt_acknowledged=True)
                self._write(state, 'owner work native admission acknowledgement recorded');return True
        for receipt in native.get('receipts', []):
            key = _orphan_key(receipt)
            if key is None or key in self.active.get('work_orphans', {}):continue
            if any(_matches(receipt, j) for j in self.active.get('work_jobs', {}).values()):continue
            state = copy.deepcopy(self.active)
            job = {'id': receipt['job_id'], **{k: receipt[k] for k in IDENTITY if k in receipt}, 'orphan': True, 'orphan_key': key,
                   'phase': 'held', 'outcome': 'orphan_owner_work_held', 'received_session': self.session,
                   'cancel_requested': True, 'receipt': _safe(receipt), 'receipt_hash': _hash(_safe(receipt)),
                   'effect_unreconciled': receipt.get('effects_issued') is not False,
                   'release_verified': receipt['release_verified'], 'receipt_acknowledged': False,
                   'settlement': {'phase': 'not_admitted', 'committed_inventory_verified': False}}
            if type(receipt.get('actor_base_id')) is int:job['actor_base_id'] = receipt['actor_base_id']
            state.setdefault('work_orphans', {})[key] = job
            self._write(state, 'orphan owner attendance quarantined for release only; no recipe authorized');return True
        return False

    def prepare_owner_work_recipe(self, observation):
        if (not self.active or self.error or self.transition or self.active.get('pending') or self.agency_busy()
            or self.conversation_busy() or self.agency_command(self.session) or self.speech_command(self.session)):return False
        if observation.get('session') != self.session or observation.get('checkpoint') != self.marker:return False
        if observation.get('inventory_checkpoint', self.marker) != self.marker:return False
        for original in owner_work_leases(self.active):
            if original.get('orphan') or original['phase'] != 'attendance_verified':continue
            state = copy.deepcopy(self.active);job = _record(state, original);day = observation.get('gameDays')
            evidence = job['attendance'];actual = _inventory(observation, job)
            current_receipt = next((r for r in (observation.get('owner_work_jobs') or {}).get('receipts', []) if _matches(r, job)), None)
            valid = (job['session'] == self.session and _current_catalog(job) and native_catalog_matches(observation,job['recipe_id'])
                     and _current_business(state, job) and actual
                     and current_receipt and _attendance_valid(current_receipt, job, day)
                     and current_receipt['attendance']['token'] == evidence['token'])
            try:after={'owner':apply_recipe(actual['owner'],job['recipe_id'])} if valid else None
            except ValueError:valid=False
            if not valid:
                self._hold_owner_job(state, job, 'Fresh owner stock, charter, identity or attendance permit changed before recipe')
                self._write(state, 'owner recipe not admitted; no inventory effect');return True
            commit_id = 'owner-recipe-' + job['id']
            command = {'id': commit_id, 'kind': 'inventory_self_produce_commit', **_identity(job),
                       'commit_id': commit_id, 'attendance_token': evidence['token'], 'before': actual, 'after': after}
            state['pending'] = {'id': commit_id, 'command': command, 'status': 'pending', 'evidence': None,
                'business_id': job['business_id'], 'work_job': job['id'], 'prepared_session': self.session,
                'recipe_definition':copy.deepcopy(job['recipe_definition']),
                'source': 'Verified independent owner attendance; single account recipe, zero wage'}
            job.update(phase='recipe_prepared', recipe_prepared_day=day,
                settlement={'phase': 'prepared', 'commit_id': commit_id, 'committed_inventory_verified': False})
            self._write(state, 'fresh owner inventory recipe persisted for the exclusive single writer');return True
        return False

    def observe_owner_work_recipe(self, observation):
        pending = self.active.get('pending')
        if not pending or pending.get('command', {}).get('kind') != 'inventory_self_produce_commit':return False
        if pending.get('status') == 'held':return False
        if observation.get('inventory_checkpoint', self.marker) != self.marker:return False
        command = pending['command'];original = self.active.get('work_jobs', {}).get(pending.get('work_job'))
        if original is None:return False
        if not _current_catalog(original) or not native_catalog_matches(observation,original['recipe_id']):
            state=copy.deepcopy(self.active);record=state['pending'];job=_record(state,original)
            record.update(status='held',error='Prepared recipe catalog no longer matches resolved native authority; do not replay')
            job['settlement']['phase']='held';job['catalog_held']=True
            self._hold_owner_job(state,job,record['error'],unreconciled=True)
            self._write(state,'owner recipe catalog mismatch quarantined without inventory credit');return True
        if pending.get('prepared_session') != self.session or observation.get('session') != self.session:
            if pending.get('status') == 'held':return False
            state = copy.deepcopy(self.active);record = state['pending'];job = _record(state, original)
            record.update(status='held', error='Recipe session changed; inventory appearance cannot authorize replay')
            job['settlement']['phase'] = 'held'
            self._hold_owner_job(state, job, record['error'], unreconciled=True)
            self._write(state, 'prepared owner recipe quarantined across load without replay');return True
        ack = observation.get('ack') or {}
        if ack.get('id') != command['id']:return False
        actual = _inventory(observation, original)
        if actual is None or not _finite(observation.get('gameDays')):return False
        state = copy.deepcopy(self.active);record = state['pending'];job = _record(state, original);day = observation.get('gameDays')
        record['evidence'] = {'actual': actual, 'ack': _safe(copy.deepcopy(ack)), 'session': self.session}
        applied = (_matches(ack, job) and ack.get('status') == 'applied' and ack.get('commit_id') == command['id']
            and ack.get('attendance_token') == command['attendance_token'] and ack.get('effects_issued') is True
            and ack.get('committed_inventory_verified') is True and ack.get('inventory') == actual == command['after'])
        if applied:
            record['status'] = 'committed'
            if not any(r['id'] == record['id'] for r in state.get('production', [])):
                state.setdefault('production', []).append(copy.deepcopy(record))
                person = state['people'][str(job['actor'])];learn_recipe(person, record['id'],job['recipe_id'])
                recipe=job['recipe_definition']
                memory={'event_id': record['id'], 'kind': 'owner_work',
                    'business_id': job['business_id'], 'work_job': job['id'],'recipe_id':job['recipe_id'],
                    'catalog_hash':job['catalog_hash'],'recipe_hash':job['recipe_hash'],
                    'inputs':copy.deepcopy(recipe['inputs']),'outputs':copy.deepcopy(recipe['outputs']),
                    'gold_paid': 0, 'work_minutes': job['work_minutes'],
                    'source': 'Qualified stationary attendance and observed native recipe; productive animation unverified'}
                if job['recipe_id']=='bread_recipe' and set(recipe['inputs'])=={'grain'} and set(recipe['outputs'])=={'bread'}:
                    memory.update(grain_used=recipe['inputs']['grain'],bread_made=recipe['outputs']['bread'])
                person['memories'] = (person.get('memories', []) + [memory])[-32:]
            job.update(phase='recipe_committed', committed_day=day, effect_unreconciled=False,
                       settlement={'phase': 'committed', 'commit_id': record['id'], 'production_record_id': record['id'],
                                   'committed_inventory_verified': True})
            state['pending'] = None
        elif (_matches(ack, job) and ack.get('status') == 'held' and ack.get('no_effects_issued') is True
              and actual == command['before']):
            record.update(status='cancelled', outcome='interrupted_before_effects')
            state.setdefault('cancelled_production', []).append(record);state['pending'] = None
            job['settlement']['phase'] = 'cancelled'
            self._hold_owner_job(state, job, 'Owner recipe rejected before effects; no output recorded')
        else:
            record.update(status='held', error='Owner recipe receipt or physical inventory needs reconciliation; do not replay')
            job['settlement']['phase'] = 'held'
            self._hold_owner_job(state, job, record['error'], unreconciled=True)
        self._write(state, 'owner recipe reconciled with its exact native permit and physical account');return True
