const test=require('node:test'),assert=require('node:assert/strict');
const {createSpeechController}=require('../bridge/speech.js');
test('finished social scene cannot hide an active economic speech caption',()=>{
 const vm=require('node:vm'),fs=require('node:fs'),nodes=new Map();
 const node=()=>({hidden:false,textContent:'',style:{},children:[],replaceChildren(){this.children=[];},append(x){this.children.push(x);}});
 const document={getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},createElement:node};
 const context={window:{},document,names:{7:'Buyer'},state:{society:{conversation:{phase:'complete'},plan:{voiced_trade:true,phase:'economic_speaking',economic_speech:{actor:7},economic_turns:[]}}},text:(id,t)=>{document.getElementById(id).textContent=t;}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../ui/speech.js'),'utf8'),context);
 context.window.drawConversation();assert.equal(document.getElementById('speech-caption').hidden,false);
 assert.match(document.getElementById('notice').textContent,/not yet a completed sale/);
 context.state.society.plan.phase='trading';context.window.drawConversation();assert.equal(document.getElementById('speech-caption').hidden,true);
 context.state.society.plan.purchase_completed=true;context.window.drawConversation();assert.match(document.getElementById('notice').textContent,/verified/);
});
function harness(){let clock=10000,range=100;const scripts=[],looks=[];
 const actor=id=>({is3DLoaded:()=>true,isDead:()=>false,getPositionX:()=>id===1?0:range,getPositionY:()=>0,getPositionZ:()=>0,setLookAt:()=>looks.push(id),clearLookAt:()=>{}});
 const sp={Actor:{from:a=>a},Game:{getFormEx:actor},browser:{executeJavaScript:s=>scripts.push(s)}};
 const speech=createSpeechController(()=>sp,()=>clock),c={id:'speech-'+'a'.repeat(24),actor:1,target:2,line:'Hello there',tone:'calm',audio:{file:'b'.repeat(64)+'.wav',sha256:'b'.repeat(64),seconds:3}};
 return {speech,c,scripts,looks,time:v=>clock+=v,range:v=>range=v};}
test('play once, look at listener, confirm completion only after duration',()=>{const h=harness();h.speech.start(h.c);h.speech.start(h.c);assert.equal(h.scripts.length,1);assert.equal(h.looks.length,2);
 h.speech.message({id:h.c.id,status:'playing'});h.speech.tick();h.time(3100);h.speech.message({id:h.c.id,status:'ended',playedSeconds:3,volume:1,muted:false});h.speech.tick();assert.equal(h.speech.status().status,'ended');h.speech.start(h.c);assert.equal(h.scripts.length,2);});
test('listener departure fails instead of adding a false witness',()=>{const h=harness();h.speech.start(h.c);h.range(700);h.speech.tick();assert.equal(h.speech.status().status,'failed');assert.equal(h.speech.status().nearbyThroughout,false);});
test('early completion and muted playback are rejected',()=>{for(const muted of [true,false]){const h=harness();h.speech.start(h.c);if(muted)h.time(3100);h.speech.message({id:h.c.id,status:'ended',playedSeconds:3,volume:1,muted});h.speech.tick();assert.equal(h.speech.status().status,'failed');}});
test('timeout and load reset stop playback',()=>{const h=harness();h.speech.start(h.c);h.time(20000);h.speech.tick();assert.equal(h.speech.status().status,'failed');h.speech.reset();assert.equal(h.speech.status(),null);});
test('unknown report ID cannot settle current speech',()=>{const h=harness();h.speech.start(h.c);h.time(3100);h.speech.message({id:'wrong',status:'ended',playedSeconds:3,volume:1});assert.equal(h.speech.status().status,'starting');});
test('targeted interruption clears active voice and ignores late completion',()=>{const h=harness();h.speech.start(h.c);assert.equal(h.speech.interrupt('wrong'),false);assert.equal(h.speech.interrupt(h.c.id),true);assert.equal(h.speech.actor(),null);assert.equal(h.speech.status().status,'interrupted');h.time(4000);h.speech.message({id:h.c.id,status:'ended',playedSeconds:3,volume:1,muted:false});h.speech.tick();assert.equal(h.speech.status().status,'interrupted');assert.equal(h.speech.interrupt(h.c.id),true);});
test('browser acknowledgements wait for a game update before native cleanup',()=>{const h=harness();h.speech.start(h.c);h.time(3100);h.speech.message({id:h.c.id,status:'ended',playedSeconds:3,volume:1,muted:false});assert.equal(h.scripts.length,1);assert.equal(h.speech.status().status,'starting');h.speech.tick();assert.equal(h.scripts.length,2);h.time(25000);h.speech.tick();assert.equal(h.speech.status().status,'ended');});
test('body turns are requested only for standing actors; head looks include both',()=>{
 const turns=[],looks=[],actors={1:{getSitState:()=>0,getPositionX:()=>0,getPositionY:()=>0},2:{getSitState:()=>3,getPositionX:()=>100,getPositionY:()=>0}};
 for(const [id,a] of Object.entries(actors))Object.assign(a,{is3DLoaded:()=>true,isDead:()=>false,getPositionZ:()=>0,setLookAt:()=>looks.push(id),setAngle:(x,y,z)=>turns.push({id,z})});
 const sp={Game:{getFormEx:id=>actors[id]},Actor:{from:a=>a},browser:{executeJavaScript:()=>{}}};
 const h=harness(),speech=createSpeechController(()=>sp);speech.start(h.c);assert.deepEqual(turns,[{id:'1',z:90}]);assert.equal(looks.length,2);
 assert.deepEqual(speech.status().facing.map(x=>x.bodyTurnRequested),[true,false]);
});
test('body yaw is measured separately from an unmeasured head or eye request',()=>{
 const actors={1:{getPositionX:()=>0,getAngleZ:()=>180},2:{getPositionX:()=>100,getAngleZ:()=>270}};
 for(const a of Object.values(actors))Object.assign(a,{is3DLoaded:()=>true,isDead:()=>false,getPositionY:()=>0,getPositionZ:()=>0,setLookAt(){}});
 const sp={Game:{getFormEx:id=>actors[id]},Actor:{from:a=>a},browser:{executeJavaScript(){}}};
 const speech=createSpeechController(()=>sp),h=harness();speech.start(h.c);speech.tick();
 assert.deepEqual(speech.status().orientation,{samples:2,sum_error_degrees:90,max_error_degrees:90,measurement:'body yaw towards partner, not head/eye gaze or raycast'});
 assert.equal(speech.status().eyeAccuracy,undefined);
});

