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
    required={'version','maximum_context_bytes','maximum_goal_context_bytes','maximum_memories','relevant_memories','maximum_memory_bytes','maximum_appraisals','maximum_commitments'}
    if set(value)!=required or not isinstance(value['version'],str) or not 1<=len(value['version'])<=64:raise ValueError('Invalid context-window policy')
    if any(type(value[k]) is not int or value[k]<0 for k in required-{'version'}):raise ValueError('Invalid context-window number')
    if not 2000<=value['maximum_context_bytes']<=12000:raise ValueError('Context window must leave room for provider contract')
    if not 2000<=value['maximum_goal_context_bytes']<=14000:raise ValueError('Goal context must leave room for provider contract')
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


def bounded_economic_context(context,own_memories=None):
    """Bound an actor-owned economic view without pruning executable choices.

    All financial terms, inventories, identity views, commitments and options
    remain exact. Only memory and relationship attention is reduced. Call this
    before persisting a claim: irreducible required data fails without inference.
    This function cannot establish ownership; its input must already belong to
    the deciding resident, never a global people or private-counterparty view.
    """
    policy=load_policy();result=copy.deepcopy(context)
    counterpart=context.get('economic_counterparty') or {}
    counterpart_id=counterpart.get('id') if isinstance(counterpart,dict) else None
    targets={str(v) for v in context.get('option_targets',{}).values() if type(v) is int}
    if type(counterpart_id) is int:targets.add(str(counterpart_id))
    memories=context.get('memories',[]) if own_memories is None else own_memories
    # Counterparty recollections outrank incidental travel and other option
    # targets. Do not count the deciding actor appearing as listener as relevant.
    relevant={str(counterpart_id)} if type(counterpart_id) is int else targets
    participant_keys=('other','speaker','listener','buyer','seller','employer','worker','counterparty','target')
    records=[]
    for index,memory in enumerate(memories):
        if not isinstance(memory,dict):continue
        view={k:copy.deepcopy(v) for k,v in memory.items() if k not in TELEMETRY_FIELDS-{'provenance'}}
        related=any(type(memory.get(k)) is int and memory[k]!=context.get('actor_id')
                    and str(memory[k]) in relevant for k in participant_keys)
        records.append((index,view,related))
    prioritized=[r for r in records if r[2]][-policy['relevant_memories']:]
    selected={r[0]:r for r in prioritized}
    for row in reversed(records):
        if len(selected)>=policy['maximum_memories']:break
        selected.setdefault(row[0],row)
    # Keep priority order separately so an older relevant refusal survives if
    # later byte pressure requires dropping additional travel recollections.
    ranked=sorted(selected.values(),key=lambda r:(r[2],r[0]),reverse=True)
    kept=[]
    for row in ranked:
        if encoded_size([r[1] for r in kept]+[row[1]])<=policy['maximum_memory_bytes']:kept.append(row)
    relationships=context.get('my_relationships',{})
    if not isinstance(relationships,dict):relationships={}
    compact={};available_appraisals=0;included_appraisals=0
    for key,relation in relationships.items():
        if not isinstance(relation,dict):continue
        appraisals=relation.get('appraisals') or []
        available_appraisals+=len(appraisals)
        if str(key) not in targets:continue
        # Keep exact current state and epistemic background. Detailed historical
        # appraisals are relevant only to the current economic counterparty.
        view={k:copy.deepcopy(v) for k,v in relation.items() if k!='appraisals'}
        view['appraisals']=copy.deepcopy(appraisals[-policy['maximum_appraisals']:]) if str(key)==str(counterpart_id) and policy['maximum_appraisals'] else []
        included_appraisals+=len(view['appraisals'])
        view['older_appraisals_omitted']=len(appraisals)-len(view['appraisals'])
        compact[key]=view
    if 'my_relationships' in result:result['my_relationships']=compact
    # Repeated authored acquaintance provenance is evidence, not disposable
    # noise. Store identical background objects once with explicit references.
    backgrounds={}
    for relation in compact.values():
        background=relation.get('background')
        if isinstance(background,dict):
            encoded=json.dumps(background,sort_keys=True,separators=(',',':'))
            backgrounds.setdefault(encoded,[]).append(relation)
    sources={}
    for owners in backgrounds.values():
        if len(owners)<2:continue
        reference='economic_source_'+str(len(sources)+1)
        sources[reference]=owners[0]['background']
        for owner in owners:owner['background']={'source_ref':reference}
    if sources:result['economic_evidence_sources']=sources
    trust=context.get('trust',{})
    if isinstance(trust,dict) and 'trust' in result:
        result['trust']={k:copy.deepcopy(v) for k,v in trust.items() if str(k) in targets}
    window={'version':policy['version'],'kind':'economic','memories_available':len(memories),
            'memories_included':len(kept),'relationships_available':len(relationships),
            'relationships_included':len(compact),'appraisals_available':available_appraisals,
            'appraisals_included':included_appraisals,
            'trust_entries_omitted':len(trust)-len(result.get('trust',{})) if isinstance(trust,dict) else 0,
            'options_preserved':len(result.get('options',[])),
            'scope':'Actor-owned evidence only. Recent and counterparty-relevant memories; relationships for current counterparty and executable option targets. Omission is not forgetting, absence or neutral feeling. All economic choices, terms, resources and identity evidence remain unchanged. Relationship background source_ref resolves exactly in economic_evidence_sources.'}
    result['context_window']=window
    def update_memories():
        result['memories']=[r[1] for r in sorted(kept,key=lambda r:r[0])]
        window['memories_included']=len(kept)
    update_memories()
    while encoded_size(result)>policy['maximum_context_bytes'] and kept:
        kept.pop();update_memories()
    if encoded_size(result)>policy['maximum_context_bytes']:
        raise ValueError('Required economic context exceeds attention budget; no claim or model call created')
    return result


