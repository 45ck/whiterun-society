"""Read-only, identity-bound evidence for independent native activity lanes."""
import math
from collections import Counter


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _identity(row):
    if not isinstance(row, dict):
        return None
    identifier = row.get('job_id', row.get('id'))
    values = (identifier, row.get('session'), row.get('epoch'))
    if not all(isinstance(value, str) and value for value in values):
        return None
    if not all(type(row.get(key)) is int and row[key] > 0 for key in ('actor', 'target')):
        return None
    if type(row.get('slot')) is not int or row['slot'] < 0:
        return None
    return (*values, row['actor'], row['target'], row['slot'])


def activity_metrics(society, observation, fresh=True):
    saved = society.get('activity_jobs') or {}
    native = observation.get('activity_jobs') or {}
    # The presentation protocol supplies a list of leased jobs and a bounded
    # acknowledged history. An internal job map is not this public protocol.
    leases = saved.get('jobs') if isinstance(saved.get('jobs'), list) else []
    history = saved.get('history') if isinstance(saved.get('history'), list) else []
    records = {}
    invalid_saved = 0
    for row in [*history, *leases]:
        identity = _identity(row)
        if identity is None:
            invalid_saved += 1
        else:
            records[identity] = row
    native_groups = {}
    invalid_native = 0
    for row in native.get('jobs') or []:
        identity = _identity(row)
        if identity is None:
            invalid_native += 1
        else:
            native_groups.setdefault(identity, []).append(row)
    session = observation.get('session')
    current = (fresh is True and isinstance(session, str) and bool(session)
               and native.get('session') == session and native.get('epoch') == saved.get('epoch')
               and isinstance(saved.get('epoch'), str))
    states = Counter()
    rows = []
    matched = set()
    known_phases = {'accepted', 'travelling', 'resting', 'releasing', 'applied', 'held'}
    seen = set()
    for job in leases:
        identity = _identity(job)
        if identity is None or identity in seen:
            continue
        seen.add(identity)
        matches = native_groups.get(identity, [])
        observed = current and job['session'] == session and len(matches) == 1
        row = matches[0] if observed else {}
        phase = row.get('phase') if row.get('phase') in known_phases else 'unmeasured'
        if observed:
            matched.add(identity)
        states[phase] += 1
        rest = row.get('rest') or {}
        rest_matches = (rest.get('id') == identity[0] and type(rest.get('actor')) is int
                        and rest['actor'] == job['actor'] and type(rest.get('target')) is int
                        and rest['target'] == job['target'])
        rows.append({'id': identity[0], 'actor': job['actor'], 'target': job['target'],
                     'actor_name': ((society.get('people') or {}).get(str(job['actor'])) or {}).get('profile', {}).get('name'),
                     'slot': job['slot'], 'source_plan': job.get('source_plan'),
                     'saved_phase': job.get('phase', 'unknown'), 'native_phase': phase,
                     'orphan': job.get('orphan') is True,
                     'native_observed': observed, 'outcome': job.get('outcome'),
                     'error': job.get('error'), 'release_verified': job.get('release_verified') is True,
                     'receipt_acknowledged': job.get('receipt_acknowledged') is True,
                     'rest_minutes': job.get('rest_minutes') if _number(job.get('rest_minutes')) else None,
                     'rested_minutes': rest.get('rested_minutes') if rest_matches and _number(rest.get('rested_minutes')) else None,
                     'seated_samples': rest.get('seated_samples') if rest_matches and type(rest.get('seated_samples')) is int and rest['seated_samples'] >= 0 else None})
    retained = list(records.values())
    complete = [job for job in retained if job.get('orphan') is not True and job.get('phase') == 'complete'
                and job.get('outcome') == 'rested_at_bench' and job.get('release_verified') is True]
    admitted = lambda job: job.get('orphan') is not True and (_number(job.get('accepted_day')) or job.get('phase') == 'running')
    foreground = []
    for kind, item in [('resident activity', society.get('plan')), ('conversation', society.get('conversation'))]:
        if item and item.get('phase') not in ('complete', 'held', 'delegated', 'cancelled'):
            foreground.append({'id': item.get('id'), 'kind': item.get('kind', kind),
                               'phase': item.get('phase', 'unknown'), 'actor': item.get('actor'),
                               'speakers': item.get('speakers', []) if kind == 'conversation' else []})
    has_saved_protocol = isinstance(saved.get('jobs'), list) and isinstance(saved.get('history'), list)
    return {'available': native.get('available') is True, 'fresh': current,
            'capacity': native.get('capacity') if type(native.get('capacity')) is int and native['capacity'] >= 0 else None,
            'leased_jobs': len(rows), 'native_matched_jobs': len(matched),
            'background_active': sum(states[phase] for phase in ('accepted', 'travelling', 'resting', 'releasing')) if current and (not rows or matched) else None,
            'states': {phase: states[phase] for phase in ('accepted', 'travelling', 'resting', 'releasing', 'applied', 'held', 'unmeasured')},
            'jobs': rows, 'foreground': foreground, 'foreground_active': len(foreground),
            'retained_jobs': len(retained) if has_saved_protocol else None,
            'recorded_admissions': sum(admitted(job) for job in retained) if has_saved_protocol else None,
            'admission_unknown': sum(job.get('orphan') is not True and not admitted(job) and job.get('phase') not in ('prepared',)
                                     and job.get('no_effects_issued') is not True for job in retained) if has_saved_protocol else None,
            'verified_completions': len(complete) if has_saved_protocol else None,
            'retained_held': sum(job.get('phase') == 'held' for job in retained) if has_saved_protocol else None,
            'retained_orphans': sum(job.get('orphan') is True for job in retained) if has_saved_protocol else None,
            'invalid_saved_rows': invalid_saved, 'invalid_native_rows': invalid_native,
            'unmatched_native_jobs': sum(len(group) for identity, group in native_groups.items() if identity not in matched),
            'scope': 'Current leased activities plus bounded acknowledged history (up to 32 jobs); not lifetime totals. Native phases require fresh exact job, actor, target, slot, session and epoch matches. Admission is not completed rest. Completion requires saved verified attendance and release; gameplay recovery is not a human realism score.'}
