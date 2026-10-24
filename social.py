"""Bounded social opportunities and authored relationship consequences.

Proximity is an engine observation, not qualified vision. No private partner
needs, traits, inventories or memories are exposed to another resident.
"""
import math
from routing import route_available
from knowledge import person_view
from dialogue_context import time_context

SOCIAL_STAGES=('choose_partner','respond','continue_dialogue','reflect_first','reflect_second')


def social_candidates(state,observation,actor):
    people=state.get('people',{});town=state.get('town') or {}
    rows={r['id']:r for r in observation.get('residents',[]) if r.get('isPerson') is True}
    own=rows.get(actor);person=people.get(str(actor),{})
    if not own or str(actor) not in town.get('residents',{}) or own.get('isGuard') is not False or person.get('commitments'):
        return []
    result=[]
    for other,row in rows.items():
        if str(other) not in town['residents'] or str(other) not in people or other==actor or row.get('isGuard') is not False or people[str(other)].get('commitments'):
            continue
        if not route_available(observation,actor,other):continue
        try:gap=math.dist([own[k] for k in ('x','y','z')],[row[k] for k in ('x','y','z')])
        except (TypeError,ValueError,KeyError):continue
        if not math.isfinite(gap) or gap>1500:continue
        result.append({**person_view(state,actor,other),'distance':round(gap,1),
                       'my_relationship':person.get('relationships',{}).get(str(other),{}),
                       'source':'native nearby proximity; vision is not qualified'})
    return sorted(result,key=lambda r:(r['distance'],r['id']))[:6]


def social_context(state,c,observation,stage):
    actor=c['initiator'] if stage in ('choose_partner','reflect_first') else c['partner']
    if stage=='continue_dialogue':actor=c['speakers'][c['turn']%2]
    person=state['people'][str(actor)]
    context={'actor_id':actor,'profile':person['profile'],'scenario_state':{'needs':person['needs']},
             'clock':time_context(observation.get('gameDays')),'own_commitments':person.get('commitments',[]),
             'memories':person['memories'][-8:],'trust':person.get('trust',{}),
             'event':{'id':c['id'],'kind':stage},'options':[]}
    if stage=='choose_partner':
        candidates=social_candidates(state,observation,actor)
        context['nearby_candidates']=candidates
        context['event']['information']='Choose a nearby person to approach for a short social exchange, or continue quietly. A meeting does not guarantee conversation. Consider your own fatigue, needs and commitments. Do not assume the other person wants to talk.'
        context['options']=[{'id':'defer','effect':'Continue quietly; no approach or speech.'}]+[
            {'id':'approach_'+str(r['id']),'effect':'Approach '+r['name']+' and let them choose whether to chat.'} for r in candidates]
    elif stage=='respond':
        other=c['initiator'];context['other']=person_view(state,actor,other)
        context['my_relationship']=person.get('relationships',{}).get(str(other),{})
        context['event']['information']='This person approached you and is nearby. Choose a brief conversation or a polite spoken refusal. Your choice grants no trade, employment or political authority. They do not know your private feelings unless you speak.'
        context['options']=[{'id':'chat','effect':f"Accept a brief exchange of up to {c.get('turn_limit',2)} turns; either resident may end it early."},
            {'id':'decline','effect':'Give one short courteous refusal, then return to your routine. No hostility is implied.'}]
    elif stage=='continue_dialogue':
        other=c['speakers'][1-c['turn']%2]
        context['other']=person_view(state,actor,other)
        context['my_relationship']=person.get('relationships',{}).get(str(other),{})
        context['heard']=[{'line':t['selected']['line'],'status':'heard claim; truth unverified'} for t in c['turns'] if t.get('delivered') and t['listener']==actor]
        context['event'].update(turns_delivered=c['turn'],remaining_turns=c['max_turns']-c['turn'],
            information='The other person finished speaking within hearing range. Decide whether a relevant reply is worthwhile, offer a brief spoken closing, or leave quietly. Consider unresolved questions, your own needs and your relationship. A greeting does not oblige either person to keep talking. Do not repeatedly prolong an exhausted topic.')
        context['options']=[{'id':'reply','effect':'Choose a relevant reply or follow-up; no economic action is executed by speech.'},
            {'id':'close_politely','effect':'Give a brief reply or acknowledgement and a natural farewell, then end the encounter.'},
            {'id':'leave_quietly','effect':'End without another spoken line. Do not invent an unheard farewell or infer hostility.'}]
    else:
        other=c['partner'] if actor==c['initiator'] else c['initiator']
        heard=[t for t in c['turns'] if t.get('delivered') and t['listener']==actor]
        context['other']=person_view(state,actor,other)
        context['my_relationship']=person.get('relationships',{}).get(str(other),{})
        context['heard']=[{'line':t['selected']['line'],'status':'heard claim; truth unverified'} for t in heard]
        context['event']['information']='Privately appraise what you actually heard, using your own personality and memories. Courtesy does not prove friendship or trustworthiness. These are authored simulation feelings, not objective facts about the other person.'
        context['options']=[{'id':'neutral','effect':'No change in affinity; hearing someone does not automatically make a friend.'}]
        if heard:context['options'] += [{'id':'felt_supported','effect':'Record a small positive subjective affinity change of 0.05.'},
                                       {'id':'felt_annoyed','effect':'Record a small negative subjective affinity change of 0.05.'}]
    return context


