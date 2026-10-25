"""Feasible paid-work opportunities, not inferred consent or public inventory.

The first executable enterprise uses the verified bread recipe. Stock targets,
wages and working hours are authored scenario policy, not discovered economics.
"""
from routing import route_available
from knowledge import person_view
from enterprises import production_policy
from employment import recently_refused

def work_opportunities(state, observation, worker):
    town = state.get('town') or {}
    resident = town.get('residents', {}).get(str(worker))
    actors = {a['id']: a for a in observation.get('residents', []) if a.get('isPerson') is True}
    if not resident or worker not in actors:
        return []
    opportunities = []
    for business_id, business in sorted(town.get('businesses', {}).items()):
        employer = business['custodian']
        if business.get('active', True) is not True or 'bread_recipe' not in business['capabilities'] or not route_available(observation, worker, employer):
            continue
        stock = actors.get(employer, {}).get('inventory', {})
        if any(type(stock.get(k)) is not int or stock[k] < 0 for k in ('gold', 'bread', 'grain')):
            continue
        policy = production_policy(business)
        if recently_refused(state, worker, business_id, business.get('revision', 0), observation.get('gameDays')):
            continue
        if stock['gold'] < policy['wage_gold'] or stock['grain'] < 1 or stock['bread'] >= policy['target_bread']:
            continue
        opportunities.append({'business_id': business_id, 'employer': employer,
            'employer_name': person_view(state,worker,employer)['name'],
            'revision': business.get('revision', 0), 'policy': policy})
    return opportunities


def settle_contract(state, plan, outcome):
    terms = plan.get('work_terms')
    if not terms:
        return
    business = state['town']['businesses'][terms['business_id']]
    contract = next((c for c in business['contracts'] if c['id'] == plan['id']), None)
    if contract:
        status = 'completed' if outcome == 'paid_work_completed' else ('held' if outcome == 'reconciliation_required' else 'ended')
        contract.update(status=status, outcome=outcome)
        if outcome == 'paid_work_completed':
            contract['production_id'] = 'produce-' + plan['id']
            if plan['actor'] not in business['workers']:
                business['workers'].append(plan['actor'])
