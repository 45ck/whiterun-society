"""Save-bound paid employment v2; legacy paid commands remain unqualified.

Attendance, physical output, each wage side, and release are separate proofs.
No receipt is reconstructed from a coincidentally matching inventory.
"""
import copy
import hashlib
import json
import math
import time

from activity_leases import activity_conflict, work_account_conflict
from economy_catalog import commodity_ids, recipe_spec, recipe_hash, catalog_hash, apply_recipe, native_catalog_matches, MAX_STOCK
from employment import validate_paid_consent
from enterprises import current_work_terms
from entrepreneurship import learn_recipe
from resident_identity import resident_identity_status, valid_actor_id

IDENTITY = ('protocol','worker','worker_base_id','employer','employer_base_id','slot','session','epoch',
    'business_id','business_revision','recipe_id','catalog_hash','recipe_hash','terms_hash','consent_hash',
    'work_minutes','wage_gold','currency','expected_package','anchor','cell_id','before','after')


def _finite(value):return type(value) in (int,float) and math.isfinite(value)
def _hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def _same(a,b):
    if type(a) is not type(b):return False
    if isinstance(a,dict):return set(a)==set(b) and all(_same(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(_same(x,y) for x,y in zip(a,b))
    return a==b


def paid_identity(job):
    return {'job_id':job.get('job_id',job.get('id')),**{key:copy.deepcopy(job[key]) for key in IDENTITY if key in job}}


def paid_receipt_matches(receipt,job):
    if not isinstance(receipt,dict):return False
    expected=paid_identity(job)
    for key,value in expected.items():
        if key=='anchor':
            other=receipt.get(key)
            if not isinstance(other,list) or len(other)!=3 or any(not _finite(v) for v in other) or other!=value:return False
        elif key not in receipt or not _same(receipt[key],value):return False
    return set(expected)=={'job_id',*IDENTITY}


def _accounts(value):
    return (isinstance(value,dict) and set(value)=={'worker','employer'} and all(
        isinstance(row,dict) and set(row)==set(commodity_ids()) and all(type(n) is int and 0<=n<=MAX_STOCK for n in row.values())
        for row in value.values()))


def _inventory(observation,job):
    result={}
    for role in ('worker','employer'):
        rows=[r for r in observation.get('residents',[]) if isinstance(r,dict) and r.get('id')==job[role]]
        if len(rows)!=1 or rows[0].get('baseId')!=job[role+'_base_id'] or rows[0].get('isPerson') is not True:return None
        result[role]=copy.deepcopy(rows[0].get('inventory'))
    return result if _accounts(result) else None


def paid_stages(command):
    """Catalog-authorized four-leg accounting oracle, with full account snapshots."""
    if (command.get('catalog_hash')!=catalog_hash() or command.get('recipe_hash')!=recipe_hash(command['recipe_id'])
        or not _accounts(command.get('before')) or type(command.get('wage_gold')) is not int or not 1<=command['wage_gold']<=20):
        raise ValueError('Paid contract catalog, accounts or wage invalid')
    from economy_catalog import ECONOMY_CATALOG
    currency=command['currency']
    if not any(item['id']==currency and item['currency'] for item in ECONOMY_CATALOG['commodities']):raise ValueError('Paid currency unavailable')
    recipe=recipe_spec(command['recipe_id']);input_item,input_amount=next(iter(recipe['inputs'].items()));output_item,output_amount=next(iter(recipe['outputs'].items()))
    definitions=[('input','employer',input_item,-input_amount),('output','employer',output_item,output_amount),
                 ('wage_debit','employer',currency,-command['wage_gold']),('wage_credit','worker',currency,command['wage_gold'])]
    stage=copy.deepcopy(command['before']);legs=[]
    for leg,role,item,delta in definitions:
        before=copy.deepcopy(stage);stage[role][item]+=delta
        if not _accounts(stage):raise ValueError('Paid contract exceeds finite stock or account capacity')
        legs.append({'leg':leg,'role':role,'item':item,'amount':abs(delta),'before':before,'after':copy.deepcopy(stage)})
    if not _same(stage,command.get('after')):raise ValueError('Paid after accounts differ from approved recipe and wage')
    return legs


def paid_effect_evidence(command,receipt,actual=None):
    result={'valid':False,'output_verified':None,'wage_debit_verified':None,'wages_verified':None,'inventory_verified':False,'observed_legs':0}
    try:expected=paid_stages(command)
    except (KeyError,TypeError,ValueError):return result
    if (not paid_receipt_matches(receipt,command) or receipt.get('commit_id')!=command.get('commit_id')
        or receipt.get('attendance_token')!=command.get('attendance_token')
        or not isinstance(command.get('attendance_token'),str) or not command['attendance_token']
        or command.get('commit_id')!=command.get('id')):return result
    legs=receipt.get('legs')
    if not isinstance(legs,list) or len(legs)!=4:return result
    observed=0;issued=False;unfinished=False
    for leg,want in zip(legs,expected):
        if not isinstance(leg,dict) or any(not _same(leg.get(k),v) for k,v in want.items()):return result
        if type(leg.get('issued')) is not bool or type(leg.get('observed')) is not bool:return result
        if leg['observed'] and not leg['issued'] or unfinished and (leg['issued'] or leg['observed']):return result
        if leg['issued']:
            issued=True
            if not _finite(leg.get('issued_at')):return result
        if leg['observed']:observed+=1
        else:unfinished=True
    if receipt.get('effects_issued') is not issued:return result
    possible=[command['before'] if observed==0 else expected[observed-1]['after']]
    if observed<4 and legs[observed]['issued']:possible.append(expected[observed]['after'])
    inventory=receipt.get('inventory')
    if not _accounts(inventory) or not any(_same(inventory,stage) for stage in possible):return result
    if actual is not None and not _same(actual,inventory):return result
    output=observed>=2;debit=observed>=3;wages=observed==4
    if any(receipt.get(key) is not value for key,value in [('output_verified',output),('wage_debit_verified',debit),('wages_verified',wages)]):return result
    return {'valid':True,'output_verified':output,'wage_debit_verified':debit,'wages_verified':wages,
        'inventory_verified':wages and _same(inventory,command['after']), 'observed_legs':observed,'legs':copy.deepcopy(legs)}


def paid_attendance_valid(receipt,job,day,now_ms=None):
    if not paid_receipt_matches(receipt,job):return False
    a=receipt.get('attendance') or {};at=time.time()*1000 if now_ms is None else now_ms
    return (receipt.get('phase')=='attendance_verified' and receipt.get('effects_issued') is False
        and isinstance(a.get('token'),str) and 1<=len(a['token'])<=256 and a.get('token_valid') is not False
        and type(a.get('slot')) is int and a['slot']==job['slot']
        and type(a.get('serial')) is int and 1<=a['serial']<=16777215
        and type(a.get('expected_package')) is int and a['expected_package']==job['expected_package']
        and type(a.get('cell_id')) is int and a['cell_id']==job['cell_id']
        and isinstance(a.get('anchor'),list) and len(a['anchor'])==3 and all(_finite(v) for v in a['anchor']) and a['anchor']==job['anchor']
        and type(a.get('samples')) is int and a['samples']>=2
        and _finite(a.get('worked_minutes')) and job['work_minutes']<=a['worked_minutes']<=job['work_minutes']+1
        and _finite(a.get('ready_at')) and _finite(a.get('expires_at')) and a['ready_at']<=at<a['expires_at']
        and _finite(day) and day>=job['created_day']+job['work_minutes']/1440-1e-7)


def _command(job,ack=False):
    return {'id':('paid-work-ack-' if ack else 'paid-work-start-')+job['id'],
            'kind':'paid_work_ack_receipt' if ack else 'paid_work_start',**paid_identity(job)}


def _leased(job):return not (job.get('receipt_acknowledged') is True and job.get('release_verified') is True and job.get('effect_unreconciled') is False)


def _jobs(state):return [*state.get('paid_work_jobs',{}).values(),*state.get('paid_work_orphans',{}).values()]
def _record(state,job):return state['paid_work_orphans'][job['orphan_key']] if job.get('orphan') else state['paid_work_jobs'][job['id']]


class PaidEmployment:
    def paid_employment_status(self):
        state=self.active or {};records=[*state.get('paid_work_jobs',{}).values(),*state.get('paid_work_orphans',{}).values()]
        return {'protocol':2,'schema_version':'paid-employment-v2','epoch':state.get('paid_work_epoch'),
            'capacity':state.get('paid_work_capacity',4),'jobs':[copy.deepcopy(j) for j in records if _leased(j)],
            'history':[copy.deepcopy(j) for j in records if not _leased(j)][-32:],
            'scope':'Stationary worker attendance and staged economic witnesses; animation and workstation use unverified'}

    def _paid_current(self,job,observation):
        try:return self._paid_current_bound(job,observation)
        except (KeyError,TypeError,ValueError):return False

    def _paid_current_bound(self,job,observation):
        native=observation.get('paid_employment') or {}
        return (observation.get('session')==self.session==job['session'] and observation.get('ready') is True
            and native.get('available') is True and type(native.get('protocol')) is int and native['protocol']==2 and native.get('epoch')==job['epoch']
            and job['catalog_hash']==catalog_hash() and job['recipe_hash']==recipe_hash(job['recipe_id'])
            and native_catalog_matches(observation,job['recipe_id'])
            and all(resident_identity_status(self.active,observation,job[r])['qualified']
                and resident_identity_status(self.active,observation,job[r])['base_id']==job[r+'_base_id'] for r in ('worker','employer')))

    def delegate_paid_work(self,plan,observation):
        self._agency_guard(observation)
        if plan is not self.agency_plan() or plan.get('phase')!='ready_to_paid_work':raise ValueError('Paid delegation requires the current released accepted plan')
        release=plan.get('paid_work_release') or {}
        if release.get('id')!='release-'+plan['id'] or release.get('status')!='applied' or release.get('released') is not True or plan.get('release_required'):
            raise ValueError('Paid delegation requires verified original travel release')
        proof=validate_paid_consent(self.active,plan,observation);terms=proof['terms'];native=observation.get('paid_employment') or {}
        capacity=native.get('capacity');epoch=native.get('epoch');worker=terms['worker'];employer=terms['employer']
        if (native.get('available') is not True or type(native.get('protocol')) is not int or native['protocol']!=2
            or not isinstance(epoch,str) or not 1<=len(epoch)<=160 or type(capacity) is not int or not 1<=capacity<=128):
            raise ValueError('Paid protocol 2 native capability unavailable')
        if activity_conflict(self.active,actors=(worker,employer),observation=observation) or work_account_conflict(self.active,actors=(worker,employer),business_ids=(terms['business_id'],),observation=observation):
            raise ValueError('Paid participants or enterprise already reserved')
        existing=[j for j in _jobs(self.active) if _leased(j)]
        native_jobs=[j for field in ('jobs','receipts') for j in native.get(field,[]) if isinstance(j,dict)]
        if len({j.get('job_id',j.get('id')) for j in existing+native_jobs})>=capacity:raise ValueError('Paid capacity is leased')
        actor=next(r for r in observation['residents'] if r['id']==worker)
        slotrow=next((r for r in (observation.get('resident_control') or {}).get('activities',[]) if r.get('actor')==worker),{})
        slot=slotrow.get('slot');package=slotrow.get('expectedPackage');anchor=[actor.get(k) for k in ('x','y','z')]
        cell=(actor.get('space') or {}).get('cell',actor.get('cell_id'));day=observation.get('gameDays')
        if (type(slot) is not int or not 0<=slot<128 or not valid_actor_id(package) or not valid_actor_id(cell)
            or not all(_finite(v) for v in anchor) or not _finite(day) or day<0):raise ValueError('Paid worker stationary slot, anchor, cell or clock unavailable')
        if slot in {j.get('slot') for j in existing+native_jobs}:raise ValueError('Paid worker slot already leased')
        job_id='paid-'+hashlib.sha256((self.session+':'+epoch+':'+plan['id']).encode()).hexdigest()[:24]
        if job_id in self.active.get('paid_work_jobs',{}):raise ValueError('Paid intention already delegated')
        job={'id':job_id,'job_id':job_id,'protocol':2,'worker':worker,'worker_base_id':terms['worker_base_id'],
            'employer':employer,'employer_base_id':terms['employer_base_id'],'slot':slot,'session':self.session,'epoch':epoch,
            'business_id':terms['business_id'],'business_revision':terms['revision'],'recipe_id':terms['recipe_id'],
            'catalog_hash':terms['catalog_hash'],'recipe_hash':terms['recipe_hash'],'terms_hash':proof['terms_hash'],'consent_hash':proof['consent_hash'],
            'work_minutes':terms['policy']['work_minutes'],'wage_gold':terms['policy']['wage_gold'],'currency':terms['currency'],
            'expected_package':package,'anchor':anchor,'cell_id':cell,'source_plan':plan['id'],
            'terms':copy.deepcopy(terms),'consent':copy.deepcopy(proof['consent']),'recipe_definition':recipe_spec(terms['recipe_id']),
            'phase':'prepared','created_day':day,'created_at':time.time(),'release_verified':False,'receipt_acknowledged':False,
            'effect_unreconciled':False,'settlement':{'phase':'not_prepared','output_verified':False,'wage_debit_verified':False,'wages_verified':False,'inventory_verified':False}}
        job['before']=_inventory(observation,job)
        if not self._paid_current(job,observation) or job['before'] is None:raise ValueError('Paid identity, native catalog or full inventory changed')
        job['after']=copy.deepcopy(job['before']);job['after']['employer']=apply_recipe(job['before']['employer'],job['recipe_id'])
        job['after']['employer'][job['currency']]-=job['wage_gold'];job['after']['worker'][job['currency']]+=job['wage_gold'];paid_stages(job)
        state=copy.deepcopy(self.active);state.setdefault('paid_work_jobs',{})[job_id]=job
        state.update(paid_work_epoch=epoch,paid_work_capacity=capacity)
        next(p for p in state['plans'] if p['id']==plan['id']).update(phase='delegated',paid_work_job=job_id,release_required=False)
        for event in (state.get('town') or {}).get('daily',{}).get('queue',[]):
            if event['id']==plan['id']:event.update(status='delegated',paid_work_job=job_id)
        return {'checkpoint':self._write(state,'Paid contract and both account leases persisted before native attendance'),'job_id':job_id}

    @staticmethod
    def _hold_paid(state,job,reason,ambiguous=False):
        job.update(phase='held',error=reason,cancel_requested=True,effect_unreconciled=bool(ambiguous or job.get('effect_unreconciled')))
        plan=next((p for p in state.get('plans',[]) if p['id']==job.get('source_plan')),None)
        if plan:plan.update(phase='held',outcome='paid_employment_held',error=reason,remembered=True)

    def paid_work_pending_command(self):
        if not self.active or self.transition or self.error:return None
        observation=getattr(self,'latest_observation',None) or {}
        for job in _jobs(self.active):
            if not _leased(job) or not self._paid_current(job,observation):continue
            if job.get('receipt_hash') and job.get('release_verified') and not job.get('effect_unreconciled'):return _command(job,True)
            if not job.get('orphan') and job['phase']=='prepared':return _command(job)
        return None

    def paid_work_commit_command(self,session):
        pending=(self.active or {}).get('pending') or {};command=pending.get('command') or {}
        if command.get('kind')!='inventory_paid_work_commit' or pending.get('status')!='pending' or self.transition or self.error:return None
        job=self.active.get('paid_work_jobs',{}).get(pending.get('paid_work_job'));obs=getattr(self,'latest_observation',None) or {}
        if (not job or session!=self.session or not self._paid_current(job,obs) or not paid_receipt_matches(command,job)
            or not _same(command,job.get('commit_command'))):return None
        return copy.deepcopy(command)

    def prepare_paid_work_commit(self,observation):
        if not self.active or self.transition or self.error or self.active.get('pending'):return False
        if any(getattr(self,name,lambda *a:False)(*args) for name,args in [('agency_busy',()),('conversation_busy',()),('agency_command',(self.session,)),('speech_command',(self.session,))]):return False
        if observation.get('checkpoint')!=self.marker or observation.get('inventory_checkpoint',self.marker)!=self.marker:return False
        for original in self.active.get('paid_work_jobs',{}).values():
            if original['phase']!='attendance_verified':continue
            state=copy.deepcopy(self.active);job=state['paid_work_jobs'][original['id']]
            receipt=next((r for r in (observation.get('paid_employment') or {}).get('receipts',[]) if paid_receipt_matches(r,job)),None)
            try:
                plan=next(p for p in state.get('plans',[]) if p['id']==job['source_plan'])
                current_work_terms(state,plan,observation)
                proof=validate_paid_consent(state,plan,observation)
                valid=(self._paid_current(job,observation) and proof['terms_hash']==job['terms_hash'] and proof['consent_hash']==job['consent_hash']
                    and paid_attendance_valid(receipt,job,observation.get('gameDays')) and receipt['attendance']['token']==job['attendance']['token']
                    and _same(_inventory(observation,job),job['before']))
            except (KeyError,ValueError,StopIteration,TypeError):valid=False
            if not valid:
                self._hold_paid(state,job,'Paid attendance permit, consent, identity, charter or reserved stock changed')
                self._write(state,'Paid settlement not prepared; no economic effect authorized');return True
            commit_id='paid-commit-'+job['id'];command={'id':commit_id,'commit_id':commit_id,'kind':'inventory_paid_work_commit',
                **paid_identity(job),'attendance_token':job['attendance']['token']}
            job.update(phase='commit_prepared',commit_command=copy.deepcopy(command),commit_prepared_day=observation['gameDays'],commit_prepared_at=time.time())
            job['settlement'].update(phase='prepared',commit_id=commit_id)
            state['pending']={'id':commit_id,'command':command,'status':'pending','paid_work_job':job['id'],
                'business_id':job['business_id'],'prepared_session':self.session,'evidence':None}
            self._write(state,'Paid four-leg economic intent persisted before any native inventory call');return True
        return False

    def observe_paid_production(self,observation):
        pending=(self.active or {}).get('pending') or {};command=pending.get('command') or {}
        if command.get('kind')!='inventory_paid_work_commit' or pending.get('status')=='held' or self.transition or self.error:return False
        original=self.active.get('paid_work_jobs',{}).get(pending.get('paid_work_job'))
        if not original:
            state=copy.deepcopy(self.active);state['pending'].update(status='held',error='Paid command has no saved admitted job; no replay or settlement')
            self._write(state,'Unmatched paid pending command quarantined');return True
        state=copy.deepcopy(self.active);job=state['paid_work_jobs'][original['id']];record=state['pending'];ack=observation.get('ack') or {}
        if not self._paid_current(job,observation):
            record.update(status='held',error='Paid settlement session, epoch, catalog or actor identity changed; never replay')
            self._hold_paid(state,job,record['error'],True);self._write(state,'Paid pending effects quarantined without balance inference');return True
        if observation.get('checkpoint')!=self.marker or observation.get('inventory_checkpoint',self.marker)!=self.marker:return False
        retained=False
        if ack.get('id')!=command['id']:
            ack=next((r for r in (observation.get('paid_employment') or {}).get('receipts',[])
                if paid_receipt_matches(r,job) and r.get('commit_id')==command['id'] and r.get('phase') in ('effects_verified','complete','held')),None)
            if ack is None:return False
            retained=True
        actual=_inventory(observation,job);proof=paid_effect_evidence(command,ack,actual) if actual is not None else {'valid':False}
        record['evidence']={'actual':copy.deepcopy(actual),'ack':copy.deepcopy(ack),'session':self.session,
            'receipt_source':'retained_native_journal' if retained else 'command_acknowledgement'}
        if proof['valid']:
            job.update(effect_receipt=copy.deepcopy(ack),effect_receipt_hash=_hash(ack),effect_actual=copy.deepcopy(actual))
            job['settlement'].update({k:copy.deepcopy(proof[k]) for k in ('output_verified','wage_debit_verified','wages_verified','inventory_verified','legs')})
            for field in ('output_verified','wage_debit_verified','wages_verified'):
                if proof[field] and field+'_at' not in job:job.update({field+'_at':time.time(),field+'_day':observation.get('gameDays')})
        if (proof['valid'] and proof['inventory_verified'] and ack.get('effects_verified') is True
            and (ack.get('status')=='applied' or retained and ack.get('phase') in ('effects_verified','complete'))):
            record['status']='committed';state.setdefault('production',[]).append(copy.deepcopy(record));state['pending']=None
            job.update(phase='effects_verified',effect_unreconciled=False)
            job['settlement'].update(phase='committed',production_record_id=record['id'])
        elif (paid_receipt_matches(ack,job) and ack.get('commit_id') in (None,command['id'])
                and ack.get('attendance_token')==command['attendance_token']
                and (ack.get('status')=='held' or retained and ack.get('phase')=='held')
                and ack.get('effects_issued') is False and ack.get('no_effects_issued') is True
                and (ack.get('legs')==[] or proof['valid'] and proof['observed_legs']==0 and not any(leg['issued'] for leg in ack['legs']))
                and _same(actual,job['before'])):
            record.update(status='cancelled',outcome='paid_commit_rejected_before_effects');state.setdefault('cancelled_production',[]).append(record);state['pending']=None
            job['settlement']['phase']='cancelled';self._hold_paid(state,job,'Paid commit rejected with exact live no-effect proof')
        else:
            record.update(status='held',error='Paid effect witnesses incomplete, invalid or partial; do not retry')
            job['settlement']['phase']='held';self._hold_paid(state,job,record['error'],True)
        self._write(state,'Paid economic witnesses recorded separately from contract completion and learning');return True

    def _complete_paid(self,state,job,observation):
        if job.get('completed_at') is not None:return
        job.update(phase='complete',outcome='paid_employment_completed',completed_at=time.time(),completed_day=observation.get('gameDays'),effect_unreconciled=False)
        plan=next((p for p in state.get('plans',[]) if p['id']==job['source_plan']),None)
        if plan:plan.update(phase='complete',outcome='paid_employment_completed',remembered=True,release_required=False)
        for event in (state.get('town') or {}).get('daily',{}).get('queue',[]):
            if event['id']==job['source_plan']:event.update(status='complete',outcome='paid_employment_completed')
        business=(state.get('town') or {}).get('businesses',{}).get(job['business_id'],{})
        for contract in business.get('contracts',[]):
            if contract['id']==job['source_plan']:contract.update(status='completed',outcome='paid_employment_completed',paid_work_job=job['id'],production_id=job['settlement']['commit_id'])
        if job['worker'] not in business.setdefault('workers',[]):business['workers'].append(job['worker'])
        learn_recipe(state['people'][str(job['worker'])],job['settlement']['commit_id'],job['recipe_id'])
        for role,other in [('worker','employer'),('employer','worker')]:
            person=state['people'][str(job[role])]
            memory={'event_id':job['id'],'kind':'paid_employment_'+role,'other':job[other],'recipe_id':job['recipe_id'],
                'business_id':job['business_id'],'currency':job['currency'],'wage':job['wage_gold'],
                'source':'Witnessed paid employment v2 economic effects and released worker attendance'}
            person['memories']=(person.get('memories',[])+[memory])[-32:]

    def observe_paid_employment(self,observation):
        if not self.active or self.transition or self.error or self.active.get('pending'):return False
        native=observation.get('paid_employment') or {};ack=observation.get('ack') or {};day=observation.get('gameDays')
        for original in _jobs(self.active):
            if not _leased(original):continue
            state=copy.deepcopy(self.active);job=_record(state,original)
            if not self._paid_current(job,observation):
                if job.get('reset_held'):continue
                job['reset_held']=True;self._hold_paid(state,job,'Paid native session, epoch, identity or catalog no longer current',True)
                self._write(state,'Paid task held across identity or native reset; no adoption or replay');return True
            if paid_receipt_matches(ack,job) and ack.get('id')==_command(job,True)['id'] and ack.get('status')=='applied' and ack.get('acknowledged') is True and job.get('release_verified') and not job.get('effect_unreconciled'):
                job['receipt_acknowledged']=True;self._write(state,'Paid released terminal receipt acknowledged; both accounts freed');return True
            receipt=next((r for r in native.get('receipts',[]) if paid_receipt_matches(r,job)),None)
            if job.get('orphan'):
                if (receipt and receipt.get('release_verified') is True and not job.get('release_verified')
                    and not job.get('effect_unreconciled') and receipt.get('effects_issued') is False and receipt.get('legs')==[]):
                    job.update(release_verified=True,receipt=copy.deepcopy(receipt),receipt_hash=_hash(receipt))
                    self._write(state,'Exact no-effect orphan cleanup retained without adopting paid work');return True
                continue  # Orphans may only acknowledge exact no-effect cleanup, never adopt work.
            if receipt and receipt.get('phase')=='attendance_verified' and job['phase'] in ('prepared','working'):
                if paid_attendance_valid(receipt,job,day):
                    job.update(phase='attendance_verified',attendance=copy.deepcopy(receipt['attendance']),attendance_receipt=copy.deepcopy(receipt),
                        attendance_receipt_hash=_hash(receipt),attendance_verified_day=day,attendance_verified_at=time.time())
                else:self._hold_paid(state,job,'Paid attendance proof incomplete or expired')
                self._write(state,'Paid stationary attendance receipt saved; no output or wages credited');return True
            if receipt and receipt.get('phase') in ('complete','held') and _hash(receipt)!=job.get('receipt_hash'):
                job.update(receipt=copy.deepcopy(receipt),receipt_hash=_hash(receipt),release_verified=receipt.get('release_verified') is True)
                if job['release_verified']:job.update(release_verified_at=time.time(),release_verified_day=day)
                proof=paid_effect_evidence(job.get('commit_command',{}),receipt,job.get('effect_actual'))
                try:
                    plan=next(p for p in state.get('plans',[]) if p['id']==job['source_plan'])
                    consent=validate_paid_consent(state,plan,observation)
                    unchanged=consent['terms_hash']==job['terms_hash'] and consent['consent_hash']==job['consent_hash']
                except (ValueError,KeyError,TypeError,StopIteration):unchanged=False
                if (unchanged and job['settlement'].get('phase')=='committed' and proof['valid'] and proof['inventory_verified'] and job['release_verified']):
                    self._complete_paid(state,job,observation)
                else:self._hold_paid(state,job,receipt.get('error') or 'Paid task ended without fully witnessed settlement and release',receipt.get('effects_issued') is not False)
                self._write(state,'Paid terminal cleanup recorded without inferring economic effects');return True
            if job['phase']=='prepared' and paid_receipt_matches(ack,job) and ack.get('id')==_command(job)['id']:
                if ack.get('status')=='applied' and ack.get('accepted') is True:
                    job.update(phase='working',accepted_at=time.time(),accepted_day=day)
                else:self._hold_paid(state,job,'Paid native attendance admission rejected',ack.get('effects_issued') is not False)
                self._write(state,'Paid native admission acknowledgement retained');return True
            if job['phase']=='prepared' and ack.get('id')==_command(job)['id']:
                self._hold_paid(state,job,'Paid start acknowledgement lacks its exact immutable identity',True)
                self._write(state,'Unbound paid admission acknowledgement held without repeated start');return True
        for receipt in [*native.get('jobs',[]),*native.get('receipts',[])]:
            if (not isinstance(receipt,dict) or not all(valid_actor_id(receipt.get(r)) for r in ('worker','employer'))
                or any(not isinstance(receipt.get(k),str) or not 1<=len(receipt[k])<=160 for k in ('job_id','session','epoch'))):continue
            if any(paid_receipt_matches(receipt,j) for j in _jobs(self.active)):continue
            identity=paid_identity(receipt)
            try:key=_hash(identity)
            except (TypeError,ValueError):continue
            if key in self.active.get('paid_work_orphans',{}):continue
            state=copy.deepcopy(self.active)
            no_effects=receipt.get('effects_issued') is False and receipt.get('legs')==[]
            job={**identity,'id':receipt['job_id'],'orphan':True,'orphan_key':key,'received_session':self.session,
                'phase':'held','error':'Native paid journal has no matching saved contract; no work or learning adopted',
                'cancel_requested':True,'release_verified':receipt.get('release_verified') is True,'receipt_acknowledged':False,
                'effect_unreconciled':not no_effects,'receipt':copy.deepcopy(receipt),'receipt_hash':_hash(receipt),
                'settlement':{'phase':'not_admitted','output_verified':None,'wage_debit_verified':None,'wages_verified':None,'inventory_verified':False}}
            state.setdefault('paid_work_orphans',{})[key]=job
            self._write(state,'Unknown native paid job durably quarantined after rollback; no economic credit');return True
        return False
