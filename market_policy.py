"""Reviewed market search bounds, independent of executable inventory recipes.

These are authored options, not equilibrium prices or knowledge about a seller.
An installed policy cannot authorize a changed in-flight trade retrospectively.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

import economy_catalog

DEFAULT_PATH = Path(__file__).with_name('config') / 'market-policy.json'
MAX_BYTES = 256 * 1024
ID = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}', re.ASCII)


def _fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError('Invalid market policy fields')


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def validate_policy(raw):
    _fields(raw, ('schema_version', 'id', 'catalog_hash', 'goods', 'provenance'))
    if (type(raw['schema_version']) is not int or raw['schema_version'] != 1
            or not isinstance(raw['id'], str) or not ID.fullmatch(raw['id'])
            or raw['catalog_hash'] != economy_catalog.catalog_hash()):
        raise ValueError('Invalid market policy identity or catalog binding')
    text = raw['provenance']
    if (not isinstance(text, str) or not 1 <= len(text) <= 500 or text != text.strip()
            or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in text)):
        raise ValueError('Invalid market policy provenance')
    metadata = {row['id']: row for row in economy_catalog.ECONOMY_CATALOG['commodities']}
    if not isinstance(raw['goods'], list) or not 1 <= len(raw['goods']) <= 63:
        raise ValueError('Market policy requires 1..63 goods')
    goods, capabilities = set(), {'retail_goods'}
    for row in raw['goods']:
        _fields(row, ('commodity', 'legacy_retail_capability', 'max_quantity', 'quantity_choices',
                      'price_min', 'price_max', 'price_choices', 'reserve_mode'))
        commodity, capability = row['commodity'], row['legacy_retail_capability']
        if (not isinstance(commodity, str) or commodity not in metadata
                or metadata[commodity]['currency'] or commodity in goods):
            raise ValueError('Market good must be a unique registered noncurrency commodity')
        goods.add(commodity)
        if capability is not None:
            if (not isinstance(capability, str) or not ID.fullmatch(capability)
                    or capability in capabilities):
                raise ValueError('Invalid duplicate or conflicting retail capability')
            capabilities.add(capability)
        if (not _integer(row['max_quantity'], 1, 10)
                or not _integer(row['price_min'], 1, 100)
                or not _integer(row['price_max'], row['price_min'], 100)):
            raise ValueError('Invalid market quantity or price bounds')
        for field, low, high in (('quantity_choices', 1, row['max_quantity']),
                                 ('price_choices', row['price_min'], row['price_max'])):
            values = row[field]
            if (not isinstance(values, list) or not values
                    or any(not _integer(value, low, high) for value in values)
                    or values != sorted(set(values))):
                raise ValueError('Market choices must be distinct increasing bounded integers')
        if row['reserve_mode'] not in ('existing_food_policy', 'seller_choice'):
            raise ValueError('Unknown market reserve mode')
        if row['reserve_mode'] == 'existing_food_policy' and commodity != 'bread':
            raise ValueError('Existing food reserve adapter only supports bread')
    economy_catalog.canonical_json(raw)
    return copy.deepcopy(raw)


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:raise ValueError('Duplicate market policy JSON key')
        result[key] = value
    return result


def load_policy(path=None):
    data = Path(path or DEFAULT_PATH).read_bytes()
    if len(data) > MAX_BYTES:raise ValueError('Market policy file exceeds size limit')
    return validate_policy(json.loads(data.decode('utf-8'), object_pairs_hook=_unique_pairs))


MARKET_POLICY = load_policy()


def _policy(policy):return validate_policy(MARKET_POLICY if policy is None else policy)


def policy_hash(policy=None):
    return hashlib.sha256(economy_catalog.canonical_json(_policy(policy)).encode('utf-8')).hexdigest()


def goods_policy(commodity, policy=None):
    result = next((row for row in _policy(policy)['goods'] if row['commodity'] == commodity), None)
    if result is None:raise ValueError('Commodity is not enabled by the market policy')
    return copy.deepcopy(result)


def tradable_ids(policy=None):return tuple(sorted(row['commodity'] for row in _policy(policy)['goods']))


def advertised_goods(business, policy=None):
    """Public declarations only; no inference from production, stock or names."""
    reviewed = _policy(policy)
    if ({row['legacy_retail_capability'] for row in reviewed['goods']} | {'retail_goods'}) & set(economy_catalog.recipe_ids()):
        raise ValueError('Market retail capability conflicts with a production recipe')
    if not isinstance(business, dict) or business.get('active', True) is not True:return ()
    caps = business.get('capabilities', [])
    if not isinstance(caps, list) or any(not isinstance(value, str) for value in caps):return ()
    if 'sale_commodities' in business:
        declared = business['sale_commodities']
        enabled = {row['commodity'] for row in reviewed['goods']}
        if (not isinstance(declared, list) or any(not isinstance(value, str) for value in declared)
                or len(declared) != len(set(declared)) or not set(declared) <= enabled):return ()
        allowed = {row['commodity'] for row in reviewed['goods']
                   if row['legacy_retail_capability'] in caps}
        if 'retail_goods' not in caps and not set(declared) <= allowed:return ()
        return tuple(sorted(declared))
    return tuple(sorted(row['commodity'] for row in reviewed['goods']
                        if row['legacy_retail_capability'] is not None
                        and row['legacy_retail_capability'] in caps))
