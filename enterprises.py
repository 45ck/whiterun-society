"""Save-bound public enterprise charters. Registration never creates resources.

Policies are explicit operator or resident charter choices. A worker and
employer still independently decide whether to enter each paid contract.
"""
import copy
import re
from activity_leases import work_account_conflict
from economy_catalog import recipe_ids, recipe_spec, catalog_hash, recipe_hash
from market_policy import tradable_ids, goods_policy, advertised_goods

DEFAULT_POLICY = {'target_bread': 8, 'wage_gold': 2, 'grain_per_shift': 1,
                  'bread_per_shift': 2, 'work_minutes': 30}
POLICY_SOURCE = 'Authored enterprise policy; catalog-defined inputs and outputs after qualified labour'
def retail_capabilities():
    aliases = {goods_policy(item)['legacy_retail_capability'] for item in tradable_ids()}
    aliases.discard(None)
    if (aliases | {'retail_goods'}) & set(recipe_ids()):
        raise ValueError('Market retail capability conflicts with a production recipe')
    return aliases | {'retail_goods'}


RETAIL_CAPABILITIES = retail_capabilities()

def executable_capabilities():
    return retail_capabilities() | set(recipe_ids())

# Import compatibility; admission always resolves the current validated catalog.
CAPABILITIES = executable_capabilities()


def paid_bread_recipe():
    recipe = recipe_spec('bread_recipe')
    if set(recipe['inputs']) != {'grain'} or set(recipe['outputs']) != {'bread'}:
        raise ValueError('Paid bread adapter requires a grain-to-bread catalog recipe')
    return recipe


def production_policy(business, recipe_id='bread_recipe'):
    """Resolve charter preferences; only the catalog supplies recipe quantities."""
    recipe = recipe_spec(recipe_id)
    policies = business.get('recipe_policies', {})
    if not isinstance(policies, dict):raise ValueError('Expected recipe policies object')
    overrides = policies.get(recipe_id)
    duration = recipe['work_minutes']
    if recipe_id == 'bread_recipe' and set(recipe['inputs']) == {'grain'} and set(recipe['outputs']) == {'bread'}:
        supplied = business.get('production_policy', {}) if overrides is None else overrides
        defaults = {**DEFAULT_POLICY, 'work_minutes': duration['default'],
                    'grain_per_shift': recipe['inputs']['grain'], 'bread_per_shift': recipe['outputs']['bread']}
        if not isinstance(supplied, dict):raise ValueError('Expected production policy object')
        policy = {**defaults, **supplied}
        bounds = {'target_bread': (2, 40), 'wage_gold': (1, 20), 'work_minutes': (duration['minimum'], duration['maximum']),
                  'grain_per_shift': (recipe['inputs']['grain'], recipe['inputs']['grain']),
                  'bread_per_shift': (recipe['outputs']['bread'], recipe['outputs']['bread'])}
        source = POLICY_SOURCE
    else:
        supplied = {} if overrides is None else overrides
        defaults = {'target_output': 8, 'wage_gold': 2, 'work_minutes': duration['default']}
        if not isinstance(supplied, dict):raise ValueError('Expected production policy object')
        policy = {**defaults, **supplied}
        bounds = {'target_output': (2, 40), 'wage_gold': (1, 20), 'work_minutes': (duration['minimum'], duration['maximum'])}
        source = 'Authored enterprise policy; catalog recipe after qualified labour'
    if set(policy) != set(defaults):
        raise ValueError('Unknown enterprise policy field')
    for key, (low, high) in bounds.items():
        if type(policy[key]) is not int or not low <= policy[key] <= high:
            raise ValueError('Invalid enterprise policy: ' + key)
    return {**policy, 'source': source}


def plan_work_policy(plan):
    terms = plan.get('work_terms', {})
    policy = terms.get('policy')
    if policy is None:
        return production_policy({})  # Historical pre-census display adapter only.
    recipe_id = terms.get('recipe_id', 'bread_recipe')
    return production_policy({'recipe_policies': {recipe_id: {
        k: v for k, v in policy.items() if k != 'source'}}}, recipe_id)


