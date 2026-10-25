"""Save-derived agency and exchange structure; no synthetic realism score."""
from collections import Counter
import json
import math
from statistics import mean,median
from economy_catalog import apply_recipe, catalog_hash, recipe_hash


def number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def rate(success,n):
    return {'success':success,'n':n,'percent':round(100*success/n,2) if n else None}


def distribution(values):
    values=sorted(v for v in values if number(v))
    return {'n':len(values),'mean':round(mean(values),3) if values else None,
            'median':round(median(values),3) if values else None,
            'p95':round(values[max(0,math.ceil(.95*len(values))-1)],3) if values else None}


def fixture(row):
    return row.get('provenance')=='test_fixture' or str(row.get('model','')).startswith(('test','deterministic-integration-fixture'))


def entropy(counts):
    total=sum(counts.values())
    return round(-sum((n/total)*math.log2(n/total) for n in counts.values()),3) if total else None


def choice_family(result):
    action=(result.get('decision') or {}).get('action_id')
    # A different reference ID is a destination, not a new action mechanism.
    if isinstance(action,str) and action.startswith('visit_'):return 'visit_destination'
    return action if action=='quiet' else 'unclassified'


def agency_metrics(state):
    people=state.get('people',{});town=state.get('town') or {}
    managed=town.get('residents',{})
    waves=town.get('goal_waves',[])
    raw=[r for w in waves for r in w.get('results',[])]
    results=[r for r in raw if not fixture(r)]
    accepted=[r for r in results if r.get('accepted') is True]
    choices=Counter(choice_family(r) for r in accepted)
    destinations={r['decision']['action_id'][6:] for r in accepted
                  if isinstance((r.get('decision') or {}).get('action_id'),str) and r['decision']['action_id'].startswith('visit_')}
    goals=[people.get(k,{}).get('standing_goal') or {} for k in managed]
    phases=Counter(g.get('phase','unassigned') for g in goals)
    all_outcomes={}
    for actor,p in people.items():
        for m in p.get('memories',[]):
            if m.get('kind') in ('standing_goal_arrival','standing_goal_failed') and m.get('event_id'):
                all_outcomes[(actor,m['event_id'])]=m
    outcomes=[m for m in all_outcomes.values() if not fixture(m)]
    attempted=[r for r in results if r.get('attempted') is True]
    skipped=[r for r in results if r.get('attempted') is False]
    # Old receipts lack an attempted marker; preserve their recorded timings
    # and reported costs without turning them into proven call-count samples.
    inference_receipts=[r for r in results if r.get('attempted') is not False]
    costs=[r.get('usage',{}).get('cost') for r in inference_receipts]
    known_costs=[c for c in costs if number(c)]
    return {
        'retained_waves':len(waves),'completed_waves':sum(w.get('phase')=='complete' for w in waves),
        'held_waves':sum(w.get('phase')=='held' for w in waves),
        'pending_claimed_decisions':sum(len(w.get('members',[])) for w in waves if w.get('phase')=='thinking'),
        'recorded_results':len(results),'excluded_fixture_results':len(raw)-len(results),
        'recorded_attempted_calls':len(attempted),'skipped_before_inference':len(skipped),
        'attempt_status_unknown':len(results)-len(attempted)-len(skipped),
        'attempt_status_coverage':rate(len(attempted)+len(skipped),len(results)),
        'decision_acceptance':rate(len(accepted),len(results)),
        'inference_failures':rate(sum(r.get('failure')=='inference_failed' for r in attempted),len(attempted)),
        'rejections':dict(Counter(r.get('failure') or 'unclassified' for r in results if r.get('accepted') is not True)),
        'inference_seconds':distribution(r.get('elapsed_seconds') for r in inference_receipts),
        'known_cost_usd':round(sum(known_costs),8) if known_costs else None,
        'cost_coverage':rate(sum(number(r.get('usage',{}).get('cost')) for r in attempted),len(attempted)),
        'accepted_choices':len(accepted),'choice_classes':dict(choices),
        'distinct_choice_classes':len([key for key in choices if key!='unclassified']),'choice_entropy_bits':entropy({k:v for k,v in choices.items() if k!='unclassified'}),
        'destination_kind_choices':dict(Counter(r.get('chosen_family','legacy_unrecorded') for r in accepted if choice_family(r)=='visit_destination')),
        'distinct_chosen_destinations':len(destinations),
        'options_per_decision':distribution(r.get('option_count') for r in results),
        'current_goal_phases':dict(phases),
        'current_goal_coverage':rate(sum(phases[p] for p in ('travelling','quiet','arrived','review_pending','reviewed')),len(managed)),
        'journey_arrival':rate(sum(m['kind']=='standing_goal_arrival' for m in outcomes),len(outcomes)),
        'excluded_fixture_journey_outcomes':len(all_outcomes)-len(outcomes),
        'journey_outcomes_with_model_provenance':sum(m.get('provenance')=='model_decision' for m in outcomes),
        'journey_outcomes_with_unknown_provenance':sum(m.get('provenance')!='model_decision' for m in outcomes),
        'journey_game_minutes':distribution(m.get('travel_game_minutes') for m in outcomes),
        'decision_to_settlement_seconds':distribution(m.get('elapsed_seconds') for m in outcomes),
        'scope':'Current save; retained waves and bounded personal memories, not lifetime telemetry. Goal coverage includes unloaded initialized residents. Claims are pending work, not continuous thinking. Known test models are excluded from result/outcome series; unlabelled legacy journey provenance remains explicit. Arrival implies no trade, work or need recovery.',
        'timing_scope':'Provider inference time and decision-to-settlement wall time are separate. Settlement includes waiting and interruptions; it is not pure walking time. Missing historical timestamps remain unknown.',
        'attempt_scope':'Attempt counts, inference-failure rate and billing coverage use explicit attempted=true receipts. Pre-inference skips remain rejected decisions but are not model calls. Legacy missing attempt markers are reported as unknown.',
        'cost_scope':'Known provider costs include legacy reported costs; billing coverage uses explicitly attempted calls only. Missing costs are not zero and this is not a complete provider bill.'}


