"""Owner-work attendance, inventory settlement and cleanup are separate evidence."""
import math
from collections import Counter


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _identity(row):
    if not isinstance(row, dict):return None
    keys = ('session', 'epoch', 'business_id', 'recipe_id', 'policy_version')
    identifier = row.get('job_id', row.get('id'))
    if not isinstance(identifier, str) or not identifier:return None
    if not all(isinstance(row.get(key), str) and row[key] for key in keys):return None
    if type(row.get('actor')) is not int or row['actor'] <= 0:return None
    if not all(type(row.get(key)) is int and row[key] >= 0 for key in ('slot', 'business_revision')):return None
    if not _number(row.get('work_minutes')) or row['work_minutes'] <= 0:return None
    base = row.get('actor_base_id')
    if base is not None and (type(base) is not int or base <= 0):return None
    return (identifier, row['actor'], base, row['slot'], *(row[key] for key in keys),
            row['business_revision'], row['work_minutes'])


def _inventory(value):
    return isinstance(value, dict) and 'gold' in value and all(
        isinstance(key, str) and type(amount) is int and amount >= 0 for key, amount in value.items())


def _production(job, groups):
    """Only the exact committed job record and reconciled native inventory count."""
    settlement = job.get('settlement') or {}
    commit_id = settlement.get('commit_id')
    if (job.get('orphan') is True or not isinstance(commit_id, str) or not commit_id
            or settlement.get('production_record_id') != commit_id
            or settlement.get('committed_inventory_verified') is not True):return None
    candidates = groups.get(commit_id, [])
    if not candidates or any(record != candidates[0] for record in candidates[1:]):return None
    record = candidates[0];command = record.get('command') or {};evidence = record.get('evidence') or {}
    ack = evidence.get('ack') or {};before = (command.get('before') or {}).get('owner')
    after = (command.get('after') or {}).get('owner')
    if (record.get('status') != 'committed' or command.get('kind') != 'inventory_self_produce_commit'
            or command.get('id') != commit_id or _identity(command) != _identity(job)
            or _identity(ack) != _identity(job) or ack.get('id') != commit_id or ack.get('commit_id') != commit_id
            or ack.get('status') != 'applied' or ack.get('effects_issued') is not True
            or not isinstance(command.get('attendance_token'), str) or not command['attendance_token']
            or ack.get('attendance_token') != command['attendance_token']
            or ack.get('committed_inventory_verified') is not True or ack.get('mechanism') != 'native_owner_recipe'
            or evidence.get('session') != job.get('session') or not _inventory(before) or not _inventory(after)
            or set(before) != set(after) or before['gold'] != after['gold']
            or evidence.get('actual') != command.get('after') or ack.get('inventory') != command.get('after')):return None
    inputs = {good: before[good] - after[good] for good in before if good != 'gold' and after[good] < before[good]}
    outputs = {good: after[good] - before[good] for good in before if good != 'gold' and after[good] > before[good]}
    return {'id': commit_id, 'inputs': inputs, 'outputs': outputs} if inputs and outputs else None


