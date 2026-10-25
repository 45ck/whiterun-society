"""Checkpointed trade permits and witnessed transfers; partial effects stay held."""
import copy
import hashlib
import re
from economy_catalog import commodity_ids, catalog_hash, require_native_catalog, canonical_json, MAX_STOCK
from market_policy import goods_policy, policy_hash
from world_economy import qualified_snapshot
from endowments import StaleAccountingObservation
from activity_leases import activity_conflict
from trade_consent import accepted_trade_consent, consent_envelope
from food import allocation

IDENTITY=('trade_id','catalog_hash','market_policy_hash','buyer','buyer_base_id','seller','seller_base_id',
          'commodity','currency','quantity','unit_price','cost','origin_session','delivery_epoch','before','after','consent_id','consent_hash')


def same(first,second):
    try:return canonical_json(first)==canonical_json(second)
    except (TypeError,ValueError):return False


def text(value):return isinstance(value,str) and 0<len(value)<=160 and all(ord(c)>=32 for c in value)


def integer(value):return type(value) is int and 0<=value<=MAX_STOCK


def receipt_matches(command,ack):
    return (isinstance(ack,dict) and type(ack.get('protocol')) is int and ack['protocol']==2
        and ack.get('id')==command.get('id') and all(k in ack and k in command and same(ack[k],command[k]) for k in IDENTITY))


def safe_ack(ack):
    if not isinstance(ack,dict):return {}
    result={}
    for key in ('id','protocol','phase','status','permit','error',*IDENTITY):
        value=ack.get(key)
        if isinstance(value,str):result[key]=value[:240]
        elif type(value) is int:result[key]=value
        elif key in ('before','after') and isinstance(value,dict):
            result[key]={role:{k:v for k,v in stock.items() if k in commodity_ids() and integer(v)}
                         for role,stock in value.items() if role in ('buyer','seller') and isinstance(stock,dict)}
    if isinstance(ack.get('inventory'),dict):
        result['inventory']={role:{k:v for k,v in stock.items() if k in commodity_ids() and integer(v)}
                             for role,stock in ack['inventory'].items() if role in ('buyer','seller') and isinstance(stock,dict)}
    for key in ('accepted','effects_issued','no_effects_issued'):
        if type(ack.get(key)) is bool or ack.get(key) is None:result[key]=ack.get(key)
    result['legs']=[]
    for row in ack.get('legs',[])[:4] if isinstance(ack.get('legs'),list) else []:
        if not isinstance(row,dict) or row.get('leg') not in ('goods','payment'):continue
        leg={'leg':row['leg']}
        if row.get('item') in commodity_ids():leg['item']=row['item']
        if integer(row.get('amount')):leg['amount']=row['amount']
        for key in ('issued','observed','debit_observed','credit_observed'):
            if type(row.get(key)) is bool:leg[key]=row[key]
        result['legs'].append(leg)
    return result


def arm_valid(record):
    command=record.get('command') or {};ack=record.get('arm_receipt') or {}
    expected={**command,'id':command.get('trade_id','')+'-arm'}
    return (receipt_matches(expected,ack) and ack.get('status')=='applied' and ack.get('accepted') is True
        and ack.get('phase')=='armed' and ack.get('effects_issued') is False and ack.get('no_effects_issued') is True
        and ack.get('legs')==[] and same(ack.get('inventory'),command.get('before'))
        and text(command.get('permit')) and ack.get('permit')==command['permit'])


def legs_valid(command,ack):
    expected={'goods':(command['commodity'],command['quantity']),'payment':('gold',command['cost'])}
    legs=ack.get('legs')
    if not isinstance(legs,list) or len(legs)!=2:return False
    seen=set()
    for row in legs:
        if not isinstance(row,dict):return False
        name=row.get('leg')
        if (not isinstance(name,str) or name not in expected or name in seen
            or set(row)!={'leg','item','amount','issued','observed','debit_observed','credit_observed'}
            or row.get('item')!=expected[name][0] or type(row.get('amount')) is not int
            or row['amount']!=expected[name][1] or row.get('issued') is not True or row.get('observed') is not True
            or any(row.get(key) is not True for key in ('debit_observed','credit_observed'))):return False
        seen.add(name)
    return True


def native_epoch(observation):
    require_native_catalog(observation)
    status=observation.get('trade_execution') or {}
    if (not isinstance(status,dict) or status.get('available') is not True or type(status.get('protocol')) is not int
        or status['protocol']!=2 or not text(status.get('epoch')) or status.get('catalog_hash')!=catalog_hash()
        or status.get('market_policy_hash')!=policy_hash()):
        raise ValueError('Matching trade protocol, catalog, market policy and executor epoch required')
    return status['epoch']


