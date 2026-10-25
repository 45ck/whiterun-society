"""Explicit authored conversation inputs, never autonomous resident choices."""
import copy
import hashlib
import json
import re


def validate_scenario(value):
    if not isinstance(value,dict) or set(value)!={'version','id','participants','max_turns','provenance'}:
        raise ValueError('Invalid conversation scenario fields')
    if type(value['version']) is not int or value['version']!=1:
        raise ValueError('Unsupported conversation scenario version')
    if not isinstance(value['id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',value['id']):
        raise ValueError('Invalid conversation scenario ID')
    pair=value['participants']
    if not isinstance(pair,list) or len(pair)!=2 or any(type(a) is not int or not 0<a<=0xffffffff for a in pair) or pair[0]==pair[1]:
        raise ValueError('Scenario requires two distinct explicit resident IDs')
    if type(value['max_turns']) is not int or not 2<=value['max_turns']<=6:
        raise ValueError('Scenario turn limit must be an integer from 2 to 6')
    text=value['provenance']
    if (not isinstance(text,str) or not 1<=len(text)<=500 or text!=text.strip()
            or any(ord(c)<32 or ord(c)==127 or 0xd800<=ord(c)<=0xdfff for c in text)):
        raise ValueError('Bounded authored scenario provenance required')
    return copy.deepcopy(value)


def scenario_hash(value):
    snapshot=validate_scenario(value)
    encoded=json.dumps(snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()
