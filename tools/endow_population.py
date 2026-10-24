"""Deliver a finite, once-per-resident founding grant and retain native evidence."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--actor',type=int,required=True)
args=parser.parse_args();runtime=args.root/'runtime'
config=json.loads((runtime/'bridge-config.json').read_text())
def request(route,data=None):
    req=urllib.request.Request(f"http://127.0.0.1:{config['port']}"+route,
        None if data is None else json.dumps(data).encode(),headers={'Authorization':'Bearer '+config['token'],'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
    except urllib.error.HTTPError as error:raise ValueError(json.load(error).get('error','Request rejected')) from None
def fresh():
    state=request('/state')
    if not state['bridge']['last_seen'] or time.time()-state['bridge']['last_seen']>10:raise ValueError('Stale native observation')
    if state['society']['error']:raise ValueError(state['society']['error'])
    return state
before=fresh();session=before['bridge']['session']
# A fresh bridge needs one service round trip to learn the managed roster.
# Wait for accounting observations only; never repeat a write after a timeout.
ready_deadline=time.monotonic()+10
while not any(a.get('id')==args.actor and a.get('isPerson') is True
              for a in before['bridge']['observation'].get('inventory_observations',[])+before['bridge']['observation'].get('residents',[])):
    if time.monotonic()>ready_deadline:raise ValueError('Resident inventory is unavailable; no grant requested')
    time.sleep(.4);before=fresh()
    if before['bridge']['session']!=session:raise ValueError('Game session changed before delivery')
evidence={'actor':args.actor,'before':before,'started_at':time.time(),'status':'prepared'}
path=runtime/f'endowment-{args.actor}-{time.time_ns()}.json'
try:
    prepared=request('/town/endow',{'actor':args.actor});evidence['prepared']=prepared
    if prepared.get('duplicate'):
        evidence['status']='duplicate';evidence['after']=fresh()
    else:
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            state=fresh()
            if state['bridge']['session']!=session:raise ValueError('Save/session changed; delivery observer stopped')
            society=state['society'];delivery=society.get('resource_delivery')
            if delivery and delivery['status']=='held':raise ValueError('Native delivery held; explicit reconciliation required')
            grant=(society['town'].get('resource_program') or {}).get('grants',{}).get(str(args.actor))
            if grant and not society['transition']:
                evidence.update(status='committed',after=state,receipt=grant);break
            time.sleep(.4)
        else:raise TimeoutError('No committed grant observed; do not retry blindly')
except Exception as error:
    evidence.update(status='held',error=str(error));raise
finally:
    path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps({'status':evidence['status'],'evidence':str(path)}),flush=True)
