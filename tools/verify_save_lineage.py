"""Authored lab stock/trade/save trial using an explicit observed population census.

Fresh profiles use uniform scenario-seeded traits; old fixed-profile trial choices
are not reproduced. Resume/restore paths preserve saved profiles and census seeds.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import sys
import urllib.request
import urllib.error


SOURCE = Path(__file__).resolve().parents[1]
if str(SOURCE) not in sys.path:sys.path.insert(0,str(SOURCE))
from tools.authored_population import initialize_fresh_population, validate_participants


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--resume-before-trade', action='store_true')
    parser.add_argument('--restore-existing', action='store_true')
    args = parser.parse_args()
    runtime = args.root / 'runtime'
    config = json.loads((runtime / 'bridge-config.json').read_text())
    evidence = {'run_id': args.run_id, 'steps': [], 'passed': False,
                'fixture': 'Explicitly provision Carlotta to three carried loaves before checkpoint bootstrap; no gold minted.'}
    output = runtime / 'save-lineage-evidence.json'
    if args.resume_before_trade:
        evidence=json.loads(output.read_text())
        if evidence['run_id']!=args.run_id or [s['label'] for s in evidence['steps']]!=['before']:
            raise ValueError('Resume only supports this recorded pre-trade checkpoint')
    if args.restore_existing:
        evidence=json.loads(output.read_text())
        if evidence['run_id']!=args.run_id or [s['label'] for s in evidence['steps']]!=['before','after','duplicate']:
            raise ValueError('Restore verification requires the recorded before/after trade states')
        evidence['recovery']='Restore verification rerun after correcting loadGame/preLoadGame event ordering to the SKSE pre/post pair.'

    def request(route, data=None, *, session=None):
        req = urllib.request.Request(f"http://127.0.0.1:{config['port']}" + route,
            data=None if data is None else json.dumps(data).encode(),
            headers={'Authorization': 'Bearer ' + config['token'], 'Content-Type': 'application/json',
                     **({'X-Society-Session':session} if session is not None else {})})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise ValueError(error.read().decode()) from error

    def wait(predicate, label, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = request('/state')
            if state['bridge']['last_seen'] and time.time() - state['bridge']['last_seen'] < 10 and predicate(state):
                print(label, flush=True)
                return state
            time.sleep(1)
        raise TimeoutError(label)

    def inventory(state):
        return {str(a['id']): a['inventory'] for a in state['bridge']['observation']['residents']
                if a['id'] in (108149, 108186)}

    def record(label, state):
        item = {'label': label, 'checkpoint': state['society']['checkpoint'], 'inventory': inventory(state),
                'world': state['world'], 'people': state['society']['people'], 'at': time.time()}
        evidence['steps'].append(item)
        output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        return item

    def stable(state):
        return not state['society']['error'] and not state['society']['transition']

    def save(name):
        request('/command', {'kind': 'save_game', 'name': name})
        path = args.root / 'mod-organizer/profiles/Default/saves' / (name + '.ess')
        deadline = time.monotonic() + 30
        previous = None
        while time.monotonic() < deadline:
            if path.exists() and path.with_suffix('.skse').exists():
                size = path.stat().st_size
                if size == previous and size > 1000:
                    evidence.setdefault('saves', []).append({'name': name, 'bytes': size,
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
                    print('Saved ' + name, flush=True)
                    wait(lambda s: s['bridge']['command'] is None, 'Save request acknowledged')
                    return
                previous = size
            time.sleep(1)
        raise TimeoutError('Save file was not written: ' + name)

    try:
        if args.restore_existing:
            expected_states={s['label']:s for s in evidence['steps']}
            for suffix, label in [('A','before'),('B','after')]:
                expected=expected_states[label]
                name='WS-'+args.run_id+'-'+suffix
                save_record=next(s for s in evidence['saves'] if s['name']==name)
                saved=args.root/'mod-organizer/profiles/Default/saves'/(name+'.ess')
                if hashlib.sha256(saved.read_bytes()).hexdigest()!=save_record['sha256']:
                    raise ValueError('Recorded save has changed')
                request('/command',{'kind':'load_game','name':name})
                restored=record('restored-'+suffix,wait(lambda s: stable(s) and s['society']['checkpoint']==expected['checkpoint'],'Restored checkpoint '+suffix))
                assert restored['inventory']==expected['inventory'],'Inventory mismatch after load'
                assert restored['world']==expected['world'],'Journal mismatch after load'
                assert restored['people']==expected['people'],'Memories or relationships mismatch after load'
            evidence['passed']=True
            print(json.dumps({'passed':True,'evidence':str(output)}),flush=True)
            return
        start = request('/state')
        if args.resume_before_trade:
            before=evidence['steps'][0]
            evidence.setdefault('population_initialization',{'policy':'preserved-managed-save','source':'Resume preserves recorded profiles, memories and seed; no census'})
            if not stable(start) or start['society']['checkpoint']!=before['checkpoint'] or start['world']!=before['world'] or inventory(start)!=before['inventory'] or start['society']['people']!=before['people']:
                raise ValueError('Recorded pre-trade state no longer matches the game')
        else:
            if start['society']['checkpoint'] != 0:
                raise ValueError('This fresh-world test refuses to overwrite an established timeline')
            validate_participants(start)
            request('/command', {'kind': 'prepare_market'})
            wait(lambda s: inventory(s).get('108149', {}).get('bread') == 3 and s['bridge']['command'] is None, 'Demo stock observed')
            request('/world/bootstrap', {})
            bound=wait(lambda s: stable(s) and s['society']['checkpoint'] > 0, 'Empty bootstrap checkpoint bound')
            initialized,provenance=initialize_fresh_population(request,lambda predicate:wait(predicate,'Explicit census checkpoint bound'),bound,'save-lineage',args.run_id)
            evidence['population_initialization']=provenance
            before = record('before', initialized)
            save('WS-' + args.run_id + '-A')
        validate_participants(request('/state'),require_saved=True)
        trade = {'id': args.run_id + '-trade', 'buyer': 108186, 'seller': 108149}
        request('/world/trade', trade)
        after = record('after', wait(lambda s: stable(s) and len(s['world']) == 1 and s['world'][0]['status'] == 'committed', 'Trade and memories committed'))
        assert after['inventory']['108186']['gold'] == before['inventory']['108186']['gold'] - 3
        assert after['inventory']['108149']['gold'] == before['inventory']['108149']['gold'] + 3
        assert after['inventory']['108186']['bread'] == before['inventory']['108186']['bread'] + 1
        assert after['inventory']['108149']['bread'] == before['inventory']['108149']['bread'] - 1
        assert len(after['people']['108186']['memories']) == len(before['people']['108186']['memories']) + 1
        assert after['people']['108186']['trust']['108149'] == before['people']['108186']['trust'].get('108149',0) + 1
        request('/world/trade', trade)
        duplicate = record('duplicate', request('/state'))
        assert duplicate['inventory'] == after['inventory'] and duplicate['people'] == after['people']
        save('WS-' + args.run_id + '-B')
        for suffix, expected in [('A', before), ('B', after)]:
            request('/command', {'kind': 'load_game', 'name': 'WS-' + args.run_id + '-' + suffix})
            restored = record('restored-' + suffix, wait(lambda s: stable(s) and s['society']['checkpoint'] == expected['checkpoint'], 'Restored checkpoint ' + suffix))
            assert restored['inventory'] == expected['inventory'], 'Inventory mismatch after load'
            assert restored['world'] == expected['world'], 'Journal mismatch after load'
            assert restored['people'] == expected['people'], 'Memories or relationships mismatch after load'
        evidence['passed'] = True
    finally:
        output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps({'passed': evidence['passed'], 'evidence': str(output)}), flush=True)


if __name__ == '__main__':
    main()