def economic_network(state):
    trades=[r.get('command') or {} for r in state.get('trades',[]) if r.get('status')=='committed']
    valid_id=lambda x:type(x) is int and x>0
    complete=[c for c in trades if valid_id(c.get('buyer')) and valid_id(c.get('seller')) and c['buyer']!=c['seller']]
    links=Counter((c['buyer'],c['seller']) for c in complete)
    participants={actor for pair in links for actor in pair}
    goods=Counter(c['commodity'] for c in trades if isinstance(c.get('commodity'),str) and c['commodity'])
    sellers=Counter(c['seller'] for c in complete)
    known_costs=[c['cost'] for c in trades if number(c.get('cost'))]
    total=sum(sellers.values())
    hhi=sum((n/total)**2 for n in sellers.values()) if total else None
    return {'committed_sales':len(trades),'complete_party_receipts':len(complete),
        'party_identity_coverage':rate(len(complete),len(trades)),
        'distinct_participants':len(participants),'distinct_buyers':len({c['buyer'] for c in complete}),
        'distinct_sellers':len(sellers),'directed_trade_links':len(links),
        'links':[{'buyer':a,'seller':b,'sales':n} for (a,b),n in sorted(links.items())],
        'distinct_goods':len(goods),'goods_receipts':dict(goods),'goods_label_coverage':rate(sum(goods.values()),len(trades)),
        'known_turnover_septims':sum(known_costs) if known_costs else None,
        'turnover_coverage':rate(len(known_costs),len(trades)),
        'seller_transaction_hhi':round(hhi,4) if hhi is not None else None,
        'largest_seller_transaction_share':round(100*max(sellers.values())/total,2) if total else None,
        'trade_link_density':round(len(links)/(len(participants)*(len(participants)-1)),4) if len(participants)>1 else None,
        'cashflow':account_cashflow(state),
        'scope':'Committed physical receipts, including controlled integration experiments. Graph uses complete distinct buyer/seller IDs; unknown commodity labels are not guessed. Turnover is not profit, supply-chain depth or welfare. Seller concentration is transaction-count based, not market power or a target to maximize.'}


