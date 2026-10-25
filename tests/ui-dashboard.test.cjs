const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom'),vm=require('node:vm');
const read=name=>fs.readFileSync(path.join(__dirname,'../ui',name),'utf8');
const dashboard=()=>({control:{agent:1,scene:2,native:3,unknown:1,unloaded:2},stock:Object.fromEntries(['gold','bread','grain'].map(k=>[k,{total:k==='gold'?7:null,accounts:k==='gold'?2:0,population:9}])),needs:Object.fromEntries(['hunger','fatigue','social_contact'].map(k=>[k,{high:1,known:4}])),economy:{committed_sales:2},control_scope:'Observed packages',needs_scope:'Gameplay needs',economy_scope:'Verified events'});

test('catalog readiness is plain English and stale proof cannot claim game items verified',()=>{
 const {dom,w}=native();try{const data=dashboard(),root=w.document.getElementById('town-charts');
  data.inventory_catalog={status:'missing',fresh:true,verified:false,reason:'No game-item verification report has arrived.',configured_item_count:3,configured_recipe_count:1,verified_native_item_count:null,configured_hash:'private-long-hash',reported_hash:null,diagnostics:[{item:'grain',reason:'<img src=x>'}]};
  w.renderTownCharts(root,data);
  let panel=root.querySelector('[data-catalog-status]');
  assert.match(panel.textContent,/Inventory actions waiting for verified game items/);
  assert.match(panel.textContent,/3 configured items · 1 configured recipes · — items verified/);
  assert.doesNotMatch(panel.textContent,/private-long-hash|0 resources|0 items verified/);
  const detail=[...root.querySelectorAll('details')].find(e=>e.textContent.includes('Game-item verification details'));
  assert.equal(detail.open,false);assert.match(detail.textContent,/private-long-hash/);assert.equal(root.querySelector('img'),null);
  Object.assign(data.inventory_catalog,{status:'verified',fresh:true,verified:true,verified_native_item_count:3});w.renderTownCharts(root,data);
  panel=root.querySelector('[data-catalog-status]');assert.match(panel.textContent,/Game items verified/);
  data.inventory_catalog.fresh=false;w.renderTownCharts(root,data);
  panel=root.querySelector('[data-catalog-status]');assert.equal(panel.dataset.catalogStatus,'stale');assert.match(panel.textContent,/observation is stale/);
  assert.doesNotMatch(panel.textContent,/Game items verified|3 items verified/);
 }finally{dom.window.close();}
});

test('owner work labels keep attendance, settlement and cleanup separate',()=>{
 const {ownerWorkLabel}=require('../ui/society-dashboard.js');
 assert.equal(ownerWorkLabel({attendance_state:'prepared'}),'Work intention saved · admission pending');
 assert.equal(ownerWorkLabel({attendance_state:'working'}),'Work attendance in progress');
 assert.match(ownerWorkLabel({attendance_state:'qualified',settlement_state:'awaiting_commit'}),/Attendance qualified · awaiting inventory commit/);
 assert.match(ownerWorkLabel({attendance_state:'qualified',settlement_state:'held'}),/Work held · no verified output/);
 assert.equal(ownerWorkLabel({settlement_state:'committed',cleanup_state:'held'}),'Output verified · release held');
 assert.equal(ownerWorkLabel({settlement_state:'committed'}),'Output verified · cleanup pending');
 assert.match(ownerWorkLabel({settlement_state:'unverified'}),/claim unverified/);
 assert.match(ownerWorkLabel({orphan:true,settlement_state:'committed'}),/release only; no output credited/);
});

test('versioned recipes render trusted generic quantities and clearly exclude legacy records',()=>{
 const {ownerRecipeLabel,ownerWorkLabel}=require('../ui/society-dashboard.js');
 const recipe={id:'grain_recovery',version:'v2',status:'verified',inputs:{bread:2},outputs:{grain:3},catalog_hash:'catalog-pin',recipe_hash:'recipe-pin'};
 assert.equal(ownerRecipeLabel(recipe),'grain_recovery · v2 · 2 bread → 3 grain');
 assert.match(ownerWorkLabel({recipe:{status:'legacy_unversioned'},settlement_state:'committed'}),/Legacy recipe record · no catalog-verified output credit/);
 assert.match(ownerRecipeLabel({status:'catalog_mismatch'}),/verification held · catalog mismatch/);
 assert.equal(ownerRecipeLabel(null),'Recipe quantities unverified');
 const {dom,w}=native();try{const d=dashboard();d.owner_work={jobs:[{actor:7,recipe}],consumed_goods:{bread:2},produced_goods:{grain:3},legacy_production_records:1,legacy_records:[{id:'old-record',status:'committed',provenance:'Legacy unversioned record; not credited as catalog-verified production'}]};
  const root=w.document.getElementById('town-charts');w.renderTownCharts(root,d);
  assert.match(root.textContent,/Catalog catalog-pin · recipe recipe-pin/);
  assert.match(root.textContent,/Verified output: 3 grain/);assert.match(root.textContent,/Verified inputs used: 2 bread/);
  assert.match(root.textContent,/1 legacy production records excluded from catalog-verified totals/);
  assert.match(root.textContent,/old-record · committed · Legacy unversioned/);
 }finally{dom.window.close();}
});

