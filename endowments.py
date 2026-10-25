"""Finite external starting capital; never counted as sales or production.

The source pool is outside residents' native purses. A prepared grant reserves
capacity; only observed native delivery spends it. Loading follows the saved
checkpoint, including unfinished delivery, rather than minting another grant.
"""
import copy
from activity_leases import activity_conflict
from economy_catalog import commodity_ids, require_native_catalog, native_catalog_matches, catalog_hash, MAX_STOCK

ITEMS=('gold','bread','grain')
SOURCE='founding-resources-v1'
CAPACITY={'gold':1000,'bread':100,'grain':100}


def inventory(observation,actor):
    records={a['id']:a for a in observation.get('residents',[])}
    records.update({a['id']:a for a in observation.get('inventory_observations',[])})
    resident=records.get(actor,{})
    stock=resident.get('inventory',{})
    if resident.get('isPerson') is not True or any(type(stock.get(k)) is not int or not 0<=stock[k]<=MAX_STOCK for k in commodity_ids()):
        raise ValueError('Starting resources require a classified, observed adult with complete inventory')
    return {k:stock[k] for k in commodity_ids()}


class Endowments:
    def plan_endowment(self,actor,observation):
        self._agency_guard(observation)
        if self.agency_busy() or self.conversation_busy():raise ValueError('Finish the active resident activity first')
        town=self.active.get('town')
        if type(actor) is not int or not town or str(actor) not in town['residents']:
            raise ValueError('Initialize the resident before assigning resources')
        program=town.get('resource_program')
        if program and str(actor) in program['grants']:
            return {'duplicate':True,'grant':program['grants'][str(actor)]}
        if activity_conflict(self.active,actors=(actor,),observation=observation):
            raise ValueError('An independent activity owns the resource recipient')
        bound_catalog=require_native_catalog(observation)
        if not set(ITEMS)<=set(commodity_ids()):raise ValueError('Catalog does not support the authored founding resource program')
        before=inventory(observation,actor)
        if any(before[k]>1000000 for k in ITEMS):raise ValueError('Recipient exceeds the authored founding program stock limit')
        # Authored, explicit scenario capital. Family size and wealth are not
        # inferred from appearance; business assets share their owner's purse.
        grant={'gold':100,'bread':2,'grain':20} if actor==108149 else {'gold':20,'bread':2,'grain':0}
        state=copy.deepcopy(self.active)
        program=state['town'].setdefault('resource_program',{'id':SOURCE,'capacity':CAPACITY.copy(),
            'remaining':CAPACITY.copy(),'grants':{},'source':'Explicit finite imports from outside Whiterun; not earned income'})
        if program['id']!=SOURCE or program['capacity']!=CAPACITY:raise ValueError('Unknown starting-resource program')
        if any(program['remaining'][k]<grant[k] for k in ITEMS):raise ValueError('Founding resource pool is exhausted')
        after={k:before[k]+grant.get(k,0) for k in before}
        if any(value>MAX_STOCK for value in after.values()):raise ValueError('Starting resources would overflow native inventory')
        command={'id':SOURCE+'-'+str(actor),'kind':'inventory_endowment','actor':actor,
            'catalog_hash':bound_catalog,
            'source':SOURCE,'grant':grant,'before':before,'after':after}
        state['pending']={'id':command['id'],'status':'pending','command':command,'evidence':None,
            'source':program['source']}
        return {'checkpoint':self._write(state,'finite founding grant prepared before native delivery'),'grant':grant}

    def observe_endowment(self,observation):
        pending=self.active['pending'];command=pending['command'];ack=observation.get('ack') or {}
        if pending.get('status')=='held':return
        if command.get('catalog_hash')!=catalog_hash() or not native_catalog_matches(observation):
            state=copy.deepcopy(self.active);state['pending'].update(status='held',error='Endowment catalog proof is missing or changed; do not replay')
            self._write(state,'unbound founding grant held without importing new inventory');return
        if ack.get('id')!=pending['id']:return
        try:actual=inventory(observation,command['actor'])
        except ValueError:return
        state=copy.deepcopy(self.active);record=state['pending']
        record['evidence']={'actual':actual,'ack':copy.deepcopy(ack),'session':self.session}
        if ack.get('status')!='applied' or ack.get('catalog_hash')!=command['catalog_hash'] or actual!=command['after']:
            record['status']='held'
            self._write(state,'starting resource delivery held for reconciliation; no automatic retry')
            return
        program=state['town']['resource_program'];key=str(command['actor'])
        if key in program['grants'] or any(program['remaining'][k]<command['grant'][k] for k in ITEMS):
            raise ValueError('Starting-resource accounting conflict')
        record['status']='committed';program['grants'][key]=copy.deepcopy(record)
        for k in ITEMS:program['remaining'][k]-=command['grant'][k]
        state['pending']=None
        person=state['people'][key]
        person['memories']=(person['memories']+[{'event_id':command['id'],'kind':'starting_resources_received',
            'resources':command['grant'].copy(),'source':'Observed finite external founding grant; not trade or wages'}])[-32:]
        # New food is a meaningful stimulus; the next clock review can consider
        # it without increasing hunger or immediately forcing consumption.
        if 'agency' in person:person['agency']['next_review_day']=observation.get('gameDays',person['agency']['next_review_day'])
        self._write(state,'native starting resources observed and finite external pool debited')
