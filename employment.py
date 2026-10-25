"""Observed employment encounters; public terms and personal refusal memory."""
import copy
import math
import hashlib
from economy_catalog import canonical_json, recipe_spec
import economy_catalog

REVIEW_AFTER_REFUSAL_MINUTES = 15
REFUSAL_MEMORY_MINUTES = 60


def recently_refused(state, worker, business_id, revision, day):
    if type(day) not in (int, float) or not math.isfinite(day):
        return False
    for memory in state['people'][str(worker)].get('memories', []):
        then = memory.get('day')
        if (memory.get('kind') == 'employment_unavailable'
                and memory.get('business_id') == business_id and memory.get('revision') == revision
                and type(then) in (int, float) and math.isfinite(then)
                and 0 <= (day - then) * 1440 < REFUSAL_MEMORY_MINUTES):
            return True
    return False


def approach_employer(plan):
    """Voiced requests cannot ask or reject a job across town."""
    plan.update(phase='travelling', intent='ask_work', employment_dialogue=True,
                travel_id='employment-approach-' + plan['id'], release_required=True,
                dynamic_route=True)


def remember_unavailable(state, plan, day, delivery_id):
    terms = plan['work_terms']
    person = state['people'][str(plan['actor'])]
    person['memories'].append({'event_id': delivery_id, 'kind': 'employment_unavailable',
        'other': plan['target'], 'business_id': terms['business_id'], 'revision': terms['revision'],
        'day': day, 'source': 'Heard the employer decline this request; private reason unknown'})
    person['memories'] = person['memories'][-32:]


TERM_FIELDS = ('protocol', 'worker', 'worker_base_id', 'employer', 'employer_base_id',
               'business_id', 'revision', 'recipe_id', 'catalog_hash', 'recipe_hash', 'currency', 'policy')


def work_terms_hash(terms):
    if not isinstance(terms, dict) or any(key not in terms for key in TERM_FIELDS):
        raise ValueError('Complete protocol 2 employment terms are required')
    if type(terms['protocol']) is not int or terms['protocol'] != 2:
        raise ValueError('Unsupported employment terms protocol')
    for key in ('worker', 'worker_base_id', 'employer', 'employer_base_id'):
        if type(terms[key]) is not int or not 0 < terms[key] <= 0xffffffff:
            raise ValueError('Invalid paid employment identity')
    if terms['worker'] == terms['employer']:
        raise ValueError('Paid employment requires distinct parties')
    currencies = [r['id'] for r in economy_catalog.ECONOMY_CATALOG['commodities'] if r['currency']]
    if terms['currency'] not in currencies:
        raise ValueError('Paid employment currency is not configured')
    return hashlib.sha256(canonical_json({key: terms[key] for key in TERM_FIELDS}).encode('utf-8')).hexdigest()


