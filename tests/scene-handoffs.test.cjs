const test=require('node:test'),assert=require('node:assert/strict');
const {createSceneHandoffController}=require('../bridge/scene-handoffs.js');
function fixture(){
 let time=0,sceneId=888,calls=0,throws=false,combat=false;
 const scene={getFormID:()=>sceneId,getOwningQuest:()=>({getFormID:()=>77}),stop:()=>{calls++;if(throws)throw Error('native error');}};
 const actor={is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,getCurrentScene:()=>sceneId?scene:null,
  isInCombat:()=>combat,getSleepState:()=>0,getCurrentPackage:()=>null,evaluatePackage:()=>{}};
 const controller=createSceneHandoffController(()=>({Actor:{from:a=>a},Game:{getFormEx:()=>actor}}),()=>time);
 const command={id:'a',actor:99,scene_id:888};
 return {controller,command,actor,step:()=>controller.step(command),calls:()=>calls,
  scene:n=>sceneId=n,time:n=>time=n,throws:()=>throws=true,combat:()=>combat=true};
}
test('stop is issued once; stable release must be observed separately',()=>{
 const f=fixture();assert.equal(f.step().done,false);f.step();assert.equal(f.calls(),1);
 f.scene(0);assert.equal(f.step().done,false);f.time(251);
 const ack=f.step().ack;assert.equal(ack.status,'applied');assert.equal(ack.owning_quest,77);
 assert.equal(ack.release_observed,true);assert.deepEqual(f.step().ack,ack);assert.equal(f.calls(),1);
});
test('a changed scene is never stopped using stale authorization',()=>{
 const f=fixture();f.scene(999);assert.equal(f.step().ack.reason,'scene_changed');assert.equal(f.calls(),0);
});
test('scene restarting during release is held without another stop',()=>{
 const f=fixture();f.step();f.scene(0);f.step();f.scene(888);
 assert.equal(f.step().ack.reason,'scene_restarted');assert.equal(f.calls(),1);
});
test('native exception and timeout cannot retry scene.stop',()=>{
 const f=fixture();f.throws();assert.equal(f.step().ack.reason,'scene_stop_failed');f.step();assert.equal(f.calls(),1);
 const g=fixture();g.step();g.time(15001);assert.equal(g.step().ack.reason,'scene_release_timeout');g.step();assert.equal(g.calls(),1);
});
test('natural end before dispatch is recorded without a stop call',()=>{
 const f=fixture();f.scene(0);f.step();f.time(251);const ack=f.step().ack;
 assert.equal(ack.status,'applied');assert.equal(ack.stop_called,false);assert.equal(f.calls(),0);
});
test('unknown activity and combat cannot stop a scene',()=>{
 const f=fixture();delete f.actor.getCurrentScene;assert.equal(f.step().ack.reason,'activity_changed');assert.equal(f.calls(),0);
 const g=fixture();g.combat();assert.equal(g.step().ack.reason,'activity_changed');assert.equal(g.calls(),0);
});
