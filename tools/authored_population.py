"""Explicit population admission for authored lab tools; no native or HTTP calls.

The caller supplies its transport/wait functions. A census seeds every observed
adult with the uniform population policy; required IDs constrain only this
historical authored scenario, never the town population. No profiles, businesses,
acquaintances, stock or occupations are implicitly restored from old fixtures.
"""
import hashlib
from population import eligible_actors
from labour import work_opportunities

PARTICIPANTS = (108186, 108149)
POPULATION_POLICY = 'uniform-observed-census-v1'


def validate_participants(state, require_saved=False):
    observation = state.get('bridge', {}).get('observation') or {}
    actors = {row['id']: row for row in eligible_actors(observation)}
    missing = [actor for actor in PARTICIPANTS if actor not in actors or actors[actor].get('loaded') is False]
    if missing:
        raise ValueError('Authored scenario requires observed loaded adult participant IDs: ' + ', '.join(map(str, missing)))
    if require_saved:
        people = state.get('society', {}).get('people', {})
        if any(str(actor) not in people for actor in PARTICIPANTS):
            raise ValueError('Required scenario participants are not initialized in this managed save; initialize an explicit census separately, never reseed or substitute profiles')
    return actors


def census_spec(kind, run_id):
    if kind not in ('market-day', 'save-lineage') or not isinstance(run_id, str) or not run_id:
        raise ValueError('An explicit authored scenario kind and run ID are required')
    suffix = hashlib.sha256((kind + ':' + run_id).encode()).hexdigest()[:20]
    return {'id': kind + '-census-' + suffix, 'seed': kind + '-seed-' + suffix}


def initialize_fresh_population(request, wait_bound, bound, kind, run_id):
    """Only immediately after this tool bound its new empty bootstrap checkpoint."""
    validate_participants(bound)
    society = bound['society']
    session = bound.get('bridge', {}).get('session')
    if not isinstance(session,str) or not session or bound['bridge']['observation'].get('session') != session:
        raise ValueError('Fresh census requires matching nonempty bridge and observation sessions')
    if society.get('people') or society.get('town'):
        raise ValueError('Fresh census helper refuses to reseed or expand an existing managed population')
    if (type(society.get('checkpoint')) is not int or society['checkpoint'] <= 0 or
            society.get('transition') or society.get('error') or
            bound['bridge']['observation'].get('checkpoint') != society['checkpoint']):
        raise ValueError('Fresh census requires a bound bootstrap checkpoint')
    spec = census_spec(kind, run_id)
    result = request('/town/initialize', spec, session=session)
    checkpoint = result.get('checkpoint')
    if type(checkpoint) is not int or checkpoint <= society['checkpoint']:
        raise ValueError('Census did not create the expected new checkpoint; inspect state before retrying')
    def settled(state):
        current = state.get('society', {})
        town = current.get('town') or {}
        bridge = state.get('bridge', {})
        return (bridge.get('session') == session and (bridge.get('observation') or {}).get('session') == session and
                current.get('checkpoint') == checkpoint and not current.get('transition') and not current.get('error') and
                state.get('bridge', {}).get('observation', {}).get('checkpoint') == checkpoint and
                town.get('seed') == spec['seed'] and any(row.get('id') == spec['id'] for row in town.get('census_events', [])))
    state = wait_bound(settled)
    if not settled(state):
        raise ValueError('Census checkpoint and provenance were not observed')
    validate_participants(state, require_saved=True)
    return state, {**spec, 'policy': POPULATION_POLICY, 'checkpoint': checkpoint, 'session': session,
        'source': 'Explicit authored-tool census of observed adults; synthetic traits, not measurements or legacy profiles',
        'historical_comparability': 'Fresh choices may differ from historical fixed-profile trials; no traits, jobs or social priors are copied'}


def validate_market_contract(state, scenario_id):
    """Reject before locking the finite sequence if its authored work cannot start."""
    society = state['society']; prior = society.get('market_day')
    if prior and prior.get('id') == scenario_id and prior.get('status') == 'complete':
        return  # Reading a completed result needs no current residents or business.
    validate_participants(state, require_saved=True)
    if prior and prior.get('id') == scenario_id:
        return  # Resume the recorded stage; do not reopen already completed work.
    town = society.get('town') or {}
    businesses = list(town.get('businesses', {}).values())
    capabilities = {cap for business in businesses if business.get('custodian') == 108149 and business.get('active') is True
                    for cap in business.get('capabilities', [])}
    if not {'bread_recipe', 'retail_food'} <= capabilities:
        raise ValueError('Market-day requires explicit active bread-production and food-retail charters for authored seller 108149. Census creates no business; configure /town/enterprise separately. Existing saves are not replenished or reseeded')
    jobs = work_opportunities(society, state['bridge']['observation'], 108186)
    if not jobs or jobs[0]['employer'] != 108149:
        raise ValueError('Authored market-day opening work requires a currently feasible first offer from 108149: verify charter, observed inputs/wages, native catalog and route availability. No stock or jobs are invented')
