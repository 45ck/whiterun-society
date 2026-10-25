"""Validated authored recipes shared with the native effect authority.

Version 1 deliberately permits one input and one distinct output and no currency
conversion. Cross-recipe cycles are allowed; this is not an economic calibration.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

DEFAULT_PATH = Path(__file__).with_name('config') / 'economy-catalog.json'
MAX_STOCK = 2**31 - 1
ID = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}', re.ASCII)
RECORD_TYPES = {'MISC', 'ALCH', 'INGR'}


def _fields(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):raise ValueError('Invalid ' + label + ' fields')


def _string(value, limit, label):
    if (not isinstance(value, str) or not 1 <= len(value) <= limit or value != value.strip()
        or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise ValueError('Invalid ' + label)


def _id(value, label):
    if not isinstance(value, str) or not ID.fullmatch(value):raise ValueError('Invalid ' + label)


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:raise ValueError('Invalid ' + label)


def canonical_json(value):
    """Canonical UTF-8 JSON: sorted ASCII keys, unchanged strings, integers only."""
    def check(item):
        if item is None or type(item) is bool:return
        if type(item) is int:
            _integer(item, -(2**53 - 1), 2**53 - 1, 'canonical integer');return
        if isinstance(item, str):
            if any(0xD800 <= ord(c) <= 0xDFFF for c in item):raise ValueError('Unpaired surrogate is not canonical text')
            return
        if isinstance(item, list):
            for child in item:check(child)
            return
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*', key, re.ASCII):
                    raise ValueError('Canonical object keys must be ASCII identifiers')
                check(child)
            return
        raise ValueError('Canonical catalog JSON does not permit floats or unsupported values')
    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def validate_catalog(raw):
    _fields(raw, ('schema_version', 'version', 'commodities', 'recipes'), 'catalog')
    _integer(raw['schema_version'], 1, 1, 'catalog schema version');_id(raw['version'], 'catalog version')
    if not isinstance(raw['commodities'], list) or not 1 <= len(raw['commodities']) <= 64:
        raise ValueError('Catalog requires 1..64 commodities')
    if not isinstance(raw['recipes'], list) or not 1 <= len(raw['recipes']) <= 128:
        raise ValueError('Catalog requires 1..128 recipes')
    commodities = {};native_ids = set()
    for commodity in raw['commodities']:
        _fields(commodity, ('id', 'label', 'native', 'currency', 'provenance'), 'commodity')
        _id(commodity['id'], 'commodity ID');_string(commodity['label'], 120, 'commodity label')
        _string(commodity['provenance'], 500, 'commodity provenance')
        if commodity['id'] in commodities:raise ValueError('Duplicate commodity ID')
        if type(commodity['currency']) is not bool:raise ValueError('Currency flag must be boolean')
        native = commodity['native'];_fields(native, ('plugin', 'local_form_id', 'record_type'), 'native commodity')
        if (not isinstance(native['plugin'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,119}\.(?:esm|esp|esl)', native['plugin'], re.ASCII | re.IGNORECASE)
            or '..' in native['plugin']):raise ValueError('Invalid native plugin name')
        _integer(native['local_form_id'], 1, 0xFFFFFF, 'local native form ID')
        if not isinstance(native['record_type'],str) or native['record_type'] not in RECORD_TYPES:raise ValueError('Unsupported inventory record type')
        identity = (native['plugin'].lower(), native['local_form_id'])
        if identity in native_ids:raise ValueError('Duplicate native commodity mapping')
        native_ids.add(identity);commodities[commodity['id']] = commodity
    if {c['id'] for c in commodities.values() if c['currency']} != {'gold'}:
        raise ValueError('Version 1 requires gold as its only currency')
    recipes = set()
    for recipe in raw['recipes']:
        _fields(recipe, ('id', 'version', 'inputs', 'outputs', 'work_minutes', 'provenance'), 'recipe')
        _id(recipe['id'], 'recipe ID');_integer(recipe['version'], 1, 1000000, 'recipe version')
        if recipe['id'] in recipes:raise ValueError('Duplicate recipe ID')
        recipes.add(recipe['id']);_string(recipe['provenance'], 500, 'recipe provenance')
        for side in ('inputs', 'outputs'):
            quantities = recipe[side]
            if not isinstance(quantities, dict) or len(quantities) != 1:raise ValueError('Version 1 requires exactly one input and one output')
            for key, count in quantities.items():
                if key not in commodities or commodities[key]['currency']:raise ValueError('Recipe references missing commodity or currency')
                _integer(count, 1, 1000, 'recipe quantity')
        source = next(iter(recipe['inputs']));target = next(iter(recipe['outputs']))
        if source == target:raise ValueError('Recipe input and output must differ')
        minutes = recipe['work_minutes'];_fields(minutes, ('minimum', 'default', 'maximum'), 'recipe work minutes')
        for value in minutes.values():_integer(value, 5, 120, 'work duration')
        if not minutes['minimum'] <= minutes['default'] <= minutes['maximum']:raise ValueError('Unordered work duration bounds')
    canonical_json(raw)
    return copy.deepcopy(raw)


def load_catalog(path=None):
    return validate_catalog(json.loads(Path(path or DEFAULT_PATH).read_text(encoding='utf-8')))


ECONOMY_CATALOG = load_catalog()


def _catalog(catalog):return ECONOMY_CATALOG if catalog is None else validate_catalog(catalog)


def catalog_hash(catalog=None):
    return hashlib.sha256(canonical_json(_catalog(catalog)).encode('utf-8')).hexdigest()


def commodity_ids(catalog=None):return tuple(sorted(c['id'] for c in _catalog(catalog)['commodities']))


def recipe_ids(catalog=None):return tuple(sorted(r['id'] for r in _catalog(catalog)['recipes']))


def recipe_spec(recipe_id, catalog=None):
    result = next((r for r in _catalog(catalog)['recipes'] if r['id'] == recipe_id), None)
    if result is None:raise ValueError('Unknown catalog recipe')
    return copy.deepcopy(result)


def recipe_hash(recipe_id, catalog=None):
    trusted=_catalog(catalog)
    recipe=next((row for row in trusted['recipes'] if row['id']==recipe_id),None)
    if recipe is None:raise ValueError('Unknown catalog recipe')
    digest=hashlib.sha256(canonical_json(trusted).encode('utf-8')).hexdigest()
    payload = {'catalog_hash': digest, 'recipe': recipe}
    return hashlib.sha256(canonical_json(payload).encode('utf-8')).hexdigest()


def apply_recipe(inventory, recipe_id, catalog=None):
    catalog = _catalog(catalog)
    recipe=next((row for row in catalog['recipes'] if row['id']==recipe_id),None)
    if recipe is None:raise ValueError('Unknown catalog recipe')
    if not isinstance(inventory, dict) or set(inventory) != {row['id'] for row in catalog['commodities']}:
        raise ValueError('Recipe requires the complete configured commodity account')
    for count in inventory.values():_integer(count, 0, MAX_STOCK, 'observed inventory count')
    after = dict(inventory)
    for key, count in recipe['inputs'].items():
        if after[key] < count:raise ValueError('Insufficient observed recipe input')
        after[key] -= count
    for key, count in recipe['outputs'].items():
        after[key] += count
        if after[key] > MAX_STOCK:raise ValueError('Recipe output would overflow native inventory')
    return after


def native_catalog_matches(observation, recipe_id=None, catalog=None):
    native = observation.get('economy_catalog') or {}
    if not isinstance(native, dict) or native.get('available') is not True:return False
    # Validate/serialize the manifest once per observation, not once per recipe.
    # Hashing this immutable local snapshot also avoids identity-only caching of
    # a catalogue object that a configuration reload could replace or mutate.
    trusted=_catalog(catalog)
    digest=hashlib.sha256(canonical_json(trusted).encode('utf-8')).hexdigest()
    if native.get('catalog_hash')!=digest:return False
    if (native.get('type_verified') is not True or native.get('errors') != {}
        or not isinstance(native.get('item_ids'),list) or native['item_ids'] != sorted(row['id'] for row in trusted['commodities'])):return False
    hashes = native.get('recipe_hashes')
    if not isinstance(hashes, dict):return False
    recipes={row['id']:row for row in trusted['recipes']}
    required=recipes if recipe_id is None else (recipe_id,)
    for key in required:
        if key not in recipes:return False
        expected=hashlib.sha256(canonical_json({'catalog_hash':digest,'recipe':recipes[key]}).encode('utf-8')).hexdigest()
        if hashes.get(key)!=expected:return False
    return True


def require_native_catalog(observation, recipe_id=None):
    if not native_catalog_matches(observation,recipe_id):
        raise ValueError('A matching resolved and type-verified native economy catalog is required')
    return catalog_hash()
