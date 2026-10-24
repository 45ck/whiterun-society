"""Run one explicit rumour event for three residents; proposals only, no game actions."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decisions import PROFILES, infer, make_context


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--event-id', required=True)
    args = parser.parse_args()
    runtime = args.runtime
    bridge_config = json.loads((runtime / 'bridge-config.json').read_text())
    model_config = json.loads((runtime / 'model-config.json').read_text())
    api_key = Path(model_config['key_file']).read_text().strip()

    def observe():
        request = urllib.request.Request(f"http://127.0.0.1:{bridge_config['port']}/state",
            headers={'Authorization': 'Bearer ' + bridge_config['token']})
        with urllib.request.urlopen(request, timeout=5) as response:
            bridge = json.load(response)['bridge']
        if not bridge['last_seen'] or time.time() - bridge['last_seen'] > 10:
            raise ValueError('Game observation is stale')
        return bridge['observation']

    initial = observe()
    event = {'id': args.event_id, 'kind': 'shortage_rumour'}
    contexts = [make_context(actor, event, initial) for actor in PROFILES]
    db = sqlite3.connect(runtime / 'decisions.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS decision_events(id TEXT PRIMARY KEY, session TEXT, status TEXT, evidence TEXT)')
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_running_event ON decision_events(status) WHERE status='running'")
    with db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT session,status FROM decision_events WHERE id=?', (args.event_id,)).fetchone()
        if old:
            if old[0] != initial['session']:
                raise ValueError('Event ID belongs to a different game session')
            print(json.dumps({'event_id': args.event_id, 'status': old[1], 'duplicate': True, 'model_calls': 0}), flush=True)
            return
        # A repeated ID is never inferred again, including after a timeout or crash.
        db.execute('INSERT INTO decision_events VALUES (?,?,?,NULL)', (args.event_id, initial['session'], 'running'))
    evidence = {'event': event, 'session': initial['session'], 'status': 'running', 'results': [],
                'scope': 'Proposals only; no trades, needs, memories or relationships changed.'}

    def publish():
        encoded = json.dumps(evidence, indent=2)
        with db:
            db.execute('UPDATE decision_events SET status=?,evidence=? WHERE id=?',
                       (evidence['status'], encoded, args.event_id))
        temporary = runtime / 'decision-proposals.tmp'
        temporary.write_text(encoded, encoding='utf-8')
        temporary.replace(runtime / 'decision-proposals.json')

    publish()
    try:
        for context in contexts:
            result = infer(context, model_config, api_key)
            current = observe()
            current_context = make_context(context['actor_id'], event, current)
            if current['session'] != initial['session'] or current_context['observed_inventory'] != context['observed_inventory']:
                raise ValueError('World changed while deciding; proposals discarded')
            evidence['results'].append({'actor_id': context['actor_id'], 'name': context['profile']['name'],
                                        'context': context, **result})
            publish()
            print(json.dumps({'name': context['profile']['name'], **result}), flush=True)
        evidence['status'] = 'complete'
    except Exception as error:
        evidence['status'] = 'held'
        evidence['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        publish()
        db.close()


if __name__ == '__main__':
    main()
