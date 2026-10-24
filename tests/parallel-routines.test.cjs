const test=require('node:test'),assert=require('node:assert/strict');
const {createParallelRoutineController}=require('../bridge/parallel-routines.js');
function fixture(){
 let clock=0;const rows=[{x:2000,pkg:42,loaded:true},{x:3000,pkg:42,loaded:true}];
 const space={getParentCell:()=>({isInterior:()=>false}),getWorldSpace:()=>({getFormID:()=>1}),isDisabled:()=>false};
 const actors=rows.map((row,i)=>({...space,getFormID:()=>99+i,is3DLoaded:()=>row.loaded,isDead:()=>false,isChild:()=>false,
  getPositionX:()=>row.x,getPositionY:()=>0,getPositionZ:()=>0,getCurrentPackage:()=>({getFormID:()=>row.pkg}),evaluatePackage:()=>{}}));
 const target={...space,getFormID:()=>0x2be1b,getPositionX:()=>0,getPositionY:()=>0,getPositionZ:()=>0};
 const list=()=>{let v=[];return {revert:()=>v=[],addForm:f=>v.push(f),getSize:()=>v.length,getAt:i=>v[i]};};
 const global=()=>{let v=0;return {getValue:()=>v,setValue:n=>v=n};};
 const slots=Array.from({length:8},(_,slot)=>{let running=false;const forms=[null,{getFormID:()=>1000+slot},list(),list(),global(),global(),global()];
  forms[0]={isRunning:()=>running,start:()=>{running=true;forms[5].setValue(forms[4].getValue());forms[6].setValue(1);rows[forms[2].getAt(0).getFormID()-99].pkg=1000+slot;return true;},
   stop:()=>{running=false;const actor=forms[2].getAt(0);if(actor)rows[actor.getFormID()-99].pkg=42;}};return forms;});
 const sp={Game:{getFormFromFile:id=>slots[Math.floor((id-0x800)/16)]?.[(id-0x800)%16],getFormEx:id=>id===0x2be1b?target:actors[id-99]},
  Actor:{from:x=>x},ObjectReference:{from:x=>x},Quest:{from:x=>x},FormList:{from:x=>x},GlobalVariable:{from:x=>x}};
 const c=createParallelRoutineController(()=>sp,()=>clock),command={id:'cohort',jobs:rows.map((_,slot)=>({id:'job'+slot,slot,actor:99+slot,target:0x2be1b,target_kind:'place',retain:false}))};
 return {c,rows,slots,command,step:()=>c.step(command),time:n=>clock=n,start(){for(let i=0;i<5;i++)this.step();}};
}
test('two distinct native leases overlap and releasing one does not release the other',()=>{
 const f=fixture();f.start();assert.equal(f.c.status().peak_owned,2);assert.ok(f.c.status().overlap_samples>0);
 f.rows[0].x=100;f.step();f.step();assert.equal(f.slots[0][0].isRunning(),false);assert.equal(f.slots[1][0].isRunning(),true);
 f.rows[1].x=100;f.step();const end=f.step();assert.equal(end.done,true);assert.equal(end.ack.status,'applied');
 assert.equal(end.ack.routines.length,2);assert.ok(end.ack.routines.every(r=>r.release_verified));
});
test('one missing resident cannot fabricate arrival or cancel the other lease',()=>{
 const f=fixture();f.start();f.rows[0].loaded=false;f.step();f.time(10001);f.step();
 assert.equal(f.slots[1][0].isRunning(),true);f.rows[1].x=100;f.step();const end=f.step();
 assert.equal(end.ack.status,'held');assert.equal(end.ack.routines[0].release_verified,false);assert.equal(end.ack.routines[1].status,'applied');
});
test('duplicate actor or slot is rejected before any quest starts',()=>{
 for(const field of ['actor','slot','id']){const f=fixture();f.command.jobs[1][field]=f.command.jobs[0][field];assert.equal(f.step().ack.status,'held');assert.ok(f.slots.every(s=>!s[0].isRunning()));}
});
test('load recovery releases every lane and clears receipts',()=>{
 const f=fixture();f.start();f.c.release();f.c.reset();assert.ok(f.slots.every(s=>!s[0].isRunning()));assert.deepEqual(f.c.status().activities,[]);
});
