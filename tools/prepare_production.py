"""Explicitly import two grain once into a synchronized lab society.

This is scenario setup, not resident production. It never creates gold and cannot
replenish an already imported lineage. The authoritative service enforces both.
"""
import argparse
import json
from pathlib import Path
import time
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    runtime=args.root/'runtime'
    config=json.loads((runtime/'bridge-config.json').read_text())
    def request(route,data=None):
        r=urllib.request.Request(f"http://127.0.0.1:{config['port']}"+route,
            None if data is None else json.dumps(data).encode(),
            headers={'Authorization':'Bearer '+config['token'],'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(r,timeout=15) as response:return json.load(response)
        except urllib.error.HTTPError as error:
            raise ValueError(json.load(error).get('error','Scenario setup rejected')) from None
    before=request('/state')
    result=request('/world/setup-production',{})
    if result.get('duplicate'):
        print(json.dumps({'duplicate':True,'added_grain':0}));return
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        state=request('/state')
        if state['society']['imports'] and not state['society']['transition']:
            evidence={'scope':'Explicit finite grain import, not production','before':before,'after':state}
            path=runtime/'production-setup.json'
            path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
            print(json.dumps({'checkpoint':state['society']['checkpoint'],'imported_grain':2,'evidence':str(path)}))
            return
        time.sleep(.5)
    raise TimeoutError('Import was not observed; inspect pending state before retrying')


if __name__=='__main__':main()