test('owner work charts show configured capacity, missing observations and verified outputs only',()=>{
 const {dom,w}=native();try{const d=dashboard();d.owner_work={fresh:true,configured_capacity:4,native_capacity:4,leased_jobs:4,native_matched_jobs:1,unmeasured_jobs:3,observed_working:1,awaiting_commit:0,recorded_admissions:4,qualified_attendance:0,committed_jobs:0,released_jobs:0,produced_goods:{},jobs:[{actor:7,actor_name:'<img src=x>',attendance_state:'working',settlement_state:'not_ready',cleanup_state:'reserved',worked_minutes:10,work_minutes:30,attendance_samples:4}]};
  const root=w.document.getElementById('town-charts');w.renderTownCharts(root,d);
  assert.match(root.textContent,/4 \/ 4Reserved work slots/);
  assert.match(root.textContent,/1 matched \/ 4 leases · 3 unmeasured/);
  assert.match(root.textContent,/separate from rest and citizen-control slots/);
  assert.match(root.textContent,/All configured work slots reserved/);
  assert.match(root.textContent,/10 \/ 30 game min observed attendance · 4 samples/);
  assert.match(root.textContent,/No verified output counted/);assert.equal(root.querySelector('img'),null);
  d.owner_work.produced_goods={bread:2};d.owner_work.committed_jobs=1;d.owner_work.jobs[0].settlement_state='committed';d.owner_work.jobs[0].cleanup_state='held';
  w.renderTownCharts(root,d);assert.match(root.textContent,/Verified output: 2 bread/);assert.match(root.textContent,/Output verified · release held/);
  d.owner_work.fresh=false;d.owner_work.observed_working=null;w.renderTownCharts(root,d);
  assert.match(root.textContent,/—Observed attendance/);assert.match(root.textContent,/native work telemetry unavailable or stale/);
 }finally{dom.window.close();}
});

test('background owner work appears in inspector even when another resident owns foreground',()=>{
 const {dom,w}=native();try{
  const person={profile:{name:'Owner',role:'resident',big_five:{}},needs:{hunger:.2},memories:[],relationships:{}};
  const job={actor:7,attendance_state:'qualified',settlement_state:'awaiting_commit',cleanup_state:'reserved',worked_minutes:30,work_minutes:30,attendance_samples:8};
  w.whiterunRender({residents:[{id:7,name:'Owner',isPerson:true,inventory:{gold:2,bread:1}}],trades:[],society:{people:{7:person},town:{residents:{7:{name:'Owner'}}},plan:{id:'foreground',actor:9,phase:'travelling'}},dashboard:{...dashboard(),owner_work:{jobs:[job]}}});
  w.whiterunInspectKey(2);
  const text=w.document.getElementById('resident-inspector').textContent;
  assert.match(text,/Independent owner workAttendance qualified · awaiting inventory commit/);
  assert.match(text,/settlement: awaiting commit/);
  assert.doesNotMatch(text,/Output verified/);
 }finally{dom.window.close();}
});

test('legacy owner completion never acquires a current catalog verification label',()=>{
 const {dom,w}=native();try{
  const person={profile:{name:'Owner',role:'resident',big_five:{}},needs:{hunger:.2},memories:[],relationships:{}};
  const plan={id:'legacy-work',actor:7,phase:'complete',outcome:'owner_work_completed',own_work_terms:{policy:{work_minutes:30}}};
  w.whiterunRender({residents:[{id:7,name:'Owner',isPerson:true,inventory:{gold:2,bread:1}}],trades:[],society:{people:{7:person},town:{residents:{7:{name:'Owner'}}},plan},dashboard:dashboard()});
  w.whiterunInspectKey(2);
  const text=w.document.getElementById('resident-inspector').textContent;
  assert.match(text,/Recipe quantities unverified/);
  assert.match(text,/Recorded owner-work completion · current catalog verification unavailable/);
  assert.doesNotMatch(text,/1 grain → 2 bread|Catalog-authorized output verified|Owned output verified/);
 }finally{dom.window.close();}
});
test('resident inspector labels controlled business choices separately from model choices',()=>{
 const {dom,w}=native();try{
 const person={profile:{name:'New resident',role:'resident',big_five:{}},needs:{hunger:.4},memories:[],trust:{},relationships:{}};
 const plan={id:'business',actor:7,phase:'complete',outcome:'enterprise_registered',enterprise_change:{business_id:'resident-7',revision:1},decisions:[{model:'controlled-enterprise-fixture',decision:{action_id:'offer_food_trade_resident-7'}}]};
 const data={residents:[{id:7,name:'New resident',isPerson:true,inventory:{gold:2,bread:1,grain:0}}],trades:[],director:{running:false},society:{plan,people:{'7':person},town:{residents:{'7':{name:'New resident'}}}}};
 w.whiterunRender(data);w.whiterunInspectKey(2);
 assert.match(w.document.getElementById('resident-inspector').textContent,/Business integration test/);
 assert.match(w.document.getElementById('resident-inspector').textContent,/enterprise registered/);
 plan.decisions=[{model:'real-decision-model',decision:{action_id:'offer_food_trade_resident-7'}}];w.whiterunRender(data);
 assert.match(w.document.getElementById('resident-inspector').textContent,/Own business decision/);
 }finally{dom.window.close();}
});
function native(){
 const dom=new JSDOM(read('index.html'),{runScripts:'outside-only',url:'https://local.invalid/'}),w=dom.window,messages=[],intervals=[];
 w.setInterval=(fn,ms)=>{intervals.push({fn,ms});return intervals.length;};w.skyrimPlatform={sendMessage:m=>messages.push(m)};
 for(const script of w.document.scripts)vm.runInContext(script.src?read(path.basename(script.src)):script.textContent,dom.getInternalVMContext());
 return {dom,w,messages,intervals};
}

