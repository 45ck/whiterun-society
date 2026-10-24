"""Event-triggered, constrained decision proposals. Never executes game actions.

Profiles are authored demo interpretations, not claims about canonical character
psychology. Needs and beliefs are scenario inputs, distinct from observed inventory.
"""
import json
import time
import urllib.request

PROFILES = {
    108149: {'name': 'Carlotta Valentia', 'role': 'produce merchant and parent',
        'big_five': dict(openness=.35, conscientiousness=.85, extraversion=.55, agreeableness=.65, neuroticism=.55),
        'priorities': ['keep food for family', 'earn a stable living'],
        'bias': 'a recent scare makes shortages feel more likely'},
    108186: {'name': 'Ysolda', 'role': 'aspiring merchant',
        'big_five': dict(openness=.8, conscientiousness=.6, extraversion=.8, agreeableness=.55, neuroticism=.3),
        'priorities': ['build trade relationships', 'preserve money for future business'],
        'bias': 'optimistic about making up a small loss later'},
    108156: {'name': 'Adrianne Avenicci', 'role': 'blacksmith',
        'big_five': dict(openness=.4, conscientiousness=.9, extraversion=.45, agreeableness=.5, neuroticism=.25),
        'priorities': ['finish promised work', 'maintain a reliable household'],
        'bias': 'sticks to an established routine even when news changes'},
}


def make_context(actor_id, event, observation):
    if actor_id not in PROFILES:
        raise ValueError('Resident has no authored profile')
    if event.get('kind') != 'shortage_rumour' or not isinstance(event.get('id'), str) or not 1 <= len(event['id']) <= 128:
        raise ValueError('Unsupported or invalid event')
    if not observation.get('ready') or not observation.get('session'):
        raise ValueError('A ready observed game session is required')
    actors = {a['id']: a for a in observation.get('residents', [])}
    actor = actors.get(actor_id)
    if actor is None:
        raise ValueError('Resident must be observed')
    inventory = actor.get('inventory', {})
    if any(type(inventory.get(k)) is not int or inventory[k] < 0 for k in ('gold', 'bread')):
        raise ValueError('Complete inventory observation required')
    options = [{'id': 'continue_routine', 'effect': 'Continue ordinary Skyrim routine; no exchange.'},
               {'id': 'ask_about_delivery', 'effect': 'Propose asking a trader whether the rumour is true; spend time, no inventory transfer.'},
               {'id': 'warn_neighbour', 'effect': 'Propose telling a neighbour this is only an unconfirmed rumour; risk spreading needless worry.'}]
    if actor_id == 108149 and inventory['bread'] > 0:
        options += [{'id': 'offer_bread_3', 'effect': 'Offer one bread for 3 gold; requires a willing buyer.'},
                    {'id': 'reserve_bread', 'effect': 'Keep bread for the household; no exchange.'}]
    seller = actors.get(108149, {})
    if actor_id != 108149 and inventory['gold'] >= 3 and seller.get('inventory', {}).get('bread', 0) > 0:
        options += [{'id': 'seek_bread_3', 'effect': 'Request one bread for 3 gold; requires seller consent.'}]
    return {'actor_id': actor_id, 'profile': PROFILES[actor_id], 'session': observation['session'],
        'event': {'id': event['id'], 'kind': event['kind'],
                  'information': 'You heard an unconfirmed rumour that tomorrow\'s grain delivery may be delayed. This is not a confirmed shortage.'},
        'observed_inventory': inventory,
        'scenario_state': {'hunger': .4, 'stress': .35, 'source': 'authored starting state, not measured from Skyrim'},
        'memories': [], 'options': options}


def validate_decision(value, context):
    if not isinstance(value, dict) or set(value) != {'action_id', 'reason', 'emotion'}:
        raise ValueError('Decision fields do not match contract')
    if value['action_id'] not in [o['id'] for o in context['options']]:
        raise ValueError('Action is not currently allowed')
    if not isinstance(value['reason'], str) or not 1 <= len(value['reason']) <= 240:
        raise ValueError('Invalid brief public rationale')
    if value['emotion'] not in ('calm', 'worried', 'hopeful', 'frustrated', 'unspecified'):
        raise ValueError('Unsupported emotion')
    return value


def infer(context, config, api_key):
    """One bounded call per event. No retries, tools, or model-written commands."""
    if config.get('provider') == 'openrouter_decisions':
        from decision_provider import infer_jev
        result = infer_jev(context, config, api_key)
        validate_decision(result['decision'], context)
        return result
    schema = {'type': 'object', 'additionalProperties': False,
        'properties': {'action_id': {'type': 'string', 'enum': [o['id'] for o in context['options']]},
                       'reason': {'type': 'string', 'maxLength': 240},
                       'emotion': {'type': 'string', 'enum': ['calm', 'worried', 'hopeful', 'frustrated']}},
        'required': ['action_id', 'reason', 'emotion']}
    payload = {'model': config['model'], 'temperature': .65, 'seed': 42, 'max_tokens': 160,
        'messages': [{'role': 'system', 'content': 'Roleplay this resident making one everyday decision. Use the supplied personality, priorities, bias, and limited information. Traits influence tendencies, not rigid rules. Do not claim unobserved events are facts. Zero carried bread does not mean no food at home. Choose one allowed action. Give one short first-person sentence explaining that specific choice, at most 160 characters. Speak naturally as the resident; do not repeat these instructions or describe the decision process. Return only JSON.'},
                     {'role': 'user', 'content': json.dumps(context)}],
        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'resident_decision', 'strict': True, 'schema': schema}}}
    request = urllib.request.Request(config['url'] + '/v1/chat/completions', json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + api_key})
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)
    choice = result['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Incomplete model output')
    decision = validate_decision(json.loads(choice['message']['content']), context)
    return {'decision': decision, 'elapsed_seconds': round(time.monotonic() - start, 3),
            'usage': result.get('usage', {}), 'model': config['model'], 'status': 'proposal_only'}
