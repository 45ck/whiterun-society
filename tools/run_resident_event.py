"""Run a bounded meal-time event through decisions, owned travel and consent.

The local service persists each claim before inference and owns all game effects.
This worker never writes the timeline database or sends native commands.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decisions import infer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--event-id', required=True)
    parser.add_argument('--model-config', type=Path)
    parser.add_argument('--actor', type=int, default=108186)
    parser.add_argument('--kind', choices=('meal_time','stock_review','work_shift'), default='meal_time')
    args = parser.parse_args()
    config = json.loads((args.runtime/'bridge-config.json').read_text())
    model = json.loads((args.model_config or args.runtime/'model-config.json').read_text())
    key = os.environ[model['key_env']] if model.get('key_env') else Path(model['key_file']).read_text().strip()

    def request(route, data=None):
        req = urllib.request.Request(f"http://127.0.0.1:{config['port']}"+route,
            data=None if data is None else json.dumps(data).encode(),
            headers={'Authorization': 'Bearer '+config['token'], 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            raise ValueError(json.load(error).get('error', 'Request rejected')) from None
        if route == '/state' and (not result['bridge']['last_seen'] or time.time()-result['bridge']['last_seen'] > 10):
            raise ValueError('Game observation is stale')
        return result

    evidence = {'event_id': args.event_id, 'started_at': time.time(), 'model_calls': 0,
                'before': request('/state'), 'stages': []}
    path = args.runtime/('resident-event-'+hashlib.sha256(args.event_id.encode()).hexdigest()[:12]+'.json')
    def record(stage, state):
        evidence['stages'].append({'at': time.time(), 'phase': stage, 'plan': state['society'].get('plan')})
        path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(json.dumps({'phase': stage, 'model_calls': evidence['model_calls']}), flush=True)

    started = request('/agency/event', {'id': args.event_id, 'actor':args.actor, 'kind':args.kind})
    if started.get('duplicate'):
        print(json.dumps({'duplicate': True, 'model_calls': 0, 'phase': started['plan']['phase']}), flush=True)
        return
    previous = None
    deadline = time.monotonic()+480
    try:
        while time.monotonic() < deadline:
            state = request('/state')
            society = state['society']
            if society['transition']:
                time.sleep(.5)
                continue
            if society['error']:
                raise ValueError(society['error'])
            plan = society.get('plan')
            if not plan or plan['id'] != args.event_id:
                raise ValueError('Active plan changed, possibly after loading another save')
            phase = plan['phase']
            if previous != phase:
                record(phase, state)
                previous = phase
            if phase in ('complete', 'held') and not plan.get('release_required') and plan.get('remembered'):
                evidence['after'] = state
                evidence['status'] = phase
                evidence['outcome'] = plan.get('outcome')
                path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
                print(json.dumps({'status': phase, 'outcome': plan.get('outcome'), 'evidence': str(path)}), flush=True)
                return
            if phase in ('choose', 'consent', 'reconsider', 'allocate', 'after_purchase', 'job_offer', 'job_accept'):
                if evidence['model_calls'] >= 5:
                    raise ValueError('Resident event exhausted its five-call decision budget')
                claim = request('/agency/claim', {'id': args.event_id})['claim']
                # Wait for the persisted claim's game marker before making the call.
                while request('/state')['society']['transition']:
                    if time.monotonic() > deadline:
                        raise TimeoutError('Claim checkpoint did not bind')
                    time.sleep(.5)
                evidence['model_calls'] += 1
                result = infer(claim['context'], model, key)
                request('/agency/decision', {'id': args.event_id, 'claim_id': claim['id'], 'result': result})
            elif phase == 'thinking':
                raise ValueError('An inference claim already exists; it must not be automatically repeated')
            time.sleep(.5)
        raise TimeoutError('Resident event exceeded its bounded execution time')
    except Exception as error:
        evidence['status'] = 'held'
        evidence['error'] = type(error).__name__+': '+str(error)
        try:
            request('/agency/hold', {'id': args.event_id, 'reason': evidence['error']})
        except (OSError, ValueError):
            evidence['hold_not_confirmed'] = True
        path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