test('resident intent reviews show pending work and actual follow-through instead of invented quiet activity',()=>{
 const {dom,w}=native();try{
  const goal={id:'goal-7',phase:'review_pending',focus:'food',decided_day:1,follow_through:{event_id:'review-7',status:'pending'}};
  const person={profile:{name:'Resident',role:'resident',big_five:{}},standing_goal:goal,needs:{hunger:.6},memories:[],relationships:{}};
  const data={gameDays:1,camera:{manual:true,mode:'focus',id:7},residents:[{id:7,name:'Resident',isPerson:true,inventory:{gold:2,bread:1}}],trades:[],director:{dispatch:{pending_count:4,overdue_count:1,maximum_wait_game_minutes:20}},society:{people:{7:person},town:{residents:{7:{name:'Resident'}},daily:{queue:[{id:'review-7',status:'pending'}]}}}};
  for(const focus of ['food','work','rest','social']){
   goal.focus=focus;w.whiterunRender(data);w.whiterunInspectKey(2);
   const content=w.document.getElementById('resident-inspector').textContent;
   assert.match(content,new RegExp(focus.charAt(0).toUpperCase()+focus.slice(1)+' review'));
   assert.match(content,/Waiting for review · not currently thinking or completing work/);
   assert.doesNotMatch(content,/Quiet interval/);
  }
  assert.match(w.document.getElementById('dispatch-state').textContent,/4 pending · 1 overdue · longest wait 20 game min/);
  goal.phase='reviewed';data.society.town.daily.queue[0]={id:'review-7',status:'complete',outcome:'deferred'};w.whiterunRender(data);
  assert.match(w.document.getElementById('resident-inspector').textContent,/Follow-through · completeRecorded event · review-7Recorded outcome · deferred/);
  assert.match(w.document.getElementById('resident-inspector').textContent,/Movement does not imply trade, work or rest recovery/);
  goal.phase='arrived';goal.target={name:'Workshop'};goal.follow_through={status:'unavailable',reason:'No nearby opportunity'};w.whiterunRender(data);
  assert.match(w.document.getElementById('resident-inspector').textContent,/Workshop · arrived/);
  assert.match(w.document.getElementById('resident-inspector').textContent,/Follow-through · unavailableNo nearby opportunity/);
 }finally{dom.window.close();}
});

test('town review summary uses the recorded focus without claiming every model is idle',()=>{
 const {dom,w}=native();try{
  const data={camera:{manual:false,mode:'story'},residents:[],trades:[],director:{running:true},society:{people:{7:{profile:{name:'Worker'},needs:{hunger:.2},agency:{state:'decision_pending'}}},town:{residents:{7:{}},counts:{residents:1},daily:{sequence:2,queue:[{actor:7,status:'pending',kind:'need_review',goal_followups:[{focus:'work'}]}]}}}};
  w.whiterunRender(data);assert.equal(w.document.getElementById('town-next').textContent,'Queued: Worker · work review');
  data.society.town.daily.queue=[];w.whiterunRender(data);
  assert.match(w.document.getElementById('town-next').textContent,/Personal scheduling is reported separately/);
  assert.doesNotMatch(w.document.getElementById('town-next').textContent,/No model is running|considers food/);
 }finally{dom.window.close();}
});

test('native inspector shows background attendance while a different resident has the foreground activity',()=>{
 const {dom,w}=native();try{
  const data={camera:{manual:true,mode:'focus',id:7},residents:[{id:7,name:'Resting resident',isPerson:true}],trades:[],director:{running:true},dashboard:{...dashboard(),activity_jobs:{fresh:true,jobs:[{actor:7,saved_phase:'running',native_observed:true,native_phase:'resting',rested_minutes:12,rest_minutes:30,seated_samples:5}]}},society:{people:{7:{profile:{name:'Resting resident',big_five:{}},needs:{hunger:.2},memories:[],relationships:{}}},town:{residents:{7:{name:'Resting resident'}}},plan:{id:'other-work',actor:8,kind:'need_review',phase:'travelling'}}};
  w.whiterunRender(data);
  const content=w.document.getElementById('resident-inspector').textContent;
  assert.match(content,/Independent background activitySeated attendance in progress/);
  assert.match(content,/12 \/ 30 game minutes seated · 5 samples/);
  assert.match(content,/Admission and travel do not grant recovery/);
  assert.match(w.document.getElementById('people').textContent,/Seated attendance in progress/);
 }finally{dom.window.close();}
});

test('native RTS gestures use the reported camera and focused browser can release F8',()=>{
 const {dom,w,messages,intervals}=native();try{
 w.whiterunRender({residents:[],trades:[],camera:{mode:'free',manual:true,distance:1200,elevation:900,yaw:225,panX:24000,panY:-8000},director:{running:false},dashboard:dashboard()});
 w.document.body.dispatchEvent(new w.KeyboardEvent('keydown',{key:'d',bubbles:true}));
 const moved=messages.at(-1);assert.equal(moved.type,'society-camera');assert.equal(moved.yaw,-135);assert.equal(moved.distance,1200);assert.ok(moved.panX<24000);
 w.document.body.dispatchEvent(new w.KeyboardEvent('keydown',{key:'F8',bubbles:true,cancelable:true}));
 assert.equal(messages.at(-1).type,'society-ui-focus');assert.equal(messages.at(-1).focused,false);
 const input=w.document.createElement('input');w.document.body.append(input);
 input.dispatchEvent(new w.KeyboardEvent('keydown',{key:'d',bubbles:true}));
 const before=messages.length;for(const i of intervals.filter(x=>x.ms===2000))i.fn();
 const health=messages.slice(before).find(m=>m.type==='society-ui-health');
 assert.equal(health.diagnostics.counts.keydown,3);assert.equal(health.diagnostics.last_control_key,'F8','typed text is not retained');
 }finally{dom.window.close();}
});

