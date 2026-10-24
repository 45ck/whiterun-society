"""Versioned engineering OKRs. Unknown study results stay unknown."""

def quality_goals(metrics):
    result=[]
    def metric(id,objective,label,value,target,unit,n=None,minimum=0,direction='gte',scope='Retained save lineage; not a representative study'):
        status='unmeasured' if value is None else 'insufficient_sample' if minimum and (n or 0)<minimum else 'met' if (value>=target if direction=='gte' else value<=target) else 'below_target'
        result.append({'id':id,'objective':objective,'measure':label,'current':value,'target':target,'unit':unit,'n':n,
            'minimum_sample':minimum,'direction':direction,'status':status,'scope':scope})
    e=metrics['encounters'];b=metrics['embodiment'];ec=metrics['economy'];d=metrics['dialogue_analysis']
    metric('SOC-01','Believable encounters','Uninterrupted accepted chat completion',e['uninterrupted_chat_completion']['percent'],90,'percent',e['uninterrupted_chat_completion']['n'],30,scope='Excludes deliberate observer interruptions; all-attempt completion remains separately reported')
    metric('SOC-02','Believable encounters','Median reply dispatch gap',e['reply_dispatch_gap_seconds']['median'],2,'seconds',e['reply_dispatch_gap_seconds']['n'],30,'lte')
    metric('SOC-03','Believable encounters','Exact repeated lines in a scene',d['exact_repeated_lines_within_scene'],0,'lines',d['delivered_lines'],100,'lte',d['scope'])
    metric('SOC-04','Believable encounters','Human reply relevance',None,4,'anchored 1–5 rating',minimum=30,scope='Requires independent human rubric and disagreement reporting')
    metric('SOC-05','Believable encounters','Human small-talk naturalness',None,4,'anchored 1–5 rating',minimum=30,scope='Requires diverse human reviewers; no model self-rating substituted')
    metric('SOC-06','Safe interruption','Verified interruption cleanup',e['interruption_cleanup']['percent'],100,'percent',e['interruption_cleanup']['n'],10)
    metric('SOC-07','Safe interruption','Median interruption settlement',e['interruption_settle_seconds']['median'],3,'seconds',e['interruption_settle_seconds']['n'],10,'lte',scope='Request to terminal release; not acoustic stop latency')
    metric('PHY-01','Physical credibility','Uninterrupted issued voice completion',b['uninterrupted_playback_completion']['percent'],99,'percent',b['uninterrupted_playback_completion']['n'],100,scope='Excludes deliberately interrupted current delivery; raw issued completion remains separately reported')
    metric('PHY-02','Physical credibility','Independent eye-gaze trials within tolerance',None,95,'percent',minimum=30,scope='Requires calibrated eye geometry and a declared angular tolerance')
    metric('PHY-03','Physical credibility','Occlusion raycast agreement with labelled scenes',None,95,'percent',minimum=30)
    metric('PHY-04','Physical credibility','Lip-sync absolute timing error',None,100,'milliseconds',minimum=30,direction='lte')
    metric('ECO-01','Functioning economy','Committed sales',ec['committed_sales'],10,'sales',scope=ec['scope'])
    metric('ECO-02','Functioning economy','Supported traded goods',ec['supported_sale_goods'],3,'goods',scope='Implementation breadth, not economic realism')
    metric('ECO-03','Functioning economy','Supported productive transformations',ec['supported_supply_chain_transforms'],2,'steps',scope='Implementation breadth, not linked-chain qualification')
    metric('ECO-04','Functioning economy','Observed gold conservation',ec['gold_conservation']['percent'],100,'percent',ec['gold_conservation']['n'],30,scope=ec['scope'])
    metric('ECO-05','Functioning economy','Shortage/recovery scenarios without fabricated assets',None,5,'qualified scenarios',scope='Requires a supply shock, observed prices/stock and recovery evidence')
    metric('ECO-06','Functioning economy','Autonomous profitable business days',None,3,'game days',scope='Requires revenues, wages, input costs and explicit accounting period')
    for id,label in [('BEH-01','Hunger intervention changes food-seeking probability'),('BEH-02','Fatigue intervention changes rest choice probability'),('BEH-03','Price increase changes purchase acceptance probability'),('BEH-04','Personality contrast changes social approach probability')]:
        metric(id,'Behavioural sensitivity',label,None,15,'percentage-point effect',minimum=30,scope='Proposed authored sensitivity target, not a human psychological law; paired counterfactual conditions and uncertainty required')
    for id,label in [('REL-01','Known favourable history versus stranger affects cooperation'),('REL-02','Refusal does not create automatic hostility'),('REL-03','Conflict can resolve through later observed interaction'),('EVO-01','Resource scarcity alters sharing under controlled opportunities'),('EVO-02','Reciprocity history affects cooperation when cost is controlled')]:
        metric(id,'Social mechanism experiments',label,None,30,'paired trials',scope='Experiment coverage target. No evolutionary mechanism or real-world validity inferred; kinship and cultural systems remain incomplete')
    return {'version':1,'source':'Authored development targets, not validated scientific norms','items':result}
