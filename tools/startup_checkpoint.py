"""Save-bound startup previews and one-shot writes; no unknown-outcome retry."""
import hashlib
import json
import math
from pathlib import Path
import time
from population import eligible_actors
from tools.checkpoint_http import CheckpointHTTP


def frozen(value):return json.loads(json.dumps(value,allow_nan=False))


def definition_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()


def client_for(runtime):
    config=json.loads((Path(runtime)/'bridge-config.json').read_text(encoding='utf-8'))
    return CheckpointHTTP(f"http://127.0.0.1:{config['port']}",config['token'],timeout=5,checkpoint_wait=10)


def fresh_state(client,bound=True):
    state=client('/state');bridge=state.get('bridge') or {};society=state.get('society') or {}
    observation=bridge.get('observation') or {};session=bridge.get('session');seen=bridge.get('last_seen')
    if (type(seen) not in (int,float) or not math.isfinite(seen) or not 0<=time.time()-seen<=10):
        raise ValueError('Fresh game observation required before startup configuration')
    if not isinstance(session,str) or not session or observation.get('session')!=session:
        raise ValueError('Bridge and observed game sessions must match')
    if observation.get('ready') is not True:raise ValueError('Game observation is not ready')
    if society.get('error'):raise ValueError(society['error'])
    if bound:
        marker=society.get('checkpoint')
        if (society.get('transition') or type(marker) is not int or marker<=0
            or type(observation.get('checkpoint')) is not int or observation['checkpoint']!=marker):
            raise ValueError('Startup requires a bound observed checkpoint')
    return frozen(state)


def observed_cohort(state,actor_ids=None):
    rows={row['id']:row for row in eligible_actors(state['bridge']['observation'])}
    selected=sorted(rows) if actor_ids is None else list(actor_ids)
    if (not selected or any(type(actor) is not int for actor in selected)
        or len(set(selected))!=len(selected)):
        raise ValueError('An explicit distinct observed adult cohort is required')
    cohort=[]
    for actor in sorted(selected):
        row=rows.get(actor) or {};base=row.get('baseId')
        if (not row or row.get('loaded') is False or row.get('isChild') is True or row.get('isDead') is True
            or any(key in row and type(row[key]) is not bool for key in ('loaded','isChild','isDead'))
            or type(base) is not int or not 0<base<=0xffffffff):
            raise ValueError('Every selected adult must be observed with its current base identity')
        cohort.append({'actor':actor,'base_id':base})
    return cohort


def unchanged_preflight(client,before,cohort):
    current=fresh_state(client)
    if current['bridge']['session']!=before['bridge']['session']:
        raise ValueError('Game session changed before startup mutation')
    if current['society']['checkpoint']!=before['society']['checkpoint']:
        raise ValueError('Checkpoint changed since preview; review a new preview')
    if observed_cohort(current,[row['actor'] for row in cohort])!=cohort:
        raise ValueError('Observed actor identities changed since preview')
    return current


def apply_checkpoint(client,route,body,before,cohort,confirms,runtime,kind,wait_seconds=30):
    """Persist intent, submit once, and distinguish pending from bound evidence."""
    payload=frozen(body);payload['expected_checkpoint']=before['society']['checkpoint']
    current=unchanged_preflight(client,before,cohort)
    if 'expected_cohort' in payload and observed_cohort(current)!=payload['expected_cohort']:
        raise ValueError('Observed census cohort changed since preview')
    path=Path(runtime)/(kind+'-'+hashlib.sha256(payload['id'].encode()).hexdigest()[:12]+'-'+str(time.time_ns())+'.json')
    evidence={'status':'request_in_flight','confirmed':False,'request':payload,
        'request_session':before['bridge']['session'],'request_checkpoint':before['society']['checkpoint'],
        'cohort':frozen(cohort),'started_at':time.time()}
    def record():path.write_text(json.dumps(evidence,indent=2,allow_nan=False),encoding='utf-8')
    record()
    try:
        # CheckpointHTTP encodes this body once. Only a certified pre-mutation
        # checkpoint_busy response permits its identical transport retry.
        result=client(route,frozen(payload));evidence['result']=frozen(result)
        duplicate=result.get('duplicate') is True
        target=before['society']['checkpoint'] if duplicate else result.get('checkpoint')
        if type(target) is not int or (not duplicate and target<=before['society']['checkpoint']):
            raise ValueError('Startup response lacks a new exact checkpoint; outcome unknown')
        evidence.update(status='checkpoint_pending',target_checkpoint=target);record()
        deadline=time.monotonic()+wait_seconds
        while True:
            after=fresh_state(client,bound=False)
            if after['bridge']['session']!=before['bridge']['session']:
                raise ValueError('Game session changed while observing startup checkpoint')
            society=after['society'];observation=after['bridge']['observation']
            if (not society.get('transition') and type(society.get('checkpoint')) is int
                and society['checkpoint']==target and type(observation.get('checkpoint')) is int
                and observation['checkpoint']==target):
                proof=confirms(after,result)
                if proof:
                    evidence.update(status='duplicate_confirmed' if duplicate else 'checkpoint_confirmed',confirmed=True,
                        confirmation={'session':after['bridge']['session'],'checkpoint':target,'observed_checkpoint':observation['checkpoint'],
                            'saved_record':frozen(proof)})
                    break
            if time.monotonic()>=deadline:
                evidence['limitation']='Prepared checkpoint not confirmed; no automatic mutation retry.'
                break
            time.sleep(.4)
    except Exception as error:
        evidence.update(status='observation_interrupted' if 'result' in evidence else 'request_outcome_unknown',error=str(error))
        error.add_note('Startup evidence: '+str(path)+'; status='+evidence['status']+'. Do not blindly replay the request.')
        raise
    finally:record()
    return {**evidence,'evidence':str(path)}
