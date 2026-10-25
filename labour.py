"""Feasible paid-work opportunities, not inferred consent or public inventory.

The first executable enterprise uses the verified bread recipe. Stock targets,
wages and working hours are authored scenario policy, not discovered economics.
"""
from routing import route_available
from knowledge import person_view
from enterprises import production_policy, paid_bread_recipe
from employment import recently_refused
from paid_work_policy import paid_work_capability
from economy_catalog import native_catalog_matches, commodity_ids, recipe_spec, recipe_hash, catalog_hash, MAX_STOCK

def work_opportunities(state, observation, worker):
    if not paid_work_capability()['available']:
        return []
    if not native_catalog_matches(observation, 'bread_recipe'):return []
    try:recipe = paid_bread_recipe()
    except ValueError:return []
    town = state.get('town') or {}
    resident = town.get('residents', {}).get(str(worker))
    actors = {a['id']: a for a in observation.get('residents', []) if a.get('isPerson') is True}
    if not resident or worker not in actors:
        return []
    opportunities = []
    for business_id, business in sorted(town.get('businesses', {}).items()):
        employer = business['custodian']
        if business.get('active', True) is not True or 'bread_recipe' not in business['capabilities'] or not route_available(observation, worker, employer,state):
            continue
        stock = actors.get(employer, {}).get('inventory', {})
        if any(type(stock.get(k)) is not int or not 0 <= stock[k] <= MAX_STOCK for k in commodity_ids()):
            continue
        try:policy = production_policy(business)
        except (ValueError, KeyError):continue
        if recently_refused(state, worker, business_id, business.get('revision', 0), observation.get('gameDays')):
            continue
        if stock['gold'] < policy['wage_gold'] or any(stock[k] < n for k, n in recipe['inputs'].items()) or stock['bread'] >= policy['target_bread']:
            continue
        if any(stock[k] > MAX_STOCK-n for k, n in recipe['outputs'].items()):continue
        worker_stock=actors[worker].get('inventory',{})
        if any(type(worker_stock.get(k)) is not int or not 0 <= worker_stock[k] <= MAX_STOCK for k in commodity_ids()):continue
        if worker_stock['gold'] > MAX_STOCK-policy['wage_gold']:continue
        opportunities.append({'business_id': business_id, 'employer': employer,
            'employer_name': person_view(state,worker,employer)['name'],
            'revision': business.get('revision', 0), 'policy': policy,
            'recipe_id':'bread_recipe','catalog_hash':catalog_hash(),'recipe_hash':recipe_hash('bread_recipe')})
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
