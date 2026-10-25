"""Retained paid-employment evidence, never a score for human realism.

Attendance, recipe effects, payment, completion and release are independent.
Missing proof is unknown; a legacy after-balance is not a receipt.
"""
from collections import Counter
import hashlib
import json
import math
from statistics import mean, median

STAGES = ('offered', 'accepted', 'attendance_qualified', 'output_verified',
          'wage_paid', 'completed', 'released', 'held')
TIMING_PAIRS = {
    'native_admission_to_attendance': ('accepted', 'attendance_verified'),
    'attendance_to_output': ('attendance_verified', 'output_verified'),
    'output_to_wages': ('output_verified', 'wages_verified'),
    'native_admission_to_completion': ('accepted', 'completed'),
    'wages_to_release': ('wages_verified', 'release_verified'),
}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _digest(value):
    try:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                          allow_nan=False).encode()).hexdigest()
    except (TypeError, ValueError):
        return None


def _distribution(values, eligible):
    values = sorted(value for value in values if _number(value))
    return {'n': len(values), 'eligible': eligible, 'unknown': eligible - len(values),
            'mean': round(mean(values), 3) if values else None,
            'median': round(median(values), 3) if values else None,
            'p95': round(values[max(0, math.ceil(.95 * len(values)) - 1)], 3) if values else None}


def _stage_summary(rows, stage, measured):
    if not measured:return {'success': None, 'n': None, 'unknown': None, 'percent': None}
    values = [row['stages'][stage] for row in rows]
    known = [value for value in values if type(value) is bool]
    success = sum(value is True for value in known)
    return {'success': success, 'n': len(known), 'unknown': len(values) - len(known),
            'percent': round(100 * success / len(known), 2) if known else None}


def _conversion(rows, first, last):
    eligible = [row for row in rows if row['stages'][first] is True]
    known = [row for row in eligible if type(row['stages'][last]) is bool]
    success = sum(row['stages'][last] is True for row in known)
    return {'success': success, 'eligible': len(eligible), 'n': len(known),
            'unknown': len(eligible) - len(known),
            'percent': round(100 * success / len(eligible), 2)
                       if eligible and len(eligible) == len(known) else None}


def _latency(records, rows):
    result = {}
    stage_names = {'accepted': 'accepted', 'attendance_verified': 'attendance_qualified',
                   'output_verified': 'output_verified', 'wages_verified': 'wage_paid',
                   'completed': 'completed', 'release_verified': 'released'}
    for label, (start, end) in TIMING_PAIRS.items():
        eligible = [(job, row) for job, row in zip(records, rows)
                    if row['stages'][stage_names[end]] is True]
        for suffix, scale, unit in (('_day', 1440, 'game_minutes'), ('_at', 1, 'wall_seconds')):
            values = []
            for job, row in eligible:
                a, b = job.get(start + suffix), job.get(end + suffix)
                if (row['stages'][stage_names[start]] is True and _number(a) and _number(b) and b >= a):
                    values.append((b - a) * scale)
            result[label + '_' + unit] = _distribution(values, len(eligible))
    return result


def _jobs(state):
    """Accept canonical saved maps or the read-only status projection."""
    if 'paid_work_jobs' in state or 'paid_work_orphans' in state:
        values = [state.get(key, {}) for key in ('paid_work_jobs', 'paid_work_orphans')]
        if any(not isinstance(value, dict) for value in values):return [], False
        return [row for value in values for row in value.values()], True
    status = state.get('paid_employment')
    if not isinstance(status, dict):return [], False
    if not all(isinstance(status.get(key), list) for key in ('jobs', 'history')):return [], False
    return status['jobs'] + status['history'], True


