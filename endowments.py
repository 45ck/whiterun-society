"""Finite reviewed resource scenarios with bound arm/delivery journals.

External imports are never earned income. A held delivery keeps its reservation;
matching inventory alone is never evidence that this delivery executed.
"""
import copy
import hashlib
import json
from activity_leases import activity_conflict, work_account_conflict
from economy_catalog import commodity_ids, require_native_catalog, catalog_hash, MAX_STOCK
from resource_manifest import load_manifest, manifest_hash, select_grant, validate_manifest

IDENTITY=('grant_id','source','manifest_hash','catalog_hash','actor','actor_base_id',
          'origin_session','delivery_epoch','selector_id','grant_hash','grant','before','after')


def _integer(value):return type(value) is int and 0<=value<=MAX_STOCK

def _text(value):return isinstance(value,str) and 0<len(value)<=160 and all(ord(c)>=32 for c in value)


def _same(first,second):
    try:return json.dumps(first,sort_keys=True,allow_nan=False)==json.dumps(second,sort_keys=True,allow_nan=False)
    except (TypeError,ValueError):return False


class StaleAccountingObservation(ValueError):
    """A checkpoint presentation lag cannot prove delivery or permanent failure."""


def observed_recipient(observation,actor,expected_base=None):
    """Neither observation channel may silently overwrite conflicting identity."""
    rows=[];stale=False
    for field in ('residents','inventory_observations'):
        source=observation.get(field,[])
        if not isinstance(source,list):raise ValueError('Invalid resource inventory observation')
        selected=[r for r in source if isinstance(r,dict) and r.get('id')==actor]
        if len(selected)>1:raise ValueError('Duplicate resource recipient observations')
        if selected and field=='inventory_observations' and observation.get('inventory_checkpoint')!=observation.get('checkpoint'):
            stale=True
        rows.extend(selected)
    if not rows:raise ValueError('Resource recipient is not observed')
    keys=set(commodity_ids());result=[]
    for row in rows:
        base=row.get('baseId');stock=row.get('inventory')
        if (row.get('isPerson') is not True or row.get('isChild') is True or row.get('isDead') is True
            or type(base) is not int or not 0<base<=0xffffffff
            or 'session' in row and row['session']!=observation.get('session')
            or not isinstance(stock,dict) or set(stock)!=keys or not all(_integer(v) for v in stock.values())):
            raise ValueError('Resource delivery requires a classified adult, observed base identity and complete inventory')
        if expected_base is not None and base!=expected_base:raise ValueError('Resource recipient base identity changed')
        result.append((base,stock))
    if any(row[0]!=result[0][0] for row in result[1:]):raise ValueError('Conflicting resource recipient base identity')
    if stale:raise StaleAccountingObservation('Accounting inventory checkpoint is stale')
    if any(not _same(row,result[0]) for row in result[1:]):raise ValueError('Conflicting resource recipient identity or inventory')
    return result[0][0],copy.deepcopy(result[0][1])


def inventory(observation,actor):return observed_recipient(observation,actor)[1]


def _native(observation,manifest,digest):
    require_native_catalog(observation)
    status=observation.get('resource_import') or {}
    if (status.get('available') is not True or type(status.get('protocol')) is not int or status['protocol']!=2
        or not _text(status.get('epoch')) or status.get('manifest_hash')!=digest
        or status.get('catalog_hash')!=manifest['catalog_hash']):
        raise ValueError('Matching resource import protocol, epoch and reviewed manifest are required')
    return status['epoch']


