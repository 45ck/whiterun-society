"""Evidence-derived diagnostics, not a synthetic score for human realism."""
import math
from collections import Counter
from statistics import mean, median
from relationship_metrics import relationship_metrics
from dialogue_metrics import dialogue_metrics
from quality_goals import quality_goals
from dialogue_policy import recorded_model_results


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def distribution(values):
    values=sorted(v for v in values if number(v))
    return {'n':len(values), 'mean':round(mean(values),3) if values else None,
            'median':round(median(values),3) if values else None,
            'p95':round(values[max(0,math.ceil(.95*len(values))-1)],3) if values else None}


def rate(success, total):
    return {'success':success,'n':total,'percent':round(100*success/total,2) if total else None}


def failure_category(error):
    value=str(error).lower()
    for words,category in [(('listener left','partner left','hearing range'),'attendance'),
                           (('not observed','unavailable','unloaded'),'availability'),
                           (('language output','language candidates'),'language_output'),
                           (('playback','audio'),'playback'),
                           (('route','meeting','package'),'routing'),
                           (('save','session'),'save_session')]:
        if any(word in value for word in words):return category
    return 'other'


def simulation_metrics(state):
    state=state or {}
    history=state.get('conversation_history',[])+([state['conversation']] if state.get('conversation') else [])
    history=list({c['id']:c for c in history}.values())
    def fixture(c):
        results=recorded_model_results(c)
        return any(str(r.get('model','')).startswith(('test','deterministic-integration-fixture')) for r in results)
    scenes=[c for c in history if c.get('mode')=='autonomous_social' and not fixture(c)]
    terminal=[c for c in scenes if c['phase'] in ('complete','held')]
    chats=[c for c in terminal if c.get('response')=='chat']
    turns=[t for c in scenes for t in c.get('turns',[]) if t.get('delivered')]
    attempts=turns+[c['current'] for c in scenes if c.get('current',{}).get('delivery_id')]
    # Deliberately unspoken proposals and held current turns still incurred cost.
    results=[r for c in scenes for r in recorded_model_results(c)]
    durations=[c['finished_at']-c['started_at'] for c in terminal if number(c.get('started_at')) and number(c.get('finished_at'))]
    gaps=[current['prepared_at']-previous['ended_at'] for c in scenes for previous,current in zip(c.get('turns',[]),c.get('turns',[])[1:]) if number(previous.get('ended_at')) and number(current.get('prepared_at'))]
    orientations=[t['playback']['orientation'] for t in turns if t.get('playback',{}).get('orientation',{}).get('samples',0)>0]
    orientation_n=sum(o['samples'] for o in orientations)
    model_cost=[r.get('usage',{}).get('cost') for r in results]
    # Choosing different named partners is not a new behavioural mechanism.
    actions=Counter('approach_nearby_person' if r['decision']['action_id'].startswith('approach_') else r['decision']['action_id']
                    for c in scenes for r in c.get('social_decisions',[]) if r.get('decision'))
    trades=[r['command'] for r in state.get('trades',[]) if r['status']=='committed']
    production=[r['command'] for r in state.get('production',[]) if r['status']=='committed']
    conserved=[]
    for c in trades+production:
        parties=('owner',) if c.get('kind')=='inventory_self_produce' else ('buyer','seller') if 'buyer' in c.get('before',{}) else ('employer','worker')
        if all(number(c.get(phase,{}).get(p,{}).get('gold')) for phase in ('before','after') for p in parties):
            conserved.append(sum(c['before'][p]['gold'] for p in parties)==sum(c['after'][p]['gold'] for p in parties))
    relations=[r for p in state.get('people',{}).values() for r in p.get('relationships',{}).values()]
    plans=state.get('plans',[])
    terminal_plans=[p for p in plans if p['phase'] in ('complete','held')]
    followups=[f for c in scenes for f in c.get('follow_through',[])]
    followup_ids={f['event_id'] for f in followups}
    followup_plans=[p for p in plans if p.get('id') in followup_ids]
    followup_queue=[e for e in (state.get('town') or {}).get('daily',{}).get('queue',[]) if e['id'] in followup_ids]
    economic_turns=[t for p in plans for t in p.get('economic_turns',[]) if t.get('delivered')]
    trade_turns=[t for t in economic_turns if not t['act'].startswith('work_')]
    work_turns=[t for t in economic_turns if t['act'].startswith('work_')]
    employment_plans=[p for p in plans if p.get('employment_dialogue')]
    negotiations=[p for p in plans if p.get('economic_pair') and not p.get('employment_dialogue')]
    committed_trade_ids={r.get('id') for r in state.get('trades',[]) if r.get('status')=='committed' and r.get('id')}
    trade_outcomes=Counter()
    for p in negotiations:
        # A delivered acceptance or a completed plan is not an inventory receipt.
        category=('sale' if p.get('trade_id') in committed_trade_ids else
                  'technical_failure' if p.get('phase')=='held' else
                  'active' if p.get('phase')!='complete' else
                  'seller_refused' if p.get('outcome')=='seller_declined' else
                  'buyer_left' if p.get('outcome')=='left_without_food' else 'other')
        trade_outcomes[category]+=1
    option_counts=[len(d['context']['options']) for p in plans for d in p.get('decisions',[]) if isinstance(d.get('context',{}).get('options'),list)]
    bargaining_plans=[p for p in plans if p.get('pricing_policy')=='resident-bargaining-v1']
    by_commodity={}
    for commodity in ('bread','grain'):
        relevant=[p for p in bargaining_plans if p.get('commodity','bread')==commodity]
        proposals=[(d['decision']['action_id'],d.get('context',{}).get('price_options',{}).get(d['decision']['action_id']))
                   for p in relevant for d in p.get('decisions',[]) if d.get('decision')]
        bids=[v for a,v in proposals if a.startswith('bid_price_') and number(v)]
        asks=[v for a,v in proposals if a.startswith('ask_price_') and number(v)]
        ids={p.get('trade_id') for p in relevant}
        paid=[r['command']['cost']/r['command']['quantity'] for r in state.get('trades',[])
              if r.get('status')=='committed' and r.get('id') in ids and r['command'].get('quantity',0)>0
              and r['command'].get('commodity','bread')==commodity]
        by_commodity[commodity]={'plans':len(relevant),'buyer_offers':distribution(bids),
            'seller_counteroffers':distribution(asks),'paid_prices':distribution(paid),
            'buyer_offer_histogram':dict(Counter(str(v) for v in bids)),
            'seller_ask_histogram':dict(Counter(str(v) for v in asks))}
    total_actions=sum(actions.values())
    interrupted=[c for c in terminal if c.get('interruption')]
    natural_chats=[c for c in chats if not c.get('interruption')]
    stop_reports=[c['release_evidence']['speechStop'] for c in interrupted if c.get('release_evidence',{}).get('speechStop')]
    background=[b for b in state.get('routine_batches',[]) if b.get('background') and
        not any(str(m.get('result',{}).get('model','')).startswith(('test','deterministic-integration-fixture')) for m in b.get('members',[]))]
    finished_background=[b for b in background if b['phase'] in ('complete','held')]
    notices=[b for b in background if b.get('social_notice')]
    noticed_scenes=[c for c in scenes if c.get('social_notice')]
    result={
        'scope':'Current save lineage and retained encounter history. Not lifetime telemetry or a representative population study.',
        'dialogue_policies':{policy:{
            'encounters':len(group),'recorded_model_results':sum(len(recorded_model_results(c)) for c in group),
            'unspoken_proposals':sum(len(c.get('unspoken_turns',[])) for c in group),
            'rejected_inferences':sum(len(c.get('rejected_inferences',[])) for c in group),
            'language_validation_failures':dict(Counter(r['receipt']['validation_failure'] for c in group for r in c.get('rejected_inferences',[]))),
            'delivered_turns':sum(len(c.get('turns',[])) for c in group),
            'reply_dispatch_gap_seconds':distribution([n['prepared_at']-p['ended_at'] for c in group for p,n in zip(c.get('turns',[]),c.get('turns',[])[1:]) if number(p.get('ended_at')) and number(n.get('prepared_at'))])}
            for policy in sorted({c.get('reply_policy','separate_choice') for c in scenes})
            for group in [[c for c in scenes if c.get('reply_policy','separate_choice')==policy]]},
        'conversation_followthrough':{'resident_choices':len(followups),'distinct_reviews':len(followup_ids),
            'pending':sum(e['status']=='pending' for e in followup_queue),
            'completed_plans':sum(p['phase']=='complete' for p in followup_plans),
            'held_plans':sum(p['phase']=='held' for p in followup_plans),
            'focus':dict(Counter(f['focus'] for f in followups)),
            'outcomes':dict(Counter(p.get('outcome','unresolved') for p in followup_plans)),
            'scope':'Traceable resident-chosen reviews after heard speech, not proof that language caused an action or that a promise was fulfilled.'},
        'encounter_scheduling':{'background_cohorts':len(background),'notice_cohorts':len(notices),
            'cohorts_without_notice_telemetry':len(background)-len(notices),
            'captured_directed_pairs':sum(len(ids) for b in notices for ids in b['social_notice']['candidates_by_actor'].values()),
            'notices_consumed':sum(bool(b['social_notice'].get('consumed_by')) for b in notices),
            'terminal_notices_without_encounter':sum(b['phase'] in ('complete','held') and bool(b['social_notice']['candidates_by_actor']) and not b['social_notice'].get('consumed_by') for b in notices),
            'notice_to_start_seconds':distribution([c.get('notice_to_start_seconds') for c in noticed_scenes]),
            'recent_notice_approaches':sum(str(c.get('approach_source','')).startswith('recent proximity') for c in noticed_scenes),
            'travel_attendance_overlap':rate(sum(b.get('concurrency',{}).get('attendance_overlap_samples',0)>0 for b in finished_background),len(finished_background)),
            'travel_speech_overlap':rate(sum(b.get('concurrency',{}).get('speech_overlap_samples',0)>0 for b in finished_background),len(finished_background)),
            'scope':'Captured proximity notices are opportunities, not consent, perception validation or completed encounters. Overlap is native frame evidence, not a realism score.'},
        'encounters':{'eligible':len(scenes),'excluded_fixtures':sum(fixture(c) for c in history),
            'legacy_authored':sum(c.get('mode')!='autonomous_social' for c in history),
            'in_progress':len(scenes)-len(terminal),'completed':sum(c['phase']=='complete' for c in terminal),
            'failed':sum(c['phase']=='held' for c in terminal),
            'quiet_outcomes':sum(c.get('outcome')=='continued_quietly' for c in terminal),
            'polite_refusals':sum(c.get('outcome')=='spoke_brief_refusal' for c in terminal),
            'end_reasons':dict(Counter(c.get('end_reason','legacy_unrecorded') for c in terminal)),
            'observer_interruptions':len(interrupted),
            'interruption_stages':dict(Counter(c['interruption']['stage'] for c in interrupted)),
            'technical_failures':sum(c['phase']=='held' and not c.get('interruption') for c in terminal),
            'uninterrupted_chat_completion':rate(sum(c.get('outcome')=='social_exchange_completed' for c in natural_chats),len(natural_chats)),
            'interruption_audio_stop_ack':rate(sum(r.get('acknowledged') is True for r in stop_reports),len(stop_reports)),
            'interruption_audio_stop_unmeasured':sum(bool(c.get('current',{}).get('delivery_id')) for c in interrupted)-len(stop_reports),
            'interruption_cleanup':rate(sum(c['interruption'].get('release_not_required') is True or c.get('release_evidence',{}).get('released') is True for c in interrupted),len(interrupted)),
            'interruption_settle_seconds':distribution([c['finished_at']-c['interruption']['requested_at'] for c in interrupted if number(c.get('finished_at')) and number(c['interruption'].get('requested_at'))]),
            'resolution_rate':rate(sum(c['phase']=='complete' for c in terminal),len(terminal)),
            'accepted_chat_completion':rate(sum(c.get('outcome')=='social_exchange_completed' for c in chats),len(chats)),
            'failures_by_category':dict(Counter(failure_category(c.get('error')) for c in terminal if c['phase']=='held')),
            'duration_seconds':distribution(durations),'delivered_turns':len(turns),
            'turns_per_accepted_chat':distribution([len(c.get('turns',[])) for c in chats]),
            'reply_dispatch_gap_seconds':distribution(gaps)},
        'embodiment':{'playback_completion':rate(len(turns),len(attempts)),
            'uninterrupted_playback_completion':rate(len(turns),len(attempts)-sum(bool(c.get('interruption') and c.get('current',{}).get('delivery_id')) for c in scenes)),
            'nearby_playback':rate(sum(t.get('playback',{}).get('nearbyThroughout') is True for t in turns),len(turns)),
            'body_orientation':{'samples':orientation_n,
                'mean_error_degrees':round(sum(o['sum_error_degrees'] for o in orientations)/orientation_n,2) if orientation_n else None,
                'maximum_error_degrees':max((o['max_error_degrees'] for o in orientations),default=None)},
            'eye_gaze_error_degrees':None,'head_gaze_error_degrees':None,'line_of_sight_raycast_accuracy':None,
            'lip_sync_error_ms':None,'physical_audio_output_verified':None},
        'models':{'recorded_results':len(results),'latency_seconds':distribution([r.get('elapsed_seconds') for r in results]),
            'known_cost_usd':round(sum(v for v in model_cost if number(v)),8),
            'results_with_cost':sum(number(v) for v in model_cost),
            'cost_coverage':'Retained accepted results and claim-bound language rejection receipts. Older rejections and other failed calls may exist only in worker receipts; this is not a total bill.'},
        'economy':{'committed_sales':len(trades),'committed_production':len(production),
            'bargaining':{**by_commodity['bread'],'plans':len(bargaining_plans),'by_commodity':by_commodity,
                'accepted_counteroffers':sum(p.get('counter_quote_accepted') is True for p in bargaining_plans),
                'scope':'Retained resident bargaining plans, including fixtures. Offers and accepted terms are not payments; paid prices require committed native inventory receipts.'},
            'grain_procurement_sales':sum(c.get('commodity')=='grain' for c in trades),
            'grain_units_traded':sum(c['quantity'] for c in trades if c.get('commodity')=='grain'),
            'owner_production_batches':sum(c.get('kind')=='inventory_self_produce' for c in production),
            'negotiations':{'n':len(negotiations),'outcomes':dict(trade_outcomes),
                'scope':'Retained voiced trade plans, including staged experiments. Sales require committed inventory receipts; refusals are choices, not technical failures.'},
            'household_release_sales':sum(r.get('status')=='committed' and bool(r.get('reserve_release')) for r in state.get('trades',[])),
            'voiced_trade_plans':sum(bool(p.get('voiced_trade')) for p in negotiations),
            'delivered_trade_utterances':len(trade_turns),
            'spoken_trade_acts':dict(Counter(t['act'] for t in trade_turns)),
            'employment_encounters':{'n':len(employment_plans),
                'outcomes':dict(Counter(p.get('outcome') or p['phase'] for p in employment_plans)),
                'delivered_utterances':len(work_turns),'spoken_acts':dict(Counter(t['act'] for t in work_turns)),
                'scope':'Employment requests and heard terms; output and wages require separate native production receipts. Includes controlled tests.'},
            'speech_scope':'Deterministic terms driven by resident decisions. Heard acceptance is not a committed sale. Includes staged protocol tests.',
            'committed_meals':sum(r['status']=='committed' for r in state.get('consumptions',[])),
            'gold_conservation':rate(sum(conserved),len(conserved)),
            'distinct_observed_sale_prices':len({c['cost']/c['quantity'] for c in trades if c.get('quantity',0)>0}),
            'active_enterprises':sum(b.get('active',True) for b in state.get('town',{}).get('businesses',{}).values()),
            'resident_enterprise_changes':sum('actor' in e and 'plan_id' in e for e in state.get('town',{}).get('enterprise_events',[])),
            'operator_enterprise_changes':sum('actor' not in e for e in state.get('town',{}).get('enterprise_events',[])),
            'supported_production_recipes':1,'supported_sale_goods':2,'supported_supply_chain_transforms':1,
            'pricing':'Residents choose bids and counteroffers from bounded price options using personal history; legacy fixtures retain 3/5 offers. No market-clearing equilibrium is claimed.',
            'scope':'Physical ledger includes explicitly staged integration experiments; not all outcomes prove autonomous economic behaviour.'},
        'resident_plans':{'terminal':len(terminal_plans),'held':sum(p['phase']=='held' for p in terminal_plans),
            'outcomes':dict(Counter(p.get('outcome') or 'held_without_outcome' for p in terminal_plans)),
            'failures_by_category':dict(Counter(failure_category(p.get('error')) for p in terminal_plans if p['phase']=='held')),
            'feasible_options_per_decision':distribution(option_counts),
            'scope':'Retained economic/routine plans, including staged fixtures. Feasible options are not a realism score.'},
        'social_complexity':{'directed_relationships':len(relations),
            'positive_affinity_edges':sum(r.get('affinity',0)>0 for r in relations),
            'negative_affinity_edges':sum(r.get('affinity',0)<0 for r in relations),
            'distinct_social_choices':len(actions),'choices':dict(actions),
            'choice_entropy_bits':round(-sum((n/total_actions)*math.log2(n/total_actions) for n in actions.values()),3) if total_actions else None,
            'implemented_drama_mechanism':'Subjective appraisal and affinity only; no multi-party conflict/resolution system.'},
        'realism':{'human_dialogue_rating':None,'psychological_validity':None,'economic_realism_rating':None,
            'interoperability_score':None,
            'reason':'No calibrated human ratings or interoperability benchmark. Completion, entropy and feature counts are not realism scores.'}}
    handoffs=state.get('scene_handoffs',[])
    settled=[h for h in handoffs if h['status']!='pending']
    result['scene_handoffs']={'requested':len(handoffs),'pending':len(handoffs)-len(settled),
        'plans_started':sum(bool(h.get('resumed_by')) for h in handoffs),
        'resumed_plan_outcomes':dict(Counter(p.get('outcome') or p['phase'] for p in state.get('plans',[]) if p.get('scene_handoff'))),
        'verified_release':rate(sum(h['status']=='released' for h in settled),len(settled)),
        'outcomes':dict(Counter(h.get('outcome','pending') for h in handoffs)),
        'release_seconds':distribution((h.get('receipt') or {}).get('elapsed_ms',0)/1000
            for h in settled if number((h.get('receipt') or {}).get('elapsed_ms'))),
        'scope':'Native scene release only. Not quest compatibility, successful agent action, or psychological realism.'}
    result['relationships']=relationship_metrics(state.get('people',{}))
    result['dialogue_analysis']=dialogue_metrics(scenes)
    result['quality_goals']=quality_goals(result)
    return result
