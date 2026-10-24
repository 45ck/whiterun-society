"""Finite cohorts of independent decisions and native travel leases.

Only journeys run concurrently here. Inventory settlement and speech retain
their existing single-event protocol. A cohort is not a claim of a full city.
"""
import copy
import math
import re
import secrets
from decisions import validate_decision
from places import MARKET, market_opportunity


def select_routine_events(state, observation, events, limit=8):
    """Select feasible journeys within the caller's remaining event budget."""
    if type(limit) is not int or not 0<=limit<=8:raise ValueError('Invalid independent-journey capacity')
    if (observation.get('parallel_routines') or {}).get('available') is not True:return []
    actors={r['id']:r for r in observation.get('residents',[])};selected=[];seen=set()
    for event in events:
        actor=event['actor'];native=actors.get(actor);person=state.get('people',{}).get(str(actor),{})
        if len(selected)>=limit:break
        if actor in seen or event['status']!='pending' or event['kind']!='need_review' or not native:continue
        inventory=native.get('inventory',{})
        if (inventory.get('bread')!=0 or type(inventory.get('gold')) is not int or inventory['gold']<3
                or person.get('needs',{}).get('hunger',0)<.6 or not market_opportunity(state,observation,actor)):continue
        selected.append(event);seen.add(actor)
    return selected


