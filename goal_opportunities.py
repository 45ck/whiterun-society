"""Personal intentions become queued reviews, never automatic economic effects."""
import copy
import hashlib
import json
import math
from pathlib import Path
import re

from knowledge import person_view
from opportunities import food_sellers
from places import market_opportunities
from rest import rest_opportunities
from routing import activity_blocker,route_available
from social import social_candidates,same_social_space

POLICY_PATH=Path(__file__).parent/'config/goal-opportunities.json'
FOCUSES={'food','rest','work','social'}


def opportunity_policy(value=None):
    value=json.loads(POLICY_PATH.read_text(encoding='utf-8')) if value is None else value
    if (not isinstance(value,dict) or set(value)!={'version','enabled_focuses','priority_floor','maximum_followup_sources'}
            or not isinstance(value.get('version'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',value['version'])
            or not isinstance(value.get('enabled_focuses'),list) or any(not isinstance(f,str) or f not in FOCUSES for f in value['enabled_focuses'])
            or len(set(value['enabled_focuses']))!=len(value['enabled_focuses'])
            or type(value.get('priority_floor')) not in (int,float) or not math.isfinite(value['priority_floor']) or not 0<=value['priority_floor']<=1
            or type(value.get('maximum_followup_sources')) is not int or not 1<=value['maximum_followup_sources']<=32):
        raise ValueError('Invalid goal-opportunity policy')
    return copy.deepcopy(value)


def focus_opportunities(state,observation,actor):
    """Only own resources, public charters and current eligible observations."""
    own=next((r for r in observation.get('residents',[]) if r.get('id')==actor and r.get('isPerson') is True),None)
    empty={'food':False,'rest':False,'work':False,'social':False,'food_sellers':[],'public_work':[],'rest_sites':[],'nearby_people':[]}
    if not own or str(actor) not in (state.get('town') or {}).get('residents',{}) or activity_blocker(own):return empty
    stock=own.get('inventory') or {};town=state.get('town') or {}
    carried_food=type(stock.get('bread')) is int and stock['bread']>0
    can_bid=type(stock.get('gold')) is int and stock['gold']>=1
    rows={r['id']:r for r in observation.get('residents',[]) if r.get('isPerson') is True}
    sellers=[s for s in food_sellers(state,observation,actor) if same_social_space(own,rows.get(s['id'],{}))] if can_bid else []
    searches=market_opportunities(state,observation,actor)
    benches=rest_opportunities(state,observation,actor)
    neighbours=social_candidates(state,observation,actor)
    public_work=[]
    for business_id,business in sorted(town.get('businesses',{}).items()):
        employer=business.get('custodian')
        if business.get('active',True) is not True or 'bread_recipe' not in business.get('capabilities',[]):continue
        if employer==actor:
            if business.get('owner')!=actor:continue
            # Ownership and own input stock establish something to review, not
            # a paid job, available animation or completed productive labour.
            if type(stock.get('grain')) is not int or stock['grain']<1:continue
            public_work.append({'business_id':business_id,'kind':'own_enterprise','revision':business.get('revision',0)})
        elif str(employer) in town.get('residents',{}) and route_available(observation,actor,employer) and same_social_space(own,rows.get(employer,{})):
            public_work.append({'business_id':business_id,'kind':'public_employer','revision':business.get('revision',0),
                'employer':person_view(state,actor,employer),
                'source':'Public production charter only; employer resources, vacancy and consent are unknown'})
    return {'food':carried_food or can_bid and bool(sellers or searches),'rest':bool(benches),'work':bool(public_work),'social':bool(neighbours),
        'food_sellers':sellers,'public_work':public_work,'public_food_search_sites':[s['id'] for s in searches],
        'rest_sites':[{'id':b['id'],'distance':b['distance']} for b in benches],
        'nearby_people':neighbours}


def purposeful_options(state,observation,actor,destinations,policy=None):
    policy=opportunity_policy(policy);available=focus_opportunities(state,observation,actor)
    options=[];actions={};enabled=set(policy['enabled_focuses'])
    effects={
        'food':'Review eating carried food or seeking food using your own resources and public sellers. No meal or purchase has happened; you may decline or reconsider.',
        'rest':'Review a seated break at an observed available bench. Rest, exact furniture attendance and recovery require a later validated action.',
        'work':'Review your own production or ask about a public enterprise. Public registration does not establish available inputs, vacancies, a job offer or pay.',
        'social':'Offer a nearby social opportunity. You still choose a partner, they may decline, and no conversation or relationship benefit has happened.'}
    for focus in sorted(enabled):
        if not available[focus]:continue
        action='review_'+focus
        options.append({'id':action,'effect':effects[focus]})
        actions[action]={'family':action,'focus':focus,'target_id':None,'trigger':'decision'}
    rest_ids={s['id'] for s in available['rest_sites']}
    for site in destinations:
        focuses=[]
        if site['kind']=='bench_area' and site['id'] in rest_ids:focuses.append('rest')
        if site['kind']=='public_place':
            if available['food'] and site['id'] in available.get('public_food_search_sites',[]):focuses.append('food')
            if available['social']:focuses.append('social')
        for focus in focuses:
            if focus not in enabled:continue
            action='visit_'+focus+'_'+str(site['id'])
            options.append({'id':action,'effect':f"Walk to {site['name']} ({site['distance']} game units), then reconsider {focus}. "+effects[focus]})
            actions[action]={'family':'visit_to_review_'+focus,'focus':focus,'target_id':site['id'],'trigger':'arrival'}
    return {'options':options,'actions':actions,'opportunity_policy':policy,'public_opportunities':available}


def pending_goal_review(state,actor):
    return any(e.get('actor')==actor and e.get('status') in ('pending','started') and e.get('goal_followups')
               for e in (state.get('town') or {}).get('daily',{}).get('queue',[]))


def queue_goal_review(state,goal,actor,observation):
    """Append one saved review or annotate a compatible pending review."""
    focus=goal.get('focus')
    if focus not in FOCUSES:return None
    policy=opportunity_policy(goal['opportunity_policy']);day=observation['gameDays']
    kind='social_review' if focus=='social' else 'need_review'
    available=focus_opportunities(state,observation,actor)
    if focus not in policy['enabled_focuses'] or not available[focus]:
        return {'focus':focus,'status':'unavailable','observed_day':day,'reason':'Chosen focus currently has no observed executable review opportunity; no effect granted'}
    daily=state['town'].setdefault('daily',{'last_day':day,'sequence':0,'queue':[],'reviews':[]})
    if any(e.get('actor')==actor and e.get('status')=='started' for e in daily['queue']):
        return {'focus':focus,'status':'unavailable','observed_day':day,'reason':'An already started resident activity owns this opportunity; no effect granted'}
    event=next((e for e in daily['queue'] if e.get('actor')==actor and e.get('kind')==kind and e.get('status')=='pending'),None)
    if event is None:
        # A deliberate resident choice can replace a still-unaccepted invitation;
        # it never interrupts or overwrites an already started action.
        for old in daily['queue']:
            if old.get('actor')==actor and old.get('status')=='pending':
                old.update(status='superseded',settled_day=day,outcome='resident_selected_goal_review',
                    interruption_reason='Resident selected a different personal review before this invitation began')
        event={'id':'goal-'+hashlib.sha256((goal['id']+':'+focus).encode()).hexdigest()[:24],
            'actor':actor,'kind':kind,'status':'pending','created_day':day,'priority':policy['priority_floor'],
            'reason':'Resident chose to review '+focus+' as a personal goal'}
        daily['queue'].append(event)
    event.setdefault('reason','Resident chose to review '+focus+' as a personal goal')
    own_needs=state['people'][str(actor)].get('needs',{})
    need=own_needs.get({'food':'hunger','rest':'fatigue','social':'social_contact'}.get(focus,''))
    priority=event.get('priority')
    event['priority']=priority if type(priority) in (int,float) and math.isfinite(priority) and 0<=priority<=1 else policy['priority_floor']
    if type(need) in (int,float) and math.isfinite(need) and 0<=need<=1:event['priority']=max(event['priority'],need)
    expires=day+goal['policy']['review_game_minutes']/1440
    event['review_expires_day']=max(expires,event.get('review_expires_day',expires))
    source={'goal_id':goal['id'],'actor':actor,'focus':focus,'trigger':'arrival' if goal.get('target') else 'decision',
        'decision_day':goal['decided_day'],'queued_day':day,'policy_version':policy['version'],
        'model':goal.get('model','unrecorded'),'provenance':goal.get('provenance','unrecorded'),
        'source':'Resident-selected personal intent; review resources and consent again. No action or economic effect is implied.'}
    sources=event.setdefault('goal_followups',[])
    if not any(s.get('goal_id')==goal['id'] for s in sources):sources.append(source)
    del sources[:-policy['maximum_followup_sources']]
    person=state['people'][str(actor)]
    person['agency'].update(state='decision_pending',reason=event['reason'],event_id=event['id'],next_review_day=day)
    return {'event_id':event['id'],'focus':focus,'status':'pending','queued_day':day,'review_expires_day':event['review_expires_day']}
