const test=require('node:test'),assert=require('node:assert/strict');
const {createPapyrusRouterController,observeNativeActivity,nativeActivityBlocker}=require('../bridge/papyrus-router.js');
function fixture(){
 let clock=0,x=2000,running=false,current=42,loaded=true,releasePackage=true,scene=0,combat=false,sleep=0;
 const actor={getFormID:()=>843123,is3DLoaded:()=>loaded,isDead:()=>false,isChild:()=>false,
  getPositionX:()=>x,getPositionY:()=>0,getPositionZ:()=>0,getCurrentPackage:()=>({getFormID:()=>current}),evaluatePackage:()=>{},
  getCurrentScene:()=>scene?{getFormID:()=>scene}:null,isInCombat:()=>combat,getSleepState:()=>sleep};
 const target={...actor,getFormID:()=>108149,getPositionX:()=>0};
 const list=()=>{let items=[];return {revert:()=>items=[],addForm:f=>items.push(f),getSize:()=>items.length,getAt:i=>items[i]};};
 const global=()=>{let v=0;return {getValue:()=>v,setValue:n=>v=n};};
 const quest={isRunning:()=>running,start:()=>{running=true;return true;},stop:()=>{running=false;if(releasePackage)current=42;}};
 const forms=[quest,{getFormID:()=>99},list(),list(),global(),global(),global()];
 const sp={Game:{getFormFromFile:id=>forms[id-0x800],getFormEx:id=>id===843123?actor:target},
  Quest:{from:f=>f},Actor:{from:f=>f},FormList:{from:f=>f},GlobalVariable:{from:f=>f}};
 const controller=createPapyrusRouterController(()=>sp,()=>clock),command={id:'one',actor:843123,target:108149,dynamic:true};
 return {controller,command,forms,quest,sp,actor,scene:n=>scene=n,combat:n=>combat=n,sleep:n=>sleep=n,step:()=>controller.step(command),move:n=>x=n,time:n=>clock=n,
  loaded:v=>loaded=v,package:n=>current=n,retainPackage:v=>releasePackage=!v,
  bind:()=>{forms[5].setValue(forms[4].getValue());forms[6].setValue(1);},
  start(){for(let i=0;i<3;i++)this.step();},travel(){this.start();this.bind();this.step();current=99;this.step();}};
}
test('unacknowledged proximity and package cannot fabricate alias confirmation',()=>{
 const f=fixture();f.start();f.move(100);f.package(99);
 assert.equal(f.step().done,false);assert.equal(f.controller.status().aliasesConfirmed,false);
 f.bind();f.step();f.step();assert.equal(f.step().ack.status,'applied');
});
test('an unrelated stale acknowledgement cannot satisfy a new request',()=>{
 const f=fixture();f.forms[5].setValue(9);f.start();f.forms[6].setValue(1);
 assert.equal(f.forms[4].getValue(),10);assert.equal(f.step().done,false);
 f.time(15001);assert.match(f.step().ack.error,/timed out/);assert.equal(f.quest.isRunning(),false);
});
test('a rejected Papyrus binding releases the quest',()=>{
 const f=fixture();f.start();f.bind();f.forms[6].setValue(-1);
 assert.match(f.step().ack.error,/rejected/);assert.equal(f.quest.isRunning(),false);
});
test('mailbox tampering during travel holds the task even with the correct package',()=>{
 const f=fixture();f.travel();f.forms[3].revert();f.step();
 const result=f.step();assert.equal(result.ack.status,'held');assert.match(result.ack.error,/mailbox/);
});
test('release waits until the engine package actually leaves the resident',()=>{
 const f=fixture();f.travel();f.move(100);f.retainPackage(true);f.step();
 assert.equal(f.step().done,false);f.package(42);assert.equal(f.step().ack.status,'applied');
});
test('unloaded residents and interrupted packages stop the router',()=>{
 const f=fixture();f.travel();f.loaded(false);assert.equal(f.step().ack.status,'held');assert.equal(f.quest.isRunning(),false);
 const g=fixture();g.travel();g.package(42);g.step();assert.match(g.step().ack.error,/interrupted/);
});
test('router serial overflow and a missing plugin cannot start tasks',()=>{
 const f=fixture();f.forms[4].setValue(16777215);f.step();assert.match(f.step().ack.error,/exhausted/);
 const g=fixture();g.forms[0]=null;assert.match(g.step().ack.error,/unavailable/);
});
test('reset and recovery release a retained task without a new request',()=>{
 const f=fixture();f.travel();f.command.retain=true;f.move(100);assert.equal(f.step().ack.status,'applied');
 assert.equal(f.quest.isRunning(),true);f.controller.reset();f.controller.release();assert.equal(f.quest.isRunning(),false);
});
test('published movement status follows an observed release',()=>{
 const f=fixture();f.travel();f.controller.release();f.controller.observeRelease(false);
 assert.equal(f.controller.status().phase,'released');assert.equal(f.controller.status().ownedPackage,false);
});

test('native activity distinguishes a scene, combat, sleeping and unavailable sensing',()=>{
 const f=fixture();assert.equal(nativeActivityBlocker(observeNativeActivity(f.actor)),null);
 f.scene(888);assert.equal(nativeActivityBlocker(observeNativeActivity(f.actor)),'native_scene');
 f.scene(0);f.combat(true);assert.equal(nativeActivityBlocker(observeNativeActivity(f.actor)),'combat');
 f.combat(false);f.sleep(3);assert.equal(nativeActivityBlocker(observeNativeActivity(f.actor)),'sleep_transition');
 delete f.actor.getCurrentScene;assert.equal(nativeActivityBlocker(observeNativeActivity(f.actor)),'activity_unknown');
 f.actor.getCurrentScene=()=>{throw Error('native handle expired');};assert.equal(observeNativeActivity(f.actor).scene_id,null);
});

test('scene entering after a lease starts releases our route without stopping the scene',()=>{
 const f=fixture();f.travel();f.scene(888);
 assert.equal(f.step().done,false);assert.equal(f.quest.isRunning(),false);
 const result=f.step();assert.equal(result.ack.status,'held');
 assert.equal(result.ack.movement.failureReason,'native_scene');
 assert.equal(result.ack.movement.activity.scene_id,888);
 assert.equal(f.actor.getCurrentScene().getFormID(),888);
});

test('unacquired packages release after fifteen seconds, with the engine package retained as evidence',()=>{
 const f=fixture();f.start();f.bind();f.step();
 f.time(15000);assert.equal(f.step().done,false);assert.equal(f.quest.isRunning(),true);
 f.time(15001);assert.equal(f.step().done,false);assert.equal(f.quest.isRunning(),false);
 const result=f.step();assert.equal(result.ack.status,'held');
 assert.equal(result.ack.movement.failureReason,'package_not_acquired');
 assert.equal(result.ack.movement.enginePackage,42);assert.equal(result.ack.movement.hasOwnedPackage,false);
});

test('acquired walking can continue beyond fifteen seconds',()=>{
 const f=fixture();f.travel();f.time(16000);assert.equal(f.step().done,false);
 assert.equal(f.controller.status().phase,'travelling');assert.equal(f.quest.isRunning(),true);
});
