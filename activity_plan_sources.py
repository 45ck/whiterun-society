"""Resolve source plans without lending foreground authority to another resident."""
import hashlib
import json


def find_activity_plan(state, plan_id):
    rows=[p for p in state.get('plans',[]) if isinstance(p,dict) and p.get('id')==plan_id]
    independent=state.get('independent_plans',{})
    if isinstance(independent,dict) and plan_id in independent:
        rows.append(independent[plan_id])
    if len(rows)>1:raise ValueError('Ambiguous activity source plan identity')
    return rows[0] if rows and isinstance(rows[0],dict) else None


def activity_plan_hash(plan):
    keys=('id','actor','actor_base_id','session','kind','independent_review','rest_target','own_work_terms')
    return hashlib.sha256(json.dumps({k:plan[k] for k in keys if k in plan},sort_keys=True,
        separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()


def independent_plan_authorized(state, plan, phase):
    try:
        key=plan['id'];saved=state.get('independent_plans',{}).get(key)
        record=state.get('independent_reviews',{}).get(key,{})
        sources=[e for e in state['town']['daily']['queue'] if e['id']==key]
        if len(sources)!=1:return False
        source=sources[0]
        provenance=plan.get('independent_review',{})
        return (saved is plan and find_activity_plan(state,key) is plan and plan.get('phase')==phase
            and plan.get('kind')=='independent_review' and record.get('phase')=='accepted'
            and record.get('accepted') is True and record.get('plan_id')==key and record.get('event_id')==key
            and record.get('actor')==plan.get('actor')==source.get('actor')
            and record.get('actor_base_id')==plan.get('actor_base_id') and record.get('session')==plan.get('session')
            and source.get('status')=='started' and source.get('independent_review')==record.get('wave_id')
            and provenance=={'event_id':key,'wave_id':record['wave_id'],'claim_id':record['claim_id']}
            and record.get('plan_hash')==activity_plan_hash(plan))
    except (KeyError,TypeError,ValueError,StopIteration):return False