test('a missed pointer release cannot turn later hovering into camera movement',()=>{
 const {dom,w,messages}=native();try{
 const event=(name,x,buttons)=>new w.MouseEvent(name,{bubbles:true,clientX:x,clientY:300,button:0,buttons});
 w.document.body.dispatchEvent(event('pointerdown',300,1));
 const before=messages.filter(m=>m.type==='society-camera').length;
 w.document.body.dispatchEvent(event('pointermove',350,0));
 w.document.body.dispatchEvent(event('pointermove',400,1));
 assert.equal(messages.filter(m=>m.type==='society-camera').length,before);
 }finally{dom.window.close();}
});
test('native UI defaults to movie view and retains explicit Play/Pause and RTS controls',()=>{
 const {dom,w,messages,intervals}=native();try{
 assert.equal(w.whiterunRtsActive(),false);assert.equal(w.document.getElementById('tour'),null);
 w.whiterunRender({residents:[],trades:[],society:{people:{},town:{residents:{}}},director:{running:false,status:'idle'},dashboard:dashboard(),camera:{manual:true,mode:'free'}});
 assert.equal(w.document.getElementById('live-badge').textContent,'PAUSED');assert.match(w.document.getElementById('notice').textContent,/Scheduling paused/);
 w.document.getElementById('society-play').click();assert.equal(messages.at(-1).action,'play');
 w.whiterunRender({residents:[],trades:[],director:{running:true,status:'running'},dashboard:dashboard()});
 w.document.getElementById('society-pause').click();assert.equal(messages.at(-1).action,'pause');
 w.document.querySelector('[data-camera="story"]').click();assert.equal(messages.at(-1).mode,'story');
 w.whiterunRender({residents:[],trades:[],director:{running:true,status:'running'},dashboard:dashboard(),camera:{manual:false,mode:'focus',id:7}});assert.equal(w.whiterunRtsActive(),false);assert.equal(w.document.querySelector('[data-camera="story"]').classList.contains('active'),true);
 const before=messages.filter(m=>m.type==='society-camera').length;for(const i of intervals)i.fn();
 assert.equal(messages.filter(m=>m.type==='society-camera').length,before);
 w.document.getElementById('rts-mode').click();assert.equal(messages.at(-1).mode,'free');
 }finally{dom.window.close();}
});

test('both run labels distinguish an intentional stop from a completed run and settling pause',()=>{
 const {dom,w}=native();try{
  const cases=[
   [{running:false,status:'complete',outcome:'stopped'},'Paused'],
   [{running:true,status:'stopping',outcome:'running'},'Pausing'],
   [{running:true,status:'running'},'Playing'],
   [{running:false,status:'complete',outcome:'complete'},'Run complete'],
   [{running:false,status:'complete'},'Stopped'],
   [{running:false,status:'held',outcome:'held',error:'Receipt unavailable'},'Held'],
   [{running:false,status:'idle'},'Paused']
  ];
  for(const [director,label] of cases){
   w.whiterunRender({residents:[],trades:[],director:{...director,max_events:12,events_completed:1}});
   const sidebar=w.document.getElementById('society-state').textContent,left=w.document.getElementById('director-state').textContent;
   assert.equal(left,'Society '+sidebar);assert.ok(sidebar.startsWith(label+' · 1 / 12 events'));
   assert.equal(w.document.getElementById('live-badge').textContent,label.toUpperCase());
   if(label==='Pausing')assert.match(sidebar,/settling current activity/);
   if(label==='Paused')assert.doesNotMatch(left,/complete/i);
  }
 }finally{dom.window.close();}
});

test('movie camera-follow card cannot obscure the encounter during any dialogue phase',()=>{
 const {dom,w}=native();try{
  const data={residents:[{id:7,name:'Resident',isPerson:true,inventory:{gold:5,bread:1}}],trades:[],director:{running:true},camera:{manual:false,mode:'focus',id:7},society:{people:{},town:{residents:{'7':{name:'Resident'}}}}};
  for(const phase of ['meeting','thinking_propose','thinking_select','synthesize','speaking','complete']){
   data.society.conversation={id:'chat',phase,speakers:[7,8],initiator:7,current:{speaker:7},turns:[{speaker:7,selected:{line:'A long conversation remains available to read. '.repeat(30)}}]};
   w.whiterunRender(data);
   const encounter=w.document.getElementById('conversation-card'),follow=w.document.getElementById('focus-card');
   assert.equal(encounter.hidden,false,phase);assert.equal(w.getComputedStyle(follow).display,'none',phase);
   assert.match(encounter.textContent,/A long conversation remains available/);
   assert.equal(w.getComputedStyle(encounter).overflowY,'auto');assert.equal(w.getComputedStyle(encounter).maxHeight,'calc(100vh - 275px)');
  }
  delete data.society.conversation;w.whiterunRender(data);
  assert.equal(w.document.getElementById('focus-card').hidden,false);assert.notEqual(w.getComputedStyle(w.document.getElementById('focus-card')).display,'none');
 }finally{dom.window.close();}
});

