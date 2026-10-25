"""Sampled employer activity alongside exact hired-worker attendance.

Purse reservations are not physical holds. Displacement-bearing sample windows
are not proof that an employer moved continuously throughout those windows.
"""
from collections import Counter, deque
import copy
import math
import time

from activity_leases import paid_work_reservations, paid_work_activity_actors, reserved_activity_actors, reserved_work_accounts
from paid_employment import paid_identity, paid_receipt_matches
from paid_employment_metrics import _jobs, _digest
from resident_identity import resident_identity_status
from routing import actor_route_supported, activity_blocker
from spatial_telemetry import space_key

DEFAULT_POLICY = {'sample_seconds': 5, 'maximum_gap_seconds': 30, 'window_seconds': 900,
                  'maximum_samples': 256, 'position_jitter_units': 8,
                  'maximum_speed_units_per_second': 2000, 'maximum_game_gap_minutes': 10}


def _finite(value):return type(value) in (int, float) and math.isfinite(value)


def _fresh(state, obs, fresh):
    native = obs.get('paid_employment') or {}
    status = state.get('paid_employment');status = status if isinstance(status, dict) else {}
    epoch = state.get('paid_work_epoch', status.get('epoch'))
    return (fresh is True and obs.get('ready') is True and obs.get('paused') is not True
        and isinstance(obs.get('session'), str) and bool(obs['session'])
        and type(obs.get('checkpoint')) is int and obs['checkpoint'] >= 0
        and (state.get('checkpoint') is None or state['checkpoint'] == obs['checkpoint'])
        and not state.get('transition') and not state.get('error') and isinstance(native, dict)
        and native.get('available') is True and type(native.get('protocol')) is int and native['protocol'] == 2
        and isinstance(native.get('epoch'), str) and bool(native['epoch'])
        and (epoch is None or epoch == native['epoch'])
        and native.get('session') == obs['session'])


def _records(state):
    raw, measured = _jobs(state);groups = {};invalid = 0
    for job in raw:
        if not isinstance(job, dict):invalid += 1;continue
        identifier = job.get('id', job.get('job_id'))
        if not isinstance(identifier, str) or not identifier:invalid += 1;continue
        groups.setdefault(identifier, []).append(job)
    result = [];conflicts = 0
    for identifier, rows in groups.items():
        if any(row != rows[0] for row in rows[1:]):conflicts += 1;continue
        job = rows[0]
        if job.get('receipt_acknowledged') is True and job.get('release_verified') is True and job.get('effect_unreconciled') is False:continue
        identity = paid_identity(job)
        if job.get('protocol') != 2 or not paid_receipt_matches(identity, job):invalid += 1;continue
        result.append((job, _digest(identity)))
    return result, measured, invalid, conflicts


def _resident(state, obs, actor, base):
    status = resident_identity_status(state, obs, actor)
    if not status['qualified'] or status['base_id'] != base:return None
    rows = [row for row in obs.get('residents', []) if isinstance(row, dict) and row.get('id') == actor]
    return rows[0] if len(rows) == 1 else None


def _conversation(state, obs, actor):
    if 'conversationAttendance' not in obs:return None
    attendance = obs['conversationAttendance']
    if attendance is None:return False
    if not isinstance(attendance, dict) or attendance.get('phase') != 'attending':return None
    identifier = attendance.get('id');participants = attendance.get('participants')
    if not isinstance(identifier, str) or not identifier or not isinstance(participants, list) or len(participants) < 2:return None
    seen = set();identities = []
    for row in participants:
        if not isinstance(row, dict) or type(row.get('actor')) is not int or row['actor'] in seen:return None
        seen.add(row['actor'])
        if row.get('ownedPackage') is not True or row.get('loaded') is not True:return None
        identity = resident_identity_status(state, obs, row['actor'])
        if not identity['qualified']:return None
        identities.append([row['actor'], identity['base_id']])
    return {'id': identifier, 'participants': sorted(identities)} if actor in seen else False