def _consent_stages(state, job):
    """Recheck retained claim lineage, without applying today's charter to history."""
    from employment import work_terms_hash
    wrapper = job.get('consent') or {}
    consent = wrapper.get('consent', wrapper) if isinstance(wrapper, dict) else {}
    terms = wrapper.get('terms', job.get('terms')) if isinstance(wrapper, dict) else None
    try:
        digest = work_terms_hash(terms)
        if (digest != job.get('terms_hash') or _digest(consent) != job.get('consent_hash')
                or consent.get('protocol') != 2 or consent.get('terms_hash') != digest
                or consent.get('session') != job.get('session')
                or any(consent.get(key) != job.get(key) for key in ('worker', 'employer'))
                or consent.get('plan_id') != job.get('source_plan')):return None, None
        if (any(terms.get(key) != job.get(key) for key in ('worker', 'worker_base_id', 'employer',
                'employer_base_id', 'business_id', 'recipe_id', 'catalog_hash', 'recipe_hash', 'currency'))
                or terms.get('revision') != job.get('business_revision')
                or any((terms.get('policy') or {}).get(key) != job.get(key) for key in ('wage_gold', 'work_minutes'))):return None, None
        plans = [p for p in state.get('plans', []) if isinstance(p, dict) and p.get('id') == job['source_plan']]
        if not plans or any(p != plans[0] for p in plans[1:]):return None, None
        plan = plans[0];found = []
        if (plan.get('actor') != job['worker'] or plan.get('target') != job['employer']
                or work_terms_hash(plan.get('work_terms')) != digest
                or (plan.get('work_terms') or {}).get('terms_hash') != digest):return None, None
        for action, actor, claim_key in (('offer_shift', job['employer'], 'offer_claim_id'),
                                         ('take_shift', job['worker'], 'acceptance_claim_id')):
            candidates = [(index, row) for index, row in enumerate(plan.get('decisions', []))
                          if isinstance(row, dict) and row.get('actor_id') == actor
                          and (row.get('decision') or {}).get('action_id') == action]
            if len(candidates) != 1:return (True, None) if found else (None, None)
            index, record = candidates[0];context = record.get('context') or {}
            claimed = context.get('work_terms')
            if (record.get('actor_id') != actor or context.get('actor_id') != actor
                    or not isinstance(record.get('claim_id'), str) or not record['claim_id']
                    or record['claim_id'] != consent.get(claim_key)
                    or (record.get('decision') or {}).get('action_id') != action
                    or context.get('session') != consent.get('session')
                    or (context.get('event') or {}).get('id') != job['source_plan']
                    or context.get('terms_hash') != digest or work_terms_hash(claimed) != digest
                    or claimed.get('terms_hash') != digest
                    or not any(isinstance(option, dict) and option.get('id') == action
                               for option in context.get('options', []))):return None, None
            found.append(index)
        if found[0] >= found[1] or consent['offer_claim_id'] == consent['acceptance_claim_id']:return None, None
        if plan.get('voiced_trade') or plan.get('employment_dialogue'):
            turns = []
            for act, actor, listener, key in (('work_offer', job['employer'], job['worker'], 'offer_delivery_id'),
                                             ('work_accept', job['worker'], job['employer'], 'acceptance_delivery_id')):
                matches = [(index, turn) for index, turn in enumerate(plan.get('economic_turns', []))
                           if isinstance(turn, dict) and turn.get('act') == act]
                if len(matches) != 1:return None, None
                index, turn = matches[0];playback = turn.get('playback') or {}
                if (turn.get('act') != act or turn.get('actor') != actor or turn.get('listener') != listener
                        or not isinstance(turn.get('delivery_id'), str) or not turn['delivery_id']
                        or turn['delivery_id'] != consent.get(key)
                        or turn.get('delivered') is not True or turn.get('terms_hash') != digest
                        or turn.get('origin_session') != consent.get('session')
                        or playback.get('id') != consent[key] or playback.get('status') != 'ended'
                        or playback.get('nearbyThroughout') is not True):return None, None
                duration = (turn.get('audio') or {}).get('seconds');elapsed = playback.get('playedSeconds')
                if not _number(duration) or duration <= 0 or not _number(elapsed) or elapsed < duration - .3:
                    return None, None
                turns.append(index)
            if turns[0] >= turns[1] or consent.get('offer_delivery_id') == consent.get('acceptance_delivery_id'):
                return None, None
        return True, True
    except (KeyError, TypeError, ValueError):
        return None, None


