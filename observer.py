"""Read-only society projection and a narrowly scoped local camera control."""
import math
import time
from collections import Counter
from statistics import mean
from enterprises import production_policy
from routing import activity_blocker
from dashboard import town_dashboard


def camera_request(data, observation, society):
    mode=data.get('mode')
    if mode not in ('market','street','trade','focus','free','story'):
        raise ValueError('Unknown observer view')
    result={'mode':mode}
    if mode=='focus':
        actor=data.get('id')
        loaded={r['id'] for r in (observation or {}).get('residents',[]) if r.get('isPerson') is True}
        managed=(society.get('town') or {}).get('residents',{})
        if type(actor) is not int or actor not in loaded or str(actor) not in managed:
            raise ValueError('Follow requires a loaded initialized adult resident')
        result['id']=actor
    for key,default,low,high in [('distance',650,100,4000),('yaw',225,-360,360),('elevation',300,40,2500),('panX',24500,17000,30000),('panY',-7100,-15000,1000)]:
        value=data.get(key,default)
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError('Camera parameter out of range: '+key)
        result[key]=value
    return result


def observer_state(bridge,society):
    obs=bridge.get('observation') or {}
    connected=bridge.get('last_seen') is not None and time.time()-bridge['last_seen']<10
    loaded={str(r['id']):r for r in obs.get('residents',[]) if r.get('isPerson') is True}
    stock={str(r['id']):r['inventory'] for r in obs.get('inventory_observations',[])}
    stock.update({key:r.get('inventory') for key,r in loaded.items()})
    town=society.get('town') or {}
    residents=[]
    for key,resident in town.get('residents',{}).items():
        person=society.get('people',{}).get(key,{})
        actor=loaded.get(key)
        residents.append({'id':int(key),'name':resident['name'],'loaded':bool(actor),'is_guard':resident.get('is_guard',False),
            'position':[actor.get(k) for k in ('x','y','z')] if actor else None,
            'race':actor.get('race') if actor else None,
            'native_activity':actor.get('activity') if actor else None,
            'activity_blocker':activity_blocker(actor) if actor else 'not_loaded',
            'inventory':stock.get(key),'person':person,'household':resident.get('household')})
    businesses = []
    for key, business in town.get('businesses', {}).items():
        # Operator-wide accounts are intentionally separate from resident prompts.
        businesses.append({**business, 'id':key, 'revision':business.get('revision',0),
            'active':business.get('active',True), 'production_policy':production_policy(business),
            'observed_inventory':stock.get(str(business['custodian'])),
            'account_scope':'Custodian inventory shared with household and any other charters; not a separate company wallet'})
    metrics=dict(society.get('metrics') or {})
    metrics['population_breakdown']={'loaded_races':dict(Counter((r.get('race') or {}).get('name') or 'unknown' for r in residents if r['loaded'])),
        'personality_trait_means':{trait:round(mean(p['profile']['big_five'][trait] for p in society.get('people',{}).values() if trait in p.get('profile',{}).get('big_five',{})),3)
            for trait in sorted({t for p in society.get('people',{}).values() for t in p.get('profile',{}).get('big_five',{})})},
        'scope':'Race is current native descriptive metadata; unloaded races remain unknown. Personality traits are seeded independently of race. No group causal or psychological claims.'}
    return {'connected':connected,'observed_at':bridge.get('last_seen'),'checkpoint':society.get('checkpoint'),
        'error':society.get('error'),'transition':society.get('transition'),'game_days':obs.get('gameDays'),
        'audio_output':obs.get('audio_output'),'speech':obs.get('speech'),'player_controls':obs.get('player_controls'),
        'weather':obs.get('weather'),'camera':obs.get('camera'),'camera_request':bridge.get('observer_camera'),
        'metrics':metrics,'scene_handoffs':society.get('scene_handoffs',[]),'dashboard':town_dashboard(society,obs),
        'residents':residents,'places':obs.get('places',[]),'businesses':businesses,
        'daily':town.get('daily'),'plan':society.get('plan'),'conversation':society.get('conversation'),
        'routine_batch':society.get('routine_batch'),'parallel_routines':obs.get('parallel_routines'),
        'movement':obs.get('movement'),'work':obs.get('productionWork'),'rest':(obs.get('rest') or {}).get('activity'),
        'rests':society.get('rests',[])[-10:],'consumptions':society.get('consumptions',[])[-10:],
        'production':society.get('production',[])[-10:],
        'trades':society.get('trades',[])[-10:],
        'cancelled_production':society.get('cancelled_production',[])[-10:],
        'unsettled_effect':society.get('unsettled_effect'),
        'limits':[str(len(residents))+' initialized residents, not a claim of every Whiterun NPC.',
            'Up to six background journeys can overlap one disjoint conversation; exclusive travel cohorts still support eight. Inventory transactions remain serialized.',
            'Traits, needs and relationship scores are gameplay models, not measured psychology.',
            'Family households, continuous town scheduling and broad production chains remain incomplete.']}