def validate_contract(command):
    if (type(command.get('protocol')) is not int or command['protocol']!=2 or command.get('kind')!='inventory_trade'
        or command.get('phase') not in ('arm','deliver') or not isinstance(command.get('trade_id'),str)
        or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',command['trade_id'])
        or command.get('id')!=command['trade_id']+'-'+command['phase']):
        raise ValueError('Unresolved legacy or malformed trade requires reconciliation; no replay')
    if command.get('catalog_hash')!=catalog_hash() or command.get('market_policy_hash')!=policy_hash():
        raise ValueError('Trade catalog or market policy identity changed')
    for key in ('buyer','seller','buyer_base_id','seller_base_id'):
        if type(command.get(key)) is not int or not 0<command[key]<=0xffffffff:raise ValueError('Invalid trade actor identity')
    policy=goods_policy(command.get('commodity'))
    if (command['buyer']==command['seller'] or command.get('currency')!='gold'
        or type(command.get('quantity')) is not int or not 1<=command['quantity']<=policy['max_quantity']
        or type(command.get('unit_price')) is not int or not policy['price_min']<=command['unit_price']<=policy['price_max']
        or type(command.get('cost')) is not int or command['cost']!=command['quantity']*command['unit_price']
        or not text(command.get('origin_session')) or not text(command.get('delivery_epoch'))):
        raise ValueError('Invalid market trade terms')
    keys=set(commodity_ids())
    for phase in ('before','after'):
        accounts=command.get(phase)
        if (not isinstance(accounts,dict) or set(accounts)!={'buyer','seller'}
            or any(not isinstance(a,dict) or set(a)!=keys or not all(integer(v) for v in a.values()) for a in accounts.values())):
            raise ValueError('Trade requires complete bounded accounts')
    after=copy.deepcopy(command['before']);good=command['commodity']
    after['buyer']['gold']-=command['cost'];after['seller']['gold']+=command['cost']
    after['buyer'][good]+=command['quantity'];after['seller'][good]-=command['quantity']
    if not same(after,command['after']):raise ValueError('Trade account transformation is not conserved')


def validate_record(record):
    command=record['command'];validate_contract(command)
    if record.get('id')!=command['trade_id']:raise ValueError('Trade journal ID differs from its intent')
    consent=record.get('consent') or {};payload=consent.get('payload')
    if not isinstance(payload,dict):raise ValueError('Trade consent provenance is missing')
    digest=hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    prefix='operator' if payload.get('source_kind')=='operator' else 'resident' if payload.get('source_kind')=='resident_decisions' else None
    if (prefix is None or consent.get('consent_hash')!=digest or command.get('consent_hash')!=digest
        or consent.get('consent_id')!=prefix+'-'+digest[:40] or command.get('consent_id')!=consent['consent_id']
        or any(not same(payload.get(k),command[k]) for k in ('trade_id','buyer','seller','commodity','quantity','unit_price','cost','catalog_hash','market_policy_hash'))
        or payload.get('purpose') not in ('food','production_input','other')):
        raise ValueError('Trade consent no longer binds the exact terms')
    if command['phase']=='deliver' and not arm_valid(record):raise ValueError('Trade delivery has no persisted matching arm permit')


