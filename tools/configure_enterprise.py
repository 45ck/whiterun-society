"""Apply an explicit enterprise specification to the current isolated game save."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--spec', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((args.runtime/'bridge-config.json').read_text())
    spec = json.loads(args.spec.read_text(encoding='utf-8-sig'))
    def request(route, data=None):
        req = urllib.request.Request(f"http://127.0.0.1:{config['port']}" + route,
            data=None if data is None else json.dumps(data).encode(),
            headers={'Authorization':'Bearer '+config['token'], 'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise ValueError(json.load(error).get('error','Request rejected')) from None
    before = request('/state')
    result = request('/town/enterprise', {'id':args.id, 'enterprise':spec})
    if result.get('duplicate'):
        print(json.dumps(result)); return
    deadline = time.monotonic()+30
    while time.monotonic()<deadline:
        after = request('/state')
        if after['bridge']['session']!=before['bridge']['session']:
            raise ValueError('Save changed during enterprise configuration')
        if after['society']['error']:
            raise ValueError(after['society']['error'])
        if not after['society']['transition'] and after['society']['checkpoint']==result['checkpoint']:
            name='enterprise-'+hashlib.sha256(args.id.encode()).hexdigest()[:12]+'.json'
            path=args.runtime/name
            path.write_text(json.dumps({'result':result, 'before':before, 'after':after},indent=2),encoding='utf-8')
            print(json.dumps({'checkpoint':result['checkpoint'], 'business':result['business'], 'evidence':str(path)})); return
        time.sleep(.4)
    raise TimeoutError('Enterprise checkpoint was not observed')


if __name__=='__main__':main()
