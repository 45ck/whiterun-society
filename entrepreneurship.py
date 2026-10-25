"""Resident-selected charters from own resources and verified recipe knowledge.

A charter is public service registration, not a created building, sale or asset.
The starter recipe and production policy are authored gameplay rules.
"""
import copy
import hashlib
from enterprises import executable_capabilities, apply_enterprise_change
from economy_catalog import recipe_ids, recipe_spec, commodity_ids, MAX_STOCK, canonical_json
from market_policy import tradable_ids, goods_policy, advertised_goods
from routing import activity_blocker
from activity_leases import activity_conflict,work_account_conflict


def knows_recipe(person, recipe_id):
    """Knowledge is per recipe; catalog registration teaches nobody."""
    if recipe_id not in recipe_ids():
        return False
    known = person.get('known_recipes', {})
    entry = known.get(recipe_id, {})
    recipe = recipe_spec(recipe_id)
    definition = {key: recipe[key] for key in ('id', 'version', 'inputs', 'outputs')}
    if entry.get('source') == 'verified_native_production':
        if 'definition' in entry:return entry['definition'] == definition
        if recipe_id != 'bread_recipe':return False
    # Historical bread records predate explicit recipe IDs. Never infer a new
    # recipe from bread-shaped output or from another resident's participation.
    return recipe_id == 'bread_recipe' and recipe['inputs'] == {'grain': 1} and recipe['outputs'] == {'bread': 2} and (
        entry.get('source') == 'verified_native_production' or
        known.get('bread', {}).get('source') == 'verified_native_production'
        or any(m.get('kind') in ('paid_work', 'owner_work') and
               m.get('recipe_id', 'bread_recipe') == 'bread_recipe' and
               m.get('grain_used') == 1 and m.get('bread_made') == 2
               for m in person.get('memories', [])))


def learn_recipe(person, event_id, recipe_id):
    recipe = recipe_spec(recipe_id)  # Reject unknown/planned mechanisms.
    if knows_recipe(person, recipe_id):return
    person.setdefault('known_recipes', {})[recipe_id] = {
        'source': 'verified_native_production', 'event_id': event_id,
        'recipe_id': recipe_id,
        'definition': {key: recipe[key] for key in ('id', 'version', 'inputs', 'outputs')},
        'scope': 'Authored learning rule after participation in verified production; not measured skill'}
    if recipe_id == 'bread_recipe' and set(recipe['inputs']) == {'grain'} and set(recipe['outputs']) == {'bread'}:
        person['known_recipes'].setdefault('bread', copy.deepcopy(person['known_recipes'][recipe_id]))


def recipe_knowledge(person):
    return {'bread': knows_bread_recipe(person),
        'recipes': {rid: knows_recipe(person, rid) for rid in sorted(recipe_ids())},
        'source': 'Own verified production participation; legacy bread records remain readable. Catalog availability does not grant knowledge.'}


def knows_bread_recipe(person):
    if 'bread_recipe' not in recipe_ids():return False
    recipe=recipe_spec('bread_recipe')
    return set(recipe['inputs']) == {'grain'} and set(recipe['outputs']) == {'bread'} and knows_recipe(person, 'bread_recipe')


def learn_bread_recipe(person, event_id):
    recipe=recipe_spec('bread_recipe')
    if set(recipe['inputs']) != {'grain'} or set(recipe['outputs']) != {'bread'}:
        raise ValueError('Legacy bread learning requires the bread adapter')
    learn_recipe(person, event_id, 'bread_recipe')