def validate_paid_consent(state, plan, observation):
    """Proof of separate recorded choices, and heard terms for voiced contracts."""
    from enterprises import current_work_terms
    current_work_terms(state, plan, observation)
    terms = plan.get('work_terms', {})
    digest = work_terms_hash(terms)
    if terms.get('terms_hash') != digest:
        raise ValueError('Paid consent terms hash does not match')
    session = observation.get('session')
    if not isinstance(session, str) or not session:
        raise ValueError('Paid consent requires a current session')
    records = plan.get('decisions', [])
    matches = []
    for action, actor in (('offer_shift', plan['target']), ('take_shift', plan['actor'])):
        candidates = []
        for index, record in enumerate(records):
            if not isinstance(record, dict):continue
            context = record.get('context', {})
            if (record.get('decision', {}).get('action_id') != action
                    or record.get('actor_id') != actor):continue
            claimed = context.get('work_terms', {})
            if (context.get('actor_id') != actor or context.get('session') != session
                    or (context.get('event') or {}).get('id') != plan['id']
                    or context.get('terms_hash') != digest
                    or not isinstance(record.get('claim_id'), str) or not record['claim_id']
                    or not any(row.get('id') == action for row in context.get('options', []) if isinstance(row,dict))):
                raise ValueError('Paid consent claim identity is not proven')
            if work_terms_hash(claimed) != digest or claimed.get('terms_hash') != digest:
                raise ValueError('Paid consent claim terms changed')
            candidates.append((index, record))
        if len(candidates) != 1:
            raise ValueError('Paid consent requires one exact offer and acceptance claim')
        matches.append(candidates[0])
    if matches[0][0] >= matches[1][0] or matches[0][1]['claim_id'] == matches[1][1]['claim_id']:
        raise ValueError('Paid acceptance must follow a distinct employer offer')
    consent = {'protocol': 2, 'plan_id': plan['id'], 'session': session,
        'worker': plan['actor'], 'employer': plan['target'], 'terms_hash': digest,
        'offer_claim_id': matches[0][1]['claim_id'], 'acceptance_claim_id': matches[1][1]['claim_id']}
    if plan.get('voiced_trade') or plan.get('employment_dialogue'):
        heard = []
        for act, speaker, listener in (('work_offer', plan['target'], plan['actor']),
                                        ('work_accept', plan['actor'], plan['target'])):
            turns = [(index, turn) for index, turn in enumerate(plan.get('economic_turns', []))
                     if isinstance(turn, dict) and turn.get('act') == act]
            if len(turns) != 1:raise ValueError('Paid consent requires heard offer and acceptance')
            index, turn = turns[0]; playback = turn.get('playback', {})
            if (turn.get('delivered') is not True or turn.get('actor') != speaker
                    or turn.get('listener') != listener or turn.get('origin_session') != session
                    or turn.get('terms_hash') != digest
                    or not isinstance(turn.get('delivery_id'), str) or not turn['delivery_id']
                    or playback.get('id') != turn['delivery_id'] or playback.get('status') != 'ended'
                    or playback.get('nearbyThroughout') is not True):
                raise ValueError('Paid consent heard delivery witness is incomplete')
            duration=(turn.get('audio') or {}).get('seconds');elapsed=playback.get('playedSeconds')
            if (type(duration) not in (int,float) or not math.isfinite(duration) or duration<=0
                    or type(elapsed) not in (int,float) or not math.isfinite(elapsed)
                    or elapsed < duration-.3):
                raise ValueError('Paid consent speech was not heard in full')
            heard.append((index, turn['delivery_id']))
        if heard[0][0] >= heard[1][0] or heard[0][1] == heard[1][1]:
            raise ValueError('Heard acceptance must follow a distinct heard offer')
        consent.update(offer_delivery_id=heard[0][1], acceptance_delivery_id=heard[1][1])
    return {'terms': copy.deepcopy(terms), 'terms_hash': digest, 'consent': consent,
            'consent_hash': hashlib.sha256(canonical_json(consent).encode('utf-8')).hexdigest()}


validated_paid_consent = validate_paid_consent


def work_description(plan):
    terms = plan.get('work_terms', {})
    recipe = recipe_spec(terms.get('recipe_id', 'bread_recipe'))
    def goods(side):return ', '.join(str(n) + ' ' + key for key,n in sorted(recipe[side].items()))
    return 'convert ' + goods('inputs') + ' into ' + goods('outputs')


def accept_contract(state, plan, observation=None):
    terms = plan.get('work_terms')
    if not terms:return
    evidence = None
    if terms.get('protocol') == 2:
        if observation is None:raise ValueError('Paid consent needs current observation')
        evidence = validate_paid_consent(state, plan, observation)
    contracts = state['town']['businesses'][terms['business_id']]['contracts']
    existing = next((c for c in contracts if c['id'] == plan['id']), None)
    if existing:
        if evidence and existing.get('consent_hash') != evidence['consent_hash']:
            raise ValueError('Existing employment consent does not match')
        return
    contract = {'id': plan['id'], 'worker': plan['actor'], 'employer': plan['target'],
        'status': 'accepted', 'terms': copy.deepcopy(terms['policy']),
        'source': 'Historical employment dialogue; legacy execution remains unqualified'}
    if evidence:
        contract.update(evidence)
        contract['source'] = 'Separate retained employer offer and worker acceptance; no completed work yet'
        plan['paid_consent'] = copy.deepcopy(evidence)
    contracts.append(contract)
