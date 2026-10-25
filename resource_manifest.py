"""Reviewed finite external-resource policy; selection never mutates inventory."""
import copy
import hashlib
import json
from pathlib import Path
from economy_catalog import canonical_json, catalog_hash, commodity_ids, MAX_STOCK, ID

DEFAULT_PATH=Path(__file__).with_name('config')/'resource-manifest.json'


def _fields(value,fields,label):
    if not isinstance(value,dict) or set(value)!=set(fields):raise ValueError('Invalid '+label+' fields')


def _integer(value,minimum,maximum,label):
    if type(value) is not int or not minimum<=value<=maximum:raise ValueError('Invalid '+label)


def _id(value,label):
    if not isinstance(value,str) or not ID.fullmatch(value):raise ValueError('Invalid '+label)


def _text(value,label):
    if (not isinstance(value,str) or not 1<=len(value)<=500 or value!=value.strip()
            or any(ord(character)<32 or 0xd800<=ord(character)<=0xdfff for character in value)):
        raise ValueError('Invalid '+label)


def validate_manifest(raw):
    _fields(raw,('schema_version','id','version','catalog_hash','capacity','default_grant','overrides','max_recipient_stock','provenance'),'resource manifest')
    _integer(raw['schema_version'],1,1,'resource schema version')
    _id(raw['id'],'resource program ID');_id(raw['version'],'resource policy version');_text(raw['provenance'],'resource provenance')
    if raw['catalog_hash']!=catalog_hash():raise ValueError('Resource manifest catalog hash differs from the reviewed catalog')
    items=commodity_ids()
    def quantities(value,label,positive=False):
        _fields(value,items,label)
        for quantity in value.values():_integer(quantity,0,MAX_STOCK,label+' quantity')
        if positive and not any(value.values()):raise ValueError('A resource grant must contain a positive quantity')
    quantities(raw['capacity'],'resource capacity')
    _integer(raw['max_recipient_stock'],0,MAX_STOCK,'recipient stock limit')
    def grant(value):
        quantities(value,'resource grant',True)
        if any(value[item]>raw['capacity'][item] for item in items):raise ValueError('Resource grant exceeds finite capacity')
    grant(raw['default_grant'])
    if not isinstance(raw['overrides'],list) or len(raw['overrides'])>128:raise ValueError('Resource overrides require a bounded list')
    seen_ids={'default'};seen_actors=set()
    for override in raw['overrides']:
        _fields(override,('id','selector','grant','provenance'),'resource override')
        _id(override['id'],'resource selector ID');_text(override['provenance'],'override provenance')
        if override['id'] in seen_ids:raise ValueError('Duplicate or reserved resource selector ID')
        seen_ids.add(override['id'])
        selector=override['selector'];_fields(selector,('actor','actor_base_id'),'resource recipient selector')
        for key in ('actor','actor_base_id'):_integer(selector[key],1,0xffffffff,'recipient '+key)
        if selector['actor'] in seen_actors:raise ValueError('Duplicate or aliased resource recipient selector')
        seen_actors.add(selector['actor']);grant(override['grant'])
    canonical_json(raw)
    return copy.deepcopy(raw)


def load_manifest(path=None):
    def unique_fields(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate resource manifest JSON field')
            result[key]=value
        return result
    with Path(path or DEFAULT_PATH).open('rb') as handle:raw=handle.read(262145)
    if len(raw)>262144:raise ValueError('Resource manifest exceeds 256 KiB')
    return validate_manifest(json.loads(raw.decode('utf-8'),object_pairs_hook=unique_fields))


def _digest(value):return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def manifest_hash(manifest=None):
    return _digest(load_manifest() if manifest is None else validate_manifest(manifest))


def select_grant(manifest,actor,actor_base_id):
    manifest=validate_manifest(manifest)
    _integer(actor,1,0xffffffff,'recipient actor');_integer(actor_base_id,1,0xffffffff,'recipient actor_base_id')
    selector_id='default';grant=manifest['default_grant']
    for override in manifest['overrides']:
        if override['selector']['actor']==actor:
            if override['selector']['actor_base_id']!=actor_base_id:raise ValueError('Resource recipient base identity differs from the authored selector')
            selector_id=override['id'];grant=override['grant'];break
    payload={'catalog_hash':manifest['catalog_hash'],'manifest_hash':_digest(manifest),
             'recipient':{'actor':actor,'actor_base_id':actor_base_id},'selector_id':selector_id,'grant':grant}
    return {'selector_id':selector_id,'grant':copy.deepcopy(grant),'grant_hash':_digest(payload)}
