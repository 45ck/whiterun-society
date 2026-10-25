const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom'),vm=require('node:vm');
const read=name=>fs.readFileSync(path.join(__dirname,'../ui',name),'utf8');
const dashboard=()=>({control:{agent:1,scene:2,native:3,unknown:1,unloaded:2},stock:Object.fromEntries(['gold','bread','grain'].map(k=>[k,{total:k==='gold'?7:null,accounts:k==='gold'?2:0,population:9}])),needs:Object.fromEntries(['hunger','fatigue','social_contact'].map(k=>[k,{high:1,known:4}])),economy:{committed_sales:2},control_scope:'Observed packages',needs_scope:'Gameplay needs',economy_scope:'Verified events'});
function native(){
 const dom=new JSDOM(read('index.html'),{runScripts:'outside-only',url:'https://local.invalid/'}),w=dom.window,messages=[],intervals=[];
 w.setInterval=(fn,ms)=>{intervals.push({fn,ms});return intervals.length;};w.skyrimPlatform={sendMessage:m=>messages.push(m)};
 for(const script of w.document.scripts)vm.runInContext(script.src?read(path.basename(script.src)):script.textContent,dom.getInternalVMContext());
 return {dom,w,messages,intervals};
}
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
 Object.defineProperty(w.navigator,'mediaDevices',{value:{enumerateDevices:async()=>[{kind:'audiooutput',deviceId:'default',label:'System speakers'},{kind:'audiooutput',deviceId:'headset',label:'Headset'}],addEventListener(){}}});
 for(const script of w.document.scripts)vm.runInContext(script.src?read(path.basename(script.src)):script.textContent,dom.getInternalVMContext());
 return {dom,w,messages,audio};
};
test('voice output preference routes the next line without changing Windows or requesting a microphone',async()=>{
 const {dom,w,audio}=testVoice();try{await new Promise(r=>setImmediate(r));const select=w.document.getElementById('voice-output');select.value='headset';select.dispatchEvent(new w.Event('change'));
 w.whiterunSpeak({id:'test-line',actor:1,line:'Good evening',tone:'calm',audio:{file:'fixture.wav'}});await new Promise(r=>setImmediate(r));assert.equal(audio[0].sink,'headset');assert.equal(audio[0].played,true);assert.equal(w.localStorage.getItem('whiterun-voice-output'),'headset');
 }finally{dom.window.close();}
});
test('an unavailable selected voice output fails visibly instead of claiming playback',async()=>{
 const {dom,w,audio,messages}=testVoice({fail:true});try{await new Promise(r=>setImmediate(r));w.whiterunSpeak({id:'test-line',actor:1,line:'Hello',tone:'calm',audio:{file:'fixture.wav'}});await new Promise(r=>setImmediate(r));assert.equal(audio[0].played,undefined);assert.equal(messages.find(m=>m.type==='society-speech').status,'failed');
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
