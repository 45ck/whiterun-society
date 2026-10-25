"""Observe one explicitly selected finite external import; never retry unknown writes."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from economy_catalog import commodity_ids, native_catalog_matches
from resource_manifest import load_manifest, manifest_hash, select_grant
from tools.checkpoint_http import CheckpointHTTP


def fresh(client):
    state=client('/state');bridge=state.get('bridge') or {};society=state.get('society') or {}
    if not bridge.get('last_seen') or time.time()-bridge['last_seen']>10:
        raise ValueError('Stale native observation; no resource delivery authorized')
    if society.get('error'):raise ValueError(society['error'])
    return state


def require_program(state,manifest):
    program=((state.get('society') or {}).get('town') or {}).get('resource_program')
    if program:
        if program.get('protocol')!=2:
            raise ValueError('Historical resource program is read-only; a new scenario cannot replace it')
        if program.get('id')!=manifest['id'] or program.get('manifest_hash')!=manifest_hash(manifest):
            raise ValueError('Saved resource scenario differs from the explicitly selected scenario')
    return program


def observed_accounts(state):
    observation=state['bridge']['observation']
    accounts={row['id']:row for row in observation.get('inventory_observations',[])}
    accounts.update({row['id']:row for row in observation.get('residents',[])})
    return accounts


def eligible_account(state,manifest,actor):
    town=(state['society'].get('town') or {})
    if str(actor) not in town.get('residents',{}):raise ValueError('Recipient is not initialized in this census')
    row=observed_accounts(state).get(actor,{})
    if row.get('isPerson') is not True:raise ValueError('Recipient has no observed adult classification')
    base=row.get('baseId')
    if type(base) is not int or base<=0:raise ValueError('Recipient base identity is unobserved; no import requested')
    inventory=row.get('inventory') or {}
    if any(type(inventory.get(k)) is not int or inventory[k]<0 for k in commodity_ids()):
        raise ValueError('Recipient commodity inventory is incomplete; no import requested')
    select_grant(manifest,actor,base)
    return row


def require_capability(state,manifest):
    observation=state['bridge']['observation'];capability=observation.get('resource_import') or {}
    if not native_catalog_matches(observation):raise ValueError('Game items are not verified; inventory actions must wait')
    if (capability.get('available') is not True or capability.get('protocol')!=2
        or capability.get('manifest_hash')!=manifest_hash(manifest)
        or capability.get('catalog_hash')!=manifest['catalog_hash']
        or not isinstance(capability.get('epoch'),str) or not capability['epoch']):
        raise ValueError('Matching native resource-import capability is unavailable; no import requested')


def matching_receipt(state,manifest,actor,base,prepared):
    program=require_program(state,manifest) or {};record=(program.get('grants') or {}).get(str(actor))
    if not record:return None
    command=record.get('command') or {};selection=select_grant(manifest,actor,base)
    expected_id=prepared.get('grant_id') or (prepared.get('grant') or {}).get('id')
    if (not isinstance(record.get('id'),str) or not record['id'] or record.get('status')!='committed' or command.get('protocol')!=2 or command.get('phase')!='deliver'
        or command.get('source')!=manifest['id'] or command.get('manifest_hash')!=manifest_hash(manifest)
        or command.get('catalog_hash')!=manifest['catalog_hash']
        or command.get('grant')!=selection['grant'] or command.get('grant_hash')!=selection['grant_hash']
        or command.get('actor')!=actor or command.get('actor_base_id')!=base
        or record.get('id')!=command.get('grant_id')
        or expected_id is not None and record.get('id')!=expected_id):
        raise ValueError('Saved import receipt does not match this selected scenario and recipient')
    return record


def deliver(client,manifest,actor,runtime,wait_seconds=45):
    before=fresh(client);require_program(before,manifest);require_capability(before,manifest)
    row=eligible_account(before,manifest,actor)
    session=before['bridge']['session'];checkpoint=before['society'].get('checkpoint')
    evidence={'actor':actor,'actor_base_id':row['baseId'],'scenario_id':manifest['id'],
        'scenario_hash':manifest_hash(manifest),'scenario':manifest,'request_session':session,
        'request_checkpoint':checkpoint,'before':before,'started_at':time.time(),'status':'not_requested'}
    path=Path(runtime)/f'endowment-{actor}-{time.time_ns()}.json'
    def record():path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    record()
    try:
        # CheckpointHTTP retries only certified pre-mutation checkpoint conflicts.
        # A timeout, connection failure or unknown response is never resubmitted.
        evidence['status']='request_in_flight';record()
        prepared=client('/town/endow',{'actor':actor,'scenario_id':manifest['id'],'scenario_hash':manifest_hash(manifest)})
        evidence.update(prepared=prepared,status='observing');record()
        deadline=time.monotonic()+wait_seconds
        while time.monotonic()<deadline:
            state=fresh(client)
            if state['bridge']['session']!=session:raise ValueError('Game session changed; import observation stopped')
            require_program(state,manifest)
            pending=state['society'].get('resource_delivery') or {}
            if pending.get('status')=='held' and (pending.get('actor',pending.get('command',{}).get('actor'))==actor):
                raise ValueError('Import delivery is held; reconcile its receipt before any new request')
            receipt=matching_receipt(state,manifest,actor,row['baseId'],prepared)
            if receipt and not state['society'].get('transition'):
                evidence.update(status='duplicate' if prepared.get('duplicate') else 'committed',after=state,receipt=receipt)
                return evidence
            time.sleep(.4)
        raise TimeoutError('No matching committed import observed; do not retry blindly')
    except Exception as error:
        evidence.update(status='held',error=str(error));raise
    finally:
        record();print(json.dumps({'status':evidence['status'],'evidence':str(path)}),flush=True)


def parser():
    result=argparse.ArgumentParser(description=__doc__)
    result.add_argument('--root',type=Path,required=True)
    result.add_argument('--actor',type=int,required=True)
    result.add_argument('--scenario',type=Path,required=True,help='Explicit reviewed resource manifest JSON')
    return result


def main(argv=None):
    args=parser().parse_args(argv);manifest=load_manifest(args.scenario)
    runtime=args.root/'runtime';config=json.loads((runtime/'bridge-config.json').read_text(encoding='utf-8'))
    client=CheckpointHTTP(f"http://127.0.0.1:{config['port']}",config['token'],timeout=5,checkpoint_wait=10)
    deliver(client,manifest,args.actor,runtime)


if __name__=='__main__':main()
