"""Explicit save-bound starting knowledge, never a receipt for completed work.

Only a reviewed manifest and a frozen observed cohort participate. Census,
newcomer arrival, public charters and configuration reloads grant no knowledge.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

from economy_catalog import canonical_json, catalog_hash, recipe_hash, recipe_spec

DEFAULT_PATH=Path(__file__).with_name('config')/'livelihood-backgrounds.json'
ID=re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}',re.ASCII)
SOURCE='authored_livelihood_background'


def _id(value):return isinstance(value,str) and ID.fullmatch(value) is not None
def _uint(value):return type(value) is int and 0<value<=0xffffffff
def _hash(value):return isinstance(value,str) and re.fullmatch(r'[a-f0-9]{64}',value) is not None


def validate_livelihood_manifest(raw):
    if (not isinstance(raw,dict) or set(raw)!={'schema_version','id','catalog_hash','selection','rules','provenance'}
            or type(raw['schema_version']) is not int or raw['schema_version']!=1 or not _id(raw['id'])
            or raw['catalog_hash']!=catalog_hash() or raw['selection']!='ranked_initial_cohort_v1'):
        raise ValueError('Invalid livelihood manifest identity, selection or catalog binding')
    provenance=raw['provenance']
    if (not isinstance(provenance,str) or not 1<=len(provenance)<=500 or provenance!=provenance.strip()
            or any(ord(c)<32 or 0xD800<=ord(c)<=0xDFFF for c in provenance)):
        raise ValueError('Invalid livelihood manifest provenance')
    if not isinstance(raw['rules'],list) or not 1<=len(raw['rules'])<=128:
        raise ValueError('Livelihood manifest requires 1..128 explicit rules')
    ids=set();recipes=set()
    for rule in raw['rules']:
        if (not isinstance(rule,dict) or set(rule)!={'id','recipe_id','recipe_hash','recipient_count'}
                or not _id(rule['id']) or rule['id'] in ids or not _id(rule['recipe_id'])
                or rule['recipe_id'] in recipes or type(rule['recipient_count']) is not int
                or not 1<=rule['recipient_count']<=128 or rule['recipe_hash']!=recipe_hash(rule['recipe_id'])):
            raise ValueError('Invalid livelihood recipe rule or pinned recipe definition')
        ids.add(rule['id']);recipes.add(rule['recipe_id'])
    canonical_json(raw)
    return copy.deepcopy(raw)


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate livelihood manifest JSON key')
        result[key]=value
    return result


def load_livelihood_manifest(path=None):
    payload=Path(path or DEFAULT_PATH).read_bytes()
    if len(payload)>256*1024:raise ValueError('Livelihood manifest exceeds size limit')
    return validate_livelihood_manifest(json.loads(payload.decode('utf-8'),object_pairs_hook=_pairs))


def livelihood_manifest_hash(manifest=None):
    checked=load_livelihood_manifest() if manifest is None else validate_livelihood_manifest(manifest)
    return hashlib.sha256(canonical_json(checked).encode('utf-8')).hexdigest()


def _request(event_id,seed,scenario_id,scenario_hash,actor_ids):
    if not all(_id(value) for value in (event_id,seed,scenario_id)) or not _hash(scenario_hash):
        raise ValueError('Invalid livelihood request identity')
    if (not isinstance(actor_ids,list) or not 1<=len(actor_ids)<=128
            or any(not _uint(actor) for actor in actor_ids) or len(set(actor_ids))!=len(actor_ids)):
        raise ValueError('An explicit distinct bounded livelihood cohort is required')
    return {'event_id':event_id,'seed':seed,'scenario_id':scenario_id,
            'scenario_hash':scenario_hash,'actor_ids':sorted(actor_ids)}


def preview_livelihood_background(state,observation,event_id,seed,scenario_id,scenario_hash,actor_ids):
    """Pure proposal. Rank stable actor/base identities; never rank names or wealth."""
    from resident_identity import resident_identity_status
    request=_request(event_id,seed,scenario_id,scenario_hash,actor_ids)
    town=state.get('town') if isinstance(state,dict) else None
    if not town:raise ValueError('Initialize the population before assigning a livelihood background')
    backgrounds=town.get('livelihood_backgrounds',[])
    for old in backgrounds:
        if old.get('id')==event_id:
            if old.get('request')!=request:raise ValueError('Livelihood event ID reused with changed terms')
            return {'duplicate':True,'background':copy.deepcopy(old)}
    if backgrounds:
        raise ValueError('The initial livelihood cohort is already frozen; no implicit reseeding or newcomer enrollment')
    manifest=load_livelihood_manifest()
    if manifest['id']!=scenario_id or livelihood_manifest_hash(manifest)!=scenario_hash:
        raise ValueError('Livelihood scenario must match the locally reviewed manifest')
    cohort=[]
    for actor in request['actor_ids']:
        identity=resident_identity_status(state,observation,actor)
        if not identity.get('qualified') or str(actor) not in state.get('people',{}):
            raise ValueError('Livelihood cohort requires current bound resident identity: '+str(identity.get('reason')))
        cohort.append({'actor':actor,'base_id':identity['base_id']})
    assignments=[]
    for rule in manifest['rules']:
        if rule['recipient_count']>len(cohort):raise ValueError('Livelihood cohort cannot satisfy the explicit recipient count')
        def rank(identity):
            payload={'scenario_hash':scenario_hash,'seed':seed,'rule_id':rule['id'],**identity}
            return hashlib.sha256(canonical_json(payload).encode('utf-8')).hexdigest(),identity['actor'],identity['base_id']
        for identity in sorted(cohort,key=rank)[:rule['recipient_count']]:
            assignments.append({**identity,'event_id':event_id,'scenario_id':scenario_id,'scenario_hash':scenario_hash,
                'catalog_hash':manifest['catalog_hash'],'rule_id':rule['id'],'recipe_id':rule['recipe_id'],
                'recipe_hash':rule['recipe_hash'],'definition':recipe_spec(rule['recipe_id']),
                'source':SOURCE,'provenance':manifest['provenance']})
    background={'id':event_id,'request':request,'manifest':manifest,'scenario_hash':scenario_hash,
                'catalog_hash':manifest['catalog_hash'],'cohort':cohort,'assignments':assignments,
                'provenance':manifest['provenance'],
                'scope':'Explicit authored prior knowledge, not verified production, measured skill, assets or work history'}
    return {'duplicate':False,'background':background}


def authored_prior_status(state,observation,actor_id,recipe_id):
    """Authority requires both the saved journal and current actor/base evidence."""
    from resident_identity import resident_identity_status
    result={'valid':False,'source':SOURCE,'reason':'No matching authored prior'}
    if not isinstance(state,dict) or not isinstance(observation,dict) or not _uint(actor_id):return result
    identity=resident_identity_status(state,observation,actor_id)
    if identity.get('qualified') is not True:return {**result,'reason':identity.get('reason','Resident identity unqualified')}
    person=state.get('people',{}).get(str(actor_id),{})
    prior=person.get('authored_recipe_priors',{}).get(recipe_id)
    if not isinstance(prior,dict):return result
    try:
        if (prior.get('source')!=SOURCE or prior.get('actor')!=actor_id or prior.get('base_id')!=identity['base_id']
                or prior.get('recipe_id')!=recipe_id or prior.get('catalog_hash')!=catalog_hash()
                or prior.get('recipe_hash')!=recipe_hash(recipe_id) or prior.get('definition')!=recipe_spec(recipe_id)):
            return {**result,'reason':'Authored prior identity or recipe definition changed'}
        background=next((row for row in (state.get('town') or {}).get('livelihood_backgrounds',[])
                         if row.get('id')==prior.get('event_id')),None)
        if (not background or background.get('scenario_hash')!=prior.get('scenario_hash')
                or livelihood_manifest_hash(background['manifest'])!=prior['scenario_hash']
                or prior not in background.get('assignments',[])):
            return {**result,'reason':'Authored prior lacks its exact save-bound scenario journal'}
    except (ValueError,KeyError,TypeError):return {**result,'reason':'Authored prior definition is unavailable or stale'}
    return {**result,'valid':True,'reason':'Current identity matches an explicit saved scenario prior',
            'event_id':prior['event_id'],'scenario_id':prior['scenario_id'],'scenario_hash':prior['scenario_hash'],
            'catalog_hash':prior['catalog_hash'],'recipe_hash':prior['recipe_hash']}


class LivelihoodBackgrounds:
    def establish_livelihood_background(self,event_id,seed,scenario_id,scenario_hash,actor_ids,observation):
        self._agency_guard(observation)
        proposal=preview_livelihood_background(self.active,observation,event_id,seed,scenario_id,scenario_hash,actor_ids)
        if proposal['duplicate']:return proposal
        if self.agency_busy() or self.conversation_busy():
            raise ValueError('Finish active resident choices before assigning livelihood background')
        state=copy.deepcopy(self.active);background=proposal['background']
        background.update(source_checkpoint=self.marker,source_session=self.session,observed_game_day=observation.get('gameDays'))
        state['town'].setdefault('livelihood_backgrounds',[]).append(copy.deepcopy(background))
        for assignment in background['assignments']:
            person=state['people'][str(assignment['actor'])]
            if assignment['recipe_id'] in person.get('authored_recipe_priors',{}):
                raise ValueError('An authored recipe prior cannot be overwritten')
            person.setdefault('authored_recipe_priors',{})[assignment['recipe_id']]=copy.deepcopy(assignment)
        return {'checkpoint':self._write(state,'explicit livelihood background frozen without assets or work history'),
                'background':copy.deepcopy(background)}
