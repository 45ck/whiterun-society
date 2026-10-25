"""Finite scenario coordination stored in the same immutable save checkpoints."""
import copy
import re
from paid_work_policy import paid_work_capability, PAID_WORK_BLOCK_REASON

STAGES = [('work',108186,'work_shift',2), ('stock',108149,'stock_review',1),
          ('buyer_meal',108186,'meal_time',5), ('seller_meal',108149,'meal_time',1)]


def event_for(scenario):
    if scenario['status'] != 'running':return None
    name,actor,kind,budget=STAGES[scenario['cursor']]
    return {'id':scenario['id']+'-'+name,'actor':actor,'kind':kind,'max_calls':budget}


def inventories(observation):
    actors={a['id']:a for a in observation.get('residents',[])}
    result={}
    for actor in (108186,108149):
        inv=actors.get(actor,{}).get('inventory',{})
        if any(type(inv.get(k)) is not int or inv[k]<0 for k in ('gold','grain','bread')):
            raise ValueError('Both market residents must have observed inventories')
        result[str(actor)]={k:inv[k] for k in ('gold','grain','bread')}
    return result


class MarketDay:
    def scenario_status(self):
        scenario=self.active.get('market_day') if self.active else None
        return {**copy.deepcopy(scenario),'next_event':event_for(scenario),
                'execution_capability':paid_work_capability()} if scenario else None

    def start_market_day(self, scenario_id, observation):
        self._agency_guard(observation)
        if self.conversation_busy():
            raise ValueError('A conversation owns the participants')
        if not isinstance(scenario_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',scenario_id):
            raise ValueError('Use a short market-day ID')
        prior=self.active.get('market_day')
        if prior and prior['id']==scenario_id:return {'duplicate':True,'scenario':self.scenario_status()}
        for old in self.active.get('market_day_history',[]):
            if old['id']==scenario_id:return {'duplicate':True,'scenario':{**copy.deepcopy(old),'next_event':None}}
        if prior and prior['status']!='complete':raise ValueError('Existing market day requires review')
        if self.agency_busy():raise ValueError('Finish the active resident plan first')
        participants={actor for _,actor,_,_ in STAGES}
        if any(str(actor) not in self.active.get('people',{}) for actor in participants):
            raise ValueError('Initialize every authored market-day participant before starting the scenario')
        if not paid_work_capability()['available']:
            raise ValueError(PAID_WORK_BLOCK_REASON + ': this authored market day requires unavailable paid production; no scenario started')
        baseline=inventories(observation)
        state=copy.deepcopy(self.active)
        if prior:state.setdefault('market_day_history',[]).append(copy.deepcopy(prior))
        state['market_day']={'id':scenario_id,'status':'running','cursor':0,'results':[],
            'baseline':baseline,'initial_counts':{k:len(state.get(k,[])) for k in ('trades','production','consumptions')},
            'max_calls':9,'calls_observed':0,
            'source':'Authored finite sequence of opportunities; residents choose outcomes'}
        return {'checkpoint':self._write(state,'market-day sequence started')}

    def advance_market_day(self, scenario_id, event_id, observation):
        self._agency_guard(observation)
        scenario=self.active.get('market_day')
        if not scenario or scenario['id']!=scenario_id:raise ValueError('Market day does not match this save')
        if any(r['id']==event_id for r in scenario['results']):return {'duplicate':True,'scenario':self.scenario_status()}
        expected=event_for(scenario)
        if not expected or expected['id']!=event_id:raise ValueError('Unexpected market-day stage')
        plan=self.agency_plan()
        if not plan or plan['id']!=event_id or plan['phase'] not in ('complete','held') or plan.get('release_required') or not plan.get('remembered'):
            raise ValueError('Resident stage is not fully settled')
        state=copy.deepcopy(self.active);updated=state['market_day']
        calls=len(plan['decisions'])
        updated['calls_observed']+=calls
        updated['results'].append({'id':event_id,'kind':plan['kind'],'actor':plan['actor'],
            'outcome':plan.get('outcome'),'status':plan['phase'],'model_calls_observed':calls,
            'checkpoint':self.marker})
        if plan['phase']=='held' or calls>expected['max_calls']:
            updated.update(status='held',error='Stage held or exceeded its decision bound; no automatic replay')
        else:
            updated['cursor']+=1
            if updated['cursor']==len(STAGES):
                final=inventories(observation)
                updated.update(status='complete',final_inventory=final,
                    metrics={
                        'gold_before':sum(i['gold'] for i in updated['baseline'].values()),
                        'gold_after':sum(i['gold'] for i in final.values()),
                        **{k:len(state.get(k,[]))-updated['initial_counts'][k] for k in ('trades','production','consumptions')},
                        'hunger':{str(a):state['people'][str(a)]['needs']['hunger'] for a in (108186,108149)}})
        return {'checkpoint':self._write(state,'market-day stage recorded without forcing its outcome')}