def current_work_terms(state, plan, observation=None):
    """Revalidate a pinned charter; no job or inventory effect is authorized here."""
    terms = plan.get('work_terms')
    if not terms:
        if state.get('town') is not None:
            raise ValueError('Initialized town work requires an enterprise contract')
        return
    recipe_id = terms.get('recipe_id')
    if (recipe_id not in recipe_ids() or terms.get('catalog_hash') != catalog_hash()
            or terms.get('recipe_hash') != recipe_hash(recipe_id)):
        raise ValueError('Enterprise or agreed work terms changed: catalog proof is absent or stale')
    business = (state.get('town') or {}).get('businesses', {}).get(terms.get('business_id'))
    if (not business or business.get('active', True) is not True or
            business.get('custodian') != plan['target'] or
            business.get('revision', 0) != terms.get('revision', 0) or
            recipe_id not in business.get('capabilities', []) or
            production_policy(business, recipe_id) != plan_work_policy(plan)):
        raise ValueError('Enterprise or agreed work terms changed')
    if terms.get('protocol') == 2:
        from employment import work_terms_hash
        from resident_identity import resident_identity_status
        from entrepreneurship import knows_recipe
        from economy_catalog import require_native_catalog
        if (terms.get('worker') != plan['actor'] or terms.get('employer') != plan['target']
                or terms.get('terms_hash') != work_terms_hash(terms)):
            raise ValueError('Paid employment identity or terms hash changed')
        if observation is not None:
            require_native_catalog(observation, recipe_id)
            for role in ('worker', 'employer'):
                identity = resident_identity_status(state, observation, terms[role])
                if not identity['qualified'] or identity['base_id'] != terms.get(role + '_base_id'):
                    raise ValueError('Paid employment resident identity changed')
            if not knows_recipe(state['people'][str(terms['employer'])], recipe_id,
                    state=state, observation=observation, actor_id=terms['employer']):
                raise ValueError('Employer no longer knows the agreed recipe')
    return business


