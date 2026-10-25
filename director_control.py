"""One bounded director per service; stop at a settled event boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid


class DirectorControl:
    def __init__(self, runtime):
        self.runtime = Path(runtime)
        self.process = None
        self.run = None
        self.log = None

    def status(self):
        if not self.run:
            return {'status': 'idle', 'running': False}
        result = dict(self.run)
        code = self.process.poll()
        result['running'] = code is None
        if code is not None:
            if self.log:
                self.log.close()
                self.log = None
            result.update(status='complete' if code == 0 else 'held', exit_code=code)
        try:
            receipt = json.loads(Path(self.run['receipt']).read_text())
            result.update(events_completed=sum(e['status'] != 'started' for e in receipt['events']),
                          current_event=receipt['events'][-1] if receipt['events'] else None,
                          outcome=receipt['status'])
            if receipt.get('error'): result['error'] = receipt['error'][:240]
        except (OSError, ValueError, KeyError):
            pass
        # Paths and credentials are not part of the browser presentation.
        result.pop('receipt', None)
        result.pop('stop_file', None)
        return result

    def start(self, data, bridge, society):
        if self.status()['running']:
            raise ValueError('The society director is already running')
        count = data.get('max_events', 6)
        if type(count) is not int or not 1 <= count <= 12:
            raise ValueError('Choose 1 to 12 resident events')
        if time.time() - (bridge.get('last_seen') or 0) > 10:
            raise ValueError('Game bridge unavailable')
        if not society.get('town') or society.get('error') or society.get('transition') or bridge.get('command'):
            raise ValueError('An initialized, synchronized town is required')
        if society.get('unsettled_effect') or (society.get('routine_batch') or {}).get('unverified_release'):
            raise ValueError('Resolve the unverified native effect before starting society')
        for key in ('plan', 'conversation', 'routine_batch'):
            item = society.get(key) or {}
            if item and item.get('phase') not in ('complete', 'held'):
                raise ValueError('Finish the active resident event before starting society')
        configs = [self.runtime/'jev-config.json', self.runtime/'language-config.json']
        for path in configs:
            try: config = json.loads(path.read_text())
            except (OSError, ValueError): raise ValueError('Society model configuration is unavailable') from None
            if not config.get('key_env') or not os.environ.get(config['key_env']):
                raise ValueError('The service needs its configured model credential before starting society')
        run_id = 'society-' + uuid.uuid4().hex[:16]
        receipt = self.runtime/(run_id+'.json')
        stop_file = self.runtime/(run_id+'.stop')
        command = [sys.executable, str(Path(__file__).parent/'tools/run_daily_life.py'),
                   '--root', str(self.runtime.parent), '--max-events', str(count),
                   '--watch-seconds', '600', '--model-config', str(configs[0]),
                   '--language-config', str(configs[1]), '--social-opportunities', '--parallel-journeys', '--receipt', str(receipt),
                   '--stop-file', str(stop_file)]
        self.log = (self.runtime/(run_id+'.log')).open('w', encoding='utf-8')
        try:
            self.process = subprocess.Popen(command, stdout=self.log, stderr=self.log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except Exception:
            self.log.close(); self.log = None
            raise
        self.run = {'id': run_id, 'status': 'running', 'max_events': count,
                    'maximum_model_calls': 21*count, 'started_at': time.time(),
                    'receipt': str(receipt), 'stop_file': str(stop_file)}
        return self.status()

    def stop(self):
        if self.run and self.process.poll() is None:
            Path(self.run['stop_file']).write_text('Stop after the current event settles.\n')
            self.run['status'] = 'stopping'
        return self.status()
