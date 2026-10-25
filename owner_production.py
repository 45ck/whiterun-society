"""Resident-chosen production from an owner's single physical stock account."""
import copy
import math
import time
from enterprises import production_policy
from routing import activity_blocker
from entrepreneurship import learn_bread_recipe
from production import production_receipt_matches
from activity_leases import activity_conflict, work_account_conflict
from economy_catalog import commodity_ids, recipe_ids, recipe_spec, recipe_hash, catalog_hash, native_catalog_matches, require_native_catalog, MAX_STOCK


def owner_work_opportunities(state, observation, actor, *, require_owned=True):
    if activity_conflict(state,actors=(actor,),observation=observation) or work_account_conflict(state,actors=(actor,),observation=observation):return []
    resident=next((r for r in observation.get('residents',[]) if r['id']==actor and r.get('isPerson') is True),None)
    if not resident or activity_blocker(resident):return []
    inventory=resident.get('inventory',{})
    if any(type(inventory.get(k)) is not int or not 0<=inventory[k]<=MAX_STOCK for k in commodity_ids()):return []
    control=next((a for a in (observation.get('resident_control') or {}).get('activities',[]) if a.get('actor')==actor),{})
    package=control.get('expectedPackage')
    if type(package) is not int or package<=0:return []
    if require_owned and not (control.get('ownedPackage') is True and
            (resident.get('activity') or {}).get('package_id')==package):return []
    if any(type(resident.get(k)) not in (int,float) or not math.isfinite(resident[k]) for k in ('x','y','z')):return []
    result=[]
    for key,business in sorted((state.get('town') or {}).get('businesses',{}).items()):
        if (business.get('active',True) is not True or business.get('owner')!=actor or business['custodian']!=actor):continue
        for recipe_id in sorted(set(business.get('capabilities',[])) & set(recipe_ids())):
            if not native_catalog_matches(observation,recipe_id):continue
            try:recipe=recipe_spec(recipe_id);policy=production_policy(business,recipe_id)
            except (ValueError,KeyError,TypeError):continue
            output=next(iter(recipe['outputs']))
            if any(inventory[item]<count for item,count in recipe['inputs'].items()):continue
            if any(inventory[item]>MAX_STOCK-count for item,count in recipe['outputs'].items()):continue
            if inventory[output]>=policy.get('target_output',policy.get('target_bread')):continue
            result.append({'business_id':key,'owner':actor,'revision':business.get('revision',0),
                'recipe_id':recipe_id,'catalog_hash':catalog_hash(),'recipe_hash':recipe_hash(recipe_id),
                'capability_source':'Explicit executable enterprise charter; not inferred personal recipe knowledge',
                'policy':policy,'expected_package':package})
    return result


