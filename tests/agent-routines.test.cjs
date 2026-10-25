const test=require('node:test'),assert=require('node:assert/strict');
const {createAgentRoutineController}=require('../bridge/agent-routines.js');
function fixture(actorId=108186,targetId=108149){
 let clock=0,x=3000,current=42,loaded=true,releasePackage=true,routerPresent=true,starts=0;
 const actor={getFormID:()=>actorId,is3DLoaded:()=>loaded,isDead:()=>false,isChild:()=>false,
  getPositionX:()=>x,getPositionY:()=>0,getPositionZ:()=>0,getCurrentPackage:()=>({getFormID:()=>current}),evaluatePackage:()=>{},
  getCurrentScene:()=>null,isInCombat:()=>false,getSleepState:()=>0};
 const target={...actor,getFormID:()=>targetId,getPositionX:()=>0};
 function quest(packageId){let running=false;return {isRunning:()=>running,start:()=>{starts++;running=true;return true;},
  stop:()=>{running=false;if(releasePackage&&current===packageId)current=42;}};}
 const list=()=>{let items=[];return {revert:()=>items=[],addForm:f=>items.push(f),getSize:()=>items.length,getAt:i=>items[i]};};
 const global=()=>{let value=0;return {getValue:()=>value,setValue:v=>value=v};};
 const routerQuest=quest(99),legacy=Array.from({length:6},(_,i)=>quest(200+i));
 const forms=[routerQuest,{getFormID:()=>99},list(),list(),global(),global(),global()];
 const sp={Game:{getFormFromFile:(id,file)=>file==='WhiterunRouter.esp'?(routerPresent?forms[id-0x800]:null):
  file==='WhiterunAgents.esp'?(id%2===0?legacy[(id-0x800)/2]:{getFormID:()=>200+(id-0x801)/2}):null,
  getFormEx:id=>id===actorId?actor:id===targetId?target:null},
  Actor:{from:f=>f},Quest:{from:f=>f},FormList:{from:f=>f},GlobalVariable:{from:f=>f}};
 const controller=createAgentRoutineController(()=>sp,()=>clock),command={id:'one',actor:actorId,target:targetId,dynamic:true};
 const f={controller,command,quest:routerQuest,legacy,forms,sp,actor,target,step:()=>controller.step(command),
  move:v=>x=v,time:v=>clock=v,package:v=>current=v,loaded:v=>loaded=v,missingRouter:()=>routerPresent=false,
  running:()=>routerQuest.isRunning(),starts:()=>starts,retainPackage:v=>releasePackage=!v,
  bind:()=>{forms[5].setValue(forms[4].getValue());forms[6].setValue(1);},
  start(){for(let i=0;i<3;i++)this.step();},travel(){this.start();this.bind();this.step();current=99;this.step();}};
 return f;
}

test('original and newly discovered pairs use the same confirmed mailbox',()=>{
 for(const pair of [[108186,108149],[800001,800002]]){
  const f=fixture(...pair);f.travel();f.move(100);f.step();const result=f.step();
  assert.equal(result.ack.status,'applied');assert.equal(result.ack.movement.adapter,'papyrus-mailbox');
  assert.equal(result.ack.movement.aliasesConfirmed,true);assert.equal(result.ack.movement.hasOwnedPackage,true);
  assert.equal(f.legacy.some(q=>q.isRunning()),false);
 }
});
test('proximity and package without alias acknowledgement cannot complete travel',()=>{
 const f=fixture();f.start();f.move(100);f.package(99);assert.equal(f.step().done,false);
 assert.equal(f.controller.status().aliasesConfirmed,false);f.bind();f.step();f.step();assert.equal(f.step().ack.status,'applied');
});
test('original and newly discovered pairs fail equally with a missing executor',()=>{
 for(const pair of [[108186,108149],[800001,800002]]){
  const f=fixture(...pair);f.missingRouter();assert.equal(f.controller.capabilities().available,false);
  assert.equal(f.step().ack.status,'held');assert.equal(f.starts(),0);
 }
});
test('legacy false and missing route flags never start or reinterpret old quests',()=>{
 for(const dynamic of [false,undefined]){
  const f=fixture();f.command.dynamic=dynamic;const result=f.step();
  assert.equal(result.ack.status,'held');assert.equal(result.ack.release_required,true);
  assert.equal(result.ack.released,false);assert.equal(f.starts(),0);assert.equal(f.controller.status(),null);
 }
});
test('already-owned legacy route cannot claim arrival and cleanup waits for actual release',()=>{
 const f=fixture();f.command.dynamic=false;f.legacy[0].start();f.package(200);f.move(100);f.retainPackage(true);
 assert.equal(f.step().ack.status,'held');assert.equal(f.starts(),1);
 const release={id:'release-legacy',actor:f.command.actor};assert.equal(f.controller.finish(release).done,false);
 assert.equal(f.legacy[0].isRunning(),false);assert.equal(f.controller.finish(release).done,false);
 f.package(42);assert.equal(f.controller.finish(release).ack.released,true);assert.equal(f.starts(),1);
});
test('load or hot reload cleanup releases every legacy slot without restarting it',()=>{
 const f=fixture();for(const quest of f.legacy)quest.start();f.controller.reset();f.controller.release();
 assert.equal(f.legacy.some(q=>q.isRunning()),false);assert.equal(f.starts(),6);
});
test('unloaded residents and interrupted packages stop a mailbox trip',()=>{
 const f=fixture();f.travel();f.loaded(false);assert.equal(f.step().ack.status,'held');assert.equal(f.running(),false);
 const g=fixture();g.travel();g.package(42);g.move(100);g.step();assert.match(g.step().ack.error,/interrupted/);
});
test('a stalled owned mailbox package expires without fabricating arrival',()=>{
 const f=fixture();f.travel();f.time(120001);f.step();const result=f.step();
 assert.equal(result.ack.status,'held');assert.equal(f.running(),false);assert.equal(result.ack.movement.distance,3000);
});
test('retained mailbox travel remains owned until explicit verified cleanup',()=>{
 const f=fixture();f.command.retain=true;f.travel();f.move(200);const result=f.step();
 assert.equal(result.ack.status,'applied');assert.equal(f.running(),true);assert.equal(result.ack.movement.phase,'arrived');
 const release={id:'release-one',actor:f.command.actor};assert.equal(f.controller.finish(release).done,false);
 assert.equal(f.controller.finish(release).ack.released,true);assert.equal(f.controller.status().phase,'released');
});
test('release cannot be confirmed from an unloaded resident or a retained legacy package',()=>{
 const f=fixture();const release={id:'release-unloaded',actor:f.command.actor};f.controller.finish(release);f.loaded(false);
 assert.equal(f.controller.finish(release).ack.released,false);
 const g=fixture();g.legacy[3].start();g.package(203);g.retainPackage(true);g.controller.finish(release);g.time(10001);
 assert.equal(g.controller.finish(release).ack.status,'held');assert.equal(g.controller.finish(release).ack.released,false);
});
