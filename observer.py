"""Read-only society projection and a narrowly scoped local camera control."""
import math
import time
from collections import Counter
from statistics import mean
from enterprises import production_policy
from routing import activity_blocker
from dashboard import town_dashboard
from activity_metrics import activity_metrics
from owner_work_metrics import owner_work_metrics
from paid_employment_metrics import paid_employment_metrics
from employment_concurrency_metrics import snapshot_metrics
from independent_review_metrics import independent_review_metrics
import economy_catalog
from market_policy import tradable_ids, goods_policy, advertised_goods, policy_hash
from resident_identity import resident_identity_status
from entrepreneurship import recipe_knowledge
from livelihood_backgrounds import load_livelihood_manifest, livelihood_manifest_hash, authored_prior_status


def enterprise_editor_metadata():
    """Trusted configuration for editing opportunities, not native execution proof."""
    recipes=[]
    for rid in economy_catalog.recipe_ids():
        recipe=economy_catalog.recipe_spec(rid)
        defaults=production_policy({},rid)
        target='target_bread' if 'target_bread' in defaults else 'target_output'
        recipes.append({**recipe,'hash':economy_catalog.recipe_hash(rid),'fields':[
            {'key':'wage_gold','label':'Wage per shift (septims)','min':1,'max':20,'default':defaults['wage_gold']},
            {'key':'work_minutes','label':'Shift length (game minutes)','min':recipe['work_minutes']['minimum'],'max':recipe['work_minutes']['maximum'],'default':defaults['work_minutes']},
            {'key':target,'label':'Replenishment target (output units)','min':2,'max':40,'default':defaults[target]}]})
    return {'catalog_hash':economy_catalog.catalog_hash(),'market_policy_hash':policy_hash(),
        'commodities':[{'id':r['id'],'label':r['label'],'currency':r['currency']} for r in economy_catalog.ECONOMY_CATALOG['commodities']],
        'sale_goods':[{'id':rid,'legacy_capability':goods_policy(rid)['legacy_retail_capability']} for rid in tradable_ids()],
        'recipes':recipes}


def startup_projection(society,residents,current):
    town=society.get('town') or {}
    try:
        manifest=load_livelihood_manifest()
        scenario={'available':True,'id':manifest['id'],'hash':livelihood_manifest_hash(manifest),'provenance':manifest['provenance'],'rules':manifest['rules']}
    except (ValueError,OSError,KeyError) as error:
        scenario={'available':False,'reason':str(error)}
    return {'current':current,'initialized_residents':len(residents),
        'identity_qualified':sum(r['identity']['qualified'] for r in residents),
        'identity_reasons':dict(Counter(r['identity']['reason'] for r in residents if not r['identity']['qualified'])),
        'backgrounds':town.get('livelihood_backgrounds',[]),'scenario':scenario,
        'charters':len(town.get('businesses',{})),
        'paid_work_capability':society.get('paid_work_capability'),
        'committed_production':sum(r.get('status')=='committed' for r in society.get('production',[])),
        'committed_sales':sum(r.get('status')=='committed' for r in society.get('trades',[]))}


