"""Personal standing destinations. Movement never implies trade, work or rest."""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import time
from decisions import validate_decision
from routing import activity_blocker
from inference_receipts import usage_receipt
from dialogue_context import time_context
from goal_opportunities import purposeful_options,pending_goal_review,queue_goal_review
from context_window import bounded_goal_context

ACTIVE=('complete','held')
POLICY_PATH=Path(__file__).parent/'config/resident-goals.json'
LEGACY_POLICY={'version':'legacy-resident-goals','minimum_distance':250,'maximum_distance':12000,
               'review_game_minutes':15,'arrival_distance':200,'claim_timeout_seconds':1800}


def validate_policy(value):
    """Validate configuration while keeping native protocol limits explicit."""
    if not isinstance(value,dict) or set(value)!=set(LEGACY_POLICY):raise ValueError('Invalid personal-goal policy fields')
    if not isinstance(value['version'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',value['version']):raise ValueError('Invalid personal-goal policy version')
    for key in ('minimum_distance','maximum_distance','review_game_minutes','arrival_distance','claim_timeout_seconds'):
        if type(value[key]) not in (int,float) or not math.isfinite(value[key]):raise ValueError('Invalid personal-goal policy number')
    if not 200<=value['minimum_distance']<value['maximum_distance']<=100000:raise ValueError('Invalid personal-goal travel limits')
    if not 0<value['review_game_minutes']<=1440:raise ValueError('Invalid personal-goal review interval')
    if value['arrival_distance']!=200:raise ValueError('Arrival distance must match the native 200-unit contract')
    if not 60<=value['claim_timeout_seconds']<=3600:raise ValueError('Invalid personal-goal claim timeout')
    return copy.deepcopy(value)


def load_policy():
    return validate_policy(json.loads(POLICY_PATH.read_text(encoding='utf-8')))


def policy_id(policy):
    return hashlib.sha256(json.dumps(policy,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def native_day(observation):
    day=observation.get('gameDays')
    if type(day) not in (int,float) or not math.isfinite(day):raise ValueError('Native time is required')
    return day


def same_space(a,b):
    """Unknown space retains legacy eligibility; native execution rechecks it."""
    if not isinstance(a,dict) or not isinstance(b,dict):return None
    if type(a.get('cell')) is int and a['cell']>0 and a.get('cell')==b.get('cell'):return True
    if a.get('interior') is False and b.get('interior') is False:
        return type(a.get('world')) is int and a['world']>0 and a['world']==b.get('world')
    if type(a.get('cell')) is int and type(b.get('cell')) is int:return False
    return None


def families(context):
    if 'goal_actions' in context:return {o['id']:context['goal_actions'][o['id']]['family'] for o in context['options']}
    sites={str(s['id']):s['kind'] for s in context['destinations']}
    return {o['id']:'quiet' if o['id']=='quiet' else 'visit_'+sites[o['id'].removeprefix('visit_')] for o in context['options']}


def model_name(result):
    model=result.get('model')
    return model if isinstance(model,str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,160}',model) else 'unrecorded'


def provenance(model):
    return 'test_fixture' if model.startswith(('test','deterministic-integration-fixture')) else 'unrecorded' if model=='unrecorded' else 'model_decision'

def occupied(state):
    ids=set()
    plans=state.get('plans',[])
    for item in ([plans[-1]] if plans else [])+[state.get('conversation') or {}]:
        if item and (item.get('phase') not in ACTIVE or item.get('release_required')):
            ids.update(i for i in [item.get('actor'),item.get('target'),item.get('initiator'),item.get('partner'),*item.get('speakers',[]),*item.get('economic_pair',[])] if i)
    batches=state.get('routine_batches',[]);batch=batches[-1] if batches else {}
    if batch and batch.get('phase') not in ACTIVE:ids.update(m['actor'] for m in batch['members'])
    return ids

def destinations(observation,actor,policy=None):
    policy=load_policy() if policy is None else policy
    rows={r['id']:r for r in observation.get('residents',[]) if r.get('isPerson') is True}
    row=rows.get(actor)
    if not row or activity_blocker(row):return []
    sites=[]
    for site in observation.get('places',[]):
        if site.get('available') is True and actor in site.get('eligible_actors',[]):
            sites.append({'id':site['id'],'name':site['name'],'position':site.get('position'),'space':site.get('space'),'kind':'public_place'})
    # Bench locations are shared public-map starting knowledge, not claimed sight.
    for site in (observation.get('rest') or {}).get('sites',[]):
        if site.get('loaded') is True:
            sites.append({'id':site['id'],'name':site['name'],'position':site.get('position'),'space':site.get('space'),'kind':'bench_area'})
    result=[]
    for site in sites:
        try:gap=math.dist([row[k] for k in ('x','y','z')],site['position'])
        except (TypeError,ValueError,KeyError):continue
        if same_space(row.get('space'),site.get('space')) is False:continue
        if type(site.get('id')) is not int or site['id']<=0 or any(s['id']==site['id'] for s in result):continue
        if not math.isfinite(gap) or not policy['minimum_distance']<gap<=policy['maximum_distance']:continue
        result.append({**site,'distance':round(gap,1)})
    return result

def goal_context(state,observation,actor,policy=None,opportunity_policy=None,*,bounded=True):
    policy=load_policy() if policy is None else policy
    person=state['people'][str(actor)];row=next(r for r in observation['residents'] if r['id']==actor)
    clock=time_context(observation.get('gameDays'))
    clock['game_days']=observation.get('gameDays') if clock['known'] else None
    weather=observation.get('weather') if isinstance(observation.get('weather'),dict) else {}
    coordinates=[row.get(k) for k in ('x','y','z')]
    own_observation={'position':coordinates if all(type(n) in (int,float) and math.isfinite(n) for n in coordinates) else None,
        'space':{k:copy.deepcopy(row['space'].get(k)) for k in ('cell','interior','world')} if isinstance(row.get('space'),dict) else None,
        'activity':{k:copy.deepcopy(row['activity'].get(k)) for k in ('package_id','scene_id','in_combat','sleep_state')} if isinstance(row.get('activity'),dict) else None,
        'outdoors':row.get('outdoors') if type(row.get('outdoors')) is bool else None,
        'source':'Current native observation of this resident only. Package IDs do not establish work, intentions or perceived events.'}
    sites=destinations(observation,actor,policy)
    options=[{'id':'quiet','effect':'Stay here for a quiet interval. No rest recovery, work, food or social benefit is implied.'}]
    options += [{'id':'visit_'+str(s['id']),'effect':f"Walk to {s['name']} ({s['distance']} game units), a public location. "+
                ('Look for a place to take a break; sitting and recovery need a later decision.' if s['kind']=='bench_area' else 'Look for opportunities there; no supplier, purchase or conversation is guaranteed.')} for s in sites]
    goals=purposeful_options(state,observation,actor,sites,opportunity_policy)
    actions={'quiet':{'family':'quiet','focus':None,'target_id':None,'trigger':'decision'}}
    actions.update({'visit_'+str(s['id']):{'family':'visit_'+s['kind'],'focus':None,'target_id':s['id'],'trigger':'arrival'} for s in sites})
    actions.update(goals['actions']);options.extend(goals['options'])
    context={'actor_id':actor,'actor_identity':{'reference_id':actor,'base_id':row.get('baseId')},
        'policy_version':policy['version'],'policy_id':policy_id(policy),
        'profile':copy.deepcopy(person['profile']),'needs':copy.deepcopy(person['needs']),
        'clock':clock,'own_observed_state':own_observation,
        'weather':{'observation':{k:copy.deepcopy(weather.get(k)) for k in ('id','classification','label')} if weather else None,
            'source':'Current native weather classification; not a forecast or proof of what an indoor resident perceived.'},
        'own_inventory':copy.deepcopy(row.get('inventory',{})),'own_memories':copy.deepcopy(person.get('memories',[])[-5:]),
        'own_commitments':copy.deepcopy(person.get('commitments',[])),
        'previous_goal':copy.deepcopy(person.get('standing_goal')),
        'event':{'kind':'choose_personal_destination','knowledge':'Public place and bench locations are authored shared town-map knowledge. Other people private state is unknown.',
                 'purpose':'Choose a place or quiet interval that fits your needs and experience. Do not walk just to animate the town. Economic decisions remain separate.'},
        'options':options,'destinations':sites,'goal_actions':actions,
        'opportunity_policy':goals['opportunity_policy'],'public_opportunities':goals['public_opportunities']}
    return bounded_goal_context(context) if bounded else context


class ResidentGoals:
    def claim_resident_goals(self,event_id,observation,limit=32):
        self._agency_guard(observation,allow_routines=True)
        if not isinstance(event_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',event_id):raise ValueError('Invalid personal-goal wave')
        if type(limit) is not int or not 1<=limit<=32:raise ValueError('Goal wave limit must be 1 to 32')
        town=self.active.get('town') or {};control=town.get('resident_control') or {}
        if not control.get('enabled') or (observation.get('resident_control') or {}).get('goal_destinations') is not True:
            raise ValueError('Native independent destinations are unavailable')
        waves=town.get('goal_waves',[])
        existing=next((w for w in waves if w['id']==event_id),None)
        if existing:return {'duplicate':True,'wave':copy.deepcopy(existing)}
        if event_id in town.get('goal_claim_ids',[]):return {'duplicate':True,'retired':True}
        if any(w['phase']=='thinking' for w in waves):raise ValueError('A personal-goal wave is already claimed')
        day=native_day(observation);policy=load_policy()
        busy=occupied(self.active);eligible=[]
        for r in observation.get('residents',[]):
            key=str(r['id']);person=self.active['people'].get(key)
            if key not in control['assignments'] or not person or r.get('isPerson') is not True or r['id'] in busy or activity_blocker(r):continue
            if pending_goal_review(self.active,r['id']):continue
            goal=person.get('standing_goal') or {}
            if goal.get('phase')=='travelling' or day<goal.get('next_review_day',0):continue
            eligible.append((goal.get('decided_day',-1),r['id']))
        members=[{'actor':actor,'context':goal_context(self.active,observation,actor,policy)} for _,actor in sorted(set(eligible))[:limit]]
        if not members:return {'empty':True,'model_calls':0}
        now=time.time()
        wave={'id':event_id,'claim_id':secrets.token_hex(12),'session':self.session,'phase':'thinking','day':day,'members':members,
              'claimed_at':now,'deadline_at':now+policy['claim_timeout_seconds'],'policy':policy,'policy_id':policy_id(policy)}
        state=copy.deepcopy(self.active)
        state['town']['goal_claim_ids']=list(dict.fromkeys([*town.get('goal_claim_ids',[]),*(w['id'] for w in waves),event_id]))
        state['town']['goal_waves']=(state['town'].get('goal_waves',[])+[wave])[-16:]
        return {'checkpoint':self._write(state,'independent resident goals claimed before concurrent inference'),'wave':copy.deepcopy(wave)}

    def finish_resident_goals(self,event_id,claim_id,results,observation):
        self._agency_guard(observation,allow_routines=True)
        wave=next((w for w in self.active['town'].get('goal_waves',[]) if w['id']==event_id),None)
        if not wave or wave['phase']!='thinking' or wave['claim_id']!=claim_id or wave['session']!=self.session:raise ValueError('Stale or already resolved personal-goal claim')
        if not isinstance(wave.get('deadline_at'),(int,float)) or time.time()>=wave['deadline_at']:raise ValueError('Personal-goal claim expired; do not replay inference')
        if not isinstance(results,list) or not all(isinstance(r,dict) and type(r.get('actor')) is int for r in results) or len(results)!=len(wave['members']) or {r['actor'] for r in results}!={m['actor'] for m in wave['members']}:raise ValueError('Goal results must cover the claimed residents exactly')
        policy=validate_policy(wave['policy']);now=time.time()
        state=copy.deepcopy(self.active)
        rows={r['id']:r for r in observation.get('residents',[]) if r.get('isPerson') is True};busy=occupied(state);day=native_day(observation)
        if day<wave['day']:raise ValueError('Native time moved backwards within the goal claim')
        receipts=[]
        for member in wave['members']:
            actor=member['actor'];key=str(actor);raw=next(r for r in results if r['actor']==actor).get('result')
            result=raw if isinstance(raw,dict) else {};failure=None;option_families=families(member['context'])
            try:
                if not isinstance(raw,dict):raise ValueError('malformed_result')
                if result.get('failure'):raise ValueError('inference_failed')
                if actor not in rows or actor in busy or key not in state['people'] or key not in state['town']['resident_control']['assignments'] or activity_blocker(rows[actor]):raise ValueError('resident_unavailable')
                claimed_base=member['context'].get('actor_identity',{}).get('base_id')
                if claimed_base is not None and rows[actor].get('baseId')!=claimed_base:raise ValueError('resident_identity_changed')
                decision=validate_decision(result.get('decision'),member['context'])
                current=goal_context(state,observation,actor,policy,member['context'].get('opportunity_policy'),bounded=False)
                validate_decision(decision,current)
                if families(current)[decision['action_id']]!=option_families[decision['action_id']]:raise ValueError('Destination purpose changed')
                action=current['goal_actions'][decision['action_id']]
                target=next((s for s in current['destinations'] if s['id']==action['target_id']),None)
                goal={'id':event_id+'-'+key,'action_id':decision['action_id'],'phase':'travelling' if target else 'review_pending' if action['focus'] else 'quiet',
                      'decided_day':day,'decided_at':now,'next_review_day':day+policy['review_game_minutes']/1440,'target':copy.deepcopy(target),
                      'claimed_day':wave['day'],'policy':copy.deepcopy(policy),'policy_version':policy['version'],'policy_id':wave['policy_id'],
                      'option_count':len(option_families),'option_families':sorted(set(option_families.values())),
                      'action_family':option_families[decision['action_id']],'model':model_name(result),'provenance':provenance(model_name(result)),
                      'focus':action['focus'],'opportunity_policy':copy.deepcopy(current['opportunity_policy']),
                      'source':'Resident decision model selected a standing goal; no economic effect'}
                # Queue preparation can touch existing invitations. Stage it
                # separately so a rejected choice cannot leave a partial goal.
                accepted_state=copy.deepcopy(state) if action['focus'] and target is None else state
                accepted_state['people'][key]['standing_goal']=goal
                assignment=accepted_state['town']['resident_control']['assignments'][key]
                assignment.update(mode='go_to' if target else 'await_decision',target=target['id'] if target else actor,goal_id=goal['id'],source=goal['source'])
                if action['focus'] and target is None:
                    goal['follow_through']=queue_goal_review(accepted_state,goal,actor,observation)
                    if goal['follow_through']['status']=='unavailable':goal['phase']='held'
                state=accepted_state
            except (ValueError,KeyError,TypeError,StopIteration) as error:
                failure=str(error) if str(error) in ('inference_failed','resident_unavailable','resident_identity_changed','malformed_result') else 'stale_or_invalid_choice'
                # Failed inference does not erase the last goal or replay itself.
                person=state['people'].get(key)
                if person is not None:person.setdefault('standing_goal',{'phase':'held'})['next_review_day']=day+policy['review_game_minutes']/1440
            elapsed=result.get('elapsed_seconds');model=model_name(result)
            receipts.append({'actor':actor,'accepted':failure is None,'failure':failure,
                'decision':result.get('decision') if failure is None else None,
                'model':model,'provenance':provenance(model),'claimed_day':wave['day'],'decided_day':day,
                'attempted':result.get('attempted') if type(result.get('attempted')) is bool else None,
                'option_count':len(option_families),'option_families':sorted(set(option_families.values())),
                'chosen_family':option_families[result['decision']['action_id']] if failure is None else None,
                'elapsed_seconds':elapsed if type(elapsed) in (int,float) and math.isfinite(elapsed) and 0<=elapsed<3600 else None,
                'usage':usage_receipt(result.get('usage'))})
        next(w for w in state['town']['goal_waves'] if w['id']==event_id).update(phase='complete',settled_at=now,results=receipts,members=[{'actor':m['actor']} for m in wave['members']])
        return {'checkpoint':self._write(state,'personal destinations selected independently; no inventory or need changes'),'results':receipts}

    def observe_resident_goals(self,observation):
        town=self.active.get('town') or {};waves=town.get('goal_waves',[])
        now=time.time();stale={}
        for w in waves:
            if w['phase']!='thinking':continue
            if w['session']!=self.session:stale[w['id']]='Session changed; claimed inference must not be replayed'
            elif type(w.get('deadline_at')) not in (int,float) or not math.isfinite(w['deadline_at']):stale[w['id']]='Legacy claim has no bounded deadline; inference must not be replayed'
            elif now>=w['deadline_at']:stale[w['id']]='Claim deadline expired; inference must not be replayed'
        native={a['actor']:a for a in (observation.get('resident_control') or {}).get('activities',[])}
        rows={r['id']:r for r in observation.get('residents',[]) if r.get('isPerson') is True}
        sites={s['id']:s for s in observation.get('places',[])+(observation.get('rest') or {}).get('sites',[]) if s.get('available') is True or s.get('loaded') is True}
        completed=[];busy=occupied(self.active);reviewed=[]
        queue={e['id']:e for e in town.get('daily',{}).get('queue',[])}
        for key,person in self.active['people'].items():
            goal=person.get('standing_goal') or {};a=native.get(int(key)) or {}
            follow=goal.get('follow_through') or {};event=queue.get(follow.get('event_id'))
            if follow.get('status')=='pending' and event and event.get('status') not in ('pending','started'):
                reviewed.append((key,event))
            if goal.get('phase')!='travelling' or int(key) in busy or a.get('goal_id')!=goal['id'] or a.get('target')!=(goal.get('target') or {}).get('id'):continue
            row=rows.get(int(key),{});site=sites.get(a.get('target'),{});assignment=town.get('resident_control',{}).get('assignments',{}).get(key,{})
            policy=validate_policy(goal.get('policy',LEGACY_POLICY))
            try:observed_gap=math.dist([row[k] for k in ('x','y','z')],site['position'])
            except (ValueError,TypeError,KeyError):observed_gap=math.inf
            arrived=(a.get('phase')=='arrived' and a.get('ownedPackage') is True and a.get('slot')==assignment.get('slot')
                     and type(a.get('expectedPackage')) is int and a['expectedPackage']>0 and (row.get('activity') or {}).get('package_id')==a['expectedPackage']
                     and same_space(row.get('space'),site.get('space')) is not False
                     and observed_gap<=policy['arrival_distance'] and type(a.get('distance')) in (int,float) and 0<=a['distance']<=policy['arrival_distance'])
            if arrived or a.get('phase')=='failed':completed.append((key,goal,a,arrived))
        if not stale and not completed and not reviewed:return False
        state=copy.deepcopy(self.active);day=native_day(observation)
        for w in state['town'].get('goal_waves',[]):
            if w['id'] in stale:w.update(phase='held',settled_at=now,error=stale[w['id']],members=[{'actor':m['actor']} for m in w['members']])
        for key,event in reviewed:
            goal=state['people'][key]['standing_goal'];goal['follow_through'].update(status=event['status'],outcome=event.get('outcome'),settled_day=day)
            if goal['phase']=='review_pending':goal['phase']='reviewed'
            goal['next_review_day']=day+goal['policy']['review_game_minutes']/1440
        for key,goal,a,arrived in completed:
            policy=validate_policy(goal.get('policy',LEGACY_POLICY))
            elapsed=round(now-goal['decided_at'],3) if type(goal.get('decided_at')) in (int,float) and 0<=now-goal['decided_at'] else None
            game_minutes=round((day-goal['decided_day'])*1440,3) if type(goal.get('decided_day')) in (int,float) and day>=goal['decided_day'] else None
            timing={'settled_day':day,'settled_at':now,'travel_game_minutes':game_minutes,'elapsed_seconds':elapsed,
                    'timing_scope':'Decision commit to observed terminal result, including binding and interruption; not uninterrupted walking time'}
            person=state['people'][key];person['standing_goal'].update(phase='arrived' if arrived else 'held',next_review_day=day+policy['review_game_minutes']/1440,native_receipt=copy.deepcopy(a),**timing)
            person['memories']=(person.get('memories',[])+[{'kind':'standing_goal_arrival' if arrived else 'standing_goal_failed','event_id':goal['id'],'place':goal['target']['id'],'day':day,
                'decided_day':goal.get('decided_day'),'policy_version':policy['version'],'action_family':goal.get('action_family','visit_destination'),
                'model':goal.get('model','unrecorded'),'provenance':goal.get('provenance','unrecorded'),**timing,
                'source':'Native owned destination receipt; no rest, production, trade or conversation implied'}])[-32:]
            assignment=state['town']['resident_control']['assignments'].get(key)
            if assignment is not None:assignment.update(mode='await_decision',target=int(key))
            if arrived:
                person['agency']['next_review_day']=day
                if goal.get('focus'):person['standing_goal']['follow_through']=queue_goal_review(state,person['standing_goal'],int(key),observation)
        self._write(state,'independent destination arrivals settled without inventing economic effects');return True
