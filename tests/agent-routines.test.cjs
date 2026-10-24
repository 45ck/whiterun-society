const test=require('node:test'),assert=require('node:assert/strict');
const {createAgentRoutineController}=require('../bridge/agent-routines.js');
function fixture(){
 let clock=0,x=3000,running=false,current=42,loaded=true,releasePackage=true;
 const pkg={getFormID:()=>99};
 const actor={getPositionX:()=>x,getPositionY:()=>0,getPositionZ:()=>0,
  is3DLoaded:()=>loaded,getCurrentPackage:()=>({getFormID:()=>current}),evaluatePackage:()=>{}};
 const target={...actor,getPositionX:()=>0};
 const quest={isRunning:()=>running,start:()=>{running=true;return true;},stop:()=>{running=false;if(releasePackage)current=42;}};
 const sp={Game:{getFormFromFile:id=>id===0x800?quest:id%2===1?pkg:null,getFormEx:id=>id===108186?actor:target},
  Actor:{from:x=>x},Quest:{from:x=>x},ReferenceAlias:{from:x=>x}};
 const controller=createAgentRoutineController(()=>sp,()=>clock),command={id:'one',actor:108186,target:108149};
 return {controller,command,quest,sp,actor,target,step:()=>controller.step(command),
  move:v=>x=v,time:v=>clock=v,package:v=>current=v,loaded:v=>loaded=v,
  running:()=>running,retainPackage:v=>releasePackage=!v};
}
test('proximity alone cannot pass an agent-owned routine',()=>{
 const f=fixture();for(let i=0;i<4;i++)f.step();
 f.move(100);assert.equal(f.step().done,false);
 f.package(99);assert.equal(f.step().done,false);assert.equal(f.running(),false);
 const result=f.step();assert.equal(result.ack.status,'applied');assert.equal(result.ack.movement.hasOwnedPackage,true);
});
test('an unsupported resident route is rejected before starting a quest',()=>{
 const f=fixture();f.command.target=7;const result=f.step();
 assert.equal(result.ack.status,'held');assert.equal(f.running(),false);
});
test('an unloaded resident cannot leave its override quest running',()=>{
 const f=fixture();for(let i=0;i<4;i++)f.step();assert.equal(f.running(),true);
 f.loaded(false);assert.equal(f.step().ack.status,'held');assert.equal(f.running(),false);
});
test('a stalled owned package expires without fabricating arrival',()=>{
 const f=fixture();for(let i=0;i<4;i++)f.step();f.package(99);f.time(120001);
 f.step();const result=f.step();assert.equal(result.ack.status,'held');assert.equal(f.running(),false);
 assert.equal(result.ack.movement.distance,3000);
});
test('an interruption after taking ownership requires replanning',()=>{
 const f=fixture();for(let i=0;i<4;i++)f.step();f.package(99);f.step();
 f.package(42);f.move(100);f.step();const result=f.step();
 assert.equal(result.ack.status,'held');assert.match(result.ack.error,/interrupted/);
});
test('load or hot reload cleanup releases the prototype task',()=>{
 const f=fixture();for(let i=0;i<4;i++)f.step();
 f.controller.reset();f.controller.release();assert.equal(f.running(),false);
});
test('a resident plan retains its travel package while consent is pending',()=>{
 const f=fixture();f.command.retain=true;f.command.origin='resident_decision';
 for(let i=0;i<4;i++)f.step();f.package(99);f.move(200);
 const result=f.step();assert.equal(result.ack.status,'applied');assert.equal(f.running(),true);
 assert.equal(result.ack.movement.phase,'arrived');
 const release={id:'release-one',actor:108186};
 assert.equal(f.controller.finish(release).done,false);assert.equal(f.running(),false);
 f.package(42);assert.equal(f.controller.finish(release).ack.released,true);
});

test('release cannot be confirmed from an unloaded resident',()=>{
 const f=fixture();const release={id:'release-unloaded',actor:108186};
 f.controller.finish(release);f.loaded(false);
 const result=f.controller.finish(release);
 assert.equal(result.ack.status,'held');assert.equal(result.ack.released,false);
});

function dynamicFixture(){
 const f=fixture();f.command.actor=108196;f.command.target=108149;f.command.dynamic=true;
 f.actor.getFormID=()=>108196;f.target.getFormID=()=>108149;
 f.sp.Game.getFormEx=id=>id===108196?f.actor:f.target;
 const assignments=[null,null],requests=[];
 f.quest.getAlias=id=>({forceRefTo:ref=>requests.push({id,ref}),getReference:()=>assignments[id]});
 return {...f,requests,bind:()=>requests.forEach(r=>assignments[r.id]=r.ref),drift:()=>assignments[1]=f.actor};
}
test('dynamic travel waits for both assignments and does not repeat native forcing',()=>{
 const f=dynamicFixture();for(let i=0;i<6;i++)f.step();
 assert.equal(f.controller.status().phase,'binding');assert.equal(f.requests.length,2);
 f.move(100);f.package(99);assert.equal(f.step().done,false);
 f.bind();f.step();assert.equal(f.controller.status().aliasesConfirmed,true);
 f.step();const done=f.step();assert.equal(done.ack.status,'applied');assert.equal(done.ack.movement.actor,108196);
 assert.equal(f.requests.length,2);
});
test('dynamic binding timeout stops the owned quest without claiming movement',()=>{
 const f=dynamicFixture();for(let i=0;i<4;i++)f.step();f.time(10001);
 const result=f.step();assert.equal(result.ack.status,'held');assert.equal(f.running(),false);
 assert.match(result.ack.error,/assignment/);
});
test('alias drift interrupts dynamic travel even if the package ID still matches',()=>{
 const f=dynamicFixture();for(let i=0;i<4;i++)f.step();f.bind();f.step();f.package(99);f.drift();
 assert.equal(f.step().ack.status,'held');assert.equal(f.running(),false);
});
test('movement completion waits until the package actually leaves the actor',()=>{
 const f=fixture();for(let i=0;i<4;i++)f.step();f.package(99);f.move(100);f.retainPackage(true);
 f.step();assert.equal(f.running(),false);assert.equal(f.step().done,false);
 f.package(42);assert.equal(f.step().ack.status,'applied');
});
test('disappearing aliases stop dynamic travel instead of leaking its package',()=>{
 const f=dynamicFixture();for(let i=0;i<4;i++)f.step();f.bind();f.step();
 f.quest.getAlias=()=>null;const result=f.step();
 assert.equal(result.ack.status,'held');assert.equal(f.running(),false);
});
