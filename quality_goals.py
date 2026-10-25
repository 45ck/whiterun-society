"""Evaluate versioned data-defined engineering targets; unknowns never pass."""
import copy
from functools import lru_cache
import json
import hashlib
import math
from pathlib import Path


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_catalog(catalog):
    if not isinstance(catalog,dict) or type(catalog.get('version')) is not int or catalog['version']<1:
        raise ValueError('Invalid quality-goal catalog version')
    if not isinstance(catalog.get('source'),str) or not isinstance(catalog.get('items'),list):
        raise ValueError('Invalid quality-goal catalog')
    ids=set()
    for row in catalog['items']:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or row['id'] in ids:
            raise ValueError('Quality-goal IDs must be unique strings')
        ids.add(row['id'])
        if not all(isinstance(row.get(k),str) and row[k] for k in ('objective','measure','unit','scope')):
            raise ValueError('Missing quality-goal description')
        if row.get('direction') not in ('gte','lte') or not finite(row.get('target')):
            raise ValueError('Invalid quality-goal threshold')
        if type(row.get('minimum_sample')) is not int or row['minimum_sample']<0:
            raise ValueError('Invalid quality-goal sample requirement')
        for key in ('metric_path','sample_path'):
            value=row.get(key)
            if value is not None and (not isinstance(value,str) or not value or any(not p for p in value.split('.'))):
                raise ValueError('Invalid quality-goal metric path')
    return catalog


@lru_cache(maxsize=1)
def _catalog():
    return validate_catalog(json.loads((Path(__file__).parent/'config/quality-goals.json').read_text(encoding='utf-8')))


def path_value(metrics,path):
    value=metrics
    for key in path.split('.') if path else []:
        if not isinstance(value,dict):return None
        value=value.get(key)
    return value if path and finite(value) else None


def quality_goals(metrics,catalog=None):
    config=_catalog() if catalog is None else validate_catalog(catalog)
    result=[]
    for definition in config['items']:
        row=copy.deepcopy(definition)
        value=path_value(metrics,row.get('metric_path'))
        sample=path_value(metrics,row.get('sample_path'))
        n=int(sample) if sample is not None and sample>=0 and sample==int(sample) else None
        status=('unmeasured' if value is None else
                'insufficient_sample' if row['minimum_sample'] and (n or 0)<row['minimum_sample'] else
                'met' if (value>=row['target'] if row['direction']=='gte' else value<=row['target']) else 'below_target')
        row.update(current=value,n=n,status=status)
        result.append(row)
    digest=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return {'version':config['version'],'catalog_sha256':digest,'source':config['source'],'items':result}
