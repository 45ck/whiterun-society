"""Source-linked independent decisions and physical follow-through evidence.

A saved claim is not proof that a model is running. A quiet choice and a
foreground handoff are intentional outcomes, not failed native work.
"""
from collections import Counter
import hashlib
import json
import math
import re
from statistics import mean, median

STAGES = ('waiting', 'claimed', 'accepted', 'delegated', 'native_attending', 'settled', 'held', 'handoff', 'quiet')


def _id(value):return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', value) else None
def _actor(value):return value if type(value) is int and 0 < value <= 0xffffffff else None
def _number(value):return type(value) in (int, float) and math.isfinite(value) and value >= 0
def _digest(value):
    try:return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    except (TypeError, ValueError):return None


def _sample(values, eligible):
    values = sorted(value for value in values if _number(value))
    return {'n': len(values), 'eligible': eligible, 'unknown': eligible - len(values),
            'mean': round(mean(values), 6) if values else None,
            'median': round(median(values), 6) if values else None,
            'p95': round(values[max(0, math.ceil(.95 * len(values)) - 1)], 6) if values else None}


def _coverage(values):
    return {'success': sum(value is True for value in values),
            'n': sum(type(value) is bool for value in values),
            'unknown': sum(type(value) is not bool for value in values), 'eligible': len(values)}


def _matching(rows, identifier, key='id'):
    rows = [row for row in rows if isinstance(row, dict) and row.get(key) == identifier]
    return rows[0] if rows and all(row == rows[0] for row in rows[1:]) else None


def _jobs(state, kind):
    value = state.get('activity_jobs') if kind == 'rest' else state.get('work_jobs', state.get('owner_work_jobs'))
    if not isinstance(value, dict):return []
    if isinstance(value.get('jobs'), list):return value['jobs'] + (value.get('history') if isinstance(value.get('history'), list) else [])
    return list(value.values())


def _wave_evidence(state, record):
    waves = state.get('independent_review_waves') or []
    wave = _matching(waves if isinstance(waves, list) else [], record.get('wave_id'))
    if wave is None:return None, None, None
    if wave.get('claim_id') != record.get('claim_id') or wave.get('session') != record.get('session'):return False, None, None
    members = [member for member in (wave.get('members') or []) if isinstance(member, dict)
               and (member.get('source_event') == record['event_id'] or member.get('actor') == record['actor'])]
    if len(members) != 1 or members[0].get('source_event') != record['event_id'] or members[0].get('actor') != record['actor']:return False, None, None
    if members[0].get('actor_base_id', record['actor_base_id']) != record['actor_base_id']:return False, None, None
    results = [result for result in (wave.get('results') or []) if isinstance(result, dict)
               and (result.get('source_event') == record['event_id'] or result.get('actor') == record['actor'])]
    if not results:return True, None, wave
    if len(results) != 1 or results[0].get('source_event') != record['event_id'] or results[0].get('actor') != record['actor']:return False, None, wave
    result = results[0]
    if type(result.get('accepted')) is not bool or result['accepted'] is not record.get('accepted'):return False, None, wave
    if result['accepted'] and (result.get('decision') or {}).get('action_id') != record.get('action_id'):return False, None, wave
    return True, result, wave


def _plan(state, record):
    from activity_plan_sources import activity_plan_hash
    plans = state.get('independent_plans') or {}
    plan_id = record.get('plan_id')
    if not plan_id:return None, None
    plan = plans.get(plan_id) if isinstance(plans, dict) else None
    if not isinstance(plan, dict):return None, None
    try:
        valid = (plan.get('id') == plan_id == record['event_id'] and plan.get('actor') == record['actor']
            and plan.get('actor_base_id') == record['actor_base_id'] and plan.get('session') == record['session']
            and plan.get('kind') == 'independent_review'
            and plan.get('independent_review') == {key: record[key] for key in ('event_id', 'wave_id', 'claim_id')}
            and record.get('plan_hash') == activity_plan_hash(plan)
            and not any(isinstance(other, dict) and other.get('id') == plan_id for other in state.get('plans', [])))
        return valid, plan if valid else None
    except (KeyError, TypeError, ValueError):return False, None


