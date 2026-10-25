"""Recipe-based paid opportunities; eligibility is never consent or production."""
from routing import route_available
from knowledge import person_view
from enterprises import production_policy
from employment import recently_refused, work_terms_hash
from economy_catalog import native_catalog_matches, commodity_ids, recipe_spec, recipe_ids, recipe_hash, catalog_hash, MAX_STOCK
import economy_catalog
from resident_identity import resident_identity_status


def paid_employment_available(observation):
    native = observation.get('paid_employment') or {}
    return (isinstance(native, dict) and native.get('available') is True
        and type(native.get('protocol')) is int and native['protocol'] == 2
        and isinstance(native.get('epoch'), str) and bool(native['epoch'])
        and type(native.get('capacity')) is int and 1 <= native['capacity'] <= 128
        and ('session' not in native or native['session'] == observation.get('session')))


def work_opportunities(state, observation, worker):
    from entrepreneurship import knows_recipe
    if not paid_employment_available(observation) or not native_catalog_matches(observation):return []
    identity = resident_identity_status(state, observation, worker)
    if not identity['qualified']:return []
    actors = {a['id']: a for a in observation.get('residents', []) if isinstance(a,dict) and a.get('isPerson') is True}
    currency = next(row['id'] for row in economy_catalog.ECONOMY_CATALOG['commodities'] if row['currency'])
    def inventory(actor):
        row=actors.get(actor,{})
        if 'inventory_checkpoint' in row and row['inventory_checkpoint'] != observation.get('checkpoint'):return None
        stock=row.get('inventory')
        if (not isinstance(stock,dict) or set(stock) != set(commodity_ids())
                or any(type(v) is not int or not 0 <= v <= MAX_STOCK for v in stock.values())):return None
        return stock
    worker_stock=inventory(worker)
    if worker_stock is None:return []
    opportunities=[]
    for business_id,business in sorted((state.get('town') or {}).get('businesses',{}).items()):
        employer=business.get('custodian')
        if (business.get('active',True) is not True or employer==worker
                or not route_available(observation,worker,employer,state)):continue
        employer_identity=resident_identity_status(state,observation,employer)
        stock=inventory(employer)
        if not employer_identity['qualified'] or stock is None:continue
        revision=business.get('revision',0)
        if type(revision) is not int or revision<1:continue
        if recently_refused(state,worker,business_id,revision,observation.get('gameDays')):continue
        for recipe_id in sorted(set(business.get('capabilities',[])) & set(recipe_ids())):
            if not knows_recipe(state['people'].get(str(employer),{}),recipe_id,
                    state=state,observation=observation,actor_id=employer):continue
            try:policy=production_policy(business,recipe_id)
            except (ValueError,KeyError):continue
            recipe=recipe_spec(recipe_id);wage=policy['wage_gold']
            target=policy.get('target_output',policy.get('target_bread'))
            if (stock[currency]<wage or worker_stock[currency]>MAX_STOCK-wage
                    or any(stock[k]<n for k,n in recipe['inputs'].items())
                    or any(stock[k]>=target or stock[k]>MAX_STOCK-n for k,n in recipe['outputs'].items())):continue
            terms={'protocol':2,'worker':worker,'worker_base_id':identity['base_id'],
                'employer':employer,'employer_base_id':employer_identity['base_id'],
                'employer_name':person_view(state,worker,employer)['name'],
                'business_id':business_id,'revision':revision,'policy':policy,'currency':currency,
                'recipe_id':recipe_id,'catalog_hash':catalog_hash(),'recipe_hash':recipe_hash(recipe_id)}
            terms['terms_hash']=work_terms_hash(terms)
            opportunities.append(terms)
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
