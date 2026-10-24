"""Run one finite market-day scenario, with save-bound stages and no automatic retries.

Uses a ready lab game, or launches it if no lab bridge is connected. A fresh world
gets explicitly prepared demo bread and two grain; existing managed saves are not
reset or replenished. Requires the configured model key in its environment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

SOURCE=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--id',required=True)
    parser.add_argument('--model-config',type=Path,required=True)
    parser.add_argument('--audio-diagnostic',action='store_true')
    args=parser.parse_args();runtime=args.root/'runtime'
    config_path=runtime/'bridge-config.json'
    def config():return json.loads(config_path.read_text())
    def request(route,data=None):
        c=config()
        req=urllib.request.Request(f"http://127.0.0.1:{c['port']}"+route,
            None if data is None else json.dumps(data).encode(),
            headers={'Authorization':'Bearer '+c['token'],'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=15) as response:return json.load(response)
        except urllib.error.HTTPError as error:
            raise ValueError(json.load(error).get('error','Request rejected')) from None
    def child(name,*arguments):
        subprocess.run([sys.executable,str(SOURCE/'tools'/name),*map(str,arguments)],cwd=SOURCE,check=True)
    def wait_ready(predicate,timeout=30):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            s=request('/state');seen=s['bridge']['last_seen']
            if seen and time.time()-seen<8 and not s['society']['transition'] and predicate(s):return s
            time.sleep(.5)
        raise TimeoutError('Scenario state did not settle; no automatic retry')
    try:connected=request('/health')['bridge_connected']
    except (OSError,ValueError):connected=False
    if not connected:child('launch_demo.py','--root',args.root,*(['--audio-diagnostic'] if args.audio_diagnostic else []))
    state=wait_ready(lambda s:True)
    if args.audio_diagnostic and not state['bridge']['observation'].get('audioDiagnostic'):
        raise ValueError('This connected game is not in audio diagnostic mode')
    if state['society']['checkpoint']==0:
        command=request('/command',{'kind':'prepare_market'})
        prepared=wait_ready(lambda s:(s['bridge']['last_ack'] or {}).get('id')==command['id'])
        if prepared['bridge']['last_ack']['status']!='applied':raise ValueError('Demo bread setup failed')
        request('/world/bootstrap',{})
        wait_ready(lambda s:not s['society']['error'])
        child('prepare_production.py','--root',args.root)
    # No persistent client-side cursor: the loaded game checkpoint owns progress.
    result=request('/market-day/start',{'id':args.id})
    if result.get('duplicate') and result['scenario']['status']=='complete':
        print(json.dumps({'duplicate':True,'model_calls':0,'scenario':result['scenario']}));return
    path=runtime/('market-day-'+hashlib.sha256(args.id.encode()).hexdigest()[:12]+'.json')
    evidence={'id':args.id,'started_at':time.time(),'before':state,'events':[]}
    while True:
        state=wait_ready(lambda s:not s['society']['error'])
        day=state['society']['market_day']
        if not day or day['id']!=args.id:raise ValueError('Loaded save no longer belongs to this market day')
        if day['status']!='running':
            evidence.update(after=state,status=day['status'])
            path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
            print(json.dumps({'status':day['status'],'scenario':day,'evidence':str(path)}))
            if day['status']!='complete':raise ValueError('Market day held; inspect its evidence')
            return
        event=day['next_event'];plan=state['society']['plan']
        if plan and plan['id']==event['id']:
            if plan['phase'] not in ('complete','held') or plan.get('release_required') or not plan.get('remembered'):
                raise ValueError('A stage already exists but is not settled; do not repeat inference')
        else:
            child('run_resident_event.py','--runtime',runtime,'--event-id',event['id'],
                  '--actor',event['actor'],'--kind',event['kind'],'--model-config',args.model_config)
        settled=wait_ready(lambda s:s['society']['plan'] and s['society']['plan']['id']==event['id'] and
            s['society']['plan'].get('remembered') and not s['society']['plan'].get('release_required'))
        evidence['events'].append({'id':event['id'],'checkpoint':settled['society']['checkpoint'],
                                   'outcome':settled['society']['plan'].get('outcome')})
        path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        request('/market-day/advance',{'id':args.id,'event_id':event['id']})


if __name__=='__main__':main()
