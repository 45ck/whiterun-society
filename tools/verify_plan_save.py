"""Record or restore an isolated save and compare the complete society snapshot.

This never seeds resources or starts a model. A record is written only after the
ESS/cosave exist and the native save request has completed. Restoration requires
both original file hashes and a fresh game session before comparing state.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.request


def snapshot(state):
    return {'checkpoint': state['society']['checkpoint'],
            'plan': state['society']['plan'], 'people': state['society']['people'],
            'world': state['world'],
            'consumptions': state['society'].get('consumptions', []),
            'production': state['society'].get('production', []),
            'imports': state['society'].get('imports', []),
            'inventory': {str(a['id']): a['inventory']
                for a in state['bridge']['observation']['residents']
                if str(a['id']) in state['society']['people']}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'WS-[A-Za-z0-9_-]{1,48}', args.name):
        raise ValueError('Use an isolated WS- save name')
    runtime = args.root/'runtime'
    config = json.loads((runtime/'bridge-config.json').read_text())
    evidence_path = runtime/(args.name+'-plan-proof.json')
    save = args.root/'mod-organizer/profiles/Default/saves'/(args.name+'.ess')
    files = (save, save.with_suffix('.skse'))

    def request(route, data=None):
        req = urllib.request.Request(f"http://127.0.0.1:{config['port']}"+route,
            data=None if data is None else json.dumps(data).encode(),
            headers={'Authorization': 'Bearer '+config['token'], 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.load(response)

    def stable(state):
        seen = state['bridge']['last_seen']
        return (seen and time.time()-seen < 8 and not state['society']['error']
                and not state['society']['transition'] and not state['bridge']['command'])

    def wait(predicate, timeout=60):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            state = request('/state')
            if stable(state) and predicate(state):
                return state
            time.sleep(.5)
        raise TimeoutError('Fresh stable game state did not match the expected save')

    before = wait(lambda s: True)
    if args.restore:
        evidence = json.loads(evidence_path.read_text())
        for file in files:
            if hashlib.sha256(file.read_bytes()).hexdigest() != evidence['files'][file.name]['sha256']:
                raise ValueError('Recorded save changed; refusing ambiguous restore')
        request('/command', {'kind': 'load_game', 'name': args.name})
        restored = wait(lambda s: s['bridge']['session'] != before['bridge']['session']
                        and s['society']['checkpoint'] == evidence['expected']['checkpoint'])
        actual = snapshot(restored)
        comparison = {key: actual[key] == value for key, value in evidence['expected'].items()}
        evidence.setdefault('restores', []).append({'at': time.time(),
            'fresh_session': True, 'matches': comparison, 'actual': actual})
        evidence_path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(json.dumps({'restored': args.name, 'matches': comparison}), flush=True)
        if not all(comparison.values()):
            raise ValueError('Restored state differs from saved society state')
        return

    if evidence_path.exists() or any(file.exists() for file in files):
        raise ValueError('Refusing to overwrite an existing save or proof')
    plan = before['society']['plan']
    if plan and (plan['phase'] not in ('complete', 'held') or plan.get('release_required')):
        raise ValueError('This probe records settled plans only; active-plan recovery needs separate qualification')
    expected = snapshot(before)
    request('/command', {'kind': 'save_game', 'name': args.name})
    wait(lambda s: all(file.exists() and file.stat().st_size > 100 for file in files))
    # Ensure both files have finished writing, not merely appeared.
    sizes = [file.stat().st_size for file in files]
    time.sleep(1)
    if sizes != [file.stat().st_size for file in files]:
        raise ValueError('Save files are still changing; evidence not recorded')
    if snapshot(wait(lambda s: True)) != expected:
        raise ValueError('Society changed while saving; evidence not recorded')
    evidence = {'name': args.name, 'scope': 'Settled plan, people, inventory and journal; not long-term stability',
        'expected': expected, 'recorded_at': time.time(), 'files': {
            file.name: {'bytes': file.stat().st_size, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
            for file in files}}
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps({'saved': args.name, 'checkpoint': expected['checkpoint'], 'proof': str(evidence_path)}), flush=True)


if __name__ == '__main__':
    main()