test('legacy market-day records stay in collapsed labelled history and cannot replace live rest or work',()=>{
 const {dom,w}=native();try{
  const day={id:'old-controlled-sequence',status:'complete',cursor:4,source:'Authored finite sequence of opportunities; residents choose outcomes',results:[{actor:71,kind:'meal_time',outcome:'ate_bread',status:'complete'}],metrics:{production:1,trades:0,consumptions:1,gold_before:14,gold_after:14}};
  const data={residents:[],trades:[],director:{running:true},camera:{manual:false,mode:'focus',id:71},society:{people:{71:{profile:{name:'New resident'}},72:{profile:{name:'Employer'}}},market_day:day,plan:{id:'current-rest',actor:71,kind:'need_review',phase:'resting',decisions:[]}}};
  w.whiterunRender(data);
  const history=w.document.getElementById('scenario-history');
  assert.equal(w.document.getElementById('day-card'),null);assert.equal(history.hidden,false);assert.equal(history.open,false);
  assert.equal(history.closest('.sidebar')!==null,true);
  assert.match(history.textContent,/Controlled scenario history/);assert.match(history.textContent,/not current town activity/);
  assert.match(history.textContent,/New resident · meal time · ate bread/);assert.match(history.textContent,/Recorded participant gold: 14 → 14/);
  assert.doesNotMatch(history.textContent,/Ysolda|Carlotta|Paid work|Household stock review|A day in the town/);
  history.open=true;
  day.status='running';day.metrics=undefined;day.results=[];
  data.society.plan={id:'current-work',actor:71,target:72,kind:'work_shift',phase:'working',decisions:[]};
  w.whiterunRender(data);
  assert.equal(history.open,true);assert.match(history.textContent,/Recorded status: running/);assert.match(history.textContent,/No settled results recorded/);
  assert.doesNotMatch(history.textContent,/14 → 14|Scenario totals/);assert.equal(w.document.getElementById('work-card').hidden,false);
  delete data.society.market_day;w.whiterunRender(data);assert.equal(history.hidden,true);
 }finally{dom.window.close();}
});

test('controlled history renders saved actor and outcome labels as text without inventing future stages',()=>{
 const {dom,w}=native();try{
  w.whiterunRender({residents:[],trades:[],director:{running:false},society:{people:{93:{profile:{name:'<img src=x onerror=alert(1)>'}}},market_day_history:[{id:'history',status:'held',results:[{actor:93,kind:'new_activity_kind',outcome:'declined'}],metrics:{trades:0}}]}});
  const history=w.document.getElementById('scenario-history');assert.match(history.textContent,/new activity kind · declined/);
  assert.equal(history.querySelector('img'),null);assert.match(history.textContent,/— production · 0 purchases · — meals/);
  assert.doesNotMatch(history.textContent,/Next:|Following the residents/);
 }finally{dom.window.close();}
});
test('charts render accessible distinct units, unknowns and untrusted labels as text',()=>{
 const {dom,w}=native();try{const d=dashboard();d.control_scope='<img src=x onerror=alert(1)>';const root=w.document.getElementById('town-charts');w.renderTownCharts(root,d);
 assert.equal(root.querySelectorAll('svg[role="img"]').length,1);assert.match(root.querySelector('svg').getAttribute('aria-label'),/Agent task 1/);
 assert.equal(root.querySelectorAll('[role="meter"]').length,3);assert.match(root.textContent,/2\/9 accounts/);assert.match(root.textContent,/—/);assert.equal(root.querySelector('img'),null);
 const first=root.firstChild;w.renderTownCharts(root,d);assert.equal(root.firstChild,first);
 }finally{dom.window.close();}
});
test('control room uses same charts and play API; rendering does not auto-steer camera',async()=>{
 const html=read('observer.html').replace('<script>','<script>\n'+read('society-dashboard.js')+'\n');
 const dom=new JSDOM(html,{runScripts:'outside-only',url:'http://127.0.0.1:17854/'}),w=dom.window,requests=[];
 const state={connected:true,residents:[],places:[],businesses:[],limits:[],director:{running:false,status:'idle'},dashboard:dashboard()};
 w.setInterval=()=>1;w.fetch=async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>url==='/observer/state'?state:{running:true,status:'running'}};};
 try{for(const script of w.document.scripts)w.eval(script.textContent);await new Promise(r=>setImmediate(r));
 assert.equal(w.document.querySelectorAll('#town-charts svg').length,1);
 for(const [director,label] of [[{status:'complete',running:false,outcome:'stopped'},'Paused'],[{status:'stopping',running:true},'Pausing'],[{status:'complete',running:false,outcome:'complete'},'Run complete']]){
  state.director={...director,max_events:12,events_completed:1};await w.poll();
  assert.match(w.document.getElementById('director-status').textContent,new RegExp('^Society '+label+' · 1 / 12 events settled'));
 }
 state.director={status:'idle',running:false};await w.poll();
 w.document.getElementById('director-start').click();await new Promise(r=>setImmediate(r));
 const request=requests.find(r=>r.url==='/observer/director');assert.equal(JSON.parse(request.options.body).action,'play');assert.equal(JSON.parse(request.options.body).max_events,96);
 assert.equal(requests.some(r=>r.url==='/observer/camera'),false);
 }finally{dom.window.close();}
});
const testVoice=(options={})=>{
 const dom=new JSDOM(read('index.html'),{runScripts:'outside-only',url:'https://local.invalid/'}),w=dom.window,messages=[],audio=[];
 w.setInterval=()=>1;w.skyrimPlatform={sendMessage:m=>messages.push(m)};
 class FakeAudio{constructor(){this.volume=1;this.muted=false;audio.push(this);}setSinkId(id){this.sink=id;return options.fail?Promise.reject(new Error('Unavailable output')):Promise.resolve();}play(){this.played=true;return Promise.resolve();}pause(){this.paused=true;}}
 w.Audio=FakeAudio;w.HTMLMediaElement.prototype.setSinkId=FakeAudio.prototype.setSinkId;
 Object.defineProperty(w.navigator,'mediaDevices',{value:{enumerateDevices:async()=>options.devices||[{kind:'audiooutput',deviceId:'default',label:'System speakers'},{kind:'audiooutput',deviceId:'headset',label:'Headset'}],addEventListener(){}}});
 for(const script of w.document.scripts)vm.runInContext(script.src?read(path.basename(script.src)):script.textContent,dom.getInternalVMContext());
 return {dom,w,messages,audio};
};