def camera_request(data, observation, society):
    mode=data.get('mode')
    if mode not in ('market','street','trade','focus','free','story','atlas','portrait'):
        raise ValueError('Unknown observer view')
    capture=data.get('capture',False)
    if type(capture) is not bool or capture and mode not in ('atlas','portrait'):
        raise ValueError('Capture requires an atlas or portrait view')
    result={'mode':mode,'capture':capture}
    if mode in ('focus','portrait'):
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
    current=connected and not society.get('transition') and not society.get('error') and obs.get('checkpoint')==society.get('checkpoint') and obs.get('ready') is True
    qualified_obs=obs if current else {}
    loaded={str(r['id']):r for r in obs.get('residents',[]) if r.get('isPerson') is True}
    stock={str(r['id']):r['inventory'] for r in obs.get('inventory_observations',[])}
    stock.update({key:r.get('inventory') for key,r in loaded.items()})
    town=society.get('town') or {}
    activities=activity_metrics(society,obs,fresh=connected)
    owner_work=owner_work_metrics(society,obs,fresh=connected)
    paid_work=paid_employment_metrics(society,obs,fresh=current)
    concurrency={**(bridge.get('employment_concurrency') or {}),**snapshot_metrics(society,obs,fresh=current)}
    independent_reviews=independent_review_metrics(society,obs,fresh=current)
    residents=[]
    for key,resident in town.get('residents',{}).items():
        person=society.get('people',{}).get(key,{})
        actor=loaded.get(key)
        residents.append({'id':int(key),'name':resident['name'],'loaded':bool(actor),'is_guard':resident.get('is_guard',False),
            'identity':resident_identity_status(society,qualified_obs,int(key)),
            'recipe_knowledge':recipe_knowledge(person,state=society,observation=qualified_obs,actor_id=int(key)),
            'authored_recipe_prior_status':{rid:authored_prior_status(society,qualified_obs,int(key),rid) for rid in person.get('authored_recipe_priors',{})},
            'baseId':actor.get('baseId') if actor else None,'space':actor.get('space') if actor else None,
            'position':[actor.get(k) for k in ('x','y','z')] if actor else None,
            'race':actor.get('race') if actor else None,
            'native_activity':actor.get('activity') if actor else None,
            'resident_control':next((a for a in (obs.get('resident_control') or {}).get('activities',[]) if a.get('actor')==int(key)),None),
            'activity_job':next((job for job in activities['jobs'] if job['actor']==int(key)),None),
            'owner_work_job':next((job for job in (owner_work or {}).get('jobs',[]) if job['actor']==int(key)),None),
            'activity_blocker':activity_blocker(actor) if actor else 'not_loaded',
            'inventory':stock.get(key),'person':person,'household':resident.get('household')})
    businesses = []
    for key, business in town.get('businesses', {}).items():
        # Operator-wide accounts are intentionally separate from resident prompts.
        businesses.append({**business, 'id':key, 'revision':business.get('revision',0),
            'active':business.get('active',True),
            'resolved_recipe_policies':{rid:production_policy(business,rid) for rid in business.get('capabilities',[]) if rid in economy_catalog.recipe_ids()},
            'advertised_goods':advertised_goods(business),
            'observed_inventory':stock.get(str(business['custodian'])),
            'account_scope':'Custodian inventory shared with household and any other charters; not a separate company wallet'})
    metrics=dict(society.get('metrics') or {})
    spatial=bridge.get('spatial')
    if spatial:
        metrics['spatial']=spatial
        metrics['quality_goals']={**metrics.get('quality_goals',{}),'items':[
            *(metrics.get('quality_goals') or {}).get('items',[]),*spatial.get('quality_goals',{}).get('items',[])]}
    metrics['population_breakdown']={'loaded_races':dict(Counter((r.get('race') or {}).get('name') or 'unknown' for r in residents if r['loaded'])),
        'personality_trait_means':{trait:round(mean(p['profile']['big_five'][trait] for p in society.get('people',{}).values() if trait in p.get('profile',{}).get('big_five',{})),3)
            for trait in sorted({t for p in society.get('people',{}).values() for t in p.get('profile',{}).get('big_five',{})})},
        'scope':'Race is current native descriptive metadata; unloaded races remain unknown. Personality traits are seeded independently of race. No group causal or psychological claims.'}
    return {'connected':connected,'observed_at':bridge.get('last_seen'),'checkpoint':society.get('checkpoint'),'session':obs.get('session'),
        'enterprise_editor':enterprise_editor_metadata(),'startup':startup_projection(society,residents,current),
        'error':society.get('error'),'transition':society.get('transition'),'game_days':obs.get('gameDays'),
        'audio_output':obs.get('audio_output'),'speech':obs.get('speech'),'player_controls':obs.get('player_controls'),
        'resident_control':obs.get('resident_control'),'activity_jobs':activities,'owner_work':owner_work,
        'weather':obs.get('weather'),'camera':obs.get('camera'),'camera_request':bridge.get('observer_camera'),
        'metrics':{**metrics,'activity_jobs':activities,'owner_work':owner_work,'paid_employment':paid_work,'employment_concurrency':concurrency,'independent_reviews':independent_reviews},'scene_handoffs':society.get('scene_handoffs',[]),'dashboard':{**town_dashboard({**society,'metrics':metrics},obs,spatial,fresh=connected),'activity_jobs':activities,'owner_work':owner_work,'paid_employment_metrics':paid_work,'employment_concurrency_metrics':concurrency,'independent_review_metrics':independent_reviews},
        'paid_employment_metrics':paid_work,
        'employment_concurrency_metrics':concurrency,
        'independent_review_metrics':independent_reviews,
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
            'Personal standing goals use up to 128 native slots; up to four goal model calls run concurrently in bounded waves. Foreground journeys and conversations take priority. Inventory transactions remain serialized.',
            'Traits, needs and relationship scores are gameplay models, not measured psychology.',
            'Family households, continuous town scheduling and broad production chains remain incomplete.']}
