"""Independent actionable reviews; claims are intentions, never physical leases."""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import time
from activity_plan_sources import activity_plan_hash,find_activity_plan,independent_plan_authorized
from resident_identity import resident_identity_status
from resident_goals import occupied,native_day,model_name
from routing import activity_blocker
from rest import rest_opportunities
from owner_production import owner_work_opportunities
from decisions import validate_decision
from context_window import encoded_size

POLICY_PATH=Path(__file__).parent/'config/independent-reviews.json'
TERMINAL={'held','deferred','foreground_review','complete'}


def _current(world, observation):
    return (isinstance(observation,dict) and observation.get('ready') is True
        and observation.get('paused') is not True and observation.get('session')==world.session
        and type(observation.get('checkpoint')) is int and observation['checkpoint']==world.marker
        and type(observation.get('gameDays')) in (int,float)
        and math.isfinite(observation['gameDays']) and observation['gameDays']>=0)


def load_policy():
    value=json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    bounds={'maximum_wave_members':(1,32),'claim_timeout_seconds':(60,3600),'accepted_timeout_seconds':(30,1800),
        'review_game_minutes':(1,120),'maximum_records':(32,16384),'retained_waves':(1,32),'maximum_context_bytes':(2000,14000)}
    if (not isinstance(value,dict) or set(value)!=set(bounds)|{'version'} or not isinstance(value['version'],str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',value['version'])):raise ValueError('Invalid independent review policy')
    for key,(low,high) in bounds.items():
        if type(value[key]) is not int or not low<=value[key]<=high:raise ValueError('Invalid independent review policy '+key)
    return value


def _event(state,key):
    rows=[e for e in (state.get('town') or {}).get('daily',{}).get('queue',[]) if e.get('id')==key]
    return rows[0] if len(rows)==1 else None


def _focus(event):
    return {r.get('focus') for r in event.get('goal_followups',[]) if isinstance(r,dict)} & {'rest','work'}


def independent_review_candidates(state,observation):
    if not isinstance(observation,dict):return []
    busy=occupied(state,observation);records=state.get('independent_reviews',{});result=[]
    actors={r.get('actor') for r in records.values() if r.get('phase') in ('claimed','accepted','delegated')}
    for event in (state.get('town') or {}).get('daily',{}).get('queue',[]):
        actor=event.get('actor')
        if (event.get('kind')!='need_review' or event.get('status')!='pending' or not _focus(event)
                or event.get('independent_review_handed_back') or event.get('id') in records or _event(state,event.get('id')) is None
                or type(actor) is not int or actor in actors or actor in busy):continue
        identity=resident_identity_status(state,observation,actor)
        row=next((r for r in observation.get('residents',[]) if r.get('id')==actor),{})
        if not identity['qualified'] or activity_blocker(row):continue
        actors.add(actor);result.append(copy.deepcopy(event))
    return result


def independent_review_context(state,observation,event,policy=None):
    policy=load_policy() if policy is None else policy;actor=event['actor'];person=state['people'][str(actor)]
    identity=resident_identity_status(state,observation,actor)
    if not identity['qualified'] or actor in occupied(state,observation):raise ValueError('Resident unavailable for independent review')
    row=next(r for r in observation['residents'] if r['id']==actor)
    if activity_blocker(row):raise ValueError('Resident currently physically occupied')
    options=[{'id':'defer','effect':'Postpone this review; no action or benefit.'},
             {'id':'foreground_review','effect':'Wait for a full foreground review, including other activities; no action or benefit now.'}]
    actions={'defer':{'kind':'defer'},'foreground_review':{'kind':'foreground_review'}}
    focuses=_focus(event)
    capability=observation.get('activity_jobs') or {}
    if 'rest' in focuses and capability.get('available') is True and capability.get('capacity')==2:
        for site in rest_opportunities(state,observation,actor):
            key='rest_'+str(site['id']);actions[key]={'kind':'rest','rest_target':site['id']}
            options.append({'id':key,'effect':f"Take a verified 30-minute seated break at {site['name']}; recovery requires native attendance and release."})
    capability=observation.get('owner_work_jobs') or {}
    if 'work' in focuses and capability.get('available') is True:
        for terms in owner_work_opportunities(state,observation,actor,require_owned=False):
            digest=hashlib.sha256(json.dumps(terms,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()[:24]
            key='owner_'+digest;actions[key]={'kind':'owner_production','own_work_terms':copy.deepcopy(terms)}
            options.append({'id':key,'effect':f"Work {terms['policy']['work_minutes']} game minutes on your {terms['recipe_id']} recipe at {terms['business_id']}; use your inputs, keep output, no wage. Attendance and inventory verification required."})
    context={'actor_id':actor,'actor_identity':{'reference_id':actor,'base_id':identity['base_id']},'session':observation['session'],
        'event':{'id':event['id'],'kind':'independent_review','focuses':sorted(focuses),
            'information':'Choose an actionable independent activity or decline. Current foreground encounters belong to other residents. No effect is granted by this choice.'},
        'profile':copy.deepcopy(person['profile']),'needs':copy.deepcopy(person.get('needs',{})),
        'own_inventory':copy.deepcopy(row.get('inventory',{})),'memories':copy.deepcopy(person.get('memories',[])[-3:]),
        'own_commitments':copy.deepcopy(person.get('commitments',[])[:8]),'game_days':native_day(observation),
        'own_observed_state':{k:copy.deepcopy(row.get(k)) for k in ('x','y','z','space','activity')},
        'weather':copy.deepcopy(observation.get('weather')),'options':options}
    if encoded_size(context)>policy['maximum_context_bytes']:
        context['memories']=[];context['own_commitments']=[]
    if encoded_size(context)>policy['maximum_context_bytes']:raise ValueError('Independent review context exceeds configured limit')
    return context,actions


def _settle(state,record,phase,day,reason=None):
    record.update(phase=phase,settled_day=day,settled_at=time.time())
    if reason:record['error']=reason
    event=_event(state,record['event_id'])
    if event and event.get('independent_review')==record['wave_id']:
        event.update(status='pending' if phase=='foreground_review' else 'held' if phase=='held' else 'complete',
            outcome='independent_'+phase,settled_day=day)
        if phase=='foreground_review':event['independent_review_handed_back']=True
    person=state.get('people',{}).get(str(record['actor']))
    if person and phase in ('held','deferred'):
        person.setdefault('agency',{}).update(next_review_day=day+record['policy']['review_game_minutes']/1440)


class IndependentReviews:
    def independent_reviews_status(self):
        state=self.active or {}
        return {'independent_reviews':copy.deepcopy(state.get('independent_reviews',{})),
                'independent_plans':copy.deepcopy(state.get('independent_plans',{})),
                'independent_review_waves':copy.deepcopy(state.get('independent_review_waves',[]))}

    def claim_independent_reviews(self,event_id,observation,limit=32):
        self._agency_guard(observation,allow_routines=True);policy=load_policy()
        if not _current(self,observation):raise ValueError('Current ready independent review observation required')
        if not isinstance(event_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',event_id):raise ValueError('Invalid independent review wave ID')
        if type(limit) is not int or not 1<=limit<=32:raise ValueError('Independent review wave limit must be 1 to 32')
        waves=self.active.get('independent_review_waves',[])
        old=next((w for w in waves if w['id']==event_id),None)
        if old:return {'duplicate':True,'wave':copy.deepcopy(old)}
        if event_id in self.active.get('independent_review_claim_ids',[]):return {'duplicate':True,'retired':True}
        if any(w.get('phase')=='thinking' for w in waves):raise ValueError('Independent review wave already claimed')
        if any(w.get('phase')=='thinking' for w in (self.active.get('town') or {}).get('goal_waves',[])):
            raise ValueError('A personal-goal inference wave is already claimed')
        if len(self.active.get('independent_review_claim_ids',[]))>=policy['maximum_records']:raise ValueError('Independent review claim capacity reached')
        remaining=policy['maximum_records']-len(self.active.get('independent_reviews',{}))
        if remaining<=0:raise ValueError('Independent review record capacity reached')
        members=[]
        for event in independent_review_candidates(self.active,observation)[:min(limit,policy['maximum_wave_members'],remaining)]:
            context,actions=independent_review_context(self.active,observation,event,policy)
            members.append({'actor':event['actor'],'actor_base_id':context['actor_identity']['base_id'],
                'source_event':event['id'],'context':context,'actions':actions})
        if not members:return {'empty':True,'model_calls':0}
        now=time.time();day=native_day(observation);claim_id=secrets.token_hex(12)
        wave={'id':event_id,'claim_id':claim_id,'session':self.session,'phase':'thinking','members':members,
            'day':day,'claimed_at':now,'deadline_at':now+policy['claim_timeout_seconds'],'policy':policy}
        state=copy.deepcopy(self.active)
        state['independent_review_waves']=(waves+[wave])[-policy['retained_waves']:]
        state.setdefault('independent_review_claim_ids',[]).append(event_id)
        for m in members:
            _event(state,m['source_event']).update(status='started',independent_review=event_id)
            state.setdefault('independent_reviews',{})[m['source_event']]={'event_id':m['source_event'],'actor':m['actor'],
                'actor_base_id':m['actor_base_id'],'session':self.session,'wave_id':event_id,'claim_id':claim_id,
                'phase':'claimed','accepted':False,'claimed_day':day,'claimed_at':now,'deadline_at':wave['deadline_at'],
                'policy':copy.deepcopy(policy),'option_count':len(m['context']['options'])}
        checkpoint=self._write(state,'independent review claims persisted; no physical or account leases acquired')
        return {'checkpoint':checkpoint,'wave':copy.deepcopy(wave)}

    def finish_independent_reviews(self,event_id,claim_id,results,observation):
        self._agency_guard(observation,allow_routines=True)
        if not _current(self,observation):raise ValueError('Current ready independent review observation required')
        wave=next((w for w in self.active.get('independent_review_waves',[]) if w['id']==event_id),None)
        if not wave or wave['phase']!='thinking' or wave['claim_id']!=claim_id or wave['session']!=self.session:raise ValueError('Stale independent review claim')
        if time.time()>=wave['deadline_at']:raise ValueError('Independent review claim expired; never replay inference')
        if (not isinstance(results,list) or len(results)!=len(wave['members'])
                or any(not isinstance(r,dict) or type(r.get('actor')) is not int for r in results)
                or {r['actor'] for r in results}!={m['actor'] for m in wave['members']}):raise ValueError('Results must cover claimed residents exactly')
        day=native_day(observation)
        if day<wave['day']:raise ValueError('Game clock moved backwards during review')
        state=copy.deepcopy(self.active);receipts=[]
        for member in wave['members']:
            record=state['independent_reviews'][member['source_event']];raw=next(r['result'] for r in results if r['actor']==member['actor'] and 'result' in r) if any(r['actor']==member['actor'] and 'result' in r for r in results) else None
            failure=None;decision=None;record['result_recorded_at']=time.time()
            try:
                if not isinstance(raw,dict) or raw.get('failure'):raise ValueError('Inference failed or malformed result')
                event=_event(state,record['event_id'])
                if not event or event.get('actor')!=record['actor'] or event.get('status')!='started' or event.get('independent_review')!=event_id:raise ValueError('Source event changed')
                identity=resident_identity_status(state,observation,record['actor'])
                if not identity['qualified'] or identity['base_id']!=record['actor_base_id']:raise ValueError('Resident identity changed')
                decision=validate_decision(raw.get('decision'),member['context'])
                context,actions=independent_review_context(state,observation,event,wave['policy'])
                validate_decision(decision,context);action=decision['action_id']
                if actions.get(action)!=member['actions'].get(action):raise ValueError('Independent activity terms changed')
                record.update(accepted=True,decided_at=time.time(),decided_day=day,action_id=action,decision=copy.deepcopy(decision),model=model_name(raw))
                selected=actions[action];kind=selected['kind']
                if kind in ('defer','foreground_review'):_settle(state,record,'deferred' if kind=='defer' else kind,day)
                else:
                    plan={'id':record['event_id'],'actor':record['actor'],'actor_base_id':record['actor_base_id'],'session':self.session,
                        'kind':'independent_review','phase':'ready_to_rest' if kind=='rest' else 'ready_to_self_work',
                        'independent_review':{'event_id':record['event_id'],'wave_id':event_id,'claim_id':claim_id},
                        **{k:copy.deepcopy(v) for k,v in selected.items() if k!='kind'}}
                    if find_activity_plan(state,plan['id']) is not None:raise ValueError('Source plan identity already exists')
                    state.setdefault('independent_plans',{})[plan['id']]=plan
                    record.update(phase='accepted',plan_id=plan['id'],plan_hash=activity_plan_hash(plan),
                        accepted_deadline_at=time.time()+wave['policy']['accepted_timeout_seconds'])
            except (ValueError,KeyError,TypeError,StopIteration) as error:
                failure=str(error)[:180];record['accepted']=False
                _settle(state,record,'held',day,failure)
            receipt={'actor':member['actor'],'source_event':record['event_id'],'accepted':failure is None,'failure':failure,
                'decision':copy.deepcopy(decision) if failure is None else None,'model':model_name(raw) if isinstance(raw,dict) else 'unknown',
                'attempted':raw.get('attempted') if isinstance(raw,dict) and type(raw.get('attempted')) is bool else None,
                'option_count':record['option_count'],'decided_day':day,'result_recorded_at':record['result_recorded_at']}
            receipts.append(receipt)
        next(w for w in state['independent_review_waves'] if w['id']==event_id).update(phase='complete',results=receipts,
            settled_at=time.time(),members=[{'actor':m['actor'],'source_event':m['source_event']} for m in wave['members']])
        return {'checkpoint':self._write(state,'independent choices persisted without effects or foreground replacement'),'results':receipts}

    def observe_independent_reviews(self,observation):
        if not self.active or self.transition or self.error or self.active.get('pending'):return False
        if not self.active.get('independent_reviews') or not _current(self,observation):return False
        day=native_day(observation);now=time.time();state=copy.deepcopy(self.active);changed=False
        for wave in state.get('independent_review_waves',[]):
            if wave.get('phase')=='thinking':
                for member in wave.get('members',[]):
                    identity=resident_identity_status(state,observation,member['actor'])
                    record=state.get('independent_reviews',{}).get(member['source_event'])
                    if record and record.get('phase')=='claimed' and (not identity['qualified'] or identity['base_id']!=member.get('actor_base_id')):
                        _settle(state,record,'held',day,'Resident identity changed during independent inference');changed=True
            if wave.get('phase')=='thinking' and (wave.get('session')!=self.session or now>=wave.get('deadline_at',0)):
                wave.update(phase='held',error='Session changed or claim deadline expired; no inference replay')
                for record in state.get('independent_reviews',{}).values():
                    if record['wave_id']==wave['id'] and record['phase']=='claimed':_settle(state,record,'held',day,wave['error'])
                wave['members']=[{'actor':m['actor'],'source_event':m['source_event']} for m in wave['members']];changed=True
        for record in state.get('independent_reviews',{}).values():
            if record['phase'] not in ('accepted','delegated'):continue
            plan=find_activity_plan(state,record.get('plan_id'));identity=resident_identity_status(state,observation,record['actor'])
            if record['phase']=='accepted' and (not plan or plan.get('phase')!='delegated') and (record['session']!=self.session or not identity['qualified'] or identity['base_id']!=record['actor_base_id'] or now>=record.get('accepted_deadline_at',0)):
                if plan and plan.get('phase') in ('ready_to_rest','ready_to_self_work'):plan.update(phase='held',outcome='independent_review_held')
                _settle(state,record,'held',day,'Accepted independent intention expired or identity changed');changed=True;continue
            if not plan:continue
            if plan.get('phase')=='delegated' and record['phase']!='delegated':
                record.update(phase='delegated',job_id=plan.get('activity_job') or plan.get('work_job'),
                    job_kind='rest' if plan.get('activity_job') else 'owner_production',delegated_day=day,delegated_at=now);changed=True
            elif plan.get('phase') in ('complete','held'):
                _settle(state,record,plan['phase'],day,plan.get('error'));record['outcome']=plan.get('outcome')
                event=_event(state,record['event_id'])
                if event and plan.get('outcome'):event['outcome']=plan['outcome']
                changed=True
        if changed:self._write(state,'independent review source events reconciled without inferring physical outcomes')
        return changed

    def prepare_independent_review_jobs(self,observation):
        if not self.active or self.transition or self.error or self.active.get('pending'):return False
        if not self.active.get('independent_reviews') or not _current(self,observation):return False
        for record in self.active.get('independent_reviews',{}).values():
            if record.get('phase')!='accepted':continue
            plan=find_activity_plan(self.active,record.get('plan_id'))
            if not plan or plan.get('phase') not in ('ready_to_rest','ready_to_self_work'):continue
            try:
                if not independent_plan_authorized(self.active,plan,plan['phase']):raise ValueError('Independent source authorization changed')
                identity=resident_identity_status(self.active,observation,plan['actor'])
                if plan['session']!=self.session or not identity['qualified'] or identity['base_id']!=plan['actor_base_id']:raise ValueError('Independent resident identity changed')
                if time.time()>=record['accepted_deadline_at']:raise ValueError('Independent accepted intention expired')
                if plan['phase']=='ready_to_rest':self.delegate_rest(plan,observation)
                else:self.delegate_owner_work(plan,observation)
            except ValueError as error:
                state=copy.deepcopy(self.active);updated=state['independent_reviews'][record['event_id']]
                find_activity_plan(state,plan['id']).update(phase='held',outcome='independent_review_held')
                _settle(state,updated,'held',native_day(observation),str(error)[:180])
                self._write(state,'independent delegation held without effects after current eligibility changed')
            return True
        return False
