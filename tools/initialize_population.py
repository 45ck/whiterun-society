"""Initialize observed adult residents in the current save without minting stock."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--id',required=True);p.add_argument('--seed',required=True);args=p.parse_args()
    runtime=args.root/'runtime';config=json.loads((runtime/'bridge-config.json').read_text())
    def request(route,data=None):
        req=urllib.request.Request(f"http://127.0.0.1:{config['port']}"+route,
            data=None if data is None else json.dumps(data).encode(),headers={'Authorization':'Bearer '+config['token'],'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)
        except urllib.error.HTTPError as e:raise ValueError(json.load(e).get('error','Rejected')) from None
    before=request('/state')
    if time.time()-(before['bridge']['last_seen'] or 0)>8:raise ValueError('Fresh game census required')
    result=request('/town/initialize',{'id':args.id,'seed':args.seed})
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        after=request('/state')
        if after['bridge']['session']!=before['bridge']['session']:raise ValueError('Session changed during census')
        if after['society']['error']:raise ValueError(after['society']['error'])
        if not after['society']['transition'] and after['society'].get('town'):
            name='population-'+hashlib.sha256(args.id.encode()).hexdigest()[:12]+'.json'
            path=runtime/name
            # Duplicate calls must not replace the original before/after evidence.
            if not result.get('duplicate'):
                path.write_text(json.dumps({'result':result,'before':before,'after':after,'at':time.time()},indent=2),encoding='utf-8')
            print(json.dumps({'result':result,'counts':after['society']['town']['counts'],'evidence':str(path)}));return
        time.sleep(.4)
    raise TimeoutError('Census checkpoint did not bind')


if __name__=='__main__':main()
