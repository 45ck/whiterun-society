function directorLabel(director){
 if(director.running)return director.status==='stopping'?'Pausing':'Playing';
 if(director.status==='held'||director.outcome==='held')return 'Held';
 if(director.outcome==='stopped'||['stopped','paused'].includes(director.status))return 'Paused';
 if(director.outcome==='complete')return 'Run complete';
 if(director.status==='complete')return 'Stopped';
 return 'Paused';
}
// Operator charts. No chart value enters a resident's private decision context.
function activityJobLabel(job){
 const native=job.native_phase;
 if(job.orphan)return 'Quarantined orphan · release only; no recovery';
 if(job.saved_phase==='held')return 'Held'+(native==='releasing'?' · native release in progress':' · no recovery granted');
 if(job.saved_phase==='complete')return 'Rest completed'+(job.receipt_acknowledged?'':' · receipt acknowledgement pending');
 if(!job.native_observed)return job.saved_phase==='prepared'?'Awaiting native admission':'Native activity unmeasured';
 return ({accepted:'Admitted · attendance not yet observed',travelling:'Travelling to selected seat',resting:'Seated attendance in progress',releasing:'Releasing native activity',applied:'Native result ready · settlement pending',held:'Native activity held · awaiting reconciliation'})[native]||'Native activity unmeasured';
}
function ownerWorkLabel(job){
 if(job.orphan)return 'Quarantined work · release only; no output credited';
 if(job.recipe&&job.recipe.status!=='verified')return ownerRecipeLabel(job.recipe);
 if(job.settlement_state==='committed')return 'Output verified · '+(({held:'release held',releasing:'releasing',released:'release verified',acknowledged:'receipt acknowledged'})[job.cleanup_state]||'cleanup pending');
 if(job.settlement_state==='unverified')return 'Production claim unverified · review required';
 if(job.settlement_state==='effects_observed')return 'Inventory effects observed · journal confirmation pending';
 if(['awaiting_commit','committing'].includes(job.settlement_state))return 'Attendance qualified · awaiting inventory commit';
 if(job.attendance_state==='held'||job.settlement_state==='held')return 'Work held · no verified output';
 if(job.attendance_state==='qualified')return 'Attendance qualified · no goods yet';
 if(job.attendance_state==='working')return 'Work attendance in progress';
 if(job.attendance_state==='acquiring')return 'Admitted · acquiring stationary attendance';
 if(job.attendance_state==='prepared')return 'Work intention saved · admission pending';
 return 'Work attendance unmeasured';
}
function ownerRecipeLabel(recipe){
 if(!recipe)return 'Recipe quantities unverified';
 if(recipe.status==='legacy_unversioned')return 'Legacy recipe record · no catalog-verified output credit';
 if(recipe.status!=='verified')return 'Recipe verification held · '+String(recipe.status||'unknown').replaceAll('_',' ');
 const goods=amounts=>Object.entries(amounts||{}).map(([good,quantity])=>`${quantity} ${good}`).join(' + ');
 return `${recipe.id} · ${recipe.version} · ${goods(recipe.inputs)} → ${goods(recipe.outputs)}`;
}
function renderTownCharts(root,data){
 if(!root||!data)return;
 const signature=JSON.stringify(data);if(root.dataset.snapshot===signature)return;root.dataset.snapshot=signature;
 const doc=root.ownerDocument,ns='http://www.w3.org/2000/svg';
 if(!doc.getElementById('town-chart-style')){
  const style=doc.createElement('style');style.id='town-chart-style';style.textContent=`
  .town-charts{display:grid;gap:16px}.town-charts h3{margin:0 0 9px;font-size:14px;font-weight:600;color:#eee5d5}
  .town-chart-note{font-size:10px;line-height:1.4;color:#aab9ba;margin:8px 0 0;overflow-wrap:anywhere}.town-control{display:flex;align-items:center;gap:13px}
  .town-control svg{width:100px;height:100px;flex:none}.town-legend{font-size:11px;display:grid;gap:5px;flex:1}.town-legend div{display:flex;gap:6px;align-items:center}.town-legend b{margin-left:auto;font-weight:600}
  .town-swatch{width:7px;height:7px;border-radius:50%;flex:none}.town-stock-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.town-stock{padding:10px 7px;border:1px solid #ffffff15;border-radius:8px;background:#ffffff04}.town-stock strong{display:block;font-size:23px;font-weight:500;color:#e0bd72}.town-stock span{font-size:11px;color:#bac5c5}.town-stock small{display:block;font-size:9px;color:#8e9ea2;margin-top:4px}
  .town-need{margin:8px 0}.town-need-label{display:flex;justify-content:space-between;font-size:11px;margin-bottom:5px}.town-need-track{height:7px;border-radius:4px;background:#ffffff0d;overflow:hidden}.town-need-fill{height:100%;border-radius:4px;background:#dfa56d}.town-flow{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;font-size:11px}.town-flow strong{display:block;color:#9dc9ac;font-size:20px;font-weight:500}.town-tabs{display:flex;gap:5px;margin:5px 0}.town-tabs button{flex:1;background:#ffffff08;border:1px solid #ffffff18;border-radius:6px;padding:7px;color:inherit}
  .town-trend{display:block;width:100%;height:88px;margin:8px 0}.town-detail{border-top:1px solid #ffffff15;padding-top:10px}.town-detail>summary{font-size:12px;cursor:pointer;color:#e0bd72}.town-detail>summary:focus-visible{outline:2px solid #e0bd72;outline-offset:4px}
  `;doc.head.append(style);
 }
 const opened=new Set([...root.querySelectorAll('details[open]')].map(e=>e.dataset.panel));
 root.replaceChildren();root.classList.add('town-charts');
 const add=(parent,tag,text,cls)=>{const e=doc.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;parent.append(e);return e;};
 const section=title=>{const e=add(root,'section');add(e,'h3',title);return e;};
 const number=value=>typeof value==='number'&&Number.isFinite(value)?value:null;
 const shown=value=>number(value)??'—';
 const ratio=value=>value?.n?`${shown(value.percent)}% · ${value.success}/${value.n}`:'Unmeasured';
 const detail=title=>{const e=add(root,'details',undefined,'town-detail');e.dataset.panel=title;e.open=opened.has(title);add(e,'summary',title);return e;};
 const metricTiles=(parent,entries)=>{const grid=add(parent,'div',undefined,'town-flow');for(const [value,label] of entries){const tile=add(grid,'div');add(tile,'strong',value);add(tile,'span',label);}return grid;};
 const control=section('Who controls the residents?'),row=add(control,'div',undefined,'town-control');
 const svg=doc.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 120 120');svg.setAttribute('role','img');row.append(svg);
 const labels=[['agent','Agent task','#9dc9ac'],['standby','Agent standby','#6ab5b6'],['scene','Native scene','#d5967f'],['native','Other native routine','#a39ac3'],['unknown','Unknown','#8296a0'],['unloaded','Not loaded','#45565f']];
 const total=labels.reduce((n,[k])=>n+(data.control[k]||0),0),circ=2*Math.PI*46;let offset=0;
 svg.setAttribute('aria-label','Current control: '+labels.map(([k,t])=>`${t} ${data.control[k]||0}`).join(', '));
 for(const [key,label,color] of labels){const value=data.control[key]||0;if(!value||!total)continue;
  const circle=doc.createElementNS(ns,'circle');for(const [k,v] of Object.entries({cx:60,cy:60,r:46,fill:'none',stroke:color,'stroke-width':12,'stroke-dasharray':`${value/total*circ} ${circ}`,'stroke-dashoffset':-offset,transform:'rotate(-90 60 60)'}))circle.setAttribute(k,String(v));svg.append(circle);offset+=value/total*circ;
 }
 const center=doc.createElementNS(ns,'text');center.setAttribute('x','60');center.setAttribute('y','60');center.setAttribute('text-anchor','middle');center.setAttribute('fill','#f0e8d7');center.setAttribute('font-size','24');center.textContent=String(data.control.agent||0);svg.append(center);
 const sub=doc.createElementNS(ns,'text');sub.setAttribute('x','60');sub.setAttribute('y','76');sub.setAttribute('text-anchor','middle');sub.setAttribute('fill','#aab9ba');sub.setAttribute('font-size','10');sub.textContent='agent tasks';svg.append(sub);
 const legend=add(row,'div',undefined,'town-legend');for(const [key,label,color] of labels){const item=add(legend,'div');add(item,'span',undefined,'town-swatch').style.background=color;add(item,'span',label);add(item,'b',String(data.control[key]||0));}
 add(control,'p',data.control_scope,'town-chart-note');
 if(data.autonomy){const a=data.autonomy,sectionGoal=section('Personal goals'),cards=add(sectionGoal,'div',undefined,'town-stock-grid');
  for(const [value,label,note] of [[`${a.with_goal} / ${a.loaded_population}`,'With a goal','Loaded managed residents'],[a.walking_now,'Travelling','Owned native tasks'],[a.held_goals,'Held',`${a.awaiting_first_goal} awaiting first goal`]]){
   const card=add(cards,'div',undefined,'town-stock');add(card,'strong',value);add(card,'span',label);add(card,'small',note);
  }
  add(sectionGoal,'p',`${a.claimed_decisions} decision requests claimed. Pending requests are not constant thinking.`,'town-chart-note');
  add(sectionGoal,'p',a.scope,'town-chart-note');
 }
 if(data.activity_jobs){const a=data.activity_jobs,panel=section('Concurrent activities'),phases=a.states||{};
  metricTiles(panel,[[shown(a.background_active),'Observed background active'],[shown(a.foreground_active),'Foreground assignments'],[`${shown(a.leased_jobs)} / ${shown(a.capacity)}`,'Reserved native slots']]);
  if(number(a.capacity)>0&&number(a.leased_jobs)>=a.capacity)add(panel,'p','No free background slot. New admission waits for verified release and receipt acknowledgement.','town-chart-note');
  add(panel,'p',['travelling','resting','releasing','held'].map(phase=>`${phase}: ${a.fresh?shown(phases[phase]):'—'}`).join(' · '),'town-chart-note');
  add(panel,'p',`${shown(a.native_matched_jobs)} / ${shown(a.leased_jobs)} leases matched to current native observations · ${shown(phases.unmeasured)} unmeasured.`,'town-chart-note');
  if(!a.fresh)add(panel,'p','Native activity telemetry unavailable or stale; current motion and attendance are unknown.','town-chart-note');
  for(const job of a.jobs||[]){const row=add(panel,'div',undefined,'town-need');
   add(row,'strong',job.actor_name||`Resident ${job.actor}`);add(row,'div',activityJobLabel(job),'town-chart-note');
   if(number(job.rested_minutes)!==null)add(row,'div',`${shown(job.rested_minutes)} / ${shown(job.rest_minutes)} game min seated · ${shown(job.seated_samples)} samples`,'town-chart-note');
  }
  const evidence=detail('Activity admission and completion evidence');
  metricTiles(evidence,[[shown(a.recorded_admissions),'Recorded admission acknowledgements'],[shown(a.verified_completions),'Verified completed rests'],[shown(a.retained_held),'Retained held jobs']]);
  add(evidence,'p',`${shown(a.retained_jobs)} retained jobs · ${shown(a.admission_unknown)} admission histories unknown · ${shown(a.unmatched_native_jobs)} unmatched native jobs.`,'town-chart-note');
  if(number(a.retained_orphans)>0)add(evidence,'p',`${a.retained_orphans} orphan records quarantined for release only; excluded from admissions and recovered rests.`,'town-chart-note');
  add(evidence,'p',a.scope,'town-chart-note');
 }
 if(data.owner_work){const work=data.owner_work,panel=section('Independent owner work');
  metricTiles(panel,[[`${shown(work.leased_jobs)} / ${shown(work.configured_capacity)}`,'Reserved work slots'],[shown(work.observed_working),'Observed attendance'],[shown(work.awaiting_commit),'Awaiting inventory commit']]);
  add(panel,'p',`${shown(work.native_matched_jobs)} matched / ${shown(work.leased_jobs)} leases · ${shown(work.unmeasured_jobs)} unmeasured. Native capacity ${shown(work.native_capacity)}; this pool is separate from rest and citizen-control slots.`,'town-chart-note');
  if(!work.fresh)add(panel,'p','Current native work telemetry unavailable or stale. Saved settlement evidence remains separate.','town-chart-note');
  if(number(work.configured_capacity)>0&&number(work.leased_jobs)>=work.configured_capacity)add(panel,'p','All configured work slots reserved; new work must wait for verified cleanup.','town-chart-note');
  const evidence=detail('Owner-work attendance, settlement and cleanup');
  for(const job of work.jobs||[]){const row=add(evidence,'div',undefined,'town-need');add(row,'strong',job.actor_name||`Resident ${job.actor}`);add(row,'div',ownerWorkLabel(job),'town-chart-note');
   add(row,'div',ownerRecipeLabel(job.recipe),'town-chart-note');
   if(job.recipe?.status==='verified')add(row,'div',`Catalog ${job.recipe.catalog_hash} · recipe ${job.recipe.recipe_hash}`,'town-chart-note');
   add(row,'div',`Attendance: ${job.attendance_state} · settlement: ${job.settlement_state} · cleanup: ${job.cleanup_state}`.replaceAll('_',' '),'town-chart-note');
   if(number(job.worked_minutes)!==null)add(row,'div',`${shown(job.worked_minutes)} / ${shown(job.work_minutes)} game min observed attendance · ${shown(job.attendance_samples)} samples`,'town-chart-note');
  }
  metricTiles(evidence,[[shown(work.recorded_admissions),'Retained admission acknowledgements'],[shown(work.qualified_attendance),'Retained qualified attendance'],[shown(work.committed_jobs),'Linked verified production records'],[shown(work.released_jobs),'Retained releases verified']]);
  const outputs=Object.entries(work.produced_goods||{});add(evidence,'p',outputs.length?'Verified output: '+outputs.map(([good,quantity])=>`${quantity} ${good}`).join(' · '):'No verified output counted from linked production receipts.','town-chart-note');
  const inputs=Object.entries(work.consumed_goods||{});if(inputs.length)add(evidence,'p','Verified inputs used: '+inputs.map(([good,quantity])=>`${quantity} ${good}`).join(' · '),'town-chart-note');
  if(number(work.legacy_production_records)>0){add(evidence,'p',`${work.legacy_production_records} legacy production records excluded from catalog-verified totals.`,'town-chart-note');for(const record of work.legacy_records||[])add(evidence,'p',`${record.id} · ${record.status} · ${record.provenance}`,'town-chart-note');}
  add(evidence,'p',work.scope||'Retained work evidence only; admissions are not goods, GDP or profit. Productive animation remains unverified.','town-chart-note');
 }
 if(data.spatial){const s=data.spatial,current=s.current||{},movement=s.movement||{},coverage=s.coverage||{},space=section('Movement over time');
  metricTiles(space,[[shown(current.observed_moving),s.fresh?'Observed moving':'Moving · last sample'],[shown(current.travel_intentions),'Travel intentions']]);
  const points=(s.chart||[]).filter(p=>number(p.at)!==null),maxY=Math.max(1,...points.map(p=>number(p.loaded)||0)),start=points[0]?.at,end=points.at(-1)?.at;
  const measured=points.some(p=>number(p.observed_moving)!==null&&(p.observed_moving+(p.observed_stationary||0))>0);
  if(measured&&end>start){
   const chart=doc.createElementNS(ns,'svg');chart.setAttribute('viewBox','0 0 300 88');chart.setAttribute('role','img');chart.setAttribute('class','town-trend');chart.setAttribute('aria-label','Observed residents moving per valid position sample; gaps have no connecting line.');space.append(chart);
   const baseline=doc.createElementNS(ns,'path');baseline.setAttribute('d','M 24 68 H 294');baseline.setAttribute('stroke','#ffffff25');chart.append(baseline);
   let path='',connected=false;
   for(const p of points){const valid=number(p.observed_moving)!==null&&p.observed_moving>=0&&number(p.observed_stationary)!==null&&p.observed_stationary>=0&&p.observed_moving+p.observed_stationary>0;
    if(!valid){connected=false;continue;}
    const x=24+(p.at-start)/(end-start)*270,y=68-Math.min(maxY,p.observed_moving)/maxY*55;
    path+=`${connected?' L':' M'} ${x.toFixed(1)} ${y.toFixed(1)}`;connected=true;
   }
   const line=doc.createElementNS(ns,'path');line.setAttribute('data-observed-movement','');line.setAttribute('d',path);line.setAttribute('fill','none');line.setAttribute('stroke',s.fresh?'#9dc9ac':'#8296a0');line.setAttribute('stroke-width','2.5');chart.append(line);
   for(const [x,y,label] of [[3,15,String(maxY)],[10,71,'0'],[24,85,`${Math.round(end-start)}s of retained samples`]]){const text=doc.createElementNS(ns,'text');text.setAttribute('x',x);text.setAttribute('y',y);text.setAttribute('fill','#aab9ba');text.setAttribute('font-size','9');text.textContent=label;chart.append(text);}
  }else add(space,'p','Waiting for comparable position samples.','town-chart-note');
  add(space,'p',`${shown(movement.moving_percent)}% of usable resident-time moving · ${shown(coverage.usable_percent)}% measurement coverage · ${shown(s.samples)} samples`,'town-chart-note');
  add(space,'p',`${shown(coverage.usable_actor_seconds)} usable / ${shown(coverage.candidate_actor_seconds)} candidate resident-seconds. ${shown(current.unmeasured_intervals)} current intervals unmeasured.`,'town-chart-note');
  add(space,'p',s.fresh?'Standing still can be conversation, work or rest. Movement is sampled displacement, not a realism score.':'Telemetry is stale. These are last observed values; no current movement is inferred.','town-chart-note');
 }
 if(data.agency){const a=data.agency,panel=detail('Decision and journey evidence');
  metricTiles(panel,[[ratio(a.decision_acceptance),'Valid decisions accepted'],[ratio(a.journey_arrival),'Recorded journeys arrived'],[a.inference_seconds?.n?`${shown(a.inference_seconds.median)}s`:'—','Median inference latency'],[number(a.known_cost_usd)===null?'—':`$${a.known_cost_usd}`,'Known decision cost · USD']]);
  add(panel,'p',`${shown(a.recorded_results)} retained results · ${shown(a.distinct_choice_classes)} action classes · ${shown(a.distinct_chosen_destinations)} chosen places`,'town-chart-note');
  add(panel,'p',`Cost coverage ${ratio(a.cost_coverage)}. ${a.cost_scope||''}`,'town-chart-note');add(panel,'p',a.scope,'town-chart-note');
 }
 const stock=section('Observed resources'),grid=add(stock,'div',undefined,'town-stock-grid');
 for(const [key,label] of [['gold','Gold'],['bread','Loaves'],['grain','Grain']]){const value=data.stock[key],card=add(grid,'div',undefined,'town-stock');add(card,'strong',value.total??'—');add(card,'span',label);add(card,'small',`${value.accounts}/${value.population} accounts`);}
 const needs=section('Residents with unmet needs');
 for(const [key,label] of [['hunger','Hungry'],['fatigue','Tired'],['social_contact','Seeking company']]){const value=data.needs[key],item=add(needs,'div',undefined,'town-need'),line=add(item,'div',undefined,'town-need-label');add(line,'span',label);add(line,'span',value.known?`${value.high} / ${value.known}`:'Unknown');const track=add(item,'div',undefined,'town-need-track');track.setAttribute('role','meter');track.setAttribute('aria-label',label);track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax',String(value.known||1));track.setAttribute('aria-valuenow',String(value.high));add(track,'div',undefined,'town-need-fill').style.width=(value.known?value.high/value.known*100:0)+'%';}
 add(needs,'p',data.needs_scope,'town-chart-note');
 const flow=section('Economy in this save'),tiles=add(flow,'div',undefined,'town-flow');
 for(const [key,label] of [['committed_sales','Completed sales'],['committed_production','Production shifts'],['committed_meals','Meals eaten'],['active_enterprises','Open businesses'],['resident_enterprise_changes','Resident business decisions'],['operator_enterprise_changes','Operator charter edits']]){const tile=add(tiles,'div');add(tile,'strong',data.economy[key]??'—');add(tile,'span',label);}
 add(flow,'p',data.economy_scope,'town-chart-note');
 if(data.economic_network){const n=data.economic_network,panel=detail('Trade network and concentration');
  metricTiles(panel,[[shown(n.distinct_goods),'Goods in labelled receipts'],[shown(n.distinct_participants),'Trading participants'],[shown(n.directed_trade_links),'Buyer → seller links'],[shown(n.known_turnover_septims),'Known turnover · septims']]);
  add(panel,'p',`Largest seller: ${shown(n.largest_seller_transaction_share)}% of identified sales · concentration HHI ${shown(n.seller_transaction_hhi)} (0–1).`,'town-chart-note');
  add(panel,'p',`Party identity coverage ${ratio(n.party_identity_coverage)}. ${n.scope||''}`,'town-chart-note');
 }
 if(data.economic_network?.cashflow){const cash=data.economic_network.cashflow,panel=section('Recorded purse cash flow');
  const fields=['sales_receipts','purchases_paid','wages_received','wages_paid','external_grants_received'];
  const accounts=Array.isArray(cash.accounts)?cash.accounts:[];
  const complete=accounts.filter(a=>fields.every(k=>number(a[k])!==null&&a[k]>=0));
  const measured=cash.record_coverage?.success>0&&complete.length>0;
  const sum=keys=>measured?complete.reduce((total,a)=>total+keys.reduce((n,k)=>n+a[k],0),0):'—';
  metricTiles(panel,[[sum(['sales_receipts','wages_received']),'Known cash in · septims'],[sum(['purchases_paid','wages_paid']),'Known cash out · septims'],[sum(['external_grants_received']),'External grants · septims']]);
  add(panel,'p',`Validated record coverage ${ratio(cash.record_coverage)} · complete cash fields ${complete.length}/${accounts.length} account rows.`,'town-chart-note');
  add(panel,'p','Cash in = sales + wages received. Cash out = purchases + wages paid. Grants are separate. Shared household/business purses; profit unmeasured.','town-chart-note');
  const scope=detail('Cash-flow accounting scope');add(scope,'p',cash.scope||'Retained receipts only; period and unrecorded changes unknown.','town-chart-note');
 }
 if(data.drama){const d=data.drama,panel=detail('Relationships and drama evidence');
  metricTiles(panel,[[shown(d.recorded_directed_edges),'Recorded directed relationships'],[ratio(d.heard_history_coverage),'Relationships with heard history'],[shown(d.positive_affinity_edges),'Positive-affinity edges'],[shown(d.negative_affinity_edges),'Negative-affinity edges']]);
  add(panel,'p',`${shown(d.authored_background_edges)} relationships have authored starting history. Conflict-resolution chains: ${d.qualified_conflict_resolution_chains??'unmeasured'}.`,'town-chart-note');add(panel,'p',d.scope,'town-chart-note');
 }
 const wording=data.economy.wording;
 if(wording){
  const speech=section('Economic voices'),counts=add(speech,'div',undefined,'town-flow');
  for(const [key,label] of [['delivered_generated_turns','Contextual lines heard'],['fallback_turns','Original wording fallbacks']]){const tile=add(counts,'div');add(tile,'strong',wording[key]??'—');add(tile,'span',label);}
  add(speech,'p',`${wording.recorded_calls||0} recorded wording calls · exact terms retained. Dialogue realism remains unscored.`,'town-chart-note');
 }
 const negotiation=data.economy.negotiations;
 if(negotiation){
  const trade=section('What happened to trade offers?');
  const outcomes=[['sale','Completed sale','#9dc9ac'],['seller_refused','Seller refused','#e0bd72'],['buyer_left','Buyer left','#6ab5b6'],['active','In progress','#a39ac3'],['technical_failure','Technical failure','#d5967f'],['other','Other / unclassified','#8296a0']];
  for(const [key,label,color] of outcomes){
   const count=negotiation.outcomes[key]||0,item=add(trade,'div',undefined,'town-need'),line=add(item,'div',undefined,'town-need-label');
   add(line,'span',label);add(line,'span',`${count} / ${negotiation.n}`);
   const track=add(item,'div',undefined,'town-need-track');track.setAttribute('role','meter');track.setAttribute('aria-label',label);track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax',String(negotiation.n||1));track.setAttribute('aria-valuenow',String(count));
   const fill=add(track,'div',undefined,'town-need-fill');fill.style.width=(negotiation.n?count/negotiation.n*100:0)+'%';fill.style.background=color;
  }
  add(trade,'p',negotiation.n?negotiation.scope:'No retained voiced trade plans yet.','town-chart-note');
  add(trade,'p',`${data.economy.household_release_sales??'Unknown'} committed sales released one reserved loaf. Remaining household stock stays reserved.`,'town-chart-note');
  const bargaining=data.economy.bargaining;
  if(bargaining?.plans){
   for(const [commodity,seriesGroup] of Object.entries(bargaining.by_commodity||{bread:bargaining})){
     if(!seriesGroup.plans)continue;
     add(trade,'h4',commodity==='grain'?'Grain input market':'Bread market');
     const prices=add(trade,'div',undefined,'town-stock-grid');
   for(const [label,key] of [['Buyer bids','buyer_offers'],['Seller asks','seller_counteroffers'],['Paid prices','paid_prices']]){
    const series=seriesGroup[key],card=add(prices,'div',undefined,'town-stock');
    add(card,'strong',series?.n?String(series.median):'—');
    add(card,'span',`${label} · ${series?.n||0}`);
   }
   add(trade,'p',`Median septims per ${commodity==='grain'?'grain unit':'loaf'}. Bids and asks are proposals; paid prices require verified inventory exchange.`,'town-chart-note');
    }
  }
 }
}
// Targets come from the versioned server catalogue; presentation invents none.
function renderQualityGoals(root,goals){
 if(!root)return;
 const items=goals?.items||[],signature=JSON.stringify(goals||{});
 if(root.dataset.snapshot===signature)return;
 root.dataset.snapshot=signature;
 const doc=root.ownerDocument,open=new Set([...root.querySelectorAll('details[open]')].map(d=>d.dataset.objective));
 if(!doc.getElementById('quality-goal-style')){
  const style=doc.createElement('style');style.id='quality-goal-style';style.textContent=`
   .quality-summary{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0 14px}.quality-summary span{border:1px solid #ffffff22;border-radius:6px;padding:7px 9px;font-size:11px}.quality-group{border:1px solid #ffffff1c;border-radius:8px;margin:8px 0;padding:10px}.quality-group>summary{cursor:pointer;font-size:13px;color:#e0bd72}.quality-group>summary:focus-visible{outline:2px solid #e0bd72;outline-offset:4px}.quality-result{padding:10px 0;border-top:1px solid #ffffff10;margin-top:10px}.quality-result strong{font-size:12px;display:block}.quality-value{font-size:13px;margin:5px 0}.quality-status{display:inline-block;font-size:10px;border-radius:4px;padding:3px 5px;background:#ffffff0a;color:#b8c6c6}.quality-status[data-status="met"]{color:#9dc9ac}.quality-status[data-status="below_target"]{color:#d5967f}.quality-status[data-status="insufficient_sample"]{color:#e0bd72}.quality-result small{display:block;font-size:10px;line-height:1.5;color:#9bafa9;margin-top:5px}
  `;doc.head.append(style);
 }
 const add=(parent,tag,text,cls)=>{const node=doc.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;parent.append(node);return node;};
 const pretty=value=>String(value||'unknown').replaceAll('_',' ');
 root.replaceChildren();
 if(!items.length){add(root,'p','No versioned targets are available.','muted');return;}
 const summary=add(root,'div',undefined,'quality-summary');
 for(const [status,label] of [['met','Met'],['below_target','Below target'],['insufficient_sample','Needs more samples'],['unmeasured','Unmeasured']])add(summary,'span',`${items.filter(i=>i.status===status).length} ${label}`);
 add(root,'p',`Catalogue v${goals.version??'unknown'} · ${items.length} targets. Passing a threshold is not a realism score.`,'muted');
 const grouped=new Map();for(const item of items){const key=item.objective||'Other targets';if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(item);}
 for(const [objective,rows] of grouped){
  const group=add(root,'details',undefined,'quality-group');group.dataset.objective=objective;group.open=open.has(objective);
  add(group,'summary',`${objective} · ${rows.filter(i=>i.status==='met').length}/${rows.length} targets met`);
  for(const item of rows){
   const row=add(group,'div',undefined,'quality-result');add(row,'strong',`${item.id} · ${item.measure}`);
   const current=typeof item.current==='number'&&Number.isFinite(item.current)?item.current:'Unmeasured';
   add(row,'div',`${current} · target ${item.direction==='lte'?'≤':'≥'} ${item.target} ${item.unit}`,'quality-value');
   const status=add(row,'span',pretty(item.status),'quality-status');status.dataset.status=item.status;
   const sample=item.n!==null&&item.n!==undefined?`Observed n=${item.n}`:'Sample count unavailable';
   add(row,'small',sample+(item.minimum_sample?` · minimum ${item.minimum_sample}`:''));
   add(row,'small',item.scope||'Evidence scope unavailable');
  }
 }
}
if(typeof module!=='undefined')module.exports={renderTownCharts,renderQualityGoals,directorLabel,activityJobLabel,ownerWorkLabel,ownerRecipeLabel};