class OwnerProduction:
    def plan_owner_production(self, observation, plan):
        require_native_catalog(observation,plan.get('own_work_terms',{}).get('recipe_id','bread_recipe'))
        if work_account_conflict(self.active,actors=(plan['actor'],),observation=observation):
            raise ValueError('A reserved economic account cannot start owner production')
        if (observation.get('owner_work_jobs') or {}).get('available') is True:
            return self.delegate_owner_work(plan, observation)
        self._agency_guard(observation)
        if plan is not self.agency_plan() or plan['phase']!='ready_to_self_work':
            raise ValueError('Owner production requires a current resident decision')
        if activity_conflict(self.active,actors=(plan['actor'],),observation=observation):
            raise ValueError('An independent activity owns the producing resident')
        terms=plan['own_work_terms']
        recipe=recipe_spec(terms.get('recipe_id','bread_recipe'))
        if (set(commodity_ids())!={'gold','bread','grain'} or recipe['inputs']!={'grain':1} or recipe['outputs']!={'bread':2}):
            raise ValueError('Legacy owner controller supports only its original complete bread account; use independent catalog work')
        if terms not in owner_work_opportunities(self.active,observation,plan['actor'],require_owned=False):
            raise ValueError('Owner production opportunity changed')
        actor=next(a for a in observation['residents'] if a['id']==plan['actor'])
        hold_id='owner-work-'+plan['id']
        acquisition=plan.get('owner_work_attendance')
        if not acquisition:
            state=copy.deepcopy(self.active)
            state['plans'][-1]['owner_work_attendance']={'id':hold_id,'started_at':time.time()}
            self._write(state,'owner stationary attendance requested before labour or inventory effects')
            return
        if (acquisition.get('id')!=hold_id or type(acquisition.get('started_at')) not in (int,float)
                or not math.isfinite(acquisition['started_at'])):
            raise ValueError('Owner attendance claim is invalid')
        elapsed=time.time()-acquisition['started_at']
        if elapsed<0 or elapsed>30:
            raise ValueError('Owner stationary attendance was not acquired within 30 seconds')
        control=next((a for a in (observation.get('resident_control') or {}).get('activities',[]) if a.get('actor')==plan['actor']),{})
        stationary=(control.get('work_hold_id')==hold_id and control.get('goal_id')==hold_id
            and control.get('mode')=='await_decision' and control.get('target')==plan['actor']
            and control.get('phase')=='work_holding' and control.get('ownedPackage') is True
            and control.get('expectedPackage')==terms['expected_package']
            and (actor.get('activity') or {}).get('package_id')==terms['expected_package']
            and type(control.get('slot')) is int and 0<=control['slot']<128
            and type(control.get('serial')) is int and 1<=control['serial']<=16777215)
        if not stationary:return
        attendance={'id':hold_id,'slot':control['slot'],'serial':control['serial'],
            'source':'Observed self-targeted continuity mailbox and owned package; productive animation unverified'}
        before={'owner':{k:actor['inventory'][k] for k in ('gold','bread','grain')}}
        after=copy.deepcopy(before);after['owner']['grain']-=1;after['owner']['bread']+=2
        command={'id':'produce-'+plan['id'],'kind':'inventory_self_produce','actor':plan['actor'],
            'catalog_hash':require_native_catalog(observation,terms.get('recipe_id','bread_recipe')),
            'recipe_id':terms.get('recipe_id','bread_recipe'),'recipe_hash':recipe_hash(terms.get('recipe_id','bread_recipe')),
            'expected_package':terms['expected_package'],'work_minutes':terms['policy']['work_minutes'],
            'anchor':[actor[k] for k in ('x','y','z')],'attendance':attendance,'before':before,'after':after}
        state=copy.deepcopy(self.active)
        state['pending']={'id':command['id'],'command':command,'status':'pending','evidence':None,
            'business_id':terms['business_id'],'source':'Owner chooses own labour and grain; no wage transfer'}
        state['plans'][-1]['phase']='working'
        self._write(state,'owner work persisted before native labour and recipe effects')

    def observe_owner_production(self, observation):
        pending=self.active['pending'];command=pending['command'];ack=observation.get('ack') or {}
        if pending.get('status')=='held':return
        try:
            catalog_ok=(command.get('catalog_hash')==catalog_hash() and
                command.get('recipe_hash')==recipe_hash(command.get('recipe_id')) and
                native_catalog_matches(observation,command.get('recipe_id')))
        except ValueError:catalog_ok=False
        if not catalog_ok:
            state=copy.deepcopy(self.active);state['pending'].update(status='held',error='Legacy owner intent has no matching resolved catalog proof; do not replay')
            state['plans'][-1].update(phase='held',error=state['pending']['error'])
            self._write(state,'unbound legacy owner intent quarantined without new catalog certification');return
        if ack.get('id')!=command['id']:return
        if not production_receipt_matches(command,ack):
            state=copy.deepcopy(self.active)
            state['pending'].update(status='held',error='Owner receipt catalog or recipe binding is missing or mismatched')
            state['plans'][-1].update(phase='held',error=state['pending']['error'])
            self._write(state,'owner production receipt quarantined without exact catalog and recipe binding');return
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
