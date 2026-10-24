"""Save-bound population initialization from classified native observations.

Synthetic starting traits, needs and household arrangements are scenario inputs,
not canonical lore, psychological measurements or evidence of native activity.
Inventories are observed once and are never copied into a second spendable wallet.
"""
import copy
import hashlib
import math
import re

TRAITS=('openness','conscientiousness','extraversion','agreeableness','neuroticism')
NEEDS=('hunger','fatigue','social_contact','safety','comfort')
CONTROLLED_ROUTES={108149,108186,108156}


def seeded_value(seed,actor,field,low=.2,high=.8):
    raw=hashlib.sha256(f'{seed}:{actor}:{field}'.encode()).digest()
    return round(low+(high-low)*int.from_bytes(raw[:4],'big')/(2**32-1),3)


def person_seed(actor,seed,day):
    actor_id=actor['id'];guard=actor.get('isGuard') is True
    traits={name:seeded_value(seed,actor_id,name) for name in TRAITS}
    return {'profile':{'name':actor['name'],'role':'guard' if guard else 'resident; occupation not yet assigned',
        'big_five':traits,'priorities':['meet household needs','maintain important relationships','fulfil commitments'],
        'bias':'uses familiar options first when tired or uncertain',
        'provenance':'Seeded scenario interpretation, not a measurement or canonical biography'},
        'needs':{name:seeded_value(seed,actor_id,name,.15,.65) for name in NEEDS},
        'memories':[],'trust':{},'relationships':{},
        'affect':{'valence':0.,'arousal':.25,'source':'authored initial neutral state'},
        'social_style':{'warmth':traits['agreeableness'],'directness':seeded_value(seed,actor_id,'directness'),
            'verbosity':traits['extraversion'],'familiarity_preference':1-traits['openness'],
            'source':'authored gameplay tendencies; not diagnostic categories'},
        'skills':{'general_labour':.5,'trade':.35,'craft':.25},
        'goals':[{'kind':'household_food','priority':.7},{'kind':'livelihood','priority':.6},{'kind':'belonging','priority':.4}],
        'commitments':[],'household':'household-'+str(actor_id),
        'agency':{'state':'awaiting_first_daily_plan','next_review_day':day,
            'native_route_supported':actor_id in CONTROLLED_ROUTES},
        'initialization':{'seed':seed,'source':'observed adult NPC; authored psychological and social state'}}


def eligible_actors(observation):
    residents=observation.get('residents',[])
    if not isinstance(residents,list) or len(residents)>128:raise ValueError('Invalid bounded census')
    accepted=[];seen=set()
    for actor in residents:
        if not isinstance(actor,dict) or actor.get('isPerson') is not True:continue
        aid=actor.get('id')
        if type(aid) is not int or not 0<aid<=0xffffffff or aid in seen:raise ValueError('Invalid or duplicate resident identity')
        seen.add(aid)
        if not isinstance(actor.get('name'),str) or not 1<=len(actor['name'])<=100:raise ValueError('Invalid resident name')
        inventory=actor.get('inventory',{})
        if any(type(inventory.get(k)) is not int or inventory[k]<0 for k in ('gold','bread','grain')):
            raise ValueError('Complete native inventory required for resident initialization')
        accepted.append(actor)
    if not accepted:raise ValueError('No positively classified adult NPCs; do not infer humanity from a name')
    return accepted


class Population:
    def initialize_population(self,event_id,seed,observation):
        self._agency_guard(observation)
        if not isinstance(event_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',event_id):raise ValueError('Invalid census event ID')
        if not isinstance(seed,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',seed):raise ValueError('Invalid scenario seed')
        if self.agency_busy() or self.conversation_busy():raise ValueError('Finish the active encounter before expanding the population')
        existing=self.active.get('town')
        if existing and event_id in [x['id'] for x in existing['census_events']]:
            if existing['seed']!=seed:raise ValueError('Census ID reused with another seed')
            return {'duplicate':True,'population':len(existing['residents'])}
        if existing and existing['seed']!=seed:raise ValueError('A living population cannot be silently reseeded')
        day=observation.get('gameDays')
        if type(day) not in (int,float) or not math.isfinite(day) or day<0:raise ValueError('Observed game clock required')
        actors=eligible_actors(observation);state=copy.deepcopy(self.active)
        town=state.setdefault('town',{'schema':1,'seed':seed,'residents':{},'households':{},'businesses':{},'census_events':[],
            'scope':'Observed adult population; assigned state is not native routine ownership',
            'initial_endowment_policy':'No resources minted by census; explicit imports require their own verified commands'})
        added=[]
        for actor in actors:
            key=str(actor['id'])
            if key in town['residents']:continue
            new=person_seed(actor,seed,day)
            if key in state['people']:
                old=state['people'][key]
                # Preserve actual memories, authored legacy personality, hunger and policies.
                for field,value in new.items():
                    if field not in old:old[field]=value
                for name,value in new['needs'].items():old['needs'].setdefault(name,value)
            else:state['people'][key]=new
            person=state['people'][key];household=person['household']
            town['households'][household]={'members':[actor['id']],
                'resource_owner':actor['id'],'daily_food_units':1,'obligations':[],
                'provenance':'Authored single-adult household placeholder; canonical family membership unverified'}
            town['residents'][key]={'id':actor['id'],'name':actor['name'],'household':household,
                'classification_source':actor.get('classificationSource','native ActorTypeNPC keyword'),
                'initial_observed_inventory':copy.deepcopy(actor['inventory']),
                'observed_game_day':day,'is_guard':actor.get('isGuard') is True,
                'native_route_supported':actor['id'] in CONTROLLED_ROUTES}
            added.append(actor['id'])
        # Business assets reference their physical custodian, not a duplicate wallet.
        for owner,name,capabilities in [(108149,'Carlotta\'s food enterprise',['bread_recipe','retail_food']),
                                         (108156,'Adrianne\'s workshop',['metalwork_planned'])]:
            if str(owner) in town['residents']:
                town['businesses'].setdefault('business-'+str(owner),{'name':name,'owner':owner,'custodian':owner,
                    'capabilities':capabilities,'workers':[],'contracts':[],
                    'resource_account':'native-inventory:'+str(owner),'separate_legal_cash_account':False,
                    'costs':{'bread_recipe':{'grain':1,'labour_game_minutes':30,'wage_gold':2}} if owner==108149 else {},
                    'provenance':'Authored business charter; capabilities may be planned, not executed'})
        town['census_events'].append({'id':event_id,'added':added,'observed_day':day,'session':self.session})
        return {'checkpoint':self._write(state,'classified town population initialized without minting resources'),
            'added':added,'population':len(town['residents'])}

    def population_status(self):
        if not self.active or not self.active.get('town'):return None
        town=copy.deepcopy(self.active['town'])
        town['counts']={'residents':len(town['residents']),'households':len(town['households']),
            'businesses':len(town['businesses']),
            'native_route_supported':sum(r['native_route_supported'] for r in town['residents'].values())}
        return town