def bounded_goal_context(context):
    """Bound personal-goal attention without changing any executable action.

    Nearby people describe potential later social review, not action targets:
    reducing their attention window does not remove destinations or choices.
    This is a preclaim view; neither saved memories nor personal goals change.
    """
    policy=load_policy();result=copy.deepcopy(context);budget=policy['maximum_goal_context_bytes']
    public=result.get('public_opportunities',{})
    people=public.get('nearby_people',[])
    relevant={p.get('id') for p in people if isinstance(p,dict)}-{None}
    memories=context.get('own_memories',[])
    result['own_memories']=memory_view(memories,relevant,policy)
    previous=result.get('previous_goal')
    previous_omitted=[]
    if isinstance(previous,dict):
        # Keep the intention, timing and observed outcome. Repeated policy and
        # mailbox telemetry are executor details, not additional recollections.
        fields={'id','action_id','phase','decided_day','next_review_day','target','focus','follow_through','source','error'}
        previous_omitted=sorted(set(previous)-fields)
        result['previous_goal']={k:v for k,v in previous.items() if k in fields}
    for person in people:
        if 'my_relationship' in person:
            person['my_relationship']=relationship_view(person['my_relationship'],{**policy,'maximum_appraisals':0})
    window={'version':policy['version'],'kind':'personal_goal','nearby_people_available':len(people),
            'nearby_people_considered':len(people),'memories_available':len(memories),
            'memories_included':len(result['own_memories']),'previous_goal_executor_fields_omitted':len(previous_omitted),
            'options_preserved':len(result.get('options',[])),
            'scope':'Actor-owned evidence only. Nearby people are a bounded attention window for a possible later social review, not the full population. Omission is not forgetting or absence. All executable choices, destinations, goal action mappings, resources and public economic terms remain unchanged.'}
    result['context_window']=window
    # social_candidates is already nearest-first. No option is removed: a
    # separate later social decision chooses an actual consenting partner.
    while encoded_size(result)>budget and people:
        people.pop();window['nearby_people_considered']=len(people)
    while encoded_size(result)>budget and result['own_memories']:
        result['own_memories'].pop(0);window['memories_included']=len(result['own_memories'])
    if encoded_size(result)>budget:
        raise ValueError('Required personal-goal context exceeds attention budget; no claim or model call created')
    return result