def _effect(job, protocol):
    command = job.get('commit_command');receipt = job.get('effect_receipt')
    if not isinstance(command, dict) or not isinstance(receipt, dict):return None
    if (type(job.get('protocol')) is not int or job['protocol'] != 2
            or command.get('kind') != 'inventory_paid_work_commit'
            or _digest(receipt) != job.get('effect_receipt_hash')
            or not isinstance(job.get('effect_actual'), dict)
            or not protocol.paid_receipt_matches(receipt, job)
            or not protocol.paid_receipt_matches(command, job)
            or command.get('attendance_token') != (job.get('attendance') or {}).get('token')):return None
    try:
        proof = protocol.paid_effect_evidence(command, receipt, job.get('effect_actual'))
        return proof if isinstance(proof, dict) and proof.get('valid') is True else None
    except (KeyError, TypeError, ValueError):
        return None


def _committed(job, state, proof):
    if not proof or proof.get('inventory_verified') is not True:return None
    settlement = job.get('settlement') or {};identifier = settlement.get('commit_id')
    if not identifier or settlement.get('phase') != 'committed' or settlement.get('production_record_id') != identifier:return None
    records = [row for row in state.get('production', [])
               if isinstance(row, dict) and row.get('id') == identifier]
    if not records or any(row != records[0] for row in records[1:]):return None
    record = records[0];evidence = record.get('evidence') or {}
    ack = evidence.get('ack') or {};source = evidence.get('receipt_source')
    receipt_accepted = ((source in (None, 'command_acknowledgement') and ack.get('status') == 'applied'
                         and ack.get('id') == identifier)
                        or (source == 'retained_native_journal' and ack.get('phase') in ('effects_verified', 'complete')))
    if (record.get('status') != 'committed' or record.get('paid_work_job') != job.get('id', job.get('job_id'))
            or record.get('command') != job.get('commit_command')
            or evidence.get('ack') != job.get('effect_receipt')
            or evidence.get('actual') != job.get('effect_actual')
            or evidence.get('session') != job.get('session')
            or not receipt_accepted
            or (evidence.get('ack') or {}).get('effects_verified') is not True):return None
    return record


def _attendance(job, protocol):
    receipt = job.get('attendance_receipt');at = job.get('attendance_verified_at')
    day = job.get('attendance_verified_day')
    return (isinstance(receipt, dict) and _digest(receipt) == job.get('attendance_receipt_hash')
            and _number(at) and _number(day)
            and protocol.paid_attendance_valid(receipt, job, day, now_ms=at * 1000))


def verified_paid_records(state):
    """Shared cashflow gate: exact committed paid-job receipts only, never partials."""
    import paid_employment as protocol
    raw, _ = _jobs(state);groups = {}
    for job in raw:
        if isinstance(job, dict) and isinstance(job.get('id'), str):groups.setdefault(job['id'], []).append(job)
    result = {}
    for rows in groups.values():
        if any(row != rows[0] for row in rows[1:]):continue
        job = rows[0]
        try:
            proof = _effect(job, protocol);record = _committed(job, state, proof)
        except (KeyError, TypeError, ValueError):continue
        if record and _attendance(job, protocol) and proof.get('output_verified') is True and proof.get('wages_verified') is True:
            result[record['id']] = record
    return result


