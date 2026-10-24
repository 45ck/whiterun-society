const test=require('node:test'),assert=require('node:assert/strict');
const {createMovementController}=require('../bridge/movement.js');
function fixture(){
 let position=1000,calls=0,releases=0,clock=0;
 const actor={getPositionX:()=>position,getPositionY:()=>0,getPositionZ:()=>0,is3DLoaded:()=>true,isDead:()=>false,
  pathToReference:()=>{calls++;return new Promise(()=>{});},evaluatePackage:()=>{releases++;}};
 const target={...actor,getPositionX:()=>0};
 const controller=createMovementController(()=>({Actor:{from:x=>x},Game:{getFormEx:id=>id===1?actor:target}}),()=>clock);
 return {controller,command:{id:'route',actor:1,target:2},move:x=>position=x,time:x=>clock=x,calls:()=>calls,releases:()=>releases};
}
test('a route requests native pathfinding once and verifies observed arrival',()=>{
 const f=fixture();assert.equal(f.controller.step(f.command).done,false);
 f.move(700);f.controller.step(f.command);assert.equal(f.calls(),1);
 f.move(200);const result=f.controller.step(f.command);assert.equal(result.ack.status,'applied');
 assert.equal(result.ack.movement.startDistance,1000);assert.equal(result.ack.movement.distance,200);
});
test('a stalled route is held without reporting arrival or endlessly retrying',()=>{
 const f=fixture();f.controller.step(f.command);f.time(46000);
 assert.equal(f.controller.step(f.command).ack.status,'held');assert.equal(f.calls(),1);assert.equal(f.releases(),1);
});
test('already being close is distinguished from walking',()=>{
 const f=fixture();f.move(100);const result=f.controller.step(f.command);
 assert.match(result.ack.error,/Already/);assert.equal(f.calls(),0);
});
test('the approach controller is explicitly cleared after reaching range',()=>{
 let x=600,started=0,cleared=0;
 const actor={getPositionX:()=>x,getPositionY:()=>0,getPositionZ:()=>0,is3DLoaded:()=>true,isDead:()=>false,
  keepOffsetFromActor:()=>started++,clearKeepOffsetFromActor:()=>cleared++};
 const target={...actor,getPositionX:()=>0};
 const controller=createMovementController(()=>({Actor:{from:x=>x},Game:{getFormEx:id=>id===1?actor:target}}));
 const command={id:'approach',actor:1,target:2,method:'offset'};
 assert.equal(controller.step(command).done,false);assert.equal(started,1);
 x=200;assert.equal(controller.step(command).ack.status,'applied');assert.equal(cleared,1);
});
