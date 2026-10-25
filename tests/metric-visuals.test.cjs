const test=require('node:test'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const {renderQualityGoals,renderTownCharts}=require('../ui/society-dashboard.js');

test('OKR groups keep unknowns and sample gates visible without a fabricated score',()=>{
 const dom=new JSDOM('<main></main>');try{
  const root=dom.window.document.querySelector('main'),goals={version:3,items:[
   {id:'A-1',objective:'Autonomy',measure:'Arrival',current:100,target:95,unit:'percent',direction:'gte',n:2,minimum_sample:100,status:'insufficient_sample',scope:'Native receipts'},
   {id:'A-2',objective:'Autonomy',measure:'Human realism',current:null,target:4,unit:'rating',direction:'gte',n:null,minimum_sample:30,status:'unmeasured',scope:'<img src=x onerror=alert(1)>'},
   {id:'E-1',objective:'Economy',measure:'Conservation',current:100,target:100,unit:'percent',direction:'gte',n:100,minimum_sample:30,status:'met'}]};
  renderQualityGoals(root,goals);
  assert.equal(root.querySelectorAll('details').length,2);assert.equal(root.querySelectorAll('details[open]').length,0);
  assert.match(root.textContent,/1 Needs more samples/);assert.match(root.textContent,/Observed n=2 · minimum 100/);
  assert.match(root.textContent,/Unmeasured · target ≥ 4 rating/);assert.match(root.textContent,/not a realism score/);
  assert.equal(root.querySelector('img'),null);assert.equal(root.querySelector('meter'),null);
  root.querySelector('details').open=true;goals.items[0].n=3;renderQualityGoals(root,goals);
  assert.equal(root.querySelector('details').open,true);
  const first=root.firstChild;renderQualityGoals(root,goals);assert.equal(root.firstChild,first);
 }finally{dom.window.close();}
});

test('missing target catalogue stays unavailable',()=>{
 const dom=new JSDOM('<main></main>');try{
  const root=dom.window.document.querySelector('main');renderQualityGoals(root,null);
  assert.match(root.textContent,/No versioned targets/);assert.equal(root.querySelectorAll('details').length,0);
 }finally{dom.window.close();}
});

function dashboard(){return {control:{},stock:Object.fromEntries(['gold','bread','grain'].map(k=>[k,{total:null,accounts:0,population:0}])),needs:Object.fromEntries(['hunger','fatigue','social_contact'].map(k=>[k,{known:0,high:0}])),economy:{}};}

test('purse cash flow keeps grants separate and labels record and account coverage without profit',()=>{
 const dom=new JSDOM('<main></main>');try{
  const root=dom.window.document.querySelector('main'),d=dashboard();
  d.economic_network={cashflow:{record_coverage:{success:3,n:4,percent:75},accounts:[
   {sales_receipts:5,purchases_paid:1,wages_received:2,wages_paid:0,external_grants_received:20,net_operating_cashflow:6},
   {sales_receipts:0,purchases_paid:5,wages_received:0,wages_paid:2,external_grants_received:0,net_operating_cashflow:-7},
   {sales_receipts:100,purchases_paid:null,wages_received:0,wages_paid:0,external_grants_received:0}
  ],scope:'Current retained receipts only'}};
  renderTownCharts(root,d);
  const cash=[...root.querySelectorAll('section')].find(s=>s.querySelector('h3')?.textContent==='Recorded purse cash flow');
  assert.match(cash.textContent,/7Known cash in · septims8Known cash out · septims20External grants · septims/);
  assert.match(cash.textContent,/75% · 3\/4 · complete cash fields 2\/3/);
  assert.match(cash.textContent,/Shared household\/business purses; profit unmeasured/);
  assert.doesNotMatch(cash.textContent,/107Known|27Known|conservation score/);
  d.economic_network.cashflow={record_coverage:{n:0,success:0,percent:null},accounts:[]};renderTownCharts(root,d);
  assert.match(root.textContent,/—Known cash in · septims—Known cash out · septims—External grants/);
  assert.match(root.textContent,/Validated record coverage Unmeasured/);
 }finally{dom.window.close();}
});
test('movement chart leaves missing intervals open and distinguishes intention from movement',()=>{
 const dom=new JSDOM('<main></main>');try{
  const root=dom.window.document.querySelector('main'),d=dashboard();
  d.spatial={fresh:true,samples:4,current:{observed_moving:1,travel_intentions:8,unmeasured_intervals:0},movement:{moving_percent:20},coverage:{usable_percent:75,usable_actor_seconds:30,candidate_actor_seconds:40},chart:[
   {at:0,loaded:10,observed_moving:2,observed_stationary:8},
   {at:5,loaded:10,observed_moving:0,observed_stationary:0},
   {at:10,loaded:10,observed_moving:0,observed_stationary:10},
   {at:15,loaded:10,observed_moving:1,observed_stationary:9}]};
  renderTownCharts(root,d);
  assert.match(root.textContent,/1Observed moving8Travel intentions/);
  const path=root.querySelector('[data-observed-movement]').getAttribute('d');
  assert.equal((path.match(/ M/g)||[]).length,2);assert.equal((path.match(/ L/g)||[]).length,1);
  assert.match(root.textContent,/30 usable \/ 40 candidate resident-seconds/);
  d.spatial.fresh=false;renderTownCharts(root,d);assert.match(root.textContent,/Telemetry is stale/);assert.match(root.textContent,/Moving · last sample/);
 }finally{dom.window.close();}
});

test('receipt summaries preserve cost unknowns, scopes, and an open detail across refreshes',()=>{
 const dom=new JSDOM('<main></main>');try{
  const root=dom.window.document.querySelector('main'),d=dashboard();
  d.agency={recorded_results:3,decision_acceptance:{n:3,success:2,percent:66.67},journey_arrival:{n:0},cost_coverage:{n:3,success:0,percent:0},known_cost_usd:null,scope:'<script>unsafe()</script>'};
  d.economic_network={distinct_goods:0,distinct_participants:0,directed_trade_links:0,known_turnover_septims:null,scope:'Controlled trials included'};
  d.drama={recorded_directed_edges:4,authored_background_edges:4,heard_history_coverage:{n:4,success:0,percent:0},qualified_conflict_resolution_chains:null};
  renderTownCharts(root,d);root.querySelector('details').open=true;
  assert.match(root.textContent,/66.67% · 2\/3/);assert.match(root.textContent,/Cost coverage 0% · 0\/3/);assert.match(root.textContent,/Conflict-resolution chains: unmeasured/);
  assert.equal(root.querySelector('script'),null);assert.doesNotMatch(root.textContent,/\$0/);
  d.agency.recorded_results=4;renderTownCharts(root,d);assert.equal(root.querySelector('details').open,true);
 }finally{dom.window.close();}
});