def apply_enterprise_change(state, event_id, specification, observation, provenance):
    """Apply one validated charter revision to a private pending checkpoint."""
    town = state['town']
    allowed = {'id', 'expected_revision', 'name', 'custodian', 'capabilities', 'production_policy', 'recipe_policies', 'active', 'sale_commodities'}
    required = {'id', 'expected_revision', 'name', 'custodian', 'capabilities', 'active'}
    if set(specification) - allowed or required - set(specification):
        raise ValueError('Enterprise specification fields do not match contract')
    key = specification['id']
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', key):
        raise ValueError('Invalid enterprise ID')
    name = specification['name']
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or any(ord(c) < 32 for c in name):
        raise ValueError('Invalid public enterprise name')
    owner = specification['custodian']
    resident = town['residents'].get(str(owner))
    actor = next((a for a in observation.get('residents', []) if a.get('id') == owner), {})
    if (type(owner) is not int or not resident or actor.get('isPerson') is not True):
        raise ValueError('Enterprise custodian must be a currently observed initialized adult')
    caps = specification['capabilities']
    if (not isinstance(caps, list) or not caps or any(not isinstance(c, str) for c in caps) or
            len(caps) != len(set(caps)) or not set(caps) <= executable_capabilities()):
        raise ValueError('Unsupported executable enterprise capabilities')
    if type(specification['active']) is not bool:
        raise ValueError('Enterprise active flag must be boolean')
    sale_goods = specification.get('sale_commodities')
    if 'sale_commodities' in specification:
        if (not isinstance(sale_goods, list) or any(not isinstance(item, str) for item in sale_goods)
                or len(sale_goods) != len(set(sale_goods)) or not set(sale_goods) <= set(tradable_ids())):
            raise ValueError('Invalid explicit enterprise sale commodities')
        aliases = {item for item in tradable_ids() if goods_policy(item)['legacy_retail_capability'] in caps}
        if 'retail_goods' not in caps and not set(sale_goods) <= aliases:
            raise ValueError('Explicit sale commodities require a matching retail capability')
    if 'retail_goods' in caps and not sale_goods:
        raise ValueError('Generic retail requires nonempty explicit sale commodities')
    supplied_policy = specification.get('production_policy', {})
    if not isinstance(supplied_policy, dict):
        raise ValueError('Expected production policy object')
    supplied_recipes = specification.get('recipe_policies', {})
    if (not isinstance(supplied_recipes, dict) or
            not set(supplied_recipes) <= (set(caps) & set(recipe_ids())) or
            any(not isinstance(p, dict) for p in supplied_recipes.values())):
        raise ValueError('Recipe policies require explicitly registered executable recipes')
    if 'bread_recipe' not in recipe_ids() and supplied_policy:
        raise ValueError('Legacy bread policy has no catalog recipe; use recipe_policies')
    policy = production_policy({'production_policy': supplied_policy}) if 'bread_recipe' in recipe_ids() else {'source':'No legacy bread recipe'}
    recipe_policies = {recipe_id: {k: v for k, v in production_policy(
        {'recipe_policies': supplied_recipes}, recipe_id).items() if k != 'source'}
        for recipe_id in supplied_recipes}
    charter = {'production_policy': supplied_policy, 'recipe_policies': recipe_policies}
    costs = {recipe_id: {**recipe_spec(recipe_id)['inputs'],
        'labour_game_minutes': production_policy(charter, recipe_id)['work_minutes'],
        'wage_gold': production_policy(charter, recipe_id)['wage_gold']}
        for recipe_id in sorted(set(caps) & set(recipe_ids()))}
    old = town.get('businesses', {}).get(key)
    revision = old.get('revision', 0) if old else 0
    if type(specification['expected_revision']) is not int or specification['expected_revision'] != revision:
        raise ValueError('Stale enterprise revision')
    if work_account_conflict(state,actors=(owner,(old or {}).get('custodian')),
                             business_ids=(key,),observation=observation):
        raise ValueError('Unsettled owner work reserves this enterprise or custodian account')
    if old and any(c['status'] in ('accepted', 'held') for c in old.get('contracts', [])):
        raise ValueError('Unsettled employment contract prevents enterprise changes')
    if not old and len(town.get('businesses', {})) >= 128:
        raise ValueError('Enterprise capacity reached')
    business = copy.deepcopy(old) if old else {'workers': [], 'contracts': []}
    business.update(id=key, name=name.strip(), owner=owner, custodian=owner,
        capabilities=sorted(caps), active=specification['active'], revision=revision + 1,
        resource_account='native-inventory:' + str(owner), separate_legal_cash_account=False,
        production_policy={k: v for k, v in policy.items() if k != 'source'},
        recipe_policies=recipe_policies, costs=costs,
        provenance=provenance)
    if 'sale_commodities' in specification:
        business['sale_commodities'] = sorted(sale_goods)
    else:
        # An exact new revision without the field returns to its explicit legacy
        # capability projection; never retain stale declarations from an old one.
        business.pop('sale_commodities', None)
    state['town']['businesses'][key] = business
    event = {'id': event_id, 'request': copy.deepcopy(specification), 'revision': revision + 1,
             'previous_custodian': old.get('custodian') if old else None, 'custodian': owner,
             'game_day': observation.get('gameDays'), 'inventory_effect': 'none'}
    state['town'].setdefault('enterprise_events', []).append(event)
    event['source'] = provenance
    return business, event


class Enterprises:
    def configure_enterprise(self, event_id, specification, observation):
        self._agency_guard(observation)
        if self.agency_busy() or self.conversation_busy():
            raise ValueError('Finish active resident activities before changing an enterprise')
        town = self.active.get('town')
        if not town:
            raise ValueError('Initialize the population before registering enterprises')
        if not isinstance(event_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', event_id):
            raise ValueError('Invalid enterprise event ID')
        if not isinstance(specification, dict):
            raise ValueError('Expected enterprise specification')
        # Exact request identity makes retries safe, including old revision numbers.
        for previous in town.get('enterprise_events', []):
            if previous['id'] == event_id:
                if previous['request'] != specification:
                    raise ValueError('Enterprise event ID reused with different terms')
                return {'duplicate': True, 'event': copy.deepcopy(previous)}
        state = copy.deepcopy(self.active)
        business, event = apply_enterprise_change(state, event_id, specification, observation,
            'Explicit operator-authored charter; assets stay in each physical custodian inventory')
        return {'checkpoint': self._write(state, 'enterprise charter updated without transferring or minting assets'),
                'business': business, 'event': event}
