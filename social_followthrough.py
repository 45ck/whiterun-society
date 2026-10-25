"""Resident-chosen follow-up reviews grounded in speech they actually heard."""
import copy
import hashlib
from labour import work_opportunities
from rest import rest_opportunities
from opportunities import food_sellers
from places import market_opportunity


FOLLOWUPS = {
    'review_food_after_talk': 'food',
    'review_rest_after_talk': 'rest',
    'review_work_after_talk': 'work',
}


def followthrough_options(state, observation, actor):
    native=next((r for r in observation.get('residents',[]) if r['id']==actor and r.get('isPerson') is True),None)
    if not native:return []
    stock=native.get('inventory',{});options=[]
    if stock.get('bread',0)>0 or stock.get('gold',0)>=3 and (
            food_sellers(state,observation,actor) or market_opportunity(state,observation,actor)):
        options.append({'id':'review_food_after_talk','effect':'What I heard prompts me to reconsider my own food plans after this exchange. Queue a food decision using my current resources; no meal or purchase has happened yet.'})
    if rest_opportunities(state,observation,actor):
        options.append({'id':'review_rest_after_talk','effect':'What I heard prompts me to consider a seated break after this exchange. Queue a rest decision; no rest or recovery has happened yet.'})
    if work_opportunities(state,observation,actor):
        options.append({'id':'review_work_after_talk','effect':'What I heard prompts me to consider currently advertised work after this exchange. Queue a livelihood decision; an employer must still offer and I must accept.'})
    return options


def queue_followthrough(state, conversation, actor, choice, observation):
    if choice not in FOLLOWUPS:return
    heard=[t for t in conversation['turns'] if t.get('delivered') and t['listener']==actor]
    if not heard:raise ValueError('Follow-through requires heard speech')
    daily=(state.get('town') or {}).get('daily')
    if daily is None:raise ValueError('Follow-through requires a resident queue')
    source={'encounter_id':conversation['id'],'actor':actor,'focus':FOLLOWUPS[choice],
            'heard':[{'delivery_id':t['delivery_id'],'speaker':t['speaker'],'line':t['selected']['line'],
                      'epistemic_status':'heard claim, not verified fact'} for t in heard],
            'source':'Resident decision after heard speech; a queued review, not a promise or completed action'}
    event=next((e for e in daily['queue'] if e['actor']==actor and e['kind']=='need_review' and e['status']=='pending'),None)
    if event is None:
        event={'id':'followup-'+hashlib.sha256((conversation['id']+':'+str(actor)).encode()).hexdigest()[:24],
               'actor':actor,'kind':'need_review','status':'pending','created_day':observation['gameDays'],
               'priority':1.0,'reason':'Resident chose to reconsider '+FOLLOWUPS[choice]+' after heard conversation'}
        daily['queue'].append(event)
    sources=event.setdefault('conversation_followups',[])
    if not any(s['encounter_id']==conversation['id'] for s in sources):sources.append(copy.deepcopy(source))
    del sources[:-8]
    event['priority']=max(event['priority'],1.0)
    conversation.setdefault('follow_through',[]).append({**source,'event_id':event['id']})
