"""Observed actor/base continuity for saved residents, not canonical biography.

A current observation cannot retroactively bind unknown historical identity.
Callers still bind observations to their active session/checkpoint before mutation.
"""
import re

SCHEMA_VERSION=1


def valid_actor_id(value):return type(value) is int and 0<value<=0xffffffff


def valid_binding(binding,actor_id):
    return (isinstance(binding,dict) and type(binding.get('schema_version')) is int
        and binding['schema_version']==SCHEMA_VERSION and type(binding.get('actor')) is int
        and binding['actor']==actor_id and valid_actor_id(binding.get('base_id'))
        and isinstance(binding.get('event_id'),str) and re.fullmatch(r'[A-Za-z0-9_-]{1,48}',binding['event_id']) is not None)


def resident_identity_status(state,observation,actor_id):
    """Return independent current qualification; cached status is never authority."""
    result={'qualified':False,'reason':'invalid_actor','actor':actor_id if valid_actor_id(actor_id) else None,'base_id':None}
    def reject(reason):return {**result,'reason':reason}
    if not valid_actor_id(actor_id):return result
    if not isinstance(state,dict):return reject('population_unavailable')
    town=state.get('town')
    if not isinstance(town,dict):return reject('population_unavailable')
    residents=town.get('residents');people=state.get('people')
    if not isinstance(residents,dict) or str(actor_id) not in residents:return reject('resident_unmanaged')
    resident=residents[str(actor_id)]
    if not isinstance(resident,dict) or type(resident.get('id')) is not int or resident['id']!=actor_id:return reject('resident_record_invalid')
    if not isinstance(people,dict) or not isinstance(people.get(str(actor_id)),dict):return reject('person_unavailable')
    binding=resident.get('identity_binding')
    if binding is None:return reject('identity_unbound')
    if not valid_binding(binding,actor_id):return reject('identity_binding_invalid')
    personal=people[str(actor_id)].get('identity_binding')
    if personal is not None and (not valid_binding(personal,actor_id) or personal!=binding):return reject('identity_binding_conflict')
    if not isinstance(observation,dict):return reject('observation_unavailable')
    if (observation.get('ready') is not True or not isinstance(observation.get('session'),str)
        or not observation['session'] or type(observation.get('checkpoint')) is not int
        or not 0<=observation['checkpoint']<2**24):return reject('observation_unqualified')
    rows=observation.get('residents')
    if not isinstance(rows,list) or len(rows)>128:return reject('observation_invalid')
    selected=[r for r in rows if isinstance(r,dict) and r.get('id')==actor_id]
    if not selected:return reject('actor_not_observed')
    if len(selected)!=1:return reject('duplicate_actor_observation')
    actor=selected[0]
    if not valid_actor_id(actor.get('id')):return reject('observed_identity_invalid')
    if 'session' in actor and actor['session']!=observation['session']:return reject('stale_actor_observation')
    if 'checkpoint' in actor and (type(actor['checkpoint']) is not int or actor['checkpoint']!=observation['checkpoint']):return reject('stale_actor_observation')
    if actor.get('isChild') is True:return reject('actor_is_child')
    if actor.get('isDead') is True:return reject('actor_is_dead')
    if actor.get('loaded') is False:return reject('actor_not_loaded')
    if actor.get('isPerson') is not True:return reject('adult_classification_unavailable')
    # Visible native rows already apply these filters. If explicitly supplied,
    # unknown or malformed flags cannot replace that classification evidence.
    if any(key in actor and type(actor[key]) is not bool for key in ('isChild','isDead','loaded')):
        return reject('adult_classification_unavailable')
    base=actor.get('baseId')
    if not valid_actor_id(base):return reject('base_identity_unavailable')
    result['base_id']=base
    if base!=binding['base_id']:return reject('base_identity_conflict')
    return {**result,'qualified':True,'reason':'qualified_actor_base'}