test('enterprise editor preserves every supported production and grain-retail combination',async()=>{
 const dom=new JSDOM(read('observer.html'),{runScripts:'outside-only',url:'http://127.0.0.1:17854/'}),w=dom.window,requests=[];
 const state={connected:true,residents:[{id:91,name:'New resident',loaded:true,is_guard:false}],places:[],businesses:[],limits:[],director:{running:false},dashboard:dashboard()};
 w.setInterval=()=>1;w.fetch=async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>url==='/observer/state'?state:{business:{revision:2},checkpoint:3}};};
 try{
  w.eval(read('society-dashboard.js'));for(const script of w.document.scripts)if(!script.src)w.eval(script.textContent);await new Promise(r=>setImmediate(r));
  const caps=['bread_recipe','retail_food','retail_grain'];
  for(let mask=1;mask<8;mask++){
   const expected=caps.filter((_,i)=>mask&(1<<i));
   w.editEnterprise({id:'b',name:'Business',custodian:91,revision:1,capabilities:expected,active:true});
   await w.document.getElementById('enterprise-form').onsubmit({preventDefault(){}});
   const sent=JSON.parse(requests.filter(r=>r.url==='/observer/enterprise').at(-1).options.body).enterprise;
   assert.deepEqual(sent.capabilities.sort(),expected.sort());assert.equal(sent.custodian,91);assert.equal(sent.expected_revision,1);
  }
 }finally{dom.window.close();}
});
test('voice output preference routes the next line without changing Windows or requesting a microphone',async()=>{
 const {dom,w,audio}=testVoice();try{await new Promise(r=>setImmediate(r));const select=w.document.getElementById('voice-output');select.value='headset';select.dispatchEvent(new w.Event('change'));
 w.whiterunSpeak({id:'test-line',actor:1,line:'Good evening',tone:'calm',audio:{file:'fixture.wav'}});await new Promise(r=>setImmediate(r));assert.equal(audio[0].sink,'headset');assert.equal(audio[0].played,true);assert.equal(w.localStorage.getItem('whiterun-voice-output'),'headset');
 }finally{dom.window.close();}
});
test('an unavailable selected voice output fails visibly instead of claiming playback',async()=>{
 const {dom,w,audio,messages}=testVoice({fail:true});try{await new Promise(r=>setImmediate(r));w.whiterunSpeak({id:'test-line',actor:1,line:'Hello',tone:'calm',audio:{file:'fixture.wav'}});await new Promise(r=>setImmediate(r));assert.equal(audio[0].played,undefined);assert.equal(messages.find(m=>m.type==='society-speech').status,'failed');
 }finally{dom.window.close();}
});
test('operator voice selection requires a unique permitted device and preserves the selection after a rejected request',async()=>{
 const {dom,w,audio,messages}=testVoice();try{
 await w.whiterunSelectVoiceOutput('pick','Headset');assert.equal(messages.at(-1).selection.status,'selected');
 await w.whiterunSelectVoiceOutput('missing','Realtek');assert.equal(messages.at(-1).selection.status,'failed');
 w.whiterunSpeak({id:'line',actor:1,line:'Hello',audio:{file:'fixture.wav'}});await new Promise(r=>setImmediate(r));assert.equal(audio[0].sink,'headset');
 await w.whiterunSelectVoiceOutput('default','default');assert.equal(w.localStorage.getItem('whiterun-voice-output'),'');
 }finally{dom.window.close();}
});
test('trade chart separates refused offers, active agreements and committed sales',()=>{
 const {dom,w}=native();try{const d=dashboard();d.economy.negotiations={n:3,outcomes:{seller_refused:1,active:2},scope:'Receipts only'};d.economy.household_release_sales=0;
 const root=w.document.getElementById('town-charts');w.renderTownCharts(root,d);
 assert.equal(root.querySelector('[aria-label="Seller refused"]').getAttribute('aria-valuenow'),'1');
 assert.equal(root.querySelector('[aria-label="Completed sale"]').getAttribute('aria-valuenow'),'0');
 assert.equal(root.querySelector('[aria-label="In progress"]').getAttribute('aria-valuemax'),'3');
 assert.match(root.textContent,/0 committed sales released one reserved loaf/);
 d.economy.negotiations={n:0,outcomes:{}};w.renderTownCharts(root,d);assert.match(root.textContent,/No retained voiced trade plans/);assert.equal(root.innerHTML.includes('NaN'),false);
 }finally{dom.window.close();}
});

