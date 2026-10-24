"""Personal identity knowledge; the global roster is not an NPC's memory.

An explicit spoken self-introduction is a claim, not verified identity. Only
completed nearby delivery may teach it. Older saves need no guessed backfill.
"""
import copy


def person_view(state, observer, other):
    person = state.get('people', {}).get(str(observer), {})
    known = person.get('known_people', {}).get(str(other), {})
    name = known.get('name')
    if not isinstance(name, str) or not name.strip():
        name = None
    return {'id': other, 'name': name or ('a familiar resident' if known.get('heard_events') else 'an unfamiliar resident'),
            'name_known': name is not None,
            'identity_source': copy.deepcopy(known.get('name_source')) if name else None}


def record_heard_identity(state, turn):
    """Called only after the conversation's native delivery checks succeed."""
    if turn.get('delivered') is not True:
        return
    speaker, listener = turn['speaker'], turn['listener']
    people = state['people']
    if speaker == listener or str(speaker) not in people or str(listener) not in people:
        return
    known = people[str(listener)].setdefault('known_people', {}).setdefault(str(speaker), {'heard_events': []})
    event = turn['delivery_id']
    if event in known['heard_events']:
        return
    known['heard_events'] = (known['heard_events'] + [event])[-64:]
    # This explicit convention avoids extracting a name from a quotation,
    # rumour, question or an omniscient lookup of another resident's profile.
    own_name = people[str(speaker)]['profile']['name']
    introduction = 'My name is ' + own_name + '.'
    line = turn['selected']['line']
    if line.startswith(introduction):
        known['name'] = own_name
        known['name_source'] = {'event_id': event, 'kind': 'heard_self_introduction',
                                'epistemic_status': 'self-reported name; identity not independently verified'}