def _program_valid(program):
    manifest=validate_manifest(program['manifest']);digest=manifest_hash(manifest)
    if program.get('protocol')!=2 or program.get('id')!=manifest['id'] or program.get('manifest_hash')!=digest:
        raise ValueError('Frozen resource program identity is invalid')
    keys=set(manifest['capacity'])
    for field in ('capacity','available','reserved','delivered','remaining'):
        values=program.get(field)
        if not isinstance(values,dict) or set(values)!=keys or not all(_integer(v) for v in values.values()):
            raise ValueError('Resource pool accounting is invalid')
    if program['capacity']!=manifest['capacity'] or any(
            program['capacity'][k]!=program['available'][k]+program['reserved'][k]+program['delivered'][k]
            or program['remaining'][k]!=program['capacity'][k]-program['delivered'][k] for k in keys):
        raise ValueError('Resource capacity conservation failed')
    deliveries=program.get('deliveries');claims=program.get('recipient_claims');grants=program.get('grants')
    if not all(isinstance(value,dict) for value in (deliveries,claims,grants)):
        raise ValueError('Resource delivery journal is missing')
    reserved={k:0 for k in keys};delivered=reserved.copy();expected_claims={};expected_grants={}
    for grant_id,record in deliveries.items():
        if not isinstance(record,dict):raise ValueError('Resource journal record is invalid')
        command=record.get('command') or {};actor=command.get('actor');base=command.get('actor_base_id')
        if type(actor) is not int or actor<=0 or type(base) is not int or base<=0:
            raise ValueError('Resource journal recipient is invalid')
        selection=select_grant(manifest,actor,base)
        if (record.get('id')!=grant_id or command.get('grant_id')!=grant_id or record.get('actor')!=actor
            or record.get('actor_base_id')!=base or command.get('source')!=manifest['id']
            or command.get('manifest_hash')!=digest or command.get('catalog_hash')!=manifest['catalog_hash']
            or any(not _same(command.get(k),selection[k]) for k in ('selector_id','grant_hash','grant'))
            or not _same(record.get('reservation'),selection['grant'])
            or record.get('status') not in ('pending','held','committed') or str(actor) in expected_claims):
            raise ValueError('Resource journal identity or reservation is invalid')
        expected_claims[str(actor)]=grant_id
        totals=delivered if record['status']=='committed' else reserved
        for key in keys:totals[key]+=selection['grant'][key]
        if record['status']=='committed':expected_grants[str(actor)]=record
    if (not _same(claims,expected_claims) or not _same(grants,expected_grants)
        or reserved!=program['reserved'] or delivered!=program['delivered']):
        raise ValueError('Resource journal does not substantiate pool accounting')
    return manifest,digest


def _safe_ack(ack):
    result={}
    for key in ('id','protocol','status','phase','permit','error',*IDENTITY):
        value=ack.get(key)
        if type(value) is int:result[key]=value
        elif isinstance(value,str):result[key]=value[:240]
        elif key in ('grant','before','after') and isinstance(value,dict):
            result[key]={k:v for k,v in value.items() if k in commodity_ids() and _integer(v)}
    for key in ('accepted','effects_issued','no_effects_issued'):
        if type(ack.get(key)) is bool or ack.get(key) is None:result[key]=ack.get(key)
    if isinstance(ack.get('inventory'),dict):result['inventory']={k:v for k,v in ack['inventory'].items() if k in commodity_ids() and _integer(v)}
    result['legs']=[]
    for row in ack.get('legs',[])[:64] if isinstance(ack.get('legs'),list) else []:
        if not isinstance(row,dict) or row.get('item') not in commodity_ids():continue
        leg={'item':row['item']}
        if _integer(row.get('amount')):leg['amount']=row['amount']
        for key in ('issued','observed'):
            if type(row.get(key)) is bool:leg[key]=row[key]
        result['legs'].append(leg)
    return result


def _receipt_matches(command,ack):
    return (type(ack.get('protocol')) is int and ack['protocol']==2 and ack.get('id')==command.get('id')
        and all(key in ack and key in command and _same(ack[key],command[key]) for key in IDENTITY))