test('bargaining chart shows proposed prices separately from absent payments',()=>{
 const {dom,w}=native();try{const d=dashboard();d.economy.negotiations={n:1,outcomes:{active:1}};
 d.economy.bargaining={plans:1,buyer_offers:{n:2,median:5.5},seller_counteroffers:{n:1,median:7},paid_prices:{n:0,median:null}};
 const root=w.document.getElementById('town-charts');w.renderTownCharts(root,d);
 assert.match(root.textContent,/5\.5Buyer bids · 2/);assert.match(root.textContent,/7Seller asks · 1/);
 assert.match(root.textContent,/—Paid prices · 0/);assert.match(root.textContent,/verified inventory exchange/);
 assert.equal(root.textContent.includes('undefined'),false);
 }finally{dom.window.close();}
});
test('ambiguous output labels cannot silently select the wrong speakers',async()=>{
 const {dom,w,messages}=testVoice({devices:[{kind:'audiooutput',deviceId:'a',label:'Realtek front'},{kind:'audiooutput',deviceId:'b',label:'Realtek rear'}]});try{
 await w.whiterunSelectVoiceOutput('ambiguous','Realtek');assert.equal(messages.at(-1).selection.status,'failed');assert.equal(messages.at(-1).selection.reason,'Ambiguous output label');
 assert.equal(w.localStorage.getItem('whiterun-voice-output'),null);
 }finally{dom.window.close();}
});

test('grain payments are displayed separately from bread bids and prices',()=>{
 const {dom,w}=native();try{const d=dashboard();d.economy.negotiations={n:2,outcomes:{sale:1,seller_refused:1}};
 d.economy.bargaining={plans:2,by_commodity:{bread:{plans:1,buyer_offers:{n:1,median:7},paid_prices:{n:0}},grain:{plans:1,buyer_offers:{n:1,median:2},paid_prices:{n:1,median:2}}}};
 const root=w.document.getElementById('town-charts');w.renderTownCharts(root,d);
 assert.match(root.textContent,/Bread market.*7Buyer bids · 1.*—Paid prices · 0.*Median septims per loaf/);
 assert.match(root.textContent,/Grain input market.*2Paid prices · 1.*Median septims per grain unit/);
 }finally{dom.window.close();}
});

test('voice check is explicitly diagnostic and does not create resident speech events',async()=>{
 const {dom,w,audio,messages}=testVoice();try{await new Promise(r=>setImmediate(r));await w.whiterunTestVoice('check');assert.equal(audio[0].played,true);audio[0].currentTime=3;audio[0].onended();assert.equal(messages.some(m=>m.type==='society-speech'),false);assert.equal(messages.at(-1).test.status,'ended');assert.match(w.document.getElementById('voice-output-status').textContent,/no resident event/);
 }finally{dom.window.close();}
});

test('audio check cannot overlap a running society even between spoken turns',async()=>{
 const {dom,w,audio}=testVoice();try{await new Promise(r=>setImmediate(r));w.whiterunRender({residents:[],trades:[],director:{running:true,status:'running'}});await w.whiterunTestVoice('check');assert.equal(audio.length,0);assert.match(w.document.getElementById('voice-output-status').textContent,/Pause society/);
 }finally{dom.window.close();}
});


test('native inspector distinguishes owned standby from activity and stale ownership',()=>{
 const {dom,w}=native();try{
 const data={residents:[{id:7,name:'Resident',activity:{package_id:9000}}],trades:[],society:{people:{},town:{residents:{}}},resident_control:{activities:[{actor:7,ownedPackage:true,expectedPackage:9000,phase:'holding'}]}};
 w.whiterunRender(data);assert.match(w.residentActivity(7),/Awaiting a decision/);
 data.residents[0].activity.package_id=42;w.whiterunRender(data);assert.equal(w.residentActivity(7),'Native routine');
 data.residents[0].activity.scene_id=888;w.whiterunRender(data);assert.equal(w.residentActivity(7),'Native scene');
 }finally{dom.window.close();}
});
const mediaFixture=()=>{
 const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'../docs/images/resident-media.json'),'utf8'));
 const dom=new JSDOM('<svg id="map"></svg>',{runScripts:'outside-only'});dom.window.RESIDENT_MEDIA=manifest;dom.window.eval(read('resident-media.js'));return {dom,w:dom.window,manifest,media:dom.window.residentMedia};
};
test('aerial markers respect native calibration, elevation and world boundaries',()=>{
 const {dom,manifest:m,media}=mediaFixture();try{
 const p=m.map.projection,space=m.map.space;
 const center=media.point([p.camera[0],p.camera[1],p.world[0][2]],space);assert.ok(Math.abs(center[0]-641)<.001);assert.ok(Math.abs(center[1]-391)<.001);
 const low=media.point([p.camera[0]+1000,p.camera[1],p.world[0][2]],space),high=media.point([p.camera[0]+1000,p.camera[1],p.world[0][2]+1000],space);assert.ok(high[0]>low[0]);
 for(const [position,s] of [[[1,2,NaN],space],[[1,2,3],{...space,interior:true}],[[1,2,3],{...space,world:42}],[[1,2,3],null],[[1,2,p.camera[2]],space]])assert.equal(media.point(position,s),null);
 }finally{dom.window.close();}
});
test('portraits require both reference and base identity and render names safely',()=>{
 const {dom,manifest,media}=mediaFixture();try{
 const [key,a]=Object.entries(manifest.portraits)[0],r={id:Number(key),baseId:a.baseId,name:'<img src=x onerror=alert(1)>'};
 assert.equal(media.portrait(r).querySelector('image').getAttribute('href'),'media/'+a.file);
 assert.equal(media.portrait({...r,baseId:a.baseId+1}).querySelector('image'),null);
 assert.equal(media.portrait({...r,id:999999}).querySelector('image'),null);
 assert.equal(media.portrait({...r,baseId:null}).querySelector('image'),null);
 assert.equal(media.portrait(r).querySelector('img'),null);
 const face=media.portrait(r);face.querySelector('image').dispatchEvent(new dom.window.Event('error'));assert.equal(face.querySelector('image'),null);
 }finally{dom.window.close();}
});
test('map selection is keyboard accessible and stale markers cannot send commands',()=>{
 const {dom,w,manifest:m,media}=mediaFixture();try{
 const svg=w.document.querySelector('svg'),selected=[],r={id:99,name:'Resident',loaded:true,position:[23500,-3500,-3320],space:m.map.space};
 media.renderMap(svg,[r,{...r,id:100,loaded:false}],99,id=>selected.push(id));assert.equal(svg.querySelectorAll('circle').length,1);
 svg.querySelector('circle').dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter'}));assert.deepEqual(selected,[99]);
 media.renderMap(svg,[r],99,id=>selected.push(id),{connected:false});svg.querySelector('circle').dispatchEvent(new w.Event('click'));assert.deepEqual(selected,[99]);assert.match(svg.getAttribute('aria-label'),/last observed/);
 }finally{dom.window.close();}
});
test('native roster presents actual faces and septims with captured map',()=>{
 const {dom,w}=native();try{const m=w.RESIDENT_MEDIA,a=m.portraits['108149'];w.whiterunRender({residents:[{id:108149,name:a.name,baseId:a.baseId,isPerson:true,x:23500,y:-3500,z:-3320,space:m.map.space,inventory:{gold:12,bread:2,grain:1}}],trades:[],society:{people:{'108149':{profile:{name:a.name},needs:{hunger:.2}}},town:{residents:{'108149':{name:a.name}}}},director:{running:false},camera:{mode:'free',manual:true}});
 assert.equal(w.document.querySelectorAll('#people .resident-face image').length,1);assert.match(w.document.querySelector('#people').textContent,/SEPTIMS/);assert.equal(w.document.querySelectorAll('#map image').length,1);assert.equal(w.document.querySelectorAll('#map circle').length,1);
 }finally{dom.window.close();}
});

