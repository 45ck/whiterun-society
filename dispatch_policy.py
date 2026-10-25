"""Schedule attention fairly; never choose a resident's response or action.

Age is measured only from the game's observed clock. Overdue requests precede
new followups and social opportunities, oldest first. This bounds overtaking,
not completion time: unavailable actors, native failures and model latency can
still delay service. Callers retain responsibility for eligibility checks.
"""
import json
import math
from pathlib import Path


POLICY_PATH = Path(__file__).parent / 'config/dispatch-policy.json'


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def load_policy():
    policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    fields = {'version', 'urgent_priority_threshold', 'urgent_wait_game_minutes',
              'ordinary_wait_game_minutes', 'followup_burst_limit'}
    if set(policy) != fields or not isinstance(policy['version'], str) or not 1 <= len(policy['version']) <= 64:
        raise ValueError('Invalid dispatch policy')
    if any(not _finite(policy[k]) for k in fields - {'version'}):
        raise ValueError('Invalid dispatch policy number')
    if not 0 <= policy['urgent_priority_threshold'] <= 1:
        raise ValueError('Invalid dispatch urgency threshold')
    if not 1 <= policy['urgent_wait_game_minutes'] <= policy['ordinary_wait_game_minutes'] <= 1440:
        raise ValueError('Invalid dispatch waiting windows')
    if type(policy['followup_burst_limit']) is not int or not 1 <= policy['followup_burst_limit'] <= 4:
        raise ValueError('Invalid dispatch followup burst')
    return policy


def _priority(event):
    value = event.get('priority', 0)
    return value if _finite(value) else 0


def _age(event, game_day):
    created = event.get('created_day')
    if not _finite(game_day) or not _finite(created) or created < 0 or game_day < created:
        return None
    return (game_day - created) * 1440


def _followup(event):
    return bool(event.get('conversation_followups') or event.get('goal_followups'))


def _overdue(event, game_day, policy):
    age = _age(event, game_day)
    threshold = (policy['urgent_wait_game_minutes']
                 if _priority(event) >= policy['urgent_priority_threshold']
                 else policy['ordinary_wait_game_minutes'])
    # Floating point game days should not turn an exact boundary into a miss.
    return age is not None and (age >= threshold or math.isclose(age, threshold, abs_tol=1e-7))


def _order(event):
    created = event.get('created_day')
    return (-_priority(event), created if _finite(created) and created >= 0 else math.inf,
            str(event.get('id', '')))


def fair_pending(events, social_first=True, game_day=None):
    """Return all supplied eligible requests once, without mutating them.

    Known overdue work gets FIFO attention across all kinds and priorities.
    Otherwise bounded followup continuity alternates with ordinary attention;
    ordinary social and economic reviews alternate as before. With no valid
    clock there is no invented age or claim of a maximum wait guarantee.
    """
    policy = load_policy()
    overdue, remaining = [], []
    for event in events:
        (overdue if _overdue(event, game_day, policy) else remaining).append(event)
    overdue.sort(key=lambda e: (e['created_day'], str(e.get('id', ''))))
    ordered = sorted(remaining, key=_order)
    followups = [e for e in ordered if _followup(e)]
    ordinary = [e for e in ordered if not _followup(e)]
    social = [e for e in ordinary if e.get('kind') == 'social_review']
    economic = [e for e in ordinary if e.get('kind') != 'social_review']
    result = overdue
    while followups or social or economic:
        result.extend(followups[:policy['followup_burst_limit']])
        del followups[:policy['followup_burst_limit']]
        lane = social if social_first else economic
        if not lane:
            lane = economic if social_first else social
        if lane:
            result.append(lane.pop(0))
            social_first = not social_first
    return result


def can_insert_social(events, game_day=None):
    """Do not inject a new chat ahead of overdue or unfinished followup work.

    Urgent requests with unknown age also block insertion: an absent clock is
    not evidence that an existing resident has had enough attention.
    """
    policy = load_policy()
    return not any(_followup(e) or _overdue(e, game_day, policy)
                   or (_priority(e) >= policy['urgent_priority_threshold'] and _age(e, game_day) is None)
                   for e in events)


def dispatch_metrics(events, game_day=None):
    """Queue observations only; these are not resident realism scores."""
    events = list(events)
    policy = load_policy()
    ages = [age for e in events if (age := _age(e, game_day)) is not None]
    return {'policy_version': policy['version'], 'pending_count': len(events),
            'age_known_count': len(ages), 'age_unknown_count': len(events) - len(ages),
            'maximum_wait_game_minutes': max(ages) if ages else None,
            'overdue_count': sum(_overdue(e, game_day, policy) for e in events),
            'followup_count': sum(_followup(e) for e in events)}
