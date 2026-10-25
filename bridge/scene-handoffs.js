// Stop only the exact observed scene, once. Never stop its owning quest.
function createSceneHandoffController(platform,now=Date.now){
 const observeActivity=typeof observeNativeActivity==='function'?observeNativeActivity:require('./papyrus-router.js').observeNativeActivity;
 let active=null;
 return {
  reset(){active=null;},
  step(command){
   if(active?.id===command.id&&active.done)return {done:true,ack:{...active.ack}};
   if(!active||active.id!==command.id)active={id:command.id,at:now(),stop_called:false};
   const finish=(status,reason,extra={})=>{
    active.done=true;active.ack={id:command.id,status,actor:command.actor,scene_id:command.scene_id,
     stop_called:active.stop_called,release_observed:status==='applied',reason,
     elapsed_ms:now()-active.at,owning_quest:active.owning_quest??null,...extra};
    return {done:true,ack:{...active.ack}};
   };
   const sp=platform(),actor=sp.Actor.from(sp.Game.getFormEx(command.actor));
   if(!actor||!actor.is3DLoaded()||actor.isDead()||actor.isChild())return finish('held','resident_unavailable');
   const activity=observeActivity(actor);
   if(activity.in_combat!==false||activity.sleep_state!==0||activity.scene_id===null)return finish('held','activity_changed');
   if(activity.scene_id===0){
    if(active.clearAt===undefined){active.clearAt=now();return {done:false};}
    if(now()-active.clearAt<250)return {done:false};
    actor.evaluatePackage();return finish('applied',active.stop_called?'scene_released':'scene_ended_before_stop');
   }
   if(active.clearAt!==undefined)return finish('held','scene_restarted',{observed_scene:activity.scene_id});
   if(activity.scene_id!==command.scene_id)return finish('held','scene_changed',{observed_scene:activity.scene_id});
   if(!active.stop_called){
    const scene=actor.getCurrentScene();
    if(!scene||scene.getFormID()!==command.scene_id||typeof scene.stop!=='function')return finish('held','scene_api_unavailable');
    try{active.owning_quest=scene.getOwningQuest?.()?.getFormID()??null;}catch(_){}
    active.stop_called=true; // Set before calling: an exception cannot cause a retry.
    try{scene.stop();}catch(_){return finish('held','scene_stop_failed');}
   }
   if(now()-active.at>15000)return finish('held','scene_release_timeout');
   return {done:false};
  }
 };
}
if(typeof module!=='undefined')module.exports={createSceneHandoffController};
