"""At most twelve language-only calls; never execute game or speech effects."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from language import LanguageOutputError, propose


def run(plan, output, key):
    cases, configs = plan['cases'], plan['configs']
    if not cases or not configs or len(cases) * len(configs) > 12:
        raise ValueError('Probe must contain 1–12 calls')
    if any(len(json.dumps(context)) > 6000 for context in cases.values()):
        raise ValueError('Probe context exceeds limit')
    if any(c.get('provider') != 'openrouter_chat' or not c.get('openrouter_provider')
           or c.get('reasoning_effort') != 'none' for c in configs):
        raise ValueError('Probe requires a fixed OpenRouter provider and reasoning disabled')
    evidence = {'scope': 'Language-only probe; no Jev, TTS, or game effects; no retries',
                'started_at': time.time(), 'plan': plan, 'results': []}
    # A prior or interrupted receipt is not permission to repeat paid calls.
    with output.open('x', encoding='utf-8') as file:
        json.dump(evidence, file, indent=2)

    def record():
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
        temporary.replace(output)

    for name, context in cases.items():
        for config in configs:
            row = {'case': name, 'config': config, 'status': 'claimed'}
            evidence['results'].append(row)
            record()
            start = time.monotonic()
            try:
                result = propose(context, config, key)
                counts = [len(c['line'].split()) for c in result['proposal']['candidates']]
                row.update(status='valid', result=result, word_counts=counts,
                           requested_word_limit_pass=all(8 <= n <= 30 for n in counts))
            except LanguageOutputError as error:
                row.update(status='rejected', receipt=error.receipt, reason=str(error))
            except (OSError, ValueError) as error:
                row.update(status='failed', error_type=type(error).__name__,
                           http_status=getattr(error, 'code', None))
            row['wall_seconds'] = round(time.monotonic() - start, 3)
            record()
            print(json.dumps({k: v for k, v in row.items() if k not in ('result', 'receipt')}), flush=True)
    evidence['finished_at'] = time.time()
    record()
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--key-env', default='WHITERUN_OPENROUTER_KEY')
    args = parser.parse_args()
    run(json.loads(args.plan.read_text(encoding='utf-8')), args.output, os.environ[args.key_env])
