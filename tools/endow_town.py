"""Deliver a frozen recipient batch from an explicitly selected finite scenario."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resource_manifest import load_manifest, manifest_hash
from tools.checkpoint_http import CheckpointHTTP
from tools.endow_population import fresh, require_program, require_capability, eligible_account, deliver


def batch_targets(state,manifest,maximum):
    if type(maximum) is not int or not 1<=maximum<=128:raise ValueError('Use a bounded maximum of 1 to 128 residents')
    program=require_program(state,manifest) or {};require_capability(state,manifest)
    known=((state['society'].get('town') or {}).get('residents') or {})
    granted=set((program.get('grants') or {}).keys());available=[];unavailable={}
    for key in sorted(known,key=int):
        if key in granted:continue
        actor=int(key)
        try:eligible_account(state,manifest,actor)
        except ValueError as error:unavailable[key]=str(error)
        else:available.append(actor)
    return available[:maximum],unavailable


def run_batch(client,manifest,runtime,maximum=32):
    before=fresh(client);targets,unavailable=batch_targets(before,manifest,maximum)
    session=before['bridge']['session']
    identities={actor:eligible_account(before,manifest,actor)['baseId'] for actor in targets}
    evidence={'before':before,'scenario':manifest,'scenario_id':manifest['id'],'scenario_hash':manifest_hash(manifest),
        'request_session':session,'request_checkpoint':before['society'].get('checkpoint'),
        'targets':targets,'recipient_base_ids':identities,'unavailable':unavailable,'completed':[],'status':'prepared','started_at':time.time()}
    path=Path(runtime)/('town-endowments-'+str(time.time_ns())+'.json')
    def record():path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    record()
    try:
        for actor in targets:
            state=fresh(client)
            if state['bridge']['session']!=session:raise ValueError('Game session changed; batch stopped')
            require_program(state,manifest)
            if eligible_account(state,manifest,actor)['baseId']!=identities[actor]:
                raise ValueError('Recipient identity changed; frozen batch stopped')
            result=deliver(client,manifest,actor,runtime)
            evidence['completed'].append({'actor':actor,'status':result['status'],'grant_id':result['receipt']['id']});record()
            print(json.dumps({'observed_receipts':len(evidence['completed']),'targeted':len(targets)}),flush=True)
        evidence.update(status='complete',after=fresh(client),elapsed_seconds=round(time.time()-evidence['started_at'],3))
        return evidence
    except Exception as error:evidence.update(status='held',error=str(error));raise
    finally:record();print(json.dumps({'status':evidence['status'],'evidence':str(path)}),flush=True)


def parser():
    result=argparse.ArgumentParser(description=__doc__)
    result.add_argument('--root',type=Path,required=True)
    result.add_argument('--scenario',type=Path,required=True,help='Explicit reviewed resource manifest JSON')
    result.add_argument('--maximum',type=int,default=32)
    return result


def main(argv=None):
    args=parser().parse_args(argv);manifest=load_manifest(args.scenario)
    runtime=args.root/'runtime';config=json.loads((runtime/'bridge-config.json').read_text(encoding='utf-8'))
    client=CheckpointHTTP(f"http://127.0.0.1:{config['port']}",config['token'],timeout=5,checkpoint_wait=10)
    run_batch(client,manifest,runtime,args.maximum)


if __name__=='__main__':main()
