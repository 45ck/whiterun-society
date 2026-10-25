"""Operator-wide town charts from observations, never resident knowledge."""
import math


def town_dashboard(society, observation):
    people=society.get('people',{});managed=(society.get('town') or {}).get('residents',{})
    loaded={str(r['id']):r for r in observation.get('residents',[]) if r.get('isPerson') is True}
    owned=set()
    def leases(value):
        if isinstance(value,dict):
            actor=str(value.get('actor'));row=loaded.get(actor);package=value.get('expectedPackage')
            if (row and value.get('ownedPackage') is True and type(package) is int and package>0
                    and (row.get('activity') or {}).get('package_id')==package):owned.add(actor)
            for child in value.values():leases(child)
        elif isinstance(value,list):
            for child in value:leases(child)
    for key in ('movement','parallel_routines','conversationAttendance','rest'):leases(observation.get(key))
    control={key:0 for key in ('agent','scene','native','unknown','unloaded')}
    for key in managed:
        row=loaded.get(key);activity=(row or {}).get('activity') or {}
        category=('unloaded' if row is None else 'agent' if key in owned else 'scene' if activity.get('scene_id')
                  else 'native' if activity.get('package_id') else 'unknown')
        control[category]+=1
    accounts={str(r['id']):r.get('inventory',{}) for r in observation.get('inventory_observations',[])}
    accounts.update({key:r.get('inventory',{}) for key,r in loaded.items()})
    stock={}
    for item in ('gold','bread','grain'):
        values=[accounts[k][item] for k in managed if k in accounts and type(accounts[k].get(item)) is int and accounts[k][item]>=0]
        stock[item]={'total':sum(values) if values else None,'accounts':len(values),'population':len(managed)}
    needs={}
    for name,threshold in (('hunger',.6),('fatigue',.8),('social_contact',.7)):
        values=[people.get(k,{}).get('needs',{}).get(name) for k in managed]
        values=[v for v in values if type(v) in (int,float) and math.isfinite(v) and 0<=v<=1]
        needs[name]={'high':sum(v>=threshold for v in values),'known':len(values),'threshold':threshold}
    economy=(society.get('metrics') or {}).get('economy',{})
    return {'population':len(managed),'loaded':sum(k in loaded for k in managed),'control':control,
        'control_scope':'Current observed package ownership, not long-term autonomy or quest compatibility.',
        'stock':stock,'needs':needs,'needs_scope':'Authored simulation needs, not measured human psychology.',
        'economy':{k:economy.get(k) for k in ('committed_sales','committed_production','committed_meals','active_enterprises')},
        'economy_scope':'Cumulative verified events in this save, including qualification experiments.'}