class TradeExecution:
    def plan_trade(self,event_id,observation,buyer,seller,quantity=1,unit_price=3,agency_plan=None,commodity='bread'):
        if self.error or not self.active or self.transition:raise ValueError('Society checkpoint is not synchronized')
        if observation.get('session')!=self.session or observation.get('checkpoint')!=self.marker:
            raise ValueError('Observation belongs to a different checkpoint')
        if not isinstance(event_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',event_id) or event_id.startswith('checkpoint-'):raise ValueError('Invalid trade event ID')
        if any(type(v) is not int or v<=0 for v in (buyer,seller,quantity,unit_price)):raise ValueError('Positive integer trade values required')
        request=dict(buyer=buyer,seller=seller,quantity=quantity,unit_price=unit_price)
        if commodity!='bread':request['commodity']=commodity
        for old in self.active['trades']+([self.active['pending']] if self.active['pending'] else []):
            if old['id']==event_id:
                if not same(old.get('request'),request):raise ValueError('Event ID reused with different trade')
                return copy.deepcopy(old)  # Historical identity is read, never upgraded or dispatched here.
        if self.active['pending']:raise ValueError('An unsettled trade must be reconciled first')
        if self.routines_busy():raise ValueError('Independent journeys are still executing')
        if self.conversation_busy():raise ValueError('A conversation owns the participants')
        if activity_conflict(self.active,actors=(buyer,seller),observation=observation):
            raise ValueError('A trade participant owns an independent activity lease')
        epoch=native_epoch(observation);bases,before=qualified_snapshot(observation,buyer,seller)
        policy=goods_policy(commodity)
        if (buyer==seller or quantity>policy['max_quantity'] or not policy['price_min']<=unit_price<=policy['price_max']):
            raise ValueError('Invalid or oversized trade')
        cost=quantity*unit_price
        if before['buyer']['gold']<cost or before['seller'][commodity]<quantity:raise ValueError('Insufficient observed funds or goods')
        if agency_plan:
            plan=(self.active.get('plans') or [{}])[-1]
            if plan.get('purpose')=='production_input':
                from procurement import validate_procurement
                if not validate_procurement(self.active,observation,buyer,plan.get('procurement')):
                    raise ValueError('Procurement opportunity changed before admission')
            consent=accepted_trade_consent(self.active,event_id,buyer,seller,quantity,unit_price,agency_plan,before,commodity,observation=observation)
        else:
            if policy['reserve_mode']=='existing_food_policy':
                stock=allocation(self.active['people'].get(str(seller),{}),before['seller'])
                if stock['allocated'] and stock['for_sale']<quantity:raise ValueError('Operator trade cannot spend resident household reserve')
            consent=consent_envelope({'trade_id':event_id,'buyer':buyer,'seller':seller,'commodity':commodity,'quantity':quantity,
                'unit_price':unit_price,'cost':cost,'catalog_hash':catalog_hash(),'market_policy_hash':policy_hash(),
                'purpose':'other','source_kind':'operator'},'operator')
        after=copy.deepcopy(before);after['buyer']['gold']-=cost;after['seller']['gold']+=cost
        after['buyer'][commodity]+=quantity;after['seller'][commodity]-=quantity
        command={'id':event_id+'-arm','trade_id':event_id,'kind':'inventory_trade','protocol':2,'phase':'arm',
            'buyer':buyer,'buyer_base_id':bases['buyer'],'seller':seller,'seller_base_id':bases['seller'],
            'commodity':commodity,'currency':'gold','quantity':quantity,'unit_price':unit_price,'cost':cost,
            'catalog_hash':catalog_hash(),'market_policy_hash':policy_hash(),'origin_session':self.session,'delivery_epoch':epoch,
            'before':before,'after':after,'consent_id':consent['consent_id'],'consent_hash':consent['consent_hash']}
        record={'id':event_id,'request':request,'command':command,'status':'pending','phase':'arm','evidence':None,'consent':consent}
        if consent.get('reserve_release'):record['reserve_release']=copy.deepcopy(consent['reserve_release'])
        validate_record(record)
        state=copy.deepcopy(self.active);state['pending']=record
        if agency_plan:state['plans'][-1]['phase']='trading'
        checkpoint=self._write(state,'trade terms and participant reservations persisted before native arm')
        return {**record,'prepared_checkpoint':checkpoint}

    def _hold_trade(self,error,observation,ack=None):
        if self.active['pending'].get('status')=='held':return
        state=copy.deepcopy(self.active);record=state['pending'];record.update(status='held',phase='held',error=str(error)[:240])
        if ack is not None:record['evidence']={'ack':safe_ack(ack),'session':observation.get('session')}
        if state.get('plans') and state['plans'][-1].get('trade_id')==record['id']:
            state['plans'][-1].update(phase='held',error='Physical trade requires reconciliation')
        self._write(state,'trade held with both accounts reserved; no delivery credit or cold replay')

    def trade_pending_command(self,session):
        record=(self.active or {}).get('pending') or {};command=record.get('command') or {}
        if record.get('status')!='pending' or command.get('origin_session')!=session:return None
        try:validate_record(record)
        except (KeyError,ValueError,TypeError):return None
        return {**command,'session':session,'checkpoint':self.marker}

    def observe_trade(self,observation):
        record=self.active['pending'];command=record.get('command') or {};ack=observation.get('ack') or {}
        if record.get('status')=='held':return
        if not isinstance(ack,dict):ack={}
        try:
            validate_record(record)
            if command['origin_session']!=self.session or observation.get('session')!=self.session:
                raise ValueError('Trade session changed; no cold replay')
            if native_epoch(observation)!=command['delivery_epoch']:raise ValueError('Trade executor epoch changed; live witnesses lost')
            payload=record['consent']['payload']
            if payload['purpose']=='production_input':
                from procurement import validate_procurement_terms
                if not validate_procurement_terms(self.active,command['buyer'],payload.get('procurement'),observation=observation):
                    raise ValueError('Procurement enterprise or listing terms changed during trade')
            actual=None
            try:
                _,actual=qualified_snapshot(observation,command['buyer'],command['seller'],
                    {'buyer':command['buyer_base_id'],'seller':command['seller_base_id']})
            except StaleAccountingObservation:pass
            # Recheck private resident consent while inventory is still untouched.
            if command['phase']=='arm' and record['consent']['payload']['source_kind']=='resident_decisions':
                payload=record['consent']['payload']
                current=accepted_trade_consent(self.active,command['trade_id'],command['buyer'],command['seller'],
                    command['quantity'],command['unit_price'],payload['plan_id'],command['before'],command['commodity'],observation=observation)
                if not same(current,record['consent']):raise ValueError('Resident trade consent changed before arm')
        except (KeyError,TypeError,ValueError) as error:
            self._hold_trade(error,observation,ack if ack.get('id')==command.get('id') else None);return
        if ack.get('id')!=command['id']:return
        if not receipt_matches(command,ack):self._hold_trade('Trade receipt identity is missing or mismatched',observation,ack);return
        if command['phase']=='arm':
            if (ack.get('status')!='applied' or ack.get('accepted') is not True or ack.get('phase')!='armed'
                or ack.get('effects_issued') is not False or ack.get('no_effects_issued') is not True
                or ack.get('legs')!=[] or not text(ack.get('permit')) or not same(ack.get('inventory'),command['before'])
                or actual is not None and actual!=command['before']):
                self._hold_trade('Trade arm lacks an effect-free matching permit',observation,ack);return
            if actual is None:return
            state=copy.deepcopy(self.active);updated=state['pending'];updated.update(phase='deliver',arm_receipt=safe_ack(ack))
            updated['command']={**command,'id':command['trade_id']+'-deliver','phase':'deliver','permit':ack['permit']}
            self._write(state,'native trade permit persisted before delivery checkpoint');return
        if (ack.get('status')!='applied' or ack.get('accepted') is not True or ack.get('phase')!='complete'
            or ack.get('permit')!=command['permit'] or ack.get('effects_issued') is not True
            or ack.get('no_effects_issued') is not False or not legs_valid(command,ack)
            or not same(ack.get('inventory'),command['after']) or actual is not None and actual!=command['after']):
            self._hold_trade('Trade lacks complete goods and payment leg witnesses',observation,ack);return
        if actual is None:return
        if any(old['id']==record['id'] for old in self.active['trades']):
            self._hold_trade('Trade terminal journal already contains this ID',observation,ack);return
        state=copy.deepcopy(self.active);updated=state['pending'];updated.update(status='committed',phase='complete',
            evidence={'actual':actual,'ack':safe_ack(ack),'session':self.session})
        state['trades'].append(updated);state['pending']=None
        purpose=updated['consent']['payload']['purpose']
        if state.get('plans') and state['plans'][-1].get('trade_id')==record['id']:
            plan=state['plans'][-1]
            if purpose=='food' and command['commodity']=='bread':plan.update(phase='after_purchase',purchase_completed=True)
            else:plan.update(phase='complete',purchase_completed=True,outcome='purchased_input' if purpose=='production_input' else 'bought_'+command['commodity'])
            self.queue_trade_speech(state,plan,'receipt')
        for actor,other,role in ((command['buyer'],command['seller'],'bought'),(command['seller'],command['buyer'],'sold')):
            person=state['people'].get(str(actor))
            if person is None:continue
            memory={'event_id':record['id'],'kind':'completed_trade','role':role,'other':other,'commodity':command['commodity'],
                    'quantity':command['quantity'],'gold':command['cost'],'unit_price':command['unit_price'],'purpose':purpose,
                    'source_kind':updated['consent']['payload']['source_kind'],'catalog_hash':command['catalog_hash'],'market_policy_hash':command['market_policy_hash']}
            if command['commodity'] in ('bread','grain'):memory[command['commodity']]=command['quantity']
            person['memories']=(person.get('memories',[])+[memory])[-32:]
            person.setdefault('trust',{})[str(other)]=min(10,person['trust'].get(str(other),0)+1)
        self._write(state,'fully witnessed trade committed once; memories follow physical goods and payment')
