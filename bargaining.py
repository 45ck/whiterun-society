"""Bounded resident offers; no global prices or private counterparty resources.

The price ladder is an authored search space, not an equilibrium calculation.
Only the resident's own completed transactions supply historical price evidence.
"""
import copy
from food import allocation
from market_policy import goods_policy, policy_hash
from economy_catalog import commodity_ids, catalog_hash, native_catalog_matches

PRICING_POLICY = 'resident-bargaining-v1'
MAX_ECONOMIC_CALLS = 6


def own_prices(person, commodity='bread'):
    result = []
    for memory in person.get('memories', []):
        quantity, paid = memory.get('quantity',memory.get(commodity)), memory.get('gold')
        if memory.get('commodity','bread')!=commodity:continue
        if (memory.get('kind') == 'completed_trade' and type(quantity) is int and quantity > 0
                and type(paid) is int and 0 < paid <= quantity * 100):
            result.append({**({'septims_per_loaf':paid/quantity} if commodity=='bread' else {}),'septims_per_unit':paid/quantity,'commodity':commodity, 'role': memory.get('role'),
                           'source': 'Own completed trade', 'event_id': memory.get('event_id')})
    return result[-6:]


def price_choices(person, maximum=100, above=0, commodity='bread'):
    """Dense low bids, wider higher bids and remembered-price neighbours."""
    if type(maximum) is not int or type(above) is not int:
        raise ValueError('Integer price bounds required')
    policy=goods_policy(commodity);cap=min(policy['price_max'],maximum)
    values=set(policy['price_choices']) | {cap,above+1}
    for record in own_prices(person,commodity):
        anchor = round(record['septims_per_unit'])
        values.update((anchor - 1, anchor, anchor + 1))
    return sorted(v for v in values if max(above,policy['price_min']-1) < v <= cap)


def quote_valid(state, plan, observation):
    quote = plan.get('counter_quote')
    if not quote:
        return False
    if (quote.get('catalog_hash')!=catalog_hash() or not native_catalog_matches(observation)
            or quote.get('market_policy_hash')!=policy_hash() or plan.get('market_policy_hash')!=policy_hash()):return False
    seller = next((r for r in observation.get('residents', []) if r['id'] == plan['target']), {})
    commodity=plan.get('commodity','bread')
    inventory = {k: seller.get('inventory', {}).get(k) for k in commodity_ids()}
    person = state['people'].get(str(plan['target']), {})
    return (quote['seller'] == plan['target'] and quote['buyer'] == plan['actor']
            and quote['unit_price'] == plan['unit_price'] and inventory == quote['inventory']
            and quote.get('commodity')==commodity and quote.get('quantity')==plan.get('quantity',1)
            and quote.get('cost')==plan.get('quantity',1)*plan['unit_price']
            and quote.get('purpose')==plan.get('purpose') and type(inventory.get(commodity)) is int
            and inventory[commodity]>=plan.get('quantity',1)
            and (goods_policy(commodity)['reserve_mode']!='existing_food_policy' or (person.get('food_policy') == quote['policy']
            and allocation(person, inventory) == quote['allocation'])))


def record_quote(state, plan, context, price, claim_id):
    """Internal consent evidence; never put these private fields in buyer prompts."""
    person = state['people'][str(plan['target'])]
    stock = context['own_food_allocation'];commodity=plan.get('commodity','bread')
    plan['counter_quote'] = {'buyer': plan['actor'], 'seller': plan['target'], 'unit_price': price,
        'commodity':commodity,'quantity':plan.get('quantity',1),'cost':price*plan.get('quantity',1),
        'purpose':plan.get('purpose'),'market_policy_hash':context.get('market_policy_hash'),'inventory': {k: context['observed_inventory'][k] for k in commodity_ids()},
        'catalog_hash':context.get('inventory_catalog_hash'),
        'policy': copy.deepcopy(person.get('food_policy')), 'allocation': copy.deepcopy(stock),
        'release_reserved': goods_policy(commodity)['reserve_mode']=='existing_food_policy' and stock['allocated'] and stock['for_sale'] < plan.get('quantity',1), 'claim_id': claim_id}


def accept_quote(state, plan, observation):
    if not quote_valid(state, plan, observation):
        raise ValueError('Seller quote changed before buyer acceptance')
    quote = plan['counter_quote']
    plan['counter_quote_accepted'] = True
    if quote['release_reserved']:
        plan['reserve_release'] = {'plan_id': plan['id'], 'trade_id': plan['trade_id'],
            'buyer': plan['actor'], 'seller': plan['target'], 'quantity': quote['quantity'],'commodity':quote['commodity'],
            'unit_price': quote['unit_price'], 'policy': copy.deepcopy(quote['policy']),
            'catalog_hash':quote['catalog_hash'],'market_policy_hash':quote['market_policy_hash'],
            'inventory': copy.deepcopy(quote['inventory']), 'decision_claim_id': quote['claim_id']}
