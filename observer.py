"""Read-only society projection and a narrowly scoped local camera control."""
import math
import time


def camera_request(data, observation, society):
    mode=data.get('mode')
    if mode not in ('market','street','trade','focus','free'):
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
        residents.append({'id':int(key),'name':resident['name'],'loaded':bool(actor),
            'position':[actor.get(k) for k in ('x','y','z')] if actor else None,
            'inventory':stock.get(key),'person':person,'household':resident.get('household')})
    return {'connected':connected,'observed_at':bridge.get('last_seen'),'checkpoint':society.get('checkpoint'),
        'error':society.get('error'),'transition':society.get('transition'),'game_days':obs.get('gameDays'),
        'weather':obs.get('weather'),'camera':obs.get('camera'),'camera_request':bridge.get('observer_camera'),
        'residents':residents,'businesses':list(town.get('businesses',{}).values()),
        'daily':town.get('daily'),'plan':society.get('plan'),'conversation':society.get('conversation'),
        'movement':obs.get('movement'),'work':obs.get('productionWork'),'rest':(obs.get('rest') or {}).get('activity'),
        'rests':society.get('rests',[])[-10:],'consumptions':society.get('consumptions',[])[-10:],
        'production':society.get('production',[])[-10:],
        'limits':['29 is the initialized census, not a claim of every Whiterun NPC.',
            'One resident plan executes at a time. Reviews and model workers run in bounded sessions.',
            'Traits, needs and relationship scores are gameplay models, not measured psychology.',
            'Autonomous social encounters, family households and broad production chains remain incomplete.']}