def snapshot_metrics(state, observation=None, fresh=False):
    state = state or {};obs = observation or {};current = bool(_fresh(state, obs, fresh))
    records, measured, invalid, conflicts = _records(state)
    activities = reserved_activity_actors(state, obs) if current else set()
    accounts = reserved_work_accounts(state, obs) if current else set()
    paid_accounts = paid_work_reservations(state, obs)[0] if current else set()
    paid_activities = paid_work_activity_actors(state, obs) if current else set()
    rows = [];employers = {};observed_workers = set()
    for job, digest in records:
        worker, employer = job['worker'], job['employer']
        resident = _resident(state, obs, employer, job['employer_base_id']) if current else None
        conversation = _conversation(state, obs, employer) if resident else None
        activity = {'state': 'unmeasured', 'conversation_id': None}
        if resident:
            blocker = activity_blocker(resident)
            activity = {'state': 'conversation_attending' if isinstance(conversation, dict)
                        else blocker or 'observed_loaded',
                        'conversation_id': conversation['id'] if isinstance(conversation, dict) else None}
        eligible = None
        if current:
            route = actor_route_supported(obs, employer) if resident else None
            eligible = (False if employer in activities or route is False or isinstance(conversation, dict)
                        else True if resident and route is True and conversation is False else None)
            employers[employer] = eligible
        working, _ = _working(state, obs, job) if current else (None, 'stale_observation')
        if working:observed_workers.add(worker)
        rows.append({'id': job.get('id', job.get('job_id')), 'identity_digest': digest,
            'worker': worker, 'employer': employer,
            'reservations': {role + '_activity': actor in activities if current else None for role, actor in (('worker', worker), ('employer', employer))}
                | {role + '_inventory': 'native-inventory:' + str(actor) in accounts if current else None for role, actor in (('worker', worker), ('employer', employer))},
            'employer_non_economic_eligible': eligible, 'employer_activity': activity,
            'worker_attendance_observed': bool(working) if current else None})
    return {'schema_version': 'employment-concurrency-v1', 'fresh': current, 'measured': measured,
        'jobs': rows, 'invalid_job_rows': invalid, 'conflicting_job_lineages': conflicts,
        'counts': {'paid_account_participants': len(paid_accounts) if current else None,
                   'paid_activity_reserved_participants': len(paid_activities) if current else None,
                   'observed_attending_workers': len(observed_workers) if current else None,
                   'employers': len({job['employer'] for job, _ in records}),
                   'employers_non_economic_eligible': sum(value is True for value in employers.values()) if current else None,
                   'employers_eligibility_unknown': sum(value is None for value in employers.values()) if current else None},
        'scope': 'Current effective activity admission exclusions and inventory reservations are distinct. Eligibility checks current identity, route executor, native occupancy and reservation gates only; it does not promise a particular target, path, choice or scheduler slot. Observed loaded is not idle. A snapshot cannot prove concurrency duration.'}


def _working(state, obs, job):
    native = obs.get('paid_employment') or {}
    if not isinstance(native, dict) or not isinstance(native.get('jobs', []), list):return None, 'invalid_native_job_collection'
    matches = [row for row in native.get('jobs', []) if isinstance(row, dict) and paid_receipt_matches(row, job)]
    if job.get('phase') == 'held' or job.get('cancel_requested') or job.get('reset_held') or job.get('effect_unreconciled') is True:
        return None, 'saved_job_held'
    if job.get('session') != obs.get('session') or job.get('epoch') != native.get('epoch'):return None, 'stale_job_identity'
    if len(matches) != 1:return None, 'missing_or_duplicate_native_job'
    row = matches[0];attendance = row.get('attendance') or {}
    if not isinstance(attendance, dict):return None, 'invalid_native_attendance'
    if row.get('phase') != 'working' or row.get('release_requested') is True or row.get('release_verified') is True:return None, 'worker_not_attending'
    worker = _resident(state, obs, job['worker'], job['worker_base_id'])
    if not worker or activity_blocker(worker):return None, 'worker_identity_or_activity_unqualified'
    controller = obs.get('resident_control') or {}
    if not isinstance(controller, dict) or not isinstance(controller.get('activities', []), list):return None, 'invalid_resident_control'
    control = [value for value in controller.get('activities', [])
               if isinstance(value, dict) and value.get('actor') == job['worker'] and value.get('slot') == job['slot']]
    hold = 'paid-work-' + job.get('job_id', job.get('id'))
    if (len(control) != 1 or control[0].get('expectedPackage') != job['expected_package']
            or control[0].get('work_hold_id') != hold or control[0].get('goal_id') != hold
            or control[0].get('mode') != 'await_decision' or control[0].get('target') != job['worker']
            or (worker.get('activity') or {}).get('package_id') != job['expected_package']
            or type(attendance.get('serial')) is not int or not 1 <= attendance['serial'] <= 16777215
            or attendance.get('slot') != job['slot'] or attendance.get('expected_package') != job['expected_package']
            or attendance.get('cell_id') != job['cell_id'] or attendance.get('anchor') != job['anchor']
            or type(attendance.get('samples')) is not int or attendance['samples'] < 1
            or not _finite(attendance.get('worked_minutes')) or attendance['worked_minutes'] < 0):
        return None, 'worker_lease_unverified'
    return {'serial': attendance['serial'], 'worked_minutes': attendance['worked_minutes'],
            'samples': attendance['samples']}, None


