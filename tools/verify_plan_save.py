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


def plugin_manifest(root):
    """Keep load order and our generated records bound to a managed save."""
    profile=root/'mod-organizer/profiles/Default/plugins.txt'
    if not profile.is_file():raise ValueError('Managed plugin list is unavailable')
    result=[]
    owned={'whiterunsociety.esp','whiterunagents.esp','whiterunrouter.esp','whiterunrest.esp','whiterunlanes.esp'}
    for line in profile.read_text(encoding='utf-8-sig').splitlines():
        if not line.startswith('*'):continue
        name=line[1:]
        if '/' in name or '\\' in name or not name.lower().endswith(('.esm','.esp','.esl')):
            raise ValueError('Invalid enabled plugin name')
        record={'name':name}
        if name.lower() in owned:
            record['sha256']=hashlib.sha256((root/'game/Data'/name).read_bytes()).hexdigest()
        result.append(record)
    return result


def plugins_compatible(expected, actual, addition=None):
    if expected==actual:return True
    return (addition=='WhiterunLanes.esp' and len(actual)==len(expected)+1 and actual[:-1]==expected
            and actual[-1].get('name')==addition and bool(actual[-1].get('sha256')))


def snapshot(state, inventory_ids=None):
    result={'checkpoint': state['society']['checkpoint'],
            'plan': state['society']['plan'], 'people': state['society']['people'],
            'world': state['world'],
            'consumptions': state['society'].get('consumptions', []),
            'production': state['society'].get('production', []),
            'cancelled_production': state['society'].get('cancelled_production', []),
            'unsettled_effect': state['society'].get('unsettled_effect'),
            'rests': state['society'].get('rests', []),
            'imports': state['society'].get('imports', []),
            'market_day': state['society'].get('market_day'),
            'conversation': state['society'].get('conversation'),
            'routine_batch': state['society'].get('routine_batch'),
            'town':state['society'].get('town'),
            'inventory': {str(a['id']): a['inventory']
                for a in state['bridge']['observation']['residents']
                if str(a['id']) in state['society']['people']}}
    if 'inventory_observations' in state['bridge']['observation']:
        result['asset_inventory']={str(a['id']):a['inventory'] for a in state['bridge']['observation']['inventory_observations']
            if str(a['id']) in state['society']['people']}
    if inventory_ids is not None:
        # Compare the same accounts after unloading, using fresh native reads.
        # Never fill a missing observation from the expected saved balances.
        observed={**result.get('asset_inventory',{}),**result['inventory']}
        result['inventory']={key:observed[key] for key in inventory_ids if key in observed}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--allow-added-plugin',choices=('WhiterunLanes.esp',))
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

    def stable(state, allow_uninitialized=False):
        seen = state['bridge']['last_seen']
        error_ok=not state['society']['error'] or (allow_uninitialized and state['society']['checkpoint']==0
            and state['society']['error']=='New world: initialize society or load a managed save')
        observation=state['bridge']['observation']
        inventory_ready='inventory_checkpoint' not in observation or observation['inventory_checkpoint']==state['society']['checkpoint']
        return (seen and time.time()-seen < 8 and error_ok and inventory_ready
                and not state['society']['transition'] and not state['bridge']['command'])

    def wait(predicate, timeout=60, allow_uninitialized=False):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            state = request('/state')
            if stable(state,allow_uninitialized) and predicate(state):
                return state
            time.sleep(.5)
        raise TimeoutError('Fresh stable game state did not match the expected save')

    before = wait(lambda s: True,allow_uninitialized=args.restore)
    if args.restore:
        evidence = json.loads(evidence_path.read_text())
        current_plugins=plugin_manifest(args.root)
        if 'plugins' in evidence and not plugins_compatible(evidence['plugins'],current_plugins,args.allow_added_plugin):
            raise ValueError('Enabled plugin order or generated plugin bytes differ from the recorded save')
        for file in files:
            if hashlib.sha256(file.read_bytes()).hexdigest() != evidence['files'][file.name]['sha256']:
                raise ValueError('Recorded save changed; refusing ambiguous restore')
        request('/command', {'kind': 'load_game', 'name': args.name})
        restored = wait(lambda s: s['bridge']['session'] != before['bridge']['session']
                        and s['society']['checkpoint'] == evidence['expected']['checkpoint'])
        actual = snapshot(restored,evidence['expected']['inventory'])
        comparison = {key: actual[key] == value for key, value in evidence['expected'].items()}
        evidence.setdefault('restores', []).append({'at': time.time(),'plugins':current_plugins,'allowed_addition':args.allow_added_plugin,
            'fresh_session': True, 'matches': comparison, 'actual': actual})
        evidence_path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(json.dumps({'restored': args.name, 'matches': comparison}), flush=True)
        if not all(comparison.values()):
            raise ValueError('Restored state differs from saved society state')
        return

    if evidence_path.exists() or any(file.exists() for file in files):
        raise ValueError('Refusing to overwrite an existing save or proof')
    plan = before['society']['plan']
    conversation=before['society'].get('conversation')
    batch=before['society'].get('routine_batch')
    if batch and (batch['phase'] not in ('complete','held') or batch.get('release_verified') is False):
        raise ValueError('This probe requires a settled cohort and verified native releases')
    if conversation and conversation['phase'] not in ('complete','held'):
        raise ValueError('This probe records settled conversations only')
    if before['society'].get('resource_delivery'):
        raise ValueError('Record a settled resource delivery, not a partial grant')
    if plan and (plan['phase'] not in ('complete', 'held') or plan.get('release_required')):
        raise ValueError('This probe records settled plans only; active-plan recovery needs separate qualification')
    expected = snapshot(before);plugins=plugin_manifest(args.root)
    request('/command', {'kind': 'save_game', 'name': args.name})
    wait(lambda s: all(file.exists() and file.stat().st_size > 100 for file in files))
    # Ensure both files have finished writing, not merely appeared.
    sizes = [file.stat().st_size for file in files]
    time.sleep(1)
    if sizes != [file.stat().st_size for file in files]:
        raise ValueError('Save files are still changing; evidence not recorded')
    observed_after_save=snapshot(wait(lambda s: True),expected['inventory'])
    if plugin_manifest(args.root)!=plugins:
        raise ValueError('Enabled plugin configuration changed while saving; evidence not recorded')
    if observed_after_save != expected:
        failure={'name':args.name,'status':'rejected','reason':'Society changed while saving',
            'differences':[key for key in expected if expected[key]!=observed_after_save[key]],
            'expected':expected,'observed_after_save':observed_after_save}
        (runtime/(args.name+'-save-rejected.json')).write_text(json.dumps(failure,indent=2),encoding='utf-8')
        raise ValueError('Society changed while saving; evidence not recorded')
    evidence = {'name': args.name, 'scope': 'Settled plan, people, inventory and journal; not long-term stability',
        'expected': expected, 'plugins':plugins, 'recorded_at': time.time(), 'files': {
            file.name: {'bytes': file.stat().st_size, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
            for file in files}}
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps({'saved': args.name, 'checkpoint': expected['checkpoint'], 'proof': str(evidence_path)}), flush=True)


if __name__ == '__main__':
    main()