def paid_employment_metrics(state, observation=None, *, fresh=False):
    """Current-save retained evidence. No provider calls or game-state mutation."""
    import paid_employment as protocol
    from economy_catalog import catalog_hash, recipe_hash, recipe_spec
    state = state if isinstance(state, dict) else {};observation = observation or {}
    raw, measured = _jobs(state);groups = {};invalid = 0;legacy = 0
    for job in raw:
        if not isinstance(job, dict) or not isinstance(job.get('id', job.get('job_id')), str):
            invalid += 1;continue
        if type(job.get('protocol')) is not int or job['protocol'] != 2:
            legacy += 1;continue
        groups.setdefault(job.get('id', job.get('job_id')), []).append(job)
    rows = [];records = [];conflicts = 0;duplicates = 0;partials = Counter();provenance = Counter()
    partial_outputs = Counter();committed_outputs = Counter();committed_wages = 0
    people = state.get('people') or {}
    for identifier, candidates in sorted(groups.items()):
        job = candidates[0];duplicates += len(candidates) - 1
        conflict = any(row != job for row in candidates[1:]);conflicts += int(conflict)
        stages = {stage: None for stage in STAGES};recipe = {'id': job.get('recipe_id'), 'status': 'unverified'}
        proof = None;committed = None
        if not conflict:
            stages['held'] = job.get('phase') == 'held'
            try:
                identity = protocol.paid_identity(job)
                if not isinstance(identity, dict) or not protocol.paid_receipt_matches(identity, job):raise ValueError('Invalid identity')
                stages['offered'], stages['accepted'] = _consent_stages(state, job)
                if _attendance(job, protocol):stages['attendance_qualified'] = True
                if job.get('catalog_hash') == catalog_hash() and job.get('recipe_hash') == recipe_hash(job.get('recipe_id')):
                    spec = recipe_spec(job['recipe_id'])
                    recipe = {'id': job['recipe_id'], 'status': 'verified', 'version': spec['version'],
                              'inputs': dict(spec['inputs']), 'outputs': dict(spec['outputs'])}
                proof = _effect(job, protocol)
                if proof:
                    stages['output_verified'] = proof.get('output_verified') if type(proof.get('output_verified')) is bool else None
                    stages['wage_paid'] = proof.get('wages_verified') if type(proof.get('wages_verified')) is bool else None
                    committed = _committed(job, state, proof)
                receipt = job.get('receipt')
                if (isinstance(receipt, dict) and _digest(receipt) == job.get('receipt_hash')
                        and protocol.paid_receipt_matches(receipt, job) and receipt.get('release_verified') is True):
                    stages['released'] = True
                terminal_effects = protocol.paid_effect_evidence(job.get('commit_command') or {}, receipt or {}, job.get('effect_actual'))
                stages['completed'] = bool(committed and stages['accepted'] is True
                    and stages['attendance_qualified'] is True and stages['output_verified'] is True
                    and stages['wage_paid'] is True and stages['released'] is True
                    and terminal_effects.get('valid') is True and terminal_effects.get('inventory_verified') is True
                    and _number(job.get('completed_day')) and job.get('phase') == 'complete')
            except (KeyError, TypeError, ValueError):
                invalid += 1
        plans = [plan for plan in state.get('plans', []) if isinstance(plan, dict) and plan.get('id') == job.get('source_plan')]
        models = [record.get('model') for plan in plans for record in plan.get('decisions', []) if isinstance(record, dict)]
        origin = ('controlled_fixture' if any(isinstance(model, str) and ('fixture' in model.lower() or model.startswith('test')) for model in models)
                  else 'recorded_model_choices' if models and all(isinstance(model, str) and model for model in models) else 'unknown')
        provenance[origin] += 1
        row = {'id': identifier, 'worker': job.get('worker'), 'employer': job.get('employer'),
               'worker_name': (people.get(str(job.get('worker'))) or {}).get('profile', {}).get('name'),
               'employer_name': (people.get(str(job.get('employer'))) or {}).get('profile', {}).get('name'),
               'recipe_id': job.get('recipe_id'), 'recipe': recipe, 'wage_gold': job.get('wage_gold'),
               'currency': job.get('currency'), 'work_minutes': job.get('work_minutes'),
               'phase': job.get('phase'), 'stages': stages, 'held_reason': job.get('error'),
               'wage_debit_verified': proof.get('wage_debit_verified') if proof else None,
               'wage_credit_verified': proof.get('wages_verified') if proof else None,
               'lineage_conflict': conflict, 'provenance': origin,
               'committed_record_id': committed['id'] if committed else None}
        rows.append(row);records.append(job)
        if proof and not committed:
            if proof.get('output_verified') is True:
                partials['output_verified_without_commit'] += 1
                if recipe['status'] == 'verified':partial_outputs.update(recipe['outputs'])
            if proof.get('wage_debit_verified') is True and proof.get('wages_verified') is not True:
                partials['wage_debit_without_verified_credit'] += 1
            if proof.get('wages_verified') is True:partials['wages_verified_without_commit'] += 1
        if committed:
            if recipe['status'] == 'verified':committed_outputs.update(recipe['outputs'])
            if type(job.get('wage_gold')) is int:committed_wages += job['wage_gold']
    native = observation.get('paid_employment') or {}
    typed_native = (isinstance(native, dict) and type(native.get('available')) is bool
                    and type(native.get('protocol')) is int and native['protocol'] == 2)
    saved_epoch = state.get('paid_work_epoch', (state.get('paid_employment') or {}).get('epoch'))
    current = (fresh is True and typed_native and observation.get('ready') is True
               and isinstance(observation.get('session'), str) and bool(observation['session'])
               and ('session' not in native or native['session'] == observation['session'])
               and isinstance(native.get('epoch'), str) and bool(native['epoch'])
               and (saved_epoch is None or native['epoch'] == saved_epoch))
    capability = {'available': native['available'] if current else None,
                  'fresh': bool(current), 'protocol': native['protocol'] if current else None}
    conversions = {label: _conversion(rows, start, end) if measured else
        {'success': None, 'eligible': None, 'n': None, 'unknown': None, 'percent': None}
        for label, start, end in (
            ('attendance_among_accepted', 'accepted', 'attendance_qualified'),
            ('wages_among_accepted', 'accepted', 'wage_paid'),
            ('completion_among_accepted', 'accepted', 'completed'),
            ('release_among_completed', 'completed', 'released'))}
    latencies = _latency(records, rows)
    if not measured:
        latencies = {key: {field: None for field in value} for key, value in latencies.items()}
    return {'schema_version': 'paid-employment-metrics-v2', 'measured': measured,
            'capability': capability, 'retained_jobs': len(rows), 'jobs': rows,
            'stages': {stage: _stage_summary(rows, stage, measured) for stage in STAGES},
            'conversion_rates': conversions,
            'eligibility': {'n': None, 'scope': 'Eligible opportunity snapshots are not journalled; retained jobs are not an opportunity denominator.'},
            'latency': latencies,
            'partial_effects': {**{key: partials[key] if measured else None for key in ('output_verified_without_commit',
                'wage_debit_without_verified_credit', 'wages_verified_without_commit')},
                'observed_output_goods': dict(partial_outputs) if measured else None},
            'committed_output_goods': dict(committed_outputs) if measured else None,
            'committed_wage_gold': committed_wages if measured else None,
            'duplicate_rows_excluded': duplicates, 'conflicting_job_lineages': conflicts,
            'invalid_rows': invalid, 'legacy_rows_excluded': legacy, 'provenance_counts': dict(provenance),
            'scope': 'Current save and retained job history only, including explicitly labelled controlled fixtures. Stage samples exclude unknown proof; conversion percentages require every eligible outcome to be known. Phase, balances and attendance alone never prove output or wages. Partial observed effects are not committed production. Completion additionally requires release. Offers before a saved job and opportunity eligibility are not fully instrumented. No profit, realism, autonomy or lifetime throughput score is inferred.',
            'timing_scope': 'Saved game-day intervals and wall-clock seconds are separate. The accepted_* clock marks native attendance admission, not the earlier human acceptance choice. Missing, reversed and invalid clocks stay unknown; elapsed durations include queues and pauses, not pure productive time.'}