test('economic encounter timing cannot reuse an earlier conversation inference',()=>{
 const {dom,w}=native();try{
 w.whiterunRender({residents:[],director:{running:false},society:{people:{},town:{residents:{}},
  conversation:{id:'old',phase:'complete',turns:[{language:{elapsed_seconds:99},decision:{elapsed_seconds:88}}]},
  plan:{id:'trade',kind:'meal_time',actor:1,phase:'economic_speaking',economic_pair:[1,2],decisions:[{actor_id:1,model:'controlled-native-fixture',decision:{action_id:'bid_price_4'}}],economic_speech:{actor:1,audio:{seconds:2.5}}}}});
 assert.equal(w.document.getElementById('encounter-timing').textContent,'Voice 2.5s');
 assert.match(w.document.getElementById('encounter-pipeline').textContent,/Controlled protocol test/);
 }finally{dom.window.close();}
});

test('employment shows work progress between spoken terms and receipt',()=>{
 const {dom,w}=native();try{
 const plan={id:'job',kind:'work_shift',actor:1,target:2,voiced_trade:true,employment_dialogue:true,phase:'working',
  work_terms:{policy:{wage_gold:4,work_minutes:10}},economic_turns:[{actor:1,act:'work_accept',line:'I accept.'}]};
 const state={residents:[],director:{running:true},society:{people:{},town:{residents:{}},plan},productionWork:{workedMinutes:3}};
 w.whiterunRender(state);
 assert.equal(w.document.getElementById('conversation-card').hidden,true);
 assert.equal(w.document.getElementById('work-card').hidden,false);
 assert.match(w.document.getElementById('work-card').textContent,/3 \/ 10/);
 w.whiterunRender({...state,society:{...state.society,plan:{...plan,phase:'economic_speaking',economic_speech:{actor:1,audio:{seconds:2}}}}});
 assert.match(w.document.getElementById('conversation-stage').textContent,/Employment/);
 assert.equal(w.document.getElementById('conversation-card').hidden,false);
 }finally{dom.window.close();}
});

test('economic wording stages and fallback provenance are visible without exposing templates',()=>{
 const {dom,w}=native();try{
 const plan={id:'wording',kind:'meal_time',actor:1,target:2,voiced_trade:true,natural_trade:true,
  phase:'economic_thinking_select',economic_pair:[1,2],decisions:[],economic_speech:{actor:1,
  line:'Would you sell me a loaf?',candidates:[{line:'Please. [[TERMS]]'}],wording_results:[{accepted:true}]}};
 w.whiterunRender({residents:[],director:{running:true},society:{people:{},town:{residents:{}},plan}});
 assert.match(w.document.getElementById('conversation-stage').textContent,/Choosing a reply/);
 assert.match(w.document.getElementById('encounter-pipeline').textContent,/language \+ Jev/);
 assert.doesNotMatch(w.document.body.textContent,/\[\[TERMS\]\]/);
 plan.phase='economic_synthesize';plan.economic_speech.wording_fallback='provider_error';
 w.whiterunRender({residents:[],director:{running:true},society:{people:{},town:{residents:{}},plan}});
 assert.match(w.document.getElementById('encounter-timing').textContent,/Original terms fallback/);
 }finally{dom.window.close();}
});