def owner_recipe_receipt(command):
    """Validate the complete owner transform; historical proof stays labelled."""
    before = command.get('before') or {}; after = command.get('after') or {}
    if set(before) != {'owner'} or set(after) != {'owner'}:
        return None
    old, new = before['owner'], after['owner']
    if not isinstance(old, dict) or not isinstance(new, dict):
        return None
    if any(type(value) is not int or value < 0 for row in (old, new) for value in row.values()):
        return None
    rid = command.get('recipe_id', 'bread_recipe')
    has_catalog_proof = 'catalog_hash' in command or 'recipe_hash' in command
    if has_catalog_proof:
        try:
            if command.get('catalog_hash') != catalog_hash() or command.get('recipe_hash') != recipe_hash(rid):
                return None
            if apply_recipe(old, rid) != new or old.get('gold') != new.get('gold'):
                return None
        except (ValueError, TypeError, KeyError):
            return None
        return {'recipe_id': rid, 'evidence': 'validated_catalog_transform'}
    # Before catalog hashes were deployed, only this fixed recipe existed.
    # Do not reinterpret a new recipe or extra stock under that old contract.
    if (rid != 'bread_recipe' or set(old) != {'gold', 'bread', 'grain'} or set(new) != set(old)
            or old['grain'] < 1 or new != {**old, 'grain': old['grain'] - 1, 'bread': old['bread'] + 2}):
        return None
    return {'recipe_id': rid, 'evidence': 'legacy_fixed_bread_transform'}


