"""Bounded founding grants for already initialized, natively observed accounts."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--maximum',type=int,default=32)
args=parser.parse_args()
if not 1<=args.maximum<=128:raise ValueError('Use a bounded maximum of 1 to 128 residents')
runtime=args.root/'runtime';config=json.loads((runtime/'bridge-config.json').read_text())
def state():
    req=urllib.request.Request(f"http://127.0.0.1:{config['port']}/state",headers={'Authorization':'Bearer '+config['token']})
    with urllib.request.urlopen(req,timeout=5) as response:result=json.load(response)
    if not result['bridge']['last_seen'] or time.time()-result['bridge']['last_seen']>10:raise ValueError('Stale game observation')
    return result
before=state();session=before['bridge']['session'];town=before['society']['town']
known=set(town['residents']);granted=set((town.get('resource_program') or {}).get('grants',{}))
available={str(a['id']) for a in before['bridge']['observation'].get('inventory_observations',[]) if a.get('isPerson') is True}
targets=sorted(int(k) for k in (known & available)-granted)[:args.maximum]
evidence={'before':before,'targets':targets,'unavailable':sorted(known-available),'completed':[],'status':'running','started_at':time.time()}
path=runtime/('town-endowments-'+str(time.time_ns())+'.json')
def record():path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
record()
try:
    for actor in targets:
        if state()['bridge']['session']!=session:raise ValueError('Game session changed; batch stopped')
        subprocess.run([sys.executable,str(Path(__file__).with_name('endow_population.py')),'--root',str(args.root),'--actor',str(actor)],check=True)
        evidence['completed'].append(actor);record()
        print(json.dumps({'delivered':len(evidence['completed']),'targeted':len(targets)}),flush=True)
    evidence.update(status='complete',after=state(),elapsed_seconds=round(time.time()-evidence['started_at'],3))
except Exception as error:evidence.update(status='held',error=str(error));raise
finally:record();print(json.dumps({'status':evidence['status'],'evidence':str(path)}),flush=True)