class EmploymentConcurrencyTelemetry:
    def __init__(self, policy=None):
        self.policy = copy.deepcopy(DEFAULT_POLICY if policy is None else policy)
        if set(self.policy) != set(DEFAULT_POLICY) or any(not _finite(value) or value <= 0 for value in self.policy.values()):
            raise ValueError('Invalid employment concurrency sampling policy')
        if (type(self.policy['maximum_samples']) is not int or self.policy['maximum_samples'] > 10000
                or self.policy['sample_seconds'] < 1 or self.policy['maximum_gap_seconds'] < self.policy['sample_seconds']):
            raise ValueError('Invalid bounded employment sampling intervals')
        self.frames = deque(maxlen=self.policy['maximum_samples']);self.previous = None
        self.segment = 0;self.segment_reason = 'not_started';self.snapshot = None;self.session = None;self.epoch = None

    def _reset(self, session, epoch, reason):
        self.frames.clear();self.previous = None;self.segment += 1
        self.session = session;self.epoch = epoch;self.segment_reason = reason

    def observe(self, state, observation, now=None):
        now = time.monotonic() if now is None else now
        if not _finite(now):raise ValueError('Finite monotonic sample time required')
        obs = observation or {};state = state or {};native = obs.get('paid_employment') or {}
        if not isinstance(native, dict):native = {}
        session = obs.get('session');epoch = native.get('epoch');day = obs.get('gameDays');checkpoint = obs.get('checkpoint')
        previous = self.previous
        if session != self.session or epoch != self.epoch:
            self._reset(session, epoch, 'session_or_native_epoch_changed');previous = None
        elif previous and (now < previous['at'] or _finite(day) and _finite(previous['day']) and day < previous['day']
                           or type(checkpoint) is int and type(previous['checkpoint']) is int and checkpoint < previous['checkpoint']):
            self._reset(session, epoch, 'clock_or_checkpoint_reversed');previous = None
        self.snapshot = snapshot_metrics(state, obs, fresh=True)
        if previous and now - previous['at'] < self.policy['sample_seconds']:return self.status(session, now)
        records, _, _, _ = _records(state);samples = {}
        for job, digest in records:
            working, reason = _working(state, obs, job) if self.snapshot['fresh'] else (None, 'stale_observation')
            employer = _resident(state, obs, job['employer'], job['employer_base_id']) if self.snapshot['fresh'] else None
            position = [employer.get(key) for key in ('x', 'y', 'z')] if employer else None
            space = space_key(employer.get('space')) if employer else None
            if employer and space is None and type(employer.get('cell_id')) is int and employer['cell_id'] > 0:space = ('cell', employer['cell_id'])
            samples[digest] = {'id': job.get('id', job.get('job_id')), 'working': working, 'reason': reason,
                'position': position if position and all(_finite(value) for value in position) else None,
                'space': space, 'conversation': _conversation(state, obs, job['employer']) if employer else None}
        exclusions = Counter();intervals = [];candidates = set(samples) | set(previous['samples'] if previous else {})
        dt = now - previous['at'] if previous else None
        for digest in candidates:
            a = previous['samples'].get(digest) if previous else None;b = samples.get(digest)
            reason = ('initial_sample' if not previous else 'observation_gap' if dt > self.policy['maximum_gap_seconds']
                      else 'job_identity_not_paired' if a is None or b is None else
                      'worker_attendance_not_paired' if not a['working'] or not b['working'] else
                      'worker_lease_changed' if a['working']['serial'] != b['working']['serial'] else None)
            minutes = b['working']['worked_minutes'] - a['working']['worked_minutes'] if reason is None else None
            game_delta = (day - previous['day']) * 1440 if previous and _finite(day) and _finite(previous['day']) else None
            if reason is None and (not _finite(game_delta) or game_delta <= 0 or game_delta > self.policy['maximum_game_gap_minutes']
                                   or minutes <= 0 or minutes > game_delta + 1e-5 or b['working']['samples'] <= a['working']['samples']):
                reason = 'attendance_clock_not_advancing_or_discontinuous'
            if reason:exclusions[reason] += 1;continue
            movement = None;conversation = None
            if a['position'] is not None and b['position'] is not None and a['space'] is not None and a['space'] == b['space']:
                distance = math.dist(a['position'], b['position'])
                if distance / dt <= self.policy['maximum_speed_units_per_second']:movement = distance > self.policy['position_jitter_units']
            if a['conversation'] is False and b['conversation'] is False:conversation = False
            elif isinstance(a['conversation'], dict) and a['conversation'] == b['conversation']:conversation = True
            intervals.append({'identity_digest': digest, 'id': b['id'], 'seconds': dt, 'game_minutes': minutes,
                              'employer_movement': movement, 'employer_conversation': conversation})
        frame = {'at': now, 'day': day if _finite(day) else None, 'checkpoint': checkpoint,
                 'samples': samples, 'intervals': intervals, 'candidate_intervals': len(candidates) if previous else 0,
                 'excluded': dict(exclusions)}
        self.frames.append(frame);self.previous = frame
        while self.frames and now - self.frames[0]['at'] > self.policy['window_seconds']:self.frames.popleft()
        return self.status(session, now)

    def status(self, session=None, now=None):
        now = time.monotonic() if now is None else now
        if not _finite(now):raise ValueError('Finite monotonic sample time required')
        current = session in (None, self.session)
        frames = [frame for frame in self.frames if current and 0 <= now - frame['at'] <= self.policy['window_seconds']]
        intervals = [row for frame in frames for row in frame['intervals']];excluded = Counter()
        for frame in frames:excluded.update(frame['excluded'])
        overlap = {}
        for channel in ('employer_movement', 'employer_conversation'):
            known = [row for row in intervals if type(row[channel]) is bool]
            positive = [row for row in known if row[channel]]
            overlap[channel] = {'n': len(known), 'positive_intervals': len(positive) if known else None,
                'unknown_intervals': len(intervals) - len(known),
                'sampled_overlap_seconds': round(sum(row['seconds'] for row in positive), 6) if known else None,
                'sampled_overlap_game_minutes': round(sum(row['game_minutes'] for row in positive), 6) if known else None,
                'measured_interval_seconds': round(sum(row['seconds'] for row in known), 6) if known else None,
                'measured_interval_game_minutes': round(sum(row['game_minutes'] for row in known), 6) if known else None}
        result = copy.deepcopy(self.snapshot or {'schema_version': 'employment-concurrency-v1', 'fresh': False, 'jobs': [], 'counts': {}})
        result['fresh'] = bool(current and result.get('fresh') and self.previous and 0 <= now - self.previous['at'] <= self.policy['maximum_gap_seconds'])
        if not result['fresh']:
            result['counts'] = {key: None for key in result.get('counts', {})}
            for row in result['jobs']:
                row['reservations'] = {key: None for key in row['reservations']}
                row['employer_non_economic_eligible'] = None;row['employer_activity'] = {'state': 'unmeasured', 'conversation_id': None}
                row['worker_attendance_observed'] = None
        initial = excluded.pop('initial_sample', 0)
        result.update(segment=self.segment, segment_reason=self.segment_reason, samples=len(frames),
            policy=copy.deepcopy(self.policy), policy_hash=_digest(self.policy),
            overlap=overlap, coverage={'candidate_job_intervals': sum(frame['candidate_intervals'] for frame in frames),
                'qualified_attendance_intervals': len(intervals), 'unpaired_initial_jobs': initial, 'excluded': dict(excluded)},
            overlap_scope='Ephemeral rolling-window paired samples, reset on session, epoch or checkpoint rollback. Durations are job-interval totals, not unique wall time. Movement means displacement above jitter within a sampled attendance window, not continuous motion throughout it. Conversation means the same owned attendance pair at both endpoints, not continuously audible speech. Worker accrued game minutes require advancing exact-lease native attendance. Gaps, missing evidence and discontinuities are excluded, never treated as inactivity; no historical totals are reconstructed.')
        return result