class ParallelRoutines:
    def routine_batch(self):
        batches=self.active.get('routine_batches',[]) if self.active else []
        return batches[-1] if batches else None

    def routines_busy(self):
        batch=self.routine_batch()
        return bool(batch and batch['phase'] not in ('complete','held'))

    def begin_routines(self, batch_id, event_ids, observation):
        self._agency_guard(observation)
        if self.agency_busy() or self.conversation_busy():raise ValueError('Finish the existing resident activity')
        if not isinstance(batch_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',batch_id):raise ValueError('Invalid cohort ID')
        if not isinstance(event_ids,list) or not 1<=len(event_ids)<=8 or any(not isinstance(x,str) for x in event_ids) or len(set(event_ids))!=len(event_ids):
            raise ValueError('Supply one to eight distinct daily opportunities')
        for batch in self.active.get('routine_batches',[]):
            if batch['id']==batch_id:
                if [m['event_id'] for m in batch['members']]!=event_ids:raise ValueError('Cohort ID reused')
                return {'duplicate':True,'batch':batch}
        if (observation.get('parallel_routines') or {}).get('available') is not True:raise ValueError('Independent native routing slots unavailable')
        state=copy.deepcopy(self.active);queue=state.get('town',{}).get('daily',{}).get('queue',[])
        actors={r['id']:r for r in observation.get('residents',[])};members=[]
        for slot,event_id in enumerate(event_ids):
            event=next((e for e in queue if e['id']==event_id),None)
            if not event or event['status']!='pending' or event['kind']!='need_review':raise ValueError('A pending daily need opportunity is required')
            actor=event['actor'];person=state['people'][str(actor)];native=actors.get(actor)
            if actor in [m['actor'] for m in members] or not native or not market_opportunity(state,observation,actor):raise ValueError('Resident has no executable public-market journey')
            inventory=native.get('inventory',{})
            if inventory.get('bread')!=0 or type(inventory.get('gold')) is not int or inventory['gold']<3 or person['needs']['hunger']<.6:
                raise ValueError('This cohort requires an unmet affordable food search')
            context={'actor_id':actor,'session':self.session,'profile':copy.deepcopy(person['profile']),
                'event':{'id':event_id,'kind':'food_search','information':'Consider visiting the known public market to seek food. This travel cohort can take you there, but buying food requires a later nearby seller consent decision. You may remain with your ordinary routine instead.'},
                'observed_inventory':copy.deepcopy(inventory),'scenario_state':{'needs':copy.deepcopy(person['needs'])},
                'memories':copy.deepcopy(person['memories'][-8:]),'my_relationships':copy.deepcopy(person.get('relationships',{})),
                'weather':copy.deepcopy(observation.get('weather')),
                'prior_knowledge':'Authored public market location. Other residents private inventories and intentions are unknown.',
                'options':[{'id':'check_market','effect':'Walk to the public market and observe whether Carlotta is nearby. No purchase or hunger relief happens automatically.'},
                           {'id':'defer','effect':'Keep your ordinary routine; do not take this journey now. No resources or needs change.'}]}
            members.append({'event_id':event_id,'actor':actor,'slot':slot,'phase':'thinking','context':context})
            event['status']='started';person['agency'].update(state='deciding',reason='Independent food-search decision',event_id=event_id)
        batch={'id':batch_id,'session':self.session,'phase':'thinking','claim_id':secrets.token_hex(12),'members':members}
        state.setdefault('routine_batches',[]).append(batch)
        return {'checkpoint':self._write(state,'independent resident decisions claimed before inference'),'batch':batch}

    def finish_routines(self, batch_id, claim_id, results, observation):
        self._agency_guard(observation,allow_routines=True)
        batch=self.routine_batch()
        if not batch or (batch['id'],batch['claim_id'],batch['phase'],batch['session'])!=(batch_id,claim_id,'thinking',self.session):
            raise ValueError('Cohort claim is not current')
        if not isinstance(results,list) or len(results)!=len(batch['members']) or any(not isinstance(r,dict) for r in results):raise ValueError('One result per claimed resident is required')
        by_id={r.get('event_id'):r for r in results}
        if len(by_id)!=len(results) or set(by_id)!={m['event_id'] for m in batch['members']}:raise ValueError('Duplicate or missing resident result')
        state=copy.deepcopy(self.active);updated=state['routine_batches'][-1];jobs=[]
        actors={r['id']:r for r in observation.get('residents',[])}
        for member in updated['members']:
            result=by_id[member['event_id']]['result'];decision=validate_decision(result['decision'],member['context'])
            member['result']=copy.deepcopy(result)
            if decision['action_id']=='defer':member.update(phase='complete',outcome='deferred');continue
            actor=member['actor'];native=actors.get(actor)
            if not market_opportunity(state,observation,actor) or not native or native.get('inventory')!=member['context']['observed_inventory']:
                member.update(phase='held',outcome='changed_before_departure');continue
            job={'id':'lane-'+member['event_id'],'actor':actor,'target':MARKET,'target_kind':'place',
                 'slot':member['slot'],'origin':'resident_decision','retain':False,'dynamic':True}
            jobs.append(job);member.update(phase='travelling',command=job)
            state['people'][str(actor)]['agency'].update(state='travelling',reason='Chosen public-market journey in an independent native slot')
        updated['phase']='travelling' if jobs else 'complete'
        if jobs:state['pending']={'id':batch_id,'status':'pending','command':{'id':batch_id,'kind':'parallel_routines','jobs':jobs,'origin_session':self.session}}
        else:self._settle_routines(state,observation)
        return {'checkpoint':self._write(state,'independent choices accepted; concurrent journeys prepared')}

    def hold_routines(self, batch_id, reason, observation):
        self._agency_guard(observation,allow_routines=True)
        batch=self.routine_batch()
        if not batch or batch['id']!=batch_id or batch['phase']!='thinking':raise ValueError('Only an unexecuted decision cohort can be held')
        state=copy.deepcopy(self.active);batch=state['routine_batches'][-1];batch['phase']='held';batch['error']=str(reason)[:200]
        for member in batch['members']:member.update(phase='held',outcome='decision_interrupted')
        self._settle_routines(state,observation)
        return {'checkpoint':self._write(state,'cohort inference held without automatic repeat')}

    def _settle_routines(self,state,observation):
        batch=state['routine_batches'][-1];day=observation.get('gameDays');queue=state['town']['daily']['queue']
        for member in batch['members']:
            person=state['people'][str(member['actor'])];outcome=member.get('outcome','journey_held')
            memory={'event_id':member['event_id'],'kind':outcome,'place':MARKET,'day':day,
                    'source':'Independent native journey receipt' if member.get('receipt') else 'Own decision or interrupted claim'}
            person['memories']=(person['memories']+[memory])[-32:]
            person['agency'].update(state='quiet_interval' if member['phase']=='complete' else 'held',reason='Last independent journey: '+outcome)
            if type(day) in (int,float) and math.isfinite(day):person['agency']['next_review_day']=day+(0 if outcome=='market_seller_observed' else 1/24)
            event=next(e for e in queue if e['id']==member['event_id']);event.update(status=member['phase'],outcome=outcome,settled_day=day)
        batch['settled']=True

    def observe_routines(self,observation):
        batch=self.routine_batch()
        if not batch or batch['phase'] in ('complete','held'):return False
        if batch['session']!=self.session:
            state=copy.deepcopy(self.active);updated=state['routine_batches'][-1];updated.update(phase='held',error='Session changed; do not replay claimed decisions or travel')
            for member in updated['members']:member.update(phase='held',outcome='journey_interrupted_by_load')
            state['pending']=None;self._settle_routines(state,observation);self._write(state,'loaded unfinished cohort held; native leases released by bridge recovery');return True
        if batch['phase']=='thinking':return True
        ack=observation.get('ack') or {}
        if ack.get('id')!=batch['id']:return True
        state=copy.deepcopy(self.active);updated=state['routine_batches'][-1];receipts=ack.get('routines',[])
        if not isinstance(receipts,list):receipts=[]
        release_ok=True
        for member in updated['members']:
            if member['phase']!='travelling':continue
            job=member['command'];matches=[r for r in receipts if isinstance(r,dict) and r.get('id')==job['id']]
            receipt=matches[0] if len(matches)==1 else {};movement=receipt.get('movement') or {};gap=movement.get('distance')
            released=receipt.get('release_verified') is True;release_ok=release_ok and released
            valid=(receipt.get('status')=='applied' and released and receipt.get('slot')==job['slot']
                and movement.get('actor')==job['actor'] and movement.get('target')==MARKET and movement.get('target_kind')=='place'
                and movement.get('aliasesConfirmed') is True and movement.get('hasOwnedPackage') is True
                and movement.get('adapter')=='papyrus-mailbox' and type(gap) in (int,float) and math.isfinite(gap) and 0<=gap<=250)
            member['receipt']=copy.deepcopy(receipt)
            member.update(phase='complete' if valid else 'held',outcome=('market_seller_observed' if receipt.get('seller_nearby') is True else 'market_seller_not_observed') if valid else 'journey_held')
        updated['phase']='complete' if all(m['phase']=='complete' for m in updated['members']) else 'held'
        updated['release_verified']=release_ok;updated['concurrency']=copy.deepcopy(ack.get('concurrency',{}))
        if release_ok:state['pending']=None
        else:state['pending']['status']='held';state['pending']['evidence']=copy.deepcopy(ack)
        self._settle_routines(state,observation);self._write(state,'independent journey receipts settled without inventory effects');return True
