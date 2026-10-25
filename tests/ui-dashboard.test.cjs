const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom'),vm=require('node:vm');
const read=name=>fs.readFileSync(path.join(__dirname,'../ui',name),'utf8');
const dashboard=()=>({control:{agent:1,scene:2,native:3,unknown:1,unloaded:2},stock:Object.fromEntries(['gold','bread','grain'].map(k=>[k,{total:k==='gold'?7:null,accounts:k==='gold'?2:0,population:9}])),needs:Object.fromEntries(['hunger','fatigue','social_contact'].map(k=>[k,{high:1,known:4}])),economy:{committed_sales:2},control_scope:'Observed packages',needs_scope:'Gameplay needs',economy_scope:'Verified events'});
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
test('native RTS UI sends Play/Pause and follows movie activity only when requested',()=>{
 const {dom,w,messages,intervals}=native();try{
 assert.equal(w.whiterunRtsActive(),true);assert.equal(w.document.getElementById('tour'),null);
 w.whiterunRender({residents:[],trades:[],society:{people:{},town:{residents:{}}},director:{running:false,status:'idle'},dashboard:dashboard(),camera:{manual:true,mode:'free'}});
 assert.equal(w.document.getElementById('live-badge').textContent,'PAUSED');assert.match(w.document.getElementById('notice').textContent,/Simulation paused/);
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
