const test=require('node:test'),assert=require('node:assert/strict');
const {createConversationAttendance}=require('../bridge/conversation-attendance.js');
function fixture(){
 let clock=0;const owned=[false,false],running=[false,false],loaded=[true,true],ready=[true,true],failed=[false,false];
 const actors=[7,8].map((id,slot)=>({is3DLoaded:()=>loaded[slot],getCurrentPackage:()=>({getFormID:()=>owned[slot]?100+slot:42})}));
 const sp={Actor:{from:a=>a},Quest:{from:q=>q},Game:{getFormEx:id=>actors[id-7],getFormFromFile:id=>{
  const slot=Math.floor((id-0x800)/16)-6;assert.ok(slot===0||slot===1);return (id-0x800)%16===1?{getFormID:()=>100+slot}:{isRunning:()=>running[slot]};}}};
 const controller=createConversationAttendance(()=>sp,()=>clock,{routerFactory:(_sp,_now,opts)=>{
  const slot=opts.offset/16-6;assert.ok(slot===0||slot===1);return {reset(){},release(){running[slot]=false;owned[slot]=false;},step(){
   if(failed[slot])return {done:true,ack:{status:'held',error:'binding rejected'}};
   if(!ready[slot])return {done:false};running[slot]=true;owned[slot]=true;return {done:true,ack:{status:'applied'}};
  }};
 }});
 return {controller,owned,running,loaded,ready,failed,time:n=>clock=n,command:{id:'attend-test',participants:[7,8]}};
}
test('both independent native leases must arrive before speech attendance succeeds',()=>{
 const f=fixture();f.ready[1]=false;assert.equal(f.controller.meet(f.command).done,false);
 f.ready[1]=true;const result=f.controller.meet(f.command);assert.equal(result.ack.status,'applied');
 assert.deepEqual(result.ack.attendance.participants.map(x=>x.actor),[7,8]);
 assert.ok(result.ack.attendance.participants.every(x=>x.ownedPackage));
 f.owned[1]=false;assert.equal(f.controller.status().participants[1].ownedPackage,false);
});
test('one failed lease releases both and cannot fabricate a meeting',()=>{
 const f=fixture();f.failed[1]=true;assert.equal(f.controller.meet(f.command).ack.status,'held');
 assert.deepEqual(f.owned,[false,false]);assert.deepEqual(f.running,[false,false]);
});
test('encounter release verifies both participants and fails unknown release',()=>{
 for(const unavailable of [true,false]){
  const f=fixture();f.controller.meet(f.command);const release={id:'release-test',participants:[7,8]};
  assert.equal(f.controller.finish(release).done,false);if(unavailable)f.loaded[1]=false;
  f.time(10001);assert.equal(f.controller.finish(release).ack.released,!unavailable);
 }
});
test('participant substitutions and overlapping encounters are rejected',()=>{
 const f=fixture();f.controller.meet(f.command);
 assert.throws(()=>f.controller.meet({...f.command,participants:[8,7]}),/changed/);
 assert.throws(()=>f.controller.meet({...f.command,id:'other'}),/Another/);
 assert.equal(f.controller.meet({...f.command,participants:[7,7]}).ack.status,'held');
});
