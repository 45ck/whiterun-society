"""Verify one explicit destination command; not a model-selected routine."""
import json
from pathlib import Path
import time
import urllib.request
import urllib.error
import argparse

parser=argparse.ArgumentParser()
parser.add_argument('--method',choices=['package'],default='package')
parser.add_argument('--target',type=int,required=True)
parser.add_argument('--actor',type=int,required=True)
parser.add_argument('--dynamic',action='store_true',default=True,help='Compatibility flag: all probes use the dynamic mailbox')
parser.add_argument('--root',type=Path,default=Path('D:/WhiterunLab'))
args=parser.parse_args()

runtime=args.root/'runtime'
config=json.loads((runtime/'bridge-config.json').read_text())
def request(route,data=None):
    req=urllib.request.Request(f"http://127.0.0.1:{config['port']}"+route,
        None if data is None else json.dumps(data).encode(),
        headers={'Authorization':'Bearer '+config['token'],'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError('Local bridge rejected probe: '+error.read().decode()) from None

before=request('/state')
command=request('/command',{'kind':'walk_to','actor':args.actor,'target':args.target,'method':args.method,'dynamic':args.dynamic})
evidence={'command':command,'before':before['bridge']['observation'],'samples':[],
          'scope':'Explicit movement probe, not autonomous destination selection','passed':False}
deadline=time.monotonic()+140
while time.monotonic()<deadline:
    state=request('/state');observation=state['bridge']['observation']
    if observation['session']!=command['session']:raise RuntimeError('Game session changed')
    movement=observation.get('movement')
    if movement and movement['id']==command['id']:
        evidence['samples'].append(movement);print(json.dumps(movement),flush=True)
    ack=observation.get('ack') or {}
    if ack.get('id')==command['id']:
        evidence['ack']=ack;evidence['after']=observation
        evidence['passed']=ack.get('status')=='applied' and ack['movement']['startDistance']>250 and ack['movement']['distance']<=250
        if args.method=='package':evidence['passed']=evidence['passed'] and ack['movement']['hasOwnedPackage']
        movement=ack.get('movement') or {}
        evidence['passed']=evidence['passed'] and movement.get('aliasesConfirmed') is True and movement.get('adapter')=='papyrus-mailbox' and movement.get('actor')==args.actor and movement.get('target')==args.target
        break
    time.sleep(2)
(runtime/('movement-'+args.method+'-'+command['id']+'-evidence.json')).write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print(json.dumps({'passed':evidence['passed']}),flush=True)
if not evidence['passed']:raise SystemExit(1)