def account_cashflow(state):
    """Reconcile cash legs of retained commits without inventing business profits.

    Household and enterprise money share one native purse. A gold movement is
    assigned to that purse only, never guessed into a custodian's business.
    """
    records=[r for field in ('trades','production') for r in state.get(field,[]) if r.get('status')=='committed']
    records += [r for r in ((state.get('town') or {}).get('resource_program') or {}).get('grants',{}).values() if r.get('status')=='committed']
    unique={};conflicts=set();duplicate_count=0;missing_ids=0
    for record in records:
        event=record.get('id');command=record.get('command')
        if not isinstance(event,str) or not event or not isinstance(command,dict):
            missing_ids+=1;continue
        fingerprint=json.dumps(command,sort_keys=True,separators=(',',':'))
        if event in unique:
            duplicate_count+=1
            if fingerprint!=unique[event][0]:conflicts.add(event)
        else:unique[event]=(fingerprint,command)
    accounts={};rejected=Counter();kinds=Counter();recognized=0
    recipe_receipts=Counter();recipe_evidence=Counter()
    valid_gold=lambda x:type(x) is int and x>=0
    valid_id=lambda x:type(x) is int and x>0
    def change(command,role=None):
        before=command.get('before') or {};after=command.get('after') or {}
        if role:before=before.get(role) or {};after=after.get(role) or {}
        a,b=before.get('gold'),after.get('gold')
        return b-a if valid_gold(a) and valid_gold(b) else None
    def add(actor,field,amount):
        row=accounts.setdefault(actor,{'actor':actor,'sales_receipts':0,'purchases_paid':0,
            'wages_received':0,'wages_paid':0,'external_grants_received':0,'production_events':0,'cash_leg_events':0})
        row[field]+=amount
        if field!='production_events':row['cash_leg_events']+=1
    for event,(_,c) in unique.items():
        if event in conflicts:rejected['conflicting_duplicate_id']+=1;continue
        kind=c.get('kind')
        if kind=='inventory_trade':
            buyer,seller=c.get('buyer'),c.get('seller');cost=c.get('cost')
            if not (valid_id(buyer) and valid_id(seller) and buyer!=seller and valid_gold(cost) and cost>0 and
                    change(c,'buyer')==-cost and change(c,'seller')==cost):
                rejected['invalid_trade_cash_leg']+=1;continue
            add(buyer,'purchases_paid',cost);add(seller,'sales_receipts',cost)
        elif kind=='inventory_produce':
            worker,employer=c.get('worker'),c.get('employer');wage=change(c,'worker')
            if not (valid_id(worker) and valid_id(employer) and worker!=employer and type(wage) is int and wage>0 and
                    change(c,'employer')==-wage and ('wage_gold' not in c or type(c['wage_gold']) is int and c['wage_gold']==wage)):
                rejected['invalid_wage_cash_leg']+=1;continue
            add(worker,'wages_received',wage);add(employer,'wages_paid',wage);add(employer,'production_events',1)
        elif kind=='inventory_self_produce':
            actor=c.get('actor')
            if not valid_id(actor) or change(c,'owner')!=0:
                rejected['invalid_owner_cash_leg']+=1;continue
            add(actor,'production_events',1)
        elif kind=='inventory_self_produce_commit':
            actor=c.get('actor');recipe=owner_recipe_receipt(c)
            if not (valid_id(actor) and recipe is not None
                    and all(key not in c or type(c[key]) is int and c[key]==actor for key in ('custodian','account_actor'))
                    and ('wage_gold' not in c or type(c['wage_gold']) is int and c['wage_gold']==0)):
                rejected['invalid_owner_recipe_cash_leg']+=1;continue
            add(actor,'production_events',1)
            recipe_receipts[recipe['recipe_id']]+=1;recipe_evidence[recipe['evidence']]+=1
        elif kind=='inventory_endowment':
            actor=c.get('actor');grant=(c.get('grant') or {}).get('gold')
            if not valid_id(actor) or not valid_gold(grant) or change(c)!=grant:
                rejected['invalid_external_grant_cash_leg']+=1;continue
            add(actor,'external_grants_received',grant)
        else:rejected['unsupported_cash_record_kind']+=1;continue
        recognized+=1;kinds[kind]+=1
    for row in accounts.values():
        row['operating_cash_in']=row['sales_receipts']+row['wages_received']
        row['operating_cash_out']=row['purchases_paid']+row['wages_paid']
        row['net_operating_cashflow']=row['operating_cash_in']-row['operating_cash_out']
        row['net_including_recorded_grants']=row['net_operating_cashflow']+row['external_grants_received']
    valid=list(accounts.values());denominator=len(unique)+missing_ids
    return {'accounts':sorted(valid,key=lambda row:row['actor']),
        'raw_committed_records':len(records),'duplicate_records_excluded':duplicate_count,
        'record_coverage':rate(recognized,denominator),'missing_id_or_command_records':missing_ids,
        'rejected_records':dict(rejected),'recognized_record_kinds':dict(kinds),
        'owner_recipe_receipts':dict(recipe_receipts),'owner_recipe_evidence':dict(recipe_evidence),
        'owner_recipe_scope':'Deduplicated committed owner job recipes with validated complete inventory deltas; legacy fixed bread transforms are distinct from catalog hash validation. No price, profit or autonomy inference.',
        'observed_transfer_balance_septims':sum(r['net_operating_cashflow'] for r in valid) if recognized else None,
        'transfer_balance_scope':'Sum of validated paired cash legs, balanced by validation; not an independent conservation test. Inspect rejected-record coverage.',
        'external_grants_received_septims':sum(r['external_grants_received'] for r in valid) if recognized else None,
        'profit':None,'accounting_period':None,
        'scope':'Retained committed trade, production and founding-grant records only, including controlled trials. Native before/after gold deltas must match the recorded payment. Household and businesses share a native purse; amounts are not attributed to a particular enterprise. Cash flow is not profit: input cost basis, inventory valuation, unpaid owner labour, overheads and accounting periods remain unmeasured. Starting wealth and unjournalled native changes are outside this reconciliation.'}


def drama_metrics(state):
    edges=[r for actor,p in state.get('people',{}).items() for other,r in p.get('relationships',{}).items() if str(actor)!=str(other)]
    heard=[r for r in edges if number(r.get('heard_turns')) and r['heard_turns']>0]
    return {'recorded_directed_edges':len(edges),'authored_background_edges':sum(bool(r.get('background')) for r in edges),
        'heard_history_coverage':rate(len(heard),len(edges)),
        'heard_turns_per_recorded_edge':distribution(r.get('heard_turns') for r in edges),
        'positive_affinity_edges':sum(type(r.get('affinity')) in (int,float) and r['affinity']>0 for r in edges),
        'negative_affinity_edges':sum(type(r.get('affinity')) in (int,float) and r['affinity']<0 for r in edges),
        'qualified_conflict_resolution_chains':None,'belief_revision_accuracy':None,'memory_consistency_rating':None,
        'scope':'Directed gameplay relationships and heard history only. Affinity polarity is not a verified conflict, motive or human psychological measure. Event-linked multi-party conflict/resolution and independent memory-consistency review remain uninstrumented.'}
