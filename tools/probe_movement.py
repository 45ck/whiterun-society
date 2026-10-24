"""Verify one explicit destination command; not a model-selected routine."""
import json
from pathlib import Path
import time
import urllib.request
import argparse

parser=argparse.ArgumentParser()
parser.add_argument('--method',choices=['path','offset','package'],default='path')
parser.add_argument('--target',type=int,choices=[108149,108156],default=108149)
args=parser.parse_args()

runtime=Path('D:/WhiterunLab/runtime')
config=json.loads((runtime/'bridge-config.json').read_text())
def request(route,data=None):
    req=urllib.request.Request(f"http://127.0.0.1:{config['port']}"+route,
        None if data is None else json.dumps(data).encode(),
        headers={'Authorization':'Bearer '+config['token'],'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)

before=request('/state')
command=request('/command',{'kind':'walk_to','actor':108186,'target':args.target,'method':args.method})
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
        break
    time.sleep(2)
(runtime/('movement-'+args.method+'-evidence.json')).write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print(json.dumps({'passed':evidence['passed']}),flush=True)
