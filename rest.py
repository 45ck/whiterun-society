"""Seated breaks with native attendance; recovery rates are authored gameplay."""
import copy
import math

FATIGUE_PER_GAME_HOUR = .025
BENCHES = {0x8f15c,0xe6c6c,0xe6c6b,0xe6c6a,0x8f15d,0x506f7,0x506f6,0x506f5,0x8f15b}


def rest_opportunities(state, observation, actor):
    person=state.get('people',{}).get(str(actor),{})
    sensor=(observation.get('rest') or {})
    senses=sensor.get('sensors',{}).get(str(actor),{})
    resident=next((r for r in observation.get('residents',[]) if r['id']==actor and r.get('isPerson') is True),None)
    if not resident or sensor.get('available') is not True or senses.get('sit_available') is not True or senses.get('furniture_reference_available') is not True or person.get('commitments'):
        return []
    result=[]
    for site in sensor.get('sites',[]):
        if site.get('id') not in BENCHES or site.get('loaded') is not True or site.get('occupancy_known') is not True:
            continue
        own_seat=senses.get('sit_state')==3 and senses.get('furniture')==site['id']
        if site.get('occupied') is not False and not own_seat:continue
        try:gap=math.dist([resident[k] for k in ('x','y','z')],site['position'])
        except (KeyError,TypeError,ValueError):continue
        if math.isfinite(gap) and gap<=5000:result.append({**site,'distance':gap})
    return sorted(result,key=lambda s:(s['distance'],s['id']))


class Rest:
    def plan_rest(self, observation, plan):
        self._agency_guard(observation)
        if plan is not self.agency_plan() or plan['phase']!='ready_to_rest':
            raise ValueError('Rest requires a current resident decision')
        if plan['rest_target'] not in [s['id'] for s in rest_opportunities(self.active,observation,plan['actor'])]:
            raise ValueError('The selected bench is no longer available')
        command={'id':'rest-'+plan['id'],'kind':'rest_at_bench','actor':plan['actor'],'target':plan['rest_target'],'rest_minutes':30}
        state=copy.deepcopy(self.active)
        state['pending']={'id':command['id'],'command':command,'status':'pending','evidence':None}
        state['plans'][-1]['phase']='resting'
        self._write(state,'seated break intent persisted before native travel and attendance')

    def observe_rest(self, observation):
        pending=self.active['pending'];command=pending['command'];ack=observation.get('ack') or {}
        if ack.get('id')!=pending['id']:return
        evidence=ack.get('rest') or {};minutes=evidence.get('rested_minutes');day=observation.get('gameDays')
        valid=(ack.get('status')=='applied' and evidence.get('actor')==command['actor'] and evidence.get('target')==command['target']
            and evidence.get('release_verified') is True and evidence.get('exact_furniture_verified') is True
            and type(evidence.get('seated_samples')) is int and evidence['seated_samples']>=2
            and type(minutes) in (int,float) and math.isfinite(minutes) and 30<=minutes<=31
            and type(day) in (int,float) and math.isfinite(day) and day>=0)
        state=copy.deepcopy(self.active);record=state['pending']
        # Invalid non-finite telemetry cannot be written into a JSON checkpoint.
        def finite(value):
            if isinstance(value,float) and not math.isfinite(value):return None
            if isinstance(value,dict):return {k:finite(v) for k,v in value.items()}
            if isinstance(value,list):return [finite(v) for v in value]
            return value
        record['evidence']=finite(copy.deepcopy(ack))
        if not valid:
            record['status']='held';state['plans'][-1].update(phase='held',error='Rest attendance or release was not verified; no recovery applied')
            self._write(state,'unverified seated break held without fatigue recovery');return
        person=state['people'][str(command['actor'])]
        resident=state.get('town',{}).get('residents',{}).get(str(command['actor']),{})
        baseline=max(person.get('needs_clock',resident.get('observed_game_day',day)),person.get('fatigue_clock',0))
        if day<baseline:
            record['status']='held';state['plans'][-1].update(phase='held',error='Rest clock predates resident needs')
            self._write(state,'rest clock mismatch held without recovery');return
        before=min(1,person['needs']['fatigue']+(day-baseline)*24*FATIGUE_PER_GAME_HOUR)
        person['needs']['fatigue']=round(max(0,before-.35),6);person['fatigue_clock']=day
        record.update(status='committed',fatigue_before=before,fatigue_after=person['needs']['fatigue'])
        state.setdefault('rests',[]).append(copy.deepcopy(record));state['pending']=None
        person['memories']=(person['memories']+[{'event_id':command['id'],'kind':'rested_at_bench','bench':command['target'],
            'minutes':minutes,'fatigue_before':before,'fatigue_after':person['needs']['fatigue'],
            'source':'Native sitting state, exact furniture, owned package and elapsed game time; authored fatigue recovery'}])[-32:]
        state['plans'][-1].update(phase='complete',outcome='rested_at_bench')
        self._write(state,'native seated attendance and task release verified; fatigue and memory updated')
