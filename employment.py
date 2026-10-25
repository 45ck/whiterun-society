"""Observed employment encounters; public terms and personal refusal memory."""
import copy
import math

REVIEW_AFTER_REFUSAL_MINUTES = 15
REFUSAL_MEMORY_MINUTES = 60


def recently_refused(state, worker, business_id, revision, day):
    if type(day) not in (int, float) or not math.isfinite(day):
        return False
    for memory in state['people'][str(worker)].get('memories', []):
        then = memory.get('day')
        if (memory.get('kind') == 'employment_unavailable'
                and memory.get('business_id') == business_id and memory.get('revision') == revision
                and type(then) in (int, float) and math.isfinite(then)
                and 0 <= (day - then) * 1440 < REFUSAL_MEMORY_MINUTES):
            return True
    return False


def approach_employer(plan):
    """Voiced requests cannot ask or reject a job across town."""
    plan.update(phase='travelling', intent='ask_work', employment_dialogue=True,
                travel_id='employment-approach-' + plan['id'], release_required=True,
                dynamic_route=True)


def remember_unavailable(state, plan, day, delivery_id):
    terms = plan['work_terms']
    person = state['people'][str(plan['actor'])]
    person['memories'].append({'event_id': delivery_id, 'kind': 'employment_unavailable',
        'other': plan['target'], 'business_id': terms['business_id'], 'revision': terms['revision'],
        'day': day, 'source': 'Heard the employer decline this request; private reason unknown'})
    person['memories'] = person['memories'][-32:]


def accept_contract(state, plan):
    terms = plan.get('work_terms')
    if not terms:
        return
    contracts = state['town']['businesses'][terms['business_id']]['contracts']
    if not any(c['id'] == plan['id'] for c in contracts):
        contracts.append({'id': plan['id'], 'worker': plan['actor'], 'employer': plan['target'],
            'status': 'accepted', 'terms': copy.deepcopy(terms['policy']),
            'source': 'Employer offer and worker consent; no completed work yet'})
