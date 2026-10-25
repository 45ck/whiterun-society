"""Authored test-only native catalog evidence; never live resolution proof."""
from economy_catalog import ECONOMY_CATALOG, catalog_hash, commodity_ids, recipe_hash, recipe_ids


def native_catalog():
    return {'available': True, 'type_verified': True, 'errors': {},
            'catalog_hash': catalog_hash(), 'version': ECONOMY_CATALOG['version'],
            'recipe_hashes': {key: recipe_hash(key) for key in recipe_ids()},
            'item_ids': list(commodity_ids())}


def native_ack(command, status='applied', **fields):
    """Authored acknowledgement of this exact command, not fallback identity."""
    return {'id': command['id'], 'status': status,
            **{key: command[key] for key in ('catalog_hash', 'recipe_id', 'recipe_hash') if key in command}, **fields}