def _job(state, record, plan):
    if plan is None:return None, None, _id(record.get('job_id')), record.get('job_kind')
    kind = record.get('job_kind') or ('rest' if 'rest_target' in plan else 'owner_production' if 'own_work_terms' in plan else None)
    identifier = record.get('job_id') or plan.get('activity_job' if kind == 'rest' else 'work_job')
    if not identifier:return None, None, None, kind
    rows = _jobs(state, kind)
    job = _matching(rows, identifier)
    if job is None:return None, None, _id(identifier), kind
    valid = (kind in ('rest', 'owner_production') and job.get('source_plan') == record['plan_id']
        and job.get('actor') == record['actor'] and job.get('actor_base_id') == record['actor_base_id']
        and job.get('session') == record['session'] and job.get('orphan') is not True
        and plan.get('activity_job' if kind == 'rest' else 'work_job') == identifier)
    if kind == 'rest':valid = valid and job.get('target') == plan.get('rest_target')
    elif kind == 'owner_production':
        terms = plan.get('own_work_terms') or {}
        valid = valid and all(job.get(key) == terms.get(key) and terms.get(key) is not None
            for key in ('business_id', 'recipe_id', 'catalog_hash', 'recipe_hash'))
        valid = valid and job.get('business_revision') == terms.get('revision') and job.get('work_minutes') == (terms.get('policy') or {}).get('work_minutes')
    return valid, job if valid else None, _id(identifier), kind


def _native(state, obs, record, job, kind, fresh):
    from resident_identity import resident_identity_status
    if job is None or not fresh or obs.get('session') != job.get('session') or job.get('phase') in ('held', 'complete') or any(job.get(key) for key in ('reset_held', 'cancel_requested', 'effect_unreconciled')):return None
    identity = resident_identity_status(state, obs, record['actor'])
    if not identity['qualified'] or identity['base_id'] != record['actor_base_id']:return None
    key = 'activity_jobs' if kind == 'rest' else 'owner_work_jobs';native = obs.get(key) or {}
    if (not isinstance(native, dict) or native.get('available') is not True
            or native.get('session') != job.get('session') or native.get('epoch') != job.get('epoch')):return None
    from activity_jobs import _matches as rest_matches
    from owner_work_jobs import _matches as owner_matches
    matches = rest_matches if kind == 'rest' else owner_matches
    rows = [row for row in (native.get('jobs') or []) if isinstance(row, dict) and matches(row, job)]
    if len(rows) != 1:return None
    row = rows[0]
    if row.get('actor_base_id') != record['actor_base_id'] or row.get('cancelled') is True:return None
    if kind == 'rest':
        evidence = row.get('rest') or {}
        if row.get('phase') != 'resting':return False
        return True if (evidence.get('actor') == job['actor'] and evidence.get('target') == job['target']
            and evidence.get('id') == job['id'] and evidence.get('exact_furniture_verified') is True
            and type(evidence.get('seated_samples')) is int and evidence['seated_samples'] > 0) else None
    if row.get('phase') != 'working':return False
    return True if type(row.get('samples')) is int and row['samples'] > 0 and _number(row.get('worked_minutes')) else None


def _settled(state, job, kind):
    if job is None:return None
    if job.get('phase') not in ('complete', 'held'):return False
    if job.get('phase') == 'held':return False
    if job.get('release_verified') is not True or not _id(job.get('receipt_hash')):return None
    if kind == 'owner_production':
        from owner_work_metrics import _production
        groups = {}
        for record in state.get('production', []):
            if isinstance(record, dict):groups.setdefault(record.get('id'), []).append(record)
        return True if job.get('outcome') == 'owner_work_completed' and _production(job, groups) else None
    from activity_jobs import _matches
    record = _matching(state.get('rests') or [], job['id'])
    if not record or record.get('status') != 'committed':return None
    receipt = record.get('evidence') or {};rest = receipt.get('rest') or {}
    minutes = (job.get('policy') or {}).get('rest_minutes', job.get('rest_minutes'))
    if (job.get('outcome') == 'rested_at_bench' and _matches(receipt, job)
            and receipt.get('actor_base_id') == job['actor_base_id']
            and receipt.get('status') == 'applied' and _digest(receipt) == record.get('receipt_hash') == job.get('receipt_hash')
            and rest.get('actor') == job['actor'] and rest.get('target') == job['target']
            and rest.get('release_verified') is True and rest.get('exact_furniture_verified') is True
            and type(rest.get('seated_samples')) is int and rest['seated_samples'] >= 2
            and _number(minutes) and _number(rest.get('rested_minutes')) and minutes <= rest['rested_minutes'] <= minutes + 1):return True
    return None