def settle_social(state,c,day):
    """Close the scheduled opportunity once; decisions alone are not encounters."""
    if c.get('social_settled'):return
    for event in state.get('town',{}).get('daily',{}).get('queue',[]):
        if event['id']==c['id']:event.update(status=c['phase'],outcome=c.get('outcome',c['phase']),settled_day=day)
    for actor in set([c['initiator']]+([c['partner']] if c.get('partner') else [])):
        p=state['people'][str(actor)]
        # Attempt fairness is separate from need relief: a failed meeting must
        # not monopolize future opportunities or count as satisfying company.
        p['social_attempt_day']=day
        p['agency'].update(state='quiet_interval' if c['phase']=='complete' else 'social_held',
            reason='Social review '+c.get('outcome',c['phase']),next_review_day=day+1/24)
        # A decline or a held delivery does not imply resentment or satisfaction.
        heard=sum(t.get('delivered',False) and t['listener']==actor for t in c.get('turns',[]))
        if heard and c['phase']=='complete' and c.get('response')=='chat':
            baseline=max(p.get('needs_clock',day),p.get('social_clock',0))
            growth=max(0,day-baseline)*24*(.018+.025*p['profile']['big_five']['extraversion'])
            p['needs']['social_contact']=round(max(0,min(1,p['needs']['social_contact']+growth)-.2),6)
            p['social_clock']=day
            # Participating also satisfies a previously queued opportunity for
            # this person; it must not immediately start the same social need again.
            for event in state.get('town',{}).get('daily',{}).get('queue',[]):
                if event['id']!=c['id'] and event['actor']==actor and event['kind']=='social_review' and event['status']=='pending':
                    event.update(status='complete',outcome='participated_as_partner',settled_day=day,encounter_id=c['id'])
    c['social_settled']=True


def record_appraisal(state,c,stage,decision):
    actor=c['initiator'] if stage=='reflect_first' else c['partner']
    other=c['partner'] if actor==c['initiator'] else c['initiator']
    heard=[t for t in c['turns'] if t.get('delivered') and t['listener']==actor]
    if not heard:return
    p=state['people'][str(actor)]
    relation=p.setdefault('relationships',{}).setdefault(str(other),{'familiarity':0,'affinity':0,'heard_turns':0,'appraisals':[]})
    if any(r['event_id']==c['id'] for r in relation['appraisals']):return
    delta={'neutral':0,'felt_supported':.05,'felt_annoyed':-.05}[decision['action_id']]
    relation['familiarity']=round(min(1,relation['familiarity']+.05*len(heard)),6)
    relation['affinity']=round(max(-1,min(1,relation['affinity']+delta)),6)
    relation['heard_turns']+=len(heard)
    relation['appraisals']=(relation['appraisals']+[{'event_id':c['id'],'choice':decision['action_id'],
        'basis':'completed nearby audio playback; subjective authored response, not verified truth'}])[-16:]
    p['memories']=(p['memories']+[{'event_id':c['id'],'kind':'social_appraisal','other':other,
        'response':decision['action_id'],'affinity_change':delta,'source':'resident decision after delivered speech; subjective gameplay state'}])[-32:]
