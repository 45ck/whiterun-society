"""Resident-chosen production from an owner's single physical stock account."""
import copy
import math
from enterprises import production_policy
from routing import activity_blocker
from entrepreneurship import learn_bread_recipe


def owner_work_opportunities(state, observation, actor):
    resident=next((r for r in observation.get('residents',[]) if r['id']==actor and r.get('isPerson') is True),None)
    if not resident or activity_blocker(resident):return []
    inventory=resident.get('inventory',{})
    if any(type(inventory.get(k)) is not int or inventory[k]<0 for k in ('gold','bread','grain')):return []
    if inventory['grain']<1:return []
    control=next((a for a in (observation.get('resident_control') or {}).get('activities',[]) if a.get('actor')==actor),{})
    package=control.get('expectedPackage')
    if not (control.get('ownedPackage') is True and type(package) is int and package>0 and
            (resident.get('activity') or {}).get('package_id')==package):return []
    if any(type(resident.get(k)) not in (int,float) or not math.isfinite(resident[k]) for k in ('x','y','z')):return []
    result=[]
    for key,business in sorted((state.get('town') or {}).get('businesses',{}).items()):
        if (business.get('active',True) is not True or business.get('owner')!=actor or
                business['custodian']!=actor or 'bread_recipe' not in business['capabilities']):continue
        policy=production_policy(business)
        if inventory['bread']>=policy['target_bread']:continue
        result.append({'business_id':key,'owner':actor,'revision':business.get('revision',0),
            'policy':policy,'expected_package':package})
    return result


class OwnerProduction:
    def plan_owner_production(self, observation, plan):
        self._agency_guard(observation)
        if plan is not self.agency_plan() or plan['phase']!='ready_to_self_work':
            raise ValueError('Owner production requires a current resident decision')
        terms=plan['own_work_terms']
        if terms not in owner_work_opportunities(self.active,observation,plan['actor']):
            raise ValueError('Owner production opportunity changed')
        actor=next(a for a in observation['residents'] if a['id']==plan['actor'])
        before={'owner':{k:actor['inventory'][k] for k in ('gold','bread','grain')}}
        after=copy.deepcopy(before);after['owner']['grain']-=1;after['owner']['bread']+=2
        command={'id':'produce-'+plan['id'],'kind':'inventory_self_produce','actor':plan['actor'],
            'expected_package':terms['expected_package'],'work_minutes':terms['policy']['work_minutes'],
            'anchor':[actor[k] for k in ('x','y','z')],'before':before,'after':after}
        state=copy.deepcopy(self.active)
        state['pending']={'id':command['id'],'command':command,'status':'pending','evidence':None,
            'business_id':terms['business_id'],'source':'Owner chooses own labour and grain; no wage transfer'}
        state['plans'][-1]['phase']='working'
        self._write(state,'owner work persisted before native labour and recipe effects')

    def observe_owner_production(self, observation):
        pending=self.active['pending'];command=pending['command'];ack=observation.get('ack') or {}
        if ack.get('id')!=command['id']:return
        actor=next((a for a in observation.get('residents',[]) if a['id']==command['actor']),None)
        if not actor or any(type(actor.get('inventory',{}).get(k)) is not int for k in ('gold','bread','grain')):return
        actual={'owner':{k:actor['inventory'][k] for k in ('gold','bread','grain')}}
        state=copy.deepcopy(self.active);record=state['pending'];plan=state['plans'][-1]
        record['evidence']={'actual':actual,'ack':ack,'session':self.session}
        if ack.get('status')=='applied' and actual==command['after']:
            record['status']='committed';state.setdefault('production',[]).append(record);state['pending']=None
            plan.update(phase='complete',outcome='owner_work_completed')
            person=state['people'][str(command['actor'])]
            learn_bread_recipe(person,pending['id'])
            person['memories']=(person['memories']+[{'event_id':command['id'],'kind':'owner_work',
                'business_id':record['business_id'],'grain_used':1,'bread_made':2,'gold_paid':0,
                'work_minutes':command['work_minutes'],
                'source':'Native single-account recipe observed; productive animation unverified'}])[-32:]
        elif ack.get('status')=='held' and ack.get('no_effects_issued') is True and actual==command['before']:
            record.update(status='cancelled',outcome='interrupted_before_effects')
            state.setdefault('cancelled_production',[]).append(record);state['pending']=None
            plan.update(phase='complete',outcome='owner_work_interrupted')
        else:
            record['status']='held';plan.update(phase='held',error='Owner work requires reconciliation; do not retry blindly')
        self._write(state,'owner production reconciled against the single native resource account')
