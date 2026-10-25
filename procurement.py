"""Alternative input purchases; shared inventory is not allocated by listing choices."""
import hashlib
from economy_catalog import commodity_ids, recipe_ids, recipe_spec, recipe_hash, catalog_hash, canonical_json, MAX_STOCK
from enterprises import production_policy
from entrepreneurship import knows_recipe
from market_policy import goods_policy, policy_hash, tradable_ids, advertised_goods
from opportunities import commodity_sellers

PINS = ('supplier', 'business_id', 'business_revision', 'recipe_id', 'recipe_hash',
        'catalog_hash', 'market_policy_hash', 'commodity', 'quantity', 'purpose',
        'listing_business_id', 'listing_revision')


def _identity(choice):
    return 'purchase-' + hashlib.sha256(canonical_json({k: choice[k] for k in PINS}).encode()).hexdigest()[:24]


def input_procurement(state, observation, actor):
    person = state.get('people', {}).get(str(actor))
    rows = [r for r in observation.get('residents', []) if r.get('id') == actor]
    if not person or len(rows) != 1 or rows[0].get('isPerson') is not True:return []
    inventory = rows[0].get('inventory', {})
    if any(type(inventory.get(k)) is not int or not 0 <= inventory[k] <= MAX_STOCK for k in commodity_ids()):return []
    result = []
    # Resolve the reviewed definitions once per observation, not per supplier
    # and quantity. These are call-local snapshots, never stale global caches.
    catalog_digest=catalog_hash();market_digest=policy_hash()
    enabled=set(tradable_ids());recipes=set(recipe_ids());suppliers={};markets={};recipe_digests={}
    for key, business in sorted((state.get('town') or {}).get('businesses', {}).items()):
        if (business.get('active', True) is not True or business.get('owner') != actor
                or business.get('custodian') != actor):continue
        for rid in sorted(set(business.get('capabilities', [])) & recipes):
            if not knows_recipe(person, rid,state=state,observation=observation,actor_id=actor):continue
            recipe = recipe_spec(rid)
            try:policy = production_policy(business, rid)
            except (ValueError, KeyError, TypeError):continue
            output, made = next(iter(recipe['outputs'].items()))
            target = policy.get('target_output', policy.get('target_bread'))
            batches = max(0, (target - inventory[output] + made - 1) // made)
            for commodity, used in sorted(recipe['inputs'].items()):
                shortfall = max(0, batches * used - inventory[commodity])
                if not shortfall or commodity not in enabled:continue
                if commodity not in markets:markets[commodity]=goods_policy(commodity)
                market = markets[commodity]
                quantities = [q for q in market['quantity_choices']
                              if q <= shortfall and q * market['price_min'] <= inventory['gold']]
                if commodity not in suppliers:suppliers[commodity]=commodity_sellers(state, observation, actor, commodity)
                if rid not in recipe_digests:recipe_digests[rid]=recipe_hash(rid)
                for seller in suppliers[commodity]:
                    for quantity in quantities:
                        choice = {'supplier': seller['id'], 'business_id': key,
                            'business_revision': business.get('revision', 0), 'recipe_id': rid,
                            'recipe_hash': recipe_digests[rid], 'catalog_hash': catalog_digest,
                            'market_policy_hash': market_digest, 'commodity': commodity,
                            'quantity': quantity, 'shortfall': shortfall, 'purpose': 'production_input',
                            'listing_business_id': seller['listing_business_id'],
                            'listing_revision': seller['listing_revision'],
                            'distance': seller['distance']}
                        choice['id'] = _identity(choice)
                        result.append(choice)
    return result


def validate_procurement(state, observation, actor, selected):
    """Recheck immutable choice and current need; walking changes distance only."""
    if not isinstance(selected, dict):return False
    try:
        if not validate_procurement_terms(state, actor, selected):return False
        return any(all(row[k] == selected[k] for k in PINS)
                   for row in input_procurement(state, observation, actor))
    except (KeyError, TypeError, ValueError):return False


def validate_procurement_terms(state, actor, selected, observation=None):
    """Validate agreed purpose without consulting stock altered by this exchange.

    Admission separately checks current need, money and routing. A pending trade
    owns its accounts and must not invalidate itself via its own reservations.
    """
    if not isinstance(selected,dict):return False
    try:
        if selected.get('id')!=_identity(selected) or selected.get('purpose')!='production_input':return False
        town=state.get('town') or {};businesses=town.get('businesses',{})
        own=businesses.get(selected['business_id'],{});listing=businesses.get(selected['listing_business_id'],{})
        person=state.get('people',{}).get(str(actor),{})
        rid=selected['recipe_id'];item=selected['commodity'];supplier=selected['supplier']
        if (type(supplier) is not int or supplier<=0 or supplier==actor
            or str(supplier) not in town.get('residents',{}) or str(supplier) not in state.get('people',{})
            or own.get('active',True) is not True or own.get('owner')!=actor or own.get('custodian')!=actor
            or own.get('revision',0)!=selected['business_revision'] or rid not in own.get('capabilities',[])
            or not knows_recipe(person,rid,state=state,observation=observation,actor_id=actor) or item not in recipe_spec(rid)['inputs']
            or selected['recipe_hash']!=recipe_hash(rid) or selected['catalog_hash']!=catalog_hash()
            or selected['market_policy_hash']!=policy_hash() or listing.get('custodian')!=supplier
            or listing.get('revision',0)!=selected['listing_revision'] or item not in advertised_goods(listing)
            or type(selected['quantity']) is not int or selected['quantity'] not in goods_policy(item)['quantity_choices']):return False
        production_policy(own,rid)
        return True
    except (KeyError,TypeError,ValueError):return False


def grain_procurement(state, observation, actor):
    """Compatibility filter; new decisions use generic alternative purchases."""
    return [row for row in input_procurement(state, observation, actor) if row['commodity'] == 'grain']