def enterprise_choices(state, observation, actor):
    if activity_conflict(state,actors=(actor,),observation=observation):return []
    town=state.get('town') or {};person=state.get('people',{}).get(str(actor))
    native=next((a for a in observation.get('residents',[]) if a.get('id')==actor and a.get('isPerson') is True),None)
    if not person or str(actor) not in town.get('residents',{}) or not native or activity_blocker(native):return []
    stock=native.get('inventory',{})
    if any(type(stock.get(k)) is not int or not 0<=stock[k]<=MAX_STOCK for k in commodity_ids()):return []
    businesses=town.get('businesses',{})
    owned=[(key,b) for key,b in sorted(businesses.items()) if b.get('owner')==actor and b.get('custodian')==actor
           and b.get('capabilities') and set(b['capabilities']) <= executable_capabilities()]
    candidates=owned
    if not owned and len(businesses)<128:
        key='resident-'+str(actor)
        if key not in businesses:candidates=[(key,None)]
    result=[]
    for key,b in candidates:
        if work_account_conflict(state,actors=(actor,),business_ids=(key,),observation=observation):continue
        if b and any(c.get('status') in ('accepted','held') for c in b.get('contracts',[])):continue
        existing=set((b or {}).get('capabilities',[]))
        base={'id':key,'expected_revision':(b or {}).get('revision',0),
            'name':(b or {}).get('name') or (person['profile']['name'][:60]+' provisions'),
            'custodian':actor,'capabilities':sorted(existing),'active':True,
            'production_policy':copy.deepcopy((b or {}).get('production_policy',{})),
            'recipe_policies':copy.deepcopy((b or {}).get('recipe_policies',{}))}
        if b and 'sale_commodities' in b:base['sale_commodities']=copy.deepcopy(b['sale_commodities'])
        def add(action,effect,caps=None,active=True,sales=None):
            spec={**base,'capabilities':sorted(caps if caps is not None else existing),'active':active}
            if sales is not None:spec['sale_commodities']=sorted(sales)
            result.append({'id':action+'_'+key,'effect':effect,'specification':spec})
        if b and b.get('active',True):
            add('close_enterprise','Stop advertising your services. Keep your own goods and money; no outstanding accepted contract may be abandoned.',active=False)
        elif b:
            add('reopen_enterprise','Advertise your existing services again. No property, goods, customers or money are created.')
        if b and not b.get('active',True):continue
        listed=set(advertised_goods(b or {}))
        for commodity in tradable_ids():
            if stock[commodity]<1 or commodity in listed:continue
            alias=goods_policy(commodity)['legacy_retail_capability']
            capability=alias or 'retail_goods'
            action='offer_food_trade' if alias=='retail_food' else 'offer_grain_trade' if alias=='retail_grain' else 'offer_goods_'+hashlib.sha256(canonical_json([key,commodity]).encode()).hexdigest()[:24]
            add(action,'Publicly offer your carried '+commodity+'. Choose whether to sell each time; household policies remain yours. Registration creates no stock, stall, sale or money.',
                existing|{capability},sales=listed|{commodity})
        for recipe_id in sorted(recipe_ids()):
            recipe = recipe_spec(recipe_id)
            can_source_inputs = (all(type(stock.get(k)) is int and stock[k] >= amount
                                     for k, amount in recipe['inputs'].items()) or stock['gold'] >= 1)
            if knows_recipe(person, recipe_id) and can_source_inputs and recipe_id not in existing:
                outputs=set(recipe['outputs']) & set(tradable_ids())
                caps = existing | {recipe_id} | {goods_policy(k)['legacy_retail_capability'] or 'retail_goods' for k in outputs}
                action = 'register_bakery' if recipe_id == 'bread_recipe' and set(recipe['inputs']) == {'grain'} and set(recipe['outputs']) == {'bread'} else 'register_recipe_' + recipe_id
                add(action, 'Register the ' + recipe_id + ' recipe you already know and advertise its market-enabled outputs. Use your own funds and inputs; procurement and work remain later decisions. Policy defaults are authored. No building, equipment, stock or money appears.', caps,
                    sales=listed|outputs if listed or outputs else None)
    return result


def apply_resident_enterprise(state, plan, specification, observation):
    if specification['custodian']!=plan['actor']:raise ValueError('Resident cannot register another person')
    key=specification['id'];old=state['town']['businesses'].get(key)
    if old and (old.get('owner')!=plan['actor'] or old.get('custodian')!=plan['actor']):
        raise ValueError('Resident cannot revise another enterprise')
    added_recipes=(set(specification['capabilities']) - set((old or {}).get('capabilities', []))) & set(recipe_ids())
    if any(not knows_recipe(state['people'][str(plan['actor'])], rid) for rid in added_recipes):
        raise ValueError('Resident has not learned this recipe through verified own participation')
    event_id='resident-enterprise-'+hashlib.sha256(plan['id'].encode()).hexdigest()[:24]
    business,event=apply_enterprise_change(state,event_id,specification,observation,
        'Resident-selected public charter; existing personal inventory only')
    event.update(actor=plan['actor'],plan_id=plan['id'],decision_claim_id=plan['decisions'][-1]['claim_id'])
    person=state['people'][str(plan['actor'])]
    person['memories']=(person['memories']+[{'event_id':event_id,'kind':'enterprise_changed',
        'business_id':key,'revision':business['revision'],'active':business['active'],
        'capabilities':business['capabilities'],'source':'Own public registration decision; no native asset effects'}])[-32:]
    plan.update(phase='complete',outcome='enterprise_registered' if old is None else 'enterprise_closed' if not business['active'] else 'enterprise_expanded' if old.get('active',True) else 'enterprise_reopened',
        enterprise_change={'business_id':key,'revision':business['revision'],'event_id':event_id})
