"""Claim a finite cohort, decide independently, then observe concurrent journeys."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from decisions import infer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--id',required=True)
    parser.add_argument('--events',nargs='+',required=True)
    parser.add_argument('--model-config',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=len(args.events)<=8:raise ValueError('One to eight resident events per bounded run')
    runtime=args.root/'runtime';config=json.loads((runtime/'bridge-config.json').read_text())
    model=json.loads(args.model_config.read_text());key=os.environ[model['key_env']] if model.get('key_env') else Path(model['key_file']).read_text().strip()
    def request(path,data=None):
        req=urllib.request.Request(f"http://127.0.0.1:{config['port']}"+path,None if data is None else json.dumps(data).encode(),
            headers={'Authorization':'Bearer '+config['token'],'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
        except urllib.error.HTTPError as e:raise ValueError(json.load(e).get('error','Request rejected')) from None
    def state():
        result=request('/state')
        if not result['bridge']['last_seen'] or time.time()-result['bridge']['last_seen']>10:raise ValueError('Stale game observation')
        if result['society']['error']:raise ValueError(result['society']['error'])
        return result
    evidence={'started_at':time.time(),'before':state(),'id':args.id,'model_calls':0,'samples':[]}
    path=runtime/('parallel-routines-'+hashlib.sha256(args.id.encode()).hexdigest()[:12]+'.json')
    def record():path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    result=request('/routines/start',{'id':args.id,'event_ids':args.events})
    if result.get('duplicate'):print(json.dumps({'duplicate':True,'model_calls':0}));return
    batch=result['batch'];deadline=time.monotonic()+240;record()
    def settled():
        while time.monotonic()<deadline:
            s=state()
            if s['bridge']['session']!=batch['session']:raise ValueError('Game session changed; do not repeat inference')
            if not s['society']['transition']:return s
            time.sleep(.3)
        raise TimeoutError('Cohort checkpoint did not bind')
    try:
        current=settled()['society']['routine_batch']
        if current['claim_id']!=batch['claim_id'] or current['phase']!='thinking':raise ValueError('Claim changed before inference')
        evidence['model_calls']=len(batch['members']);record()
        def decide(member):return {'event_id':member['event_id'],'result':infer(member['context'],model,key)}
        with ThreadPoolExecutor(max_workers=min(4,len(batch['members']))) as executor:results=list(executor.map(decide,batch['members']))
        evidence['results']=results;record()
        settled();request('/routines/decisions',{'id':args.id,'claim_id':batch['claim_id'],'results':results})
        while time.monotonic()<deadline:
            s=settled();current=s['society']['routine_batch'];native=s['bridge']['observation'].get('parallel_routines',{})
            evidence['samples'].append({'at':time.time(),'native':native});record()
            if current['phase'] in ('complete','held'):
                evidence.update(after=s,status=current['phase'],finished_at=time.time());record()
                print(json.dumps({'phase':current['phase'],'choices':[(m['actor'],m.get('result',{}).get('decision',{}).get('action_id'),m.get('outcome')) for m in current['members']],
                    'concurrency':current.get('concurrency'),'model_calls':evidence['model_calls'],'evidence':str(path)}),flush=True);return
            print(json.dumps({'phase':current['phase'],'peak_owned':native.get('peak_owned'),'activities':len(native.get('activities',[]))}),flush=True)
            time.sleep(2)
        raise TimeoutError('Cohort exceeded its execution bound; native leases remain time bounded')
    except Exception as error:
        evidence.update(status='held',error=str(error));record()
        try:request('/routines/hold',{'id':args.id,'reason':str(error)})
        except (OSError,ValueError):pass
        raise


if __name__=='__main__':main()