def independent_review_metrics(state, observation=None, fresh=False):
    state = state if isinstance(state, dict) else {};obs = observation or {}
    measured = isinstance(state.get('independent_reviews'), dict)
    current = bool(fresh is True and not state.get('error') and not state.get('transition') and obs.get('paused') is not True
        and obs.get('ready') is True and isinstance(obs.get('session'), str) and obs['session']
        and type(obs.get('checkpoint')) is int and 0 <= obs['checkpoint'] < 2**24
        and (state.get('session') is None or state['session'] == obs['session'])
        and (state.get('checkpoint') is None or state['checkpoint'] == obs['checkpoint']))
    raw = state.get('independent_reviews') if measured else {};queue = ((state.get('town') or {}).get('daily') or {}).get('queue') or []
    rows = [];invalid = 0;claimed_latencies = [];result_game_latencies = [];result_wall_latencies = []
    results_count = 0;native_admissions = 0;source_coverage = [];claim_coverage = [];plan_coverage = [];job_coverage = []
    for key, record in raw.items():
        if (not isinstance(record, dict) or _id(key) is None or record.get('event_id') != key
                or not _actor(record.get('actor')) or not _actor(record.get('actor_base_id'))
                or not _id(record.get('session')) or not _id(record.get('wave_id')) or not _id(record.get('claim_id'))):
            invalid += 1;continue
        events = [event for event in queue if isinstance(event, dict) and event.get('id') == key]
        source = (events[0].get('actor') == record['actor'] and events[0].get('independent_review') == record['wave_id']) if len(events) == 1 else False if events else None
        claim, result, wave = _wave_evidence(state, record)
        accepted = result['accepted'] if claim is True and result and source is not False else None
        plan_linked, plan = _plan(state, record)
        job_linked, job, job_id, kind = _job(state, record, plan)
        settled = _settled(state, job, kind) if job_linked is True and plan_linked is True and accepted is True else None
        attending = _native(state, obs, record, job, kind, current) if job_linked is True and accepted is True else None
        phase = record.get('phase');quiet = accepted is True and phase == 'deferred';handoff = accepted is True and phase == 'foreground_review'
        native_required = False if quiet or handoff else True if plan_linked is True else None
        held = phase == 'held' or bool(job and job.get('phase') == 'held')
        stages = {'waiting': False, 'claimed': phase == 'claimed' and claim is True, 'accepted': accepted,
            'delegated': job_linked if accepted is True else None, 'native_attending': attending, 'settled': settled,
            'held': held, 'handoff': handoff, 'quiet': quiet}
        status = ('held' if held else 'quiet' if quiet else 'handoff' if handoff else 'settled' if settled is True
                  else 'native_attending' if attending is True else 'delegated' if stages['delegated'] is True
                  else 'accepted' if accepted is True and plan_linked is True else 'claimed' if stages['claimed'] else 'unmeasured')
        model = record.get('model');provenance = ('controlled_fixture' if isinstance(model, str) and ('fixture' in model.lower() or model.startswith('test'))
            else 'recorded_model_choice' if isinstance(model, str) and model and model != 'unknown' else 'unknown')
        row = {'event_id': key, 'actor': record['actor'], 'actor_base_id': record['actor_base_id'],
            'actor_name': ((state.get('people') or {}).get(str(record['actor'])) or {}).get('profile', {}).get('name'),
            'session': record['session'], 'wave_id': record['wave_id'], 'claim_id': record['claim_id'],
            'action_id': _id(record.get('action_id')), 'plan_id': _id(record.get('plan_id')),
            'job_id': job_id, 'job_kind': kind if kind in ('rest', 'owner_production') else None,
            'status': status, 'native_required': native_required, 'source_linked': source,
            'plan_linked': plan_linked, 'job_linked': job_linked, 'stages': stages,
            'provenance': provenance, 'inference_active': None}
        rows.append(row);source_coverage.append(source);claim_coverage.append(claim)
        if record.get('plan_id'):plan_coverage.append(plan_linked)
        if job_id:job_coverage.append(job_linked)
        if result:
            results_count += 1
            finished = record.get('result_recorded_at', result.get('result_recorded_at', record.get('decided_at', wave.get('settled_at'))))
            started = record.get('claimed_at')
            if _number(started) and _number(finished) and finished >= started:claimed_latencies.append(finished - started)
        if job_linked is True and accepted is True:
            native_admissions += 1
            for suffix, scale, values in (('_day', 1440, result_game_latencies), ('_at', 1, result_wall_latencies)):
                start, end = record.get('decided' + suffix), job.get('accepted' + suffix)
                if _number(start) and _number(end) and end >= start:values.append((end - start) * scale)
    # Pending source events have no inferred base identity, claim or model activity.
    seen = set(raw)
    for event in queue:
        if (not isinstance(event, dict) or not _id(event.get('id')) or not _actor(event.get('actor'))
                or event.get('id') in seen or event.get('kind') != 'need_review' or event.get('status') != 'pending'):continue
        seen.add(event['id'])
        rows.append({'event_id': event['id'], 'actor': event['actor'], 'actor_base_id': _actor(event.get('actor_base_id')),
            'actor_name': ((state.get('people') or {}).get(str(event['actor'])) or {}).get('profile', {}).get('name'),
            'session': None, 'wave_id': None, 'claim_id': None, 'action_id': None, 'plan_id': None,
            'job_id': None, 'job_kind': None, 'status': 'waiting', 'native_required': None,
            'source_linked': True, 'plan_linked': None, 'job_linked': None,
            'stages': {stage: stage == 'waiting' for stage in STAGES}, 'provenance': 'not_claimed', 'inference_active': None})
    counts = Counter(row['status'] for row in rows)
    coverage = {'source_events': _coverage(source_coverage), 'claims': _coverage(claim_coverage),
                'plans': _coverage(plan_coverage), 'jobs': _coverage(job_coverage)}
    latency = {'claim_to_result_seconds': _sample(claimed_latencies, results_count),
               'result_to_native_admission_game_minutes': _sample(result_game_latencies, native_admissions),
               'result_to_native_admission_seconds': _sample(result_wall_latencies, native_admissions)}
    if not measured:
        coverage = {key: {field: None for field in value} for key, value in coverage.items()}
        latency = {key: {field: None for field in value} for key, value in latency.items()}
    return {'schema_version': 'independent-review-metrics-v1', 'measured': measured, 'fresh': current,
        'counts': {stage: counts[stage] if measured else None for stage in (*STAGES, 'unmeasured')},
        'reviews': rows, 'invalid_records': invalid,
        'coverage': coverage, 'latency': latency,
        'scope': 'Current save retained independent reviews only. Counts are mutually exclusive current pipeline statuses. Waiting includes pending need-review source events, not a claim that every event is eligible. A claim is a durable request, not proof of a running model. Accepted choices and delegation do not prove native attendance or settlement. Quiet and foreground handoff are intentional non-native outcomes. Native attendance requires a fresh exact job and actor/base observation; settled rest/production requires the source-linked committed receipt. No private prompts, decision reasons, inventories or permits are exposed; no realism or lifetime-throughput score is inferred.',
        'timing_scope': 'Finite saved service timestamps only. Claim-to-result includes queue time; older rejected results may use the enclosing wave settlement timestamp. Result-to-admission is separate from delegation and completion. Missing admission wall clocks remain unknown; no timestamp is reconstructed from a phase.'}
