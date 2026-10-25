"""Operator-wide town charts from observations, never resident knowledge."""
import math
from activity_metrics import activity_metrics
from owner_work_metrics import owner_work_metrics
from economy_catalog import ECONOMY_CATALOG, catalog_hash, commodity_ids, recipe_ids, native_catalog_matches


def inventory_catalog_status(observation, fresh=True):
    native=observation.get('economy_catalog')
    report=native if isinstance(native,dict) else {}
    expected=catalog_hash();verified=fresh is True and native_catalog_matches(observation)
    if fresh is not True:
        status,reason='stale','The latest game observation is stale; current item verification is unknown.'
    elif not report:
        status,reason='missing','No game-item verification report has arrived.'
    elif report.get('available') is not True:
        status,reason='unavailable','The game could not resolve or validate all configured items.'
    elif report.get('catalog_hash')!=expected:
        status,reason='mismatch','Game item definitions differ from the configured definitions.'
    elif report.get('type_verified') is not True or report.get('errors')!={}:
        status,reason='unavailable','Game item types have not all been verified.'
    elif not verified:
        status,reason='mismatch','Game item or recipe identities differ from the configured definitions.'
    else:
        status,reason='verified','Game items match the configured definitions. Each inventory action still needs its own verified receipt.'
    errors=report.get('errors')
    diagnostics=[{'item':str(key),'reason':str(value)[:300]} for key,value in errors.items()] if isinstance(errors,dict) else []
    return {'status':status,'fresh':fresh is True,'verified':verified,'reason':reason,
        'configured_item_count':len(commodity_ids()),'configured_recipe_count':len(recipe_ids()),
        'verified_native_item_count':len(commodity_ids()) if verified else None,
        'configured_version':ECONOMY_CATALOG['version'],'configured_hash':expected,
        'reported_hash':report.get('catalog_hash') if isinstance(report.get('catalog_hash'),str) else None,
        'diagnostics':diagnostics,'scope':'Configuration and game-item verification only; counts are not stock, executed recipes or completed production.'}


def town_dashboard(society, observation, spatial=None, fresh=True):
    people=society.get('people',{});managed=(society.get('town') or {}).get('residents',{})
    loaded={str(r['id']):r for r in observation.get('residents',[]) if r.get('isPerson') is True}
    activities=activity_metrics(society,observation)
    owned=set()
    def leases(value):
        if isinstance(value,dict):
            actor=str(value.get('actor'));row=loaded.get(actor);package=value.get('expectedPackage')
            if (row and value.get('ownedPackage') is True and type(package) is int and package>0
                    and (row.get('activity') or {}).get('package_id')==package):owned.add(actor)
            for child in value.values():leases(child)
        elif isinstance(value,list):
            for child in value:leases(child)
    for key in ('movement','parallel_routines','conversationAttendance','rest','productionWork'):leases(observation.get(key))
    observed_jobs={(job['id'],job['actor'],job['target'],job['slot']) for job in activities['jobs'] if job['native_observed']}
    for job in (observation.get('activity_jobs') or {}).get('jobs',[]):
        identity=(job.get('job_id',job.get('id')),job.get('actor'),job.get('target'),job.get('slot'))
        rest=job.get('rest') or {};route=rest.get('route') or {}
        if (identity in observed_jobs and rest.get('id')==identity[0]
                and type(rest.get('actor')) is int and rest['actor']==job.get('actor')
                and type(rest.get('target')) is int and rest['target']==job.get('target')
                and type(route.get('actor')) is int and route['actor']==job.get('actor')):
            leases(route)
    standby=set()
    for a in (observation.get('resident_control') or {}).get('activities',[]):
        actor=str(a.get('actor'));row=loaded.get(actor);package=a.get('expectedPackage')
        if row and a.get('ownedPackage') is True and type(package) is int and package>0 and (row.get('activity') or {}).get('package_id')==package:
            (owned if a.get('mode')=='go_to' and a.get('phase') in ('travelling','arrived') else standby).add(actor)
    control={key:0 for key in ('agent','standby','scene','native','unknown','unloaded')}
    for key in managed:
        row=loaded.get(key);activity=(row or {}).get('activity') or {}
        category=('unloaded' if row is None else 'agent' if key in owned else 'scene' if activity.get('scene_id') else 'standby' if key in standby
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
    goals=[people.get(k,{}).get('standing_goal') or {} for k in managed if k in loaded]
    autonomy={'loaded_population':len(goals),'with_goal':sum(g.get('phase') in ('travelling','quiet','arrived') for g in goals),
        'awaiting_first_goal':sum(not g for g in goals),'held_goals':sum(g.get('phase')=='held' for g in goals),
        'claimed_decisions':sum(len(w['members']) for w in (society.get('town') or {}).get('goal_waves',[]) if w['phase']=='thinking'),
        'walking_now':sum(str(a['actor']) in owned and a.get('mode')=='go_to' and a.get('phase')=='travelling' for a in (observation.get('resident_control') or {}).get('activities',[])),
        'arrivals':sum(m.get('kind')=='standing_goal_arrival' for p in people.values() for m in p.get('memories',[])),
        'scope':'Current loaded managed residents. Claims are pending requests, not constant inference. Arrival is not economic output.'}
    metrics=society.get('metrics') or {}
    return {'population':len(managed),'loaded':sum(k in loaded for k in managed),'control':control,'autonomy':autonomy,
        'inventory_catalog':inventory_catalog_status(observation,fresh=fresh),
        'resource_program':(society.get('town') or {}).get('resource_program'),
        'spatial':spatial,'agency':metrics.get('agency'),'economic_network':metrics.get('economic_network'),
        'activity_jobs':activities,
        'owner_work':owner_work_metrics(society,observation),
        'drama':metrics.get('drama'),'quality_goals':metrics.get('quality_goals'),
        'control_scope':'Current observed package ownership, not long-term autonomy or quest compatibility.',
        'stock':stock,'needs':needs,'needs_scope':'Authored simulation needs, not measured human psychology.',
        'economy':{k:economy.get(k) for k in ('committed_sales','committed_production','committed_meals','active_enterprises','resident_enterprise_changes','operator_enterprise_changes','household_release_sales','negotiations','wording')},
        'economy_scope':'Cumulative verified events in this save, including qualification experiments.'}
