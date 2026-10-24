"""Evidence-derived diagnostics, not a synthetic score for human realism."""
import math
from collections import Counter
from statistics import mean, median


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
        results=c.get('social_decisions',[])+[r for t in c.get('turns',[]) for r in (t.get('language',{}),t.get('decision',{}))]
        return any(str(r.get('model','')).startswith(('test','deterministic-integration-fixture')) for r in results)
    scenes=[c for c in history if c.get('mode')=='autonomous_social' and not fixture(c)]
    terminal=[c for c in scenes if c['phase'] in ('complete','held')]
    chats=[c for c in terminal if c.get('response')=='chat']
    turns=[t for c in scenes for t in c.get('turns',[]) if t.get('delivered')]
    attempts=turns+[c['current'] for c in scenes if c.get('current',{}).get('delivery_id')]
    results=[r for c in scenes for r in c.get('social_decisions',[])]
    results += [r for t in turns for r in (t.get('language',{}),t.get('decision',{}))]
    # A held current turn can contain a billed successful proposal/selection.
    results += [r for c in scenes if c.get('current') for r in (c['current'].get('language',{}),c['current'].get('decision',{})) if r]
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
        parties=('buyer','seller') if 'buyer' in c.get('before',{}) else ('employer','worker')
        if all(number(c.get(phase,{}).get(p,{}).get('gold')) for phase in ('before','after') for p in parties):
            conserved.append(sum(c['before'][p]['gold'] for p in parties)==sum(c['after'][p]['gold'] for p in parties))
    relations=[r for p in state.get('people',{}).values() for r in p.get('relationships',{}).values()]
    plans=state.get('plans',[])
    terminal_plans=[p for p in plans if p['phase'] in ('complete','held')]
    option_counts=[len(d['context']['options']) for p in plans for d in p.get('decisions',[]) if isinstance(d.get('context',{}).get('options'),list)]
    total_actions=sum(actions.values())
    return {
        'scope':'Current save lineage and retained encounter history. Not lifetime telemetry or a representative population study.',
        'encounters':{'eligible':len(scenes),'excluded_fixtures':sum(fixture(c) for c in history),
            'legacy_authored':sum(c.get('mode')!='autonomous_social' for c in history),
            'in_progress':len(scenes)-len(terminal),'completed':sum(c['phase']=='complete' for c in terminal),
            'failed':sum(c['phase']=='held' for c in terminal),
            'quiet_outcomes':sum(c.get('outcome')=='continued_quietly' for c in terminal),
            'polite_refusals':sum(c.get('outcome')=='spoke_brief_refusal' for c in terminal),
            'end_reasons':dict(Counter(c.get('end_reason','legacy_unrecorded') for c in terminal)),
            'resolution_rate':rate(sum(c['phase']=='complete' for c in terminal),len(terminal)),
            'accepted_chat_completion':rate(sum(c.get('outcome')=='social_exchange_completed' for c in chats),len(chats)),
            'failures_by_category':dict(Counter(failure_category(c.get('error')) for c in terminal if c['phase']=='held')),
            'duration_seconds':distribution(durations),'delivered_turns':len(turns),
            'turns_per_accepted_chat':distribution([len(c.get('turns',[])) for c in chats]),
            'reply_dispatch_gap_seconds':distribution(gaps)},
        'embodiment':{'playback_completion':rate(len(turns),len(attempts)),
            'nearby_playback':rate(sum(t.get('playback',{}).get('nearbyThroughout') is True for t in turns),len(turns)),
            'body_orientation':{'samples':orientation_n,
                'mean_error_degrees':round(sum(o['sum_error_degrees'] for o in orientations)/orientation_n,2) if orientation_n else None,
                'maximum_error_degrees':max((o['max_error_degrees'] for o in orientations),default=None)},
            'eye_gaze_error_degrees':None,'head_gaze_error_degrees':None,'line_of_sight_raycast_accuracy':None,
            'lip_sync_error_ms':None,'physical_audio_output_verified':None},
        'models':{'recorded_results':len(results),'latency_seconds':distribution([r.get('elapsed_seconds') for r in results]),
            'known_cost_usd':round(sum(v for v in model_cost if number(v)),8),
            'results_with_cost':sum(number(v) for v in model_cost),
            'cost_coverage':'Accepted retained results only. Rejected provider calls remain in worker receipts; this is not a total bill.'},
        'economy':{'committed_sales':len(trades),'committed_production':len(production),
            'committed_meals':sum(r['status']=='committed' for r in state.get('consumptions',[])),
            'gold_conservation':rate(sum(conserved),len(conserved)),
            'distinct_observed_sale_prices':len({c['cost']/c['quantity'] for c in trades if c.get('quantity',0)>0}),
            'active_enterprises':sum(b.get('active',True) for b in state.get('town',{}).get('businesses',{}).values()),
            'supported_production_recipes':1,'supported_sale_goods':1,'supported_supply_chain_transforms':1,
            'pricing':'Authored quote choices; no market-clearing price formation.',
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
