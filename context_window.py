"""Bounded actor-owned views; persisted memories and global state stay intact."""
import copy
import json
from pathlib import Path


POLICY_PATH=Path(__file__).parent/'config/context-window.json'
# Executor timing and model telemetry are not resident recollections.
TELEMETRY_FIELDS={'policy_version','policy_id','model','provenance','timing_scope','elapsed_seconds',
                  'settled_at','settled_day','decided_day','travel_game_minutes','native_receipt'}


def encoded_size(value):return len(json.dumps(value,separators=(',',':'),ensure_ascii=True).encode())


def load_policy():
    value=json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    required={'version','maximum_context_bytes','maximum_memories','relevant_memories','maximum_memory_bytes','maximum_appraisals','maximum_commitments'}
    if set(value)!=required or not isinstance(value['version'],str) or not 1<=len(value['version'])<=64:raise ValueError('Invalid context-window policy')
    if any(type(value[k]) is not int or value[k]<0 for k in required-{'version'}):raise ValueError('Invalid context-window number')
    if not 2000<=value['maximum_context_bytes']<=12000:raise ValueError('Context window must leave room for provider contract')
    if not 1<=value['maximum_memories']<=16 or value['relevant_memories']>value['maximum_memories']:raise ValueError('Invalid memory window')
    if not 256<=value['maximum_memory_bytes']<=4000 or value['maximum_appraisals']>4 or not 1<=value['maximum_commitments']<=16:raise ValueError('Invalid social-history window')
    return value


def memory_view(memories,relevant_ids,policy):
    """Preserve a recent slice plus recent memories involving current people."""
    records=[]
    for index,memory in enumerate(memories):
        if not isinstance(memory,dict):continue
        view={k:copy.deepcopy(v) for k,v in memory.items() if k not in TELEMETRY_FIELDS}
        relevant=any(memory.get(k) in relevant_ids for k in ('other','speaker','listener'))
        records.append((index,view,relevant))
    relevant=[r for r in records if r[2]][-policy['relevant_memories']:] if policy['relevant_memories'] else []
    selected={r[0]:r for r in relevant}
    for row in reversed(records):
        if len(selected)>=policy['maximum_memories']:break
        selected.setdefault(row[0],row)
    # Priority memories survive first; recency fills the remaining byte budget.
    ranked=sorted(selected.values(),key=lambda r:(r[2],r[0]),reverse=True)
    kept=[]
    for row in ranked:
        if encoded_size([r[1] for r in kept]+[row[1]])<=policy['maximum_memory_bytes']:kept.append(row)
    return [r[1] for r in sorted(kept,key=lambda r:r[0])]


def relationship_view(relation,policy):
    if not isinstance(relation,dict):return {}
    result={k:copy.deepcopy(relation[k]) for k in ('affinity','familiarity','heard_turns') if k in relation}
    if isinstance(relation.get('background'),dict):
        result['background']={k:copy.deepcopy(relation['background'][k]) for k in ('kind','epistemic_status') if k in relation['background']}
    appraisals=relation.get('appraisals') or []
    result['appraisals']=copy.deepcopy(appraisals[-policy['maximum_appraisals']:]) if policy['maximum_appraisals'] else []
    result['older_appraisals_omitted']=max(0,len(appraisals)-len(result['appraisals']))
    return result


def bounded_social_context(context,own_memories=None):
    """Compact known evidence before claim persistence, never after a decision.

    If a crowd exceeds the byte budget, retain nearest candidates with exactly
    matching approach options. This is an explicit attention window, not a
    change to the world population or opportunity catalogue.
    """
    policy=load_policy();result=copy.deepcopy(context)
    candidates=result.get('nearby_candidates',[])
    relevant_ids={r.get('id') for r in candidates}
    for key in ('other','listener'):
        other=result.get(key)
        if isinstance(other,dict):relevant_ids.add(other.get('id'))
    relevant_ids.discard(None)
    memories=context.get('memories',[]) if own_memories is None else own_memories
    result['memories']=memory_view(memories,relevant_ids,policy)
    for row in candidates:
        row['my_relationship']=relationship_view(row.get('my_relationship'),policy)
        if isinstance(row.get('identity_source'),dict):
            row['identity_source']={k:row['identity_source'][k] for k in ('kind','epistemic_status') if k in row['identity_source']}
    if 'my_relationship' in result:result['my_relationship']=relationship_view(result['my_relationship'],policy)
    if isinstance(result.get('trust'),dict):result['trust']={k:v for k,v in result['trust'].items() if k in {str(i) for i in relevant_ids}}
    if 'own_commitments' in result:result['own_commitments']=result['own_commitments'][-policy['maximum_commitments']:]
    interaction=result.get('interaction')
    if isinstance(interaction,dict) and 'own_recorded_commitments' in interaction:
        interaction['own_recorded_commitments']=interaction['own_recorded_commitments'][-policy['maximum_commitments']:]
    window={'version':policy['version'],'available_candidates':len(candidates),'considered_candidates':len(candidates),
            'memories_available':len(memories),'memories_included':len(result['memories']),
            'scope':'Actor-owned evidence only. Recent relevant and recent memories; bounded appraisal history. If needed, nearer candidates receive attention first. Omission is not forgetting or absence. source_ref resolves in evidence_sources without changing its epistemic status.'}
    result['context_window']=window
    # Shared acquaintance provenance often repeats for every nearby person.
    # Preserve its exact epistemic qualification once, with explicit references.
    provenance=[]
    for row in candidates:
        for owner,key in ((row,'identity_source'),(row['my_relationship'],'background')):
            value=owner.get(key)
            if isinstance(value,dict):provenance.append((owner,key,value))
    counts={}
    for _,_,value in provenance:
        encoded=json.dumps(value,sort_keys=True,separators=(',',':'));counts[encoded]=counts.get(encoded,0)+1
    sources={};references={}
    for owner,key,value in provenance:
        encoded=json.dumps(value,sort_keys=True,separators=(',',':'))
        if counts[encoded]<2:continue
        if encoded not in references:
            reference='source_'+str(len(references)+1);references[encoded]=reference;sources[reference]=value
        owner[key]={'source_ref':references[encoded]}
    if sources:result['evidence_sources']=sources
    while encoded_size(result)>policy['maximum_context_bytes'] and len(candidates)>1:
        # social_candidates already uses distance then identity for stable order.
        removed=candidates.pop()
        result['options']=[o for o in result['options'] if o['id']!='approach_'+str(removed['id'])]
        window['considered_candidates']=len(candidates)
    while encoded_size(result)>policy['maximum_context_bytes'] and result['memories']:
        result['memories'].pop(0);window['memories_included']=len(result['memories'])
    if encoded_size(result)>policy['maximum_context_bytes']:
        raise ValueError('Required social context exceeds attention budget; no claim or model call created')
    return result
