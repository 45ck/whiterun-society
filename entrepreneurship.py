"""Resident-selected charters from own resources and verified recipe knowledge.

A charter is public service registration, not a created building, sale or asset.
The starter recipe and production policy are authored gameplay rules.
"""
import copy
import hashlib
from enterprises import CAPABILITIES, apply_enterprise_change
from routing import activity_blocker


def knows_bread_recipe(person):
    return (person.get('known_recipes', {}).get('bread', {}).get('source') == 'verified_native_production'
        or any(m.get('kind') in ('paid_work', 'owner_work') and m.get('grain_used') == 1
               and m.get('bread_made') == 2 for m in person.get('memories', [])))


def learn_bread_recipe(person, event_id):
    person.setdefault('known_recipes', {}).setdefault('bread', {
        'source': 'verified_native_production', 'event_id': event_id,
        'scope': 'Authored learning rule after participation in verified production; not measured skill'})


def enterprise_choices(state, observation, actor):
    town=state.get('town') or {};person=state.get('people',{}).get(str(actor))
    native=next((a for a in observation.get('residents',[]) if a.get('id')==actor and a.get('isPerson') is True),None)
    if not person or str(actor) not in town.get('residents',{}) or not native or activity_blocker(native):return []
    stock=native.get('inventory',{})
    if any(type(stock.get(k)) is not int or stock[k]<0 for k in ('gold','bread','grain')):return []
    businesses=town.get('businesses',{})
    owned=[(key,b) for key,b in sorted(businesses.items()) if b.get('owner')==actor and b.get('custodian')==actor
           and b.get('capabilities') and set(b['capabilities']) <= CAPABILITIES]
    candidates=owned
    if not owned and len(businesses)<128:
        key='resident-'+str(actor)
        if key not in businesses:candidates=[(key,None)]
    result=[]
    for key,b in candidates:
        if b and any(c.get('status') in ('accepted','held') for c in b.get('contracts',[])):continue
        existing=set((b or {}).get('capabilities',[]))
        base={'id':key,'expected_revision':(b or {}).get('revision',0),
            'name':(b or {}).get('name') or (person['profile']['name'][:60]+' provisions'),
            'custodian':actor,'capabilities':sorted(existing),'active':True,
            'production_policy':copy.deepcopy((b or {}).get('production_policy',{}))}
        def add(action,effect,caps=None,active=True):
            spec={**base,'capabilities':sorted(caps if caps is not None else existing),'active':active}
            result.append({'id':action+'_'+key,'effect':effect,'specification':spec})
        if b and b.get('active',True):
            add('close_enterprise','Stop advertising your services. Keep your own goods and money; no outstanding accepted contract may be abandoned.',active=False)
        elif b:
            add('reopen_enterprise','Advertise your existing services again. No property, goods, customers or money are created.')
        if b and not b.get('active',True):continue
        if stock['bread']>=1 and 'retail_food' not in existing:
            add('offer_food_trade','Register food retail using your own carried bread. Household reserves remain yours and each sale needs separate consent. Registration creates no stall, stock or money.',existing|{'retail_food'})
        if stock['grain']>=1 and 'retail_grain' not in existing:
            add('offer_grain_trade','Register grain supply using your own carried grain. Choose whether to sell when an offer arrives; no resources or sales are created.',existing|{'retail_grain'})
        if knows_bread_recipe(person) and (stock['grain']>=1 or stock['gold']>=1) and 'bread_recipe' not in existing:
            add('register_bakery','Register the bread recipe you have already participated in. Use your own funds and inputs; procurement and work remain later decisions. Starter target, wage and duration are authored defaults. No bakery building, equipment, grain or money appears.',existing|{'bread_recipe','retail_food'})
    return result


def apply_resident_enterprise(state, plan, specification, observation):
    if specification['custodian']!=plan['actor']:raise ValueError('Resident cannot register another person')
    key=specification['id'];old=state['town']['businesses'].get(key)
    if old and (old.get('owner')!=plan['actor'] or old.get('custodian')!=plan['actor']):
        raise ValueError('Resident cannot revise another enterprise')
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