def _legs_complete(command,ack):
    expected={k:v for k,v in command['grant'].items() if v>0};legs=ack.get('legs')
    if not isinstance(legs,list) or len(legs)!=len(expected):return False
    seen=set()
    for row in legs:
        if (not isinstance(row,dict) or set(row)!={'item','amount','issued','observed'}
            or row.get('item') not in expected or row['item'] in seen or type(row.get('amount')) is not int
            or row['amount']!=expected[row['item']] or row.get('issued') is not True or row.get('observed') is not True):return False
        seen.add(row['item'])
    return True


def _armed(record):
    command=record.get('command') or {};arm=record.get('arm_receipt') or {}
    expected={**command,'phase':'arm','id':command.get('grant_id','')+'-arm'}
    return (_receipt_matches(expected,arm) and arm.get('phase')=='armed' and arm.get('status')=='applied'
        and arm.get('accepted') is True and arm.get('effects_issued') is False and arm.get('no_effects_issued') is True
        and arm.get('legs')==[] and _same(arm.get('inventory'),command.get('before')) and _text(command.get('permit')) and arm.get('permit')==command['permit'])


class Endowments:
    def plan_endowment(self,actor,observation,scenario_id,scenario_hash):
        if type(actor) is not int or not 0<actor<=0xffffffff:raise ValueError('Initialize a valid resident before assigning resources')
        town=(self.active or {}).get('town')
        if not town or str(actor) not in town['residents']:raise ValueError('Initialize the resident before assigning resources')
        program=town.get('resource_program')
        if program and program.get('protocol')!=2:raise ValueError('Legacy resource programs are historical only; no new allocations or implicit migration')
        if program:
            _program_valid(program)
            if scenario_id!=program['id'] or scenario_hash!=program['manifest_hash']:raise ValueError('Resource scenario differs from the frozen program')
            previous=program.get('recipient_claims',{}).get(str(actor))
            if previous:
                return {'duplicate':True,'grant':copy.deepcopy(program['deliveries'][previous])}
        self._agency_guard(observation)
        if self.agency_busy() or self.conversation_busy():raise ValueError('Finish the active resident activity first')
        if activity_conflict(self.active,actors=(actor,),observation=observation):raise ValueError('An independent activity owns the resource recipient')
        if work_account_conflict(self.active,actors=(actor,),observation=observation):raise ValueError('The resource recipient inventory account is reserved')
        manifest=load_manifest();digest=manifest_hash(manifest)
        if scenario_id!=manifest['id'] or scenario_hash!=digest:raise ValueError('Explicit reviewed resource scenario ID and hash are required')
        if program and (program['manifest_hash']!=digest or not _same(program['manifest'],manifest)):
            raise ValueError('Reviewed resource manifest changed; existing source pool cannot be reset')
        epoch=_native(observation,manifest,digest);base,before=observed_recipient(observation,actor)
        if any(before[k]>manifest['max_recipient_stock'] for k in before):raise ValueError('Recipient exceeds the reviewed scenario stock limit')
        selection=select_grant(manifest,actor,base);grant=selection['grant']
        after={k:before[k]+grant[k] for k in before}
        if any(v>MAX_STOCK for v in after.values()):raise ValueError('Resource delivery would overflow inventory')
        state=copy.deepcopy(self.active);zero={k:0 for k in grant}
        program=state['town'].setdefault('resource_program',{'protocol':2,'id':manifest['id'],
            'manifest':copy.deepcopy(manifest),'manifest_hash':digest,'capacity':copy.deepcopy(manifest['capacity']),
            'available':copy.deepcopy(manifest['capacity']),'reserved':zero.copy(),'delivered':zero.copy(),
            'remaining':copy.deepcopy(manifest['capacity']),'grants':{},'deliveries':{},'recipient_claims':{},
            'source':'Explicit finite external resources; not wages, sales, or production'})
        _program_valid(program)
        if any(program['available'][k]<grant[k] for k in grant):raise ValueError('Resource source pool is exhausted')
        grant_id='resource-'+hashlib.sha256((digest+':'+str(actor)+':'+str(base)).encode()).hexdigest()[:40]
        command={'id':grant_id+'-arm','kind':'inventory_endowment','protocol':2,'phase':'arm',
            'grant_id':grant_id,'source':manifest['id'],'manifest_hash':digest,'catalog_hash':manifest['catalog_hash'],
            'actor':actor,'actor_base_id':base,'origin_session':self.session,'delivery_epoch':epoch,
            **selection,'before':before,'after':after}
        record={'id':grant_id,'actor':actor,'actor_base_id':base,'status':'pending','phase':'arm',
            'command':command,'reservation':copy.deepcopy(grant),'evidence':None,'source':program['source']}
        for key,amount in grant.items():program['available'][key]-=amount;program['reserved'][key]+=amount
        program['recipient_claims'][str(actor)]=grant_id;program['deliveries'][grant_id]=copy.deepcopy(record)
        state['pending']=copy.deepcopy(record)
        return {'checkpoint':self._write(state,'finite resource reservation bound before native arm'),
                'grant':copy.deepcopy(grant),'grant_id':grant_id,'scenario_id':manifest['id'],'scenario_hash':digest}

    def _hold_endowment(self,error,observation,ack=None):
        if self.active['pending'].get('status')=='held':return
        state=copy.deepcopy(self.active);record=state['pending'];record.update(status='held',phase='held',error=str(error)[:240])
        if ack is not None:record['evidence']={'ack':_safe_ack(ack),'session':observation.get('session')}
        program=(state.get('town') or {}).get('resource_program') or {}
        grant_id=record.get('command',{}).get('grant_id')
        if program.get('protocol')==2 and grant_id in program.get('deliveries',{}):program['deliveries'][grant_id]=copy.deepcopy(record)
        self._write(state,'resource delivery held with reservation retained; no replay or completed import credit')

    def endowment_pending_command(self,session):
        record=(self.active or {}).get('pending') or {};command=record.get('command') or {}
        if (record.get('status')!='pending' or command.get('protocol')!=2 or command.get('origin_session')!=session
            or command.get('catalog_hash')!=catalog_hash() or command.get('phase')=='deliver' and not _armed(record)):return None
        return {**command,'session':session,'checkpoint':self.marker}

    def observe_endowment(self,observation):
        pending=self.active['pending'];command=pending.get('command') or {};ack=observation.get('ack') or {}
        if pending.get('status')=='held':return
        try:
            if command.get('protocol')!=2:raise ValueError('Unresolved legacy resource import cannot be resumed or stamped with new proof')
            program=self.active['town']['resource_program'];manifest,digest=_program_valid(program)
            if manifest_hash(load_manifest())!=digest:raise ValueError('Reviewed resource manifest changed during delivery')
            if command.get('source')!=manifest['id'] or command.get('manifest_hash')!=digest or command.get('catalog_hash')!=manifest['catalog_hash']:
                raise ValueError('Resource command manifest identity differs from frozen source')
            if command.get('origin_session')!=self.session or observation.get('session')!=self.session:
                raise ValueError('Resource delivery session changed; no cold replay')
            if _native(observation,manifest,digest)!=command.get('delivery_epoch'):raise ValueError('Resource executor epoch changed; delivery witness lost')
            actual=None
            try:_,actual=observed_recipient(observation,command['actor'],command['actor_base_id'])
            except StaleAccountingObservation:pass
            selected=select_grant(manifest,command['actor'],command['actor_base_id'])
            if any(not _same(command.get(k),selected[k]) for k in ('selector_id','grant_hash','grant')):
                raise ValueError('Resource command grant differs from reviewed selection')
            if command.get('phase') not in ('arm','deliver') or command.get('id')!=command['grant_id']+'-'+command['phase']:
                raise ValueError('Resource command phase identity is invalid')
            if program.get('recipient_claims',{}).get(str(command['actor']))!=command['grant_id']:
                raise ValueError('Resource recipient reservation is absent')
            saved=program.get('deliveries',{}).get(command['grant_id']) or {}
            if not _same(saved.get('command'),command) or saved.get('status')!='pending':raise ValueError('Saved resource reservation differs from command')
            if command['phase']=='deliver' and (not _armed(saved) or not _armed(pending)):
                raise ValueError('Resource delivery has no persisted matching arm permit')
            keys=set(commodity_ids())
            if (not isinstance(command.get('before'),dict) or not isinstance(command.get('after'),dict)
                or set(command['before'])!=keys or set(command['after'])!=keys
                or not all(_integer(v) for row in (command['before'],command['after']) for v in row.values())
                or any(command['after'][k]!=command['before'][k]+command['grant'][k] for k in keys)):
                raise ValueError('Resource account transform is invalid')
        except (ValueError,KeyError,TypeError) as error:
            self._hold_endowment(error,observation,ack if ack.get('id')==command.get('id') else None);return
        if ack.get('id')!=command['id']:return
        if not _receipt_matches(command,ack):self._hold_endowment('Resource receipt identity is missing or mismatched',observation,ack);return
        state=copy.deepcopy(self.active);record=state['pending'];program=state['town']['resource_program']
        record['evidence']={'actual':actual,'ack':_safe_ack(ack),'session':self.session}
        if command['phase']=='arm':
            if (ack.get('status')!='applied' or ack.get('accepted') is not True or ack.get('phase')!='armed'
                or ack.get('effects_issued') is not False or ack.get('no_effects_issued') is not True
                or ack.get('legs')!=[] or not _text(ack.get('permit')) or not _same(ack.get('inventory'),command['before'])
                or actual is not None and actual!=command['before']):
                self._hold_endowment('Native resource arm did not prove an effect-free matching permit',observation,ack);return
            if actual is None:return  # Wait for accounting to reach this bound checkpoint.
            record['arm_receipt']=_safe_ack(ack);record['phase']='deliver'
            record['command']={**command,'phase':'deliver','id':command['grant_id']+'-deliver','permit':ack['permit']}
            program['deliveries'][command['grant_id']]=copy.deepcopy(record)
            self._write(state,'native resource permit persisted before delivery checkpoint');return
        if (ack.get('status')!='applied' or ack.get('accepted') is not True or ack.get('phase')!='complete' or not _text(command.get('permit'))
            or ack.get('permit')!=command['permit'] or ack.get('effects_issued') is not True
            or ack.get('no_effects_issued') is not False or not _legs_complete(command,ack)
            or not _same(ack.get('inventory'),command['after']) or actual is not None and actual!=command['after']):
            self._hold_endowment('Resource delivery lacks complete issued and observed leg witnesses',observation,ack);return
        if actual is None:return  # Receipts cannot credit stale checkpoint inventory.
        key=str(command['actor']);grant=command['grant']
        if key in program['grants'] or any(program['reserved'][k]<grant[k] for k in grant):
            self._hold_endowment('Resource source accounting conflict',observation,ack);return
        record.update(status='committed',phase='complete');program['grants'][key]=copy.deepcopy(record)
        program['deliveries'][command['grant_id']]=copy.deepcopy(record)
        for item,amount in grant.items():
            program['reserved'][item]-=amount;program['delivered'][item]+=amount;program['remaining'][item]-=amount
        state['pending']=None
        person=state['people'][key]
        person['memories']=(person['memories']+[{'event_id':command['grant_id'],'kind':'starting_resources_received',
            'resources':copy.deepcopy(grant),'source':'Verified finite external scenario delivery; not trade or wages'}])[-32:]
        if 'agency' in person:person['agency']['next_review_day']=observation.get('gameDays',person['agency']['next_review_day'])
        self._write(state,'fully witnessed resource import committed once; reserved capacity moved to delivered')
