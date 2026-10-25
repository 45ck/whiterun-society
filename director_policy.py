"""Validated bounded run policy; every launched session freezes its own copy."""
import copy
import hashlib
import json
from pathlib import Path
import re


DEFAULT_PATH = Path(__file__).parent/'config/director-policy.json'
# Protocol ceilings bound even edited policy files. Actual settings are data.
MODE_CEILINGS = {'sample': (12, 600), 'play': (96, 3600)}
MODE_FIELDS = {'default_events', 'maximum_events', 'watch_seconds', 'goal_budget', 'goal_review_seconds'}
RUN_FIELDS = {'version', 'mode', 'max_events', 'watch_seconds', 'goal_budget', 'goal_review_seconds',
              'policy_snapshot', 'policy_sha256', 'run_policy_sha256'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def integer(value, low, high, field):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Director policy {field} must be an integer from {low} to {high}')
    return value


def validate_director_policy(config):
    if not isinstance(config, dict) or set(config) != {'version', 'modes'}:
        raise ValueError('Director policy requires only version and modes')
    version = config['version']
    if not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', version):
        raise ValueError('Invalid director policy version')
    modes = config['modes']
    if not isinstance(modes, dict) or set(modes) != set(MODE_CEILINGS):
        raise ValueError('Director policy requires sample and play modes')
    for mode, (event_cap, time_cap) in MODE_CEILINGS.items():
        settings = modes[mode]
        if not isinstance(settings, dict) or set(settings) != MODE_FIELDS:
            raise ValueError('Invalid director mode fields: '+mode)
        maximum = integer(settings['maximum_events'], 1, event_cap, mode+'.maximum_events')
        integer(settings['default_events'], 1, maximum, mode+'.default_events')
        integer(settings['watch_seconds'], 1, time_cap, mode+'.watch_seconds')
        integer(settings['goal_budget'], 1, 4096, mode+'.goal_budget')
        integer(settings['goal_review_seconds'], 1, 60, mode+'.goal_review_seconds')
    return copy.deepcopy(config)


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 32768:
        raise ValueError('Director policy file exceeds its size bound')
    return json.loads(path.read_text(encoding='utf-8'))


def load_director_policy(path=None):
    return validate_director_policy(read_json(path or DEFAULT_PATH))


def resolve_run_policy(mode='sample', max_events=None, watch_seconds=None, config=None):
    """Zero events/time remain available for explicit one-pass CLI observation."""
    config = load_director_policy() if config is None else validate_director_policy(config)
    if not isinstance(mode, str) or mode not in MODE_CEILINGS:
        raise ValueError('Choose sample or play mode')
    settings = config['modes'][mode]
    count = settings['default_events'] if max_events is None else max_events
    seconds = settings['watch_seconds'] if watch_seconds is None else watch_seconds
    integer(count, 0, settings['maximum_events'], 'max_events')
    integer(seconds, 0, settings['watch_seconds'], 'watch_seconds')
    result = {'version': config['version'], 'mode': mode, 'max_events': count, 'watch_seconds': seconds,
              'goal_budget': settings['goal_budget'], 'goal_review_seconds': settings['goal_review_seconds'],
              'policy_snapshot': config, 'policy_sha256': digest(config)}
    result['run_policy_sha256'] = digest(result)
    return result


def validate_run_policy(value, expected_max_events=None, expected_watch_seconds=None):
    if not isinstance(value, dict) or set(value) != RUN_FIELDS:
        raise ValueError('Invalid frozen director run-policy fields')
    expected = resolve_run_policy(value['mode'], value['max_events'], value['watch_seconds'], value['policy_snapshot'])
    body = {key: item for key, item in value.items() if key != 'run_policy_sha256'}
    if value != expected or digest(body) != value['run_policy_sha256']:
        raise ValueError('Frozen director run policy does not match its validated snapshot and hashes')
    for actual, wanted, field in ((value['max_events'], expected_max_events, 'max_events'),
                                  (value['watch_seconds'], expected_watch_seconds, 'watch_seconds')):
        if wanted is not None and (type(wanted) is not int or actual != wanted):
            raise ValueError('Frozen director run policy disagrees with CLI '+field)
    return expected


def load_run_policy(path, expected_max_events=None, expected_watch_seconds=None):
    return validate_run_policy(read_json(path), expected_max_events, expected_watch_seconds)


def write_run_policy(path, policy):
    """Exclusive creation prevents silently replacing a launched run's policy."""
    value = validate_run_policy(policy)
    with Path(path).open('x', encoding='utf-8') as output:
        output.write(json.dumps(value, indent=2, allow_nan=False)+'\n')
    return value