def owner_work_metrics(society, observation, fresh=True):
    saved = society.get('owner_work_jobs');native = observation.get('owner_work_jobs') or {}
    if not isinstance(saved, dict) or not isinstance(saved.get('jobs'), list) or not isinstance(saved.get('history'), list):return None
    leases = saved.get('jobs') if isinstance(saved.get('jobs'), list) else []
    history = saved.get('history') if isinstance(saved.get('history'), list) else []
    records = {};invalid_saved = 0
    for job in [*history, *leases]:
        identity = _identity(job)
        if identity is None:invalid_saved += 1
        else:records[identity] = job
    native_groups = {};invalid_native = 0
    for job in native.get('jobs') or []:
        identity = _identity(job)
        if identity is None:invalid_native += 1
        else:native_groups.setdefault(identity, []).append(job)
    production = {}
    for record in society.get('production') or []:
        if isinstance(record, dict) and isinstance(record.get('id'), str):production.setdefault(record['id'], []).append(record)
    session = observation.get('session')
    current = (fresh is True and native.get('available') is True and isinstance(session, str) and bool(session)
               and isinstance(saved.get('epoch'), str) and native.get('epoch') == saved['epoch'])
    capacity = saved.get('capacity') if type(saved.get('capacity')) is int and saved['capacity'] > 0 else None
    native_capacity = native.get('capacity') if type(native.get('capacity')) is int and native['capacity'] > 0 else None
    current = current and capacity is not None and native_capacity == capacity
    rows = [];seen = set();matched = set();commits = {};qualified = set();admitted = set();released = set()
    invalid_commit_claims = 0
    for identity, job in records.items():
        proof = _production(job, production)
        if proof:commits[proof['id']] = proof
        elif (job.get('settlement') or {}).get('committed_inventory_verified') is True:invalid_commit_claims += 1
        attendance = job.get('attendance') or {}
        is_qualified = (job.get('orphan') is not True and _number(job.get('attendance_verified_day'))
                        and _number(attendance.get('worked_minutes')) and attendance['worked_minutes'] >= job['work_minutes']
                        and type(attendance.get('samples')) is int and attendance['samples'] >= 2
                        and isinstance(job.get('attendance_receipt_hash'), str) and bool(job['attendance_receipt_hash']))
        if is_qualified:qualified.add(identity)
        if job.get('orphan') is not True and _number(job.get('accepted_day')):admitted.add(identity)
        if job.get('release_verified') is True:released.add(identity)
        if job not in leases or identity in seen:continue
        seen.add(identity)
        matches = native_groups.get(identity, [])
        observed = (current and job['session'] == session and len(matches) == 1
                    and capacity is not None and native_capacity == capacity and job['slot'] < capacity)
        if observed:matched.add(identity)
        physical = matches[0] if observed else {};phase = physical.get('phase')
        settlement = job.get('settlement') or {};saved_phase = job.get('phase')
        if proof:settlement_state = 'committed'
        elif settlement.get('committed_inventory_verified') is True:settlement_state = 'unverified'
        elif physical.get('committed_inventory_verified') is True or phase in ('recipe_committed', 'effect_verified'):settlement_state = 'effects_observed'
        elif phase in ('committing_input', 'committing_output'):settlement_state = 'committing'
        elif saved_phase in ('attendance_verified', 'recipe_prepared') or settlement.get('phase') in ('awaiting_writer', 'recipe_prepared', 'pending'):settlement_state = 'awaiting_commit'
        elif saved_phase == 'held' or phase == 'held':settlement_state = 'held'
        else:settlement_state = 'not_ready'
        if job.get('orphan') is True:attendance_state = 'held'
        elif is_qualified:attendance_state = 'qualified'
        elif observed and phase == 'working':attendance_state = 'working'
        elif observed and phase in ('accepted', 'acquiring'):attendance_state = 'acquiring'
        elif saved_phase == 'held' or phase == 'held':attendance_state = 'held'
        elif saved_phase == 'prepared':attendance_state = 'prepared'
        else:attendance_state = 'unmeasured'
        if job.get('receipt_acknowledged') is True:cleanup = 'acknowledged'
        elif job.get('release_verified') is True:cleanup = 'released'
        elif phase == 'releasing' or physical.get('release_requested') is True:cleanup = 'releasing'
        elif saved_phase == 'held' or phase == 'held':cleanup = 'held'
        else:cleanup = 'reserved'
        minutes = physical.get('worked_minutes') if observed else None
        samples = physical.get('samples') if observed else None
        if is_qualified:minutes = attendance['worked_minutes'];samples = attendance['samples']
        rows.append({'id': identity[0], 'actor': job['actor'], 'slot': job['slot'], 'business_id': job['business_id'],
                     'actor_name': ((society.get('people') or {}).get(str(job['actor'])) or {}).get('profile', {}).get('name'),
                     'orphan': job.get('orphan') is True, 'native_observed': observed,
                     'attendance_state': attendance_state, 'settlement_state': settlement_state, 'cleanup_state': cleanup,
                     'work_minutes': job['work_minutes'], 'worked_minutes': minutes if _number(minutes) else None,
                     'attendance_samples': samples if type(samples) is int and samples >= 0 else None,
                     'production_record_id': proof['id'] if proof else None,
                     'produced_goods': proof['outputs'] if proof else {}, 'consumed_goods': proof['inputs'] if proof else {}})
    outputs = Counter();inputs = Counter()
    for proof in commits.values():outputs.update(proof['outputs']);inputs.update(proof['inputs'])
    return {'schema_version': 'owner-work-metrics-v1', 'pool_id': saved.get('pool_id'),
            'available': native.get('available') is True, 'fresh': current,
            'configured_capacity': capacity, 'native_capacity': native_capacity,
            'leased_jobs': len(rows), 'native_matched_jobs': len(matched), 'unmeasured_jobs': len(rows) - len(matched),
            'observed_working': sum(row['native_observed'] and row['attendance_state'] == 'working' for row in rows) if current and (not rows or matched) else None,
            'awaiting_commit': sum(row['settlement_state'] in ('awaiting_commit', 'committing') for row in rows),
            'jobs': rows, 'retained_jobs': len(records), 'recorded_admissions': len(admitted),
            'qualified_attendance': len(qualified), 'committed_jobs': len(commits), 'released_jobs': len(released),
            'produced_goods': dict(outputs), 'consumed_goods': dict(inputs), 'invalid_commit_claims': invalid_commit_claims,
            'invalid_saved_rows': invalid_saved, 'invalid_native_rows': invalid_native,
            'scope': 'Current owner-work leases plus bounded retained history only; separate work-slot pool. Admission and attendance do not count goods. Outputs require an exact linked committed production record and reconciled native inventory; no GDP or profit inferred. Release and receipt acknowledgement are separate. Productive animation remains unverified; no fixture results are backfilled.'}
