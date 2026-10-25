// Eight independent Papyrus mailboxes. Native object handles never cross frames.
function createParallelRoutineController(platform,now=Date.now){
 const makeRouter=typeof createPapyrusRouterController==='function'?createPapyrusRouterController:require('./papyrus-router.js').createPapyrusRouterController;
 const makePlaces=typeof createPlaceObserver==='function'?createPlaceObserver:require('./places.js').createPlaceObserver;
 const places=makePlaces(platform),file='WhiterunLanes.esp';
 const lanes=Array.from({length:8},(_,slot)=>makeRouter(platform,now,{file,offset:slot*0x10,placeObserver:places}));
 let active=null;
 const formId=value=>Number.isInteger(value)&&value>0&&value<=0xffffffff;
 function identityMatches(job){
  try{
   const sp=platform(),actor=sp.Actor.from(sp.Game.getFormEx(job.actor));
   return formId(job.actor_base_id)&&!!actor&&
    (actor.getActorBase?.()||actor.getBaseObject?.())?.getFormID?.()===job.actor_base_id;
  }catch(_){return false;}
 }
 // Stop only a mailbox lease acquired by this controller, never a replacement
 // owner's slot. Stopping the quest alone is not proof of actor release.
 function releaseOwned(job){
  try{
   const state=lanes[job.slot].status();
   if(!state||state.id!==job.id||state.actor!==job.actor||state.target!==job.target||!Number.isInteger(state.serial))return;
   const sp=platform(),get=id=>sp.Game.getFormFromFile(id+job.slot*0x10,file);
   const resident=sp.FormList.from(get(0x802)),destination=sp.FormList.from(get(0x803)),request=sp.GlobalVariable.from(get(0x804));
   if(resident?.getSize()===1&&destination?.getSize()===1&&resident.getAt(0)?.getFormID()===job.actor&&
      destination.getAt(0)?.getFormID()===job.target&&request?.getValue()===state.serial)lanes[job.slot].release();
  }catch(_){}
 }
 function identityHold(job,movement){
  return {id:job.id,status:'held',actor_base_id:job.actor_base_id,error:'Resident identity changed or unavailable',
   movement:movement?{...movement,phase:'held'}:null};
 }
 function coldSlotClear(job){
  try{
   const sp=platform(),quest=sp.Quest.from(sp.Game.getFormFromFile(0x800+job.slot*0x10,file));
   const owned=sp.Game.getFormFromFile(0x801+job.slot*0x10,file),actor=sp.Actor.from(sp.Game.getFormEx(job.actor));
   return !!quest&&!!owned&&!quest.isRunning()&&!!actor&&actor.getCurrentPackage()?.getFormID()!==owned.getFormID();
  }catch(_){return false;}
 }
 function recheckReceipts(){
  if(!active)return;
  for(const job of active.jobs){
   const receipt=active.receipts[job.id];
   if(receipt?.status==='applied'&&!identityMatches(job)){
    active.receipts[job.id]={...receipt,...identityHold(job,receipt.movement),release_verified:false,seller_nearby:null};
    if(active.result)active.result={...active.result,status:'held',routines:active.jobs.map(j=>active.receipts[j.id])};
   }
  }
 }
 function released(job){
  if(!identityMatches(job))return false;
  const sp=platform(),actor=sp.Actor.from(sp.Game.getFormEx(job.actor)),quest=sp.Quest.from(sp.Game.getFormFromFile(0x800+job.slot*0x10,file));
  if(!actor?.is3DLoaded()||!quest||quest.isRunning())return false;
  const pkg=actor.getCurrentPackage(),owned=sp.Game.getFormFromFile(0x801+job.slot*0x10,file);
  return !!owned&&(!pkg||pkg.getFormID()!==owned.getFormID());
 }
 function sellerNearby(job){
  const sp=platform(),actor=sp.Actor.from(sp.Game.getFormEx(job.actor)),place=sp.ObjectReference.from(sp.Game.getFormEx(job.target));
  if(!actor?.is3DLoaded())return false;
  return (job.public_seller_ids||[]).some(id=>{
   const seller=sp.Actor.from(sp.Game.getFormEx(id));
   return id!==job.actor&&seller?.is3DLoaded()&&places.validTarget(seller,place)&&
    Math.hypot(actor.getPositionX()-seller.getPositionX(),actor.getPositionY()-seller.getPositionY(),actor.getPositionZ()-seller.getPositionZ())<=300;
  });
 }
 return {
  available(){return lanes.every(lane=>lane.available());},
  release(){for(const lane of lanes)if(lane.available())lane.release();},
  reset(){active=null;for(const lane of lanes)lane.reset();},
  ownsActor(actor){return !!active&&active.jobs.some(j=>j.actor===actor&&active.receipts[j.id]?.release_verified!==true);},
  startBackground(command){
   if(!Array.isArray(command.jobs)||command.jobs.length>6||command.jobs.some(j=>!j||j.slot>=6))
    return {done:true,ack:{id:command.id,status:'held',error:'Background travel reserves slots zero through five',routines:[]}};
   const result=this.step(command);
   if(result.done)return result;
   active.background=true;active.command=JSON.parse(JSON.stringify(command));
   return {done:true,ack:{id:command.id,status:'started'}};
  },
  tickBackground(){if(active?.background&&!active.done)this.step(active.command);},
  sampleSocialOverlap(attendance,playing){
   if(!active?.background||active.done||attendance?.phase!=='attending'||!attendance.participants?.every(p=>p.ownedPackage===true))return;
   const actors=attendance.participants.map(p=>p.actor);
   if(actors.some(a=>this.ownsActor(a)))throw Error('Overlapping actor ownership');
   if(active.jobs.some(j=>!active.receipts[j.id]&&lanes[j.slot].status()?.ownedPackage===true)){
    active.socialOverlap=(active.socialOverlap||0)+1;
    if(playing)active.speechOverlap=(active.speechOverlap||0)+1;
   }
  },
  status(){recheckReceipts();return {available:this.available(),capacity:8,background_capacity:6,background:active?.background===true,result:active?.result||null,id:active?.id,peak_owned:active?.peak||0,overlap_samples:active?.overlap||0,
   attendance_overlap_samples:active?.socialOverlap||0,speech_overlap_samples:active?.speechOverlap||0,
   activities:active?active.jobs.map(j=>({slot:j.slot,actor:j.actor,actor_base_id:j.actor_base_id,target:j.target,...(active.receipts[j.id]||lanes[j.slot].status())})):[]};},
  step(command){
   const jobs=command.jobs;
   if(Array.isArray(jobs)&&jobs.some(j=>j&&j.public_seller_ids!==undefined&&(!Array.isArray(j.public_seller_ids)||j.public_seller_ids.length>128||j.public_seller_ids.some(id=>!Number.isInteger(id)||id<=0||id>0xffffffff))))
    return {done:true,ack:{id:command.id,status:'held',error:'Invalid public seller roster',routines:[]}};
   if(!Array.isArray(jobs)||!jobs.length||jobs.length>8||jobs.some(j=>!j||!Number.isInteger(j.slot)||j.slot<0||j.slot>=8||!formId(j.actor)||!formId(j.actor_base_id)||j.target!==0x2be1b||j.target_kind!=='place'||typeof j.id!=='string')||
       new Set(jobs.map(j=>j.slot)).size!==jobs.length||new Set(jobs.map(j=>j.actor)).size!==jobs.length||new Set(jobs.map(j=>j.id)).size!==jobs.length)
    return {done:true,ack:{id:command.id,status:'held',error:'Invalid independent routing allocation',routines:[]}};
   if(!active||active.id!==command.id){
    if(active&&(!active.done||active.jobs.some(j=>active.receipts[j.id]?.release_verified!==true)))throw new Error('Cannot replace an executing or unreleased cohort');
    active={id:command.id,jobs:jobs.map(j=>({...j})),receipts:{},finishing:{},peak:0,overlap:0};
   }
   if(JSON.stringify(active.jobs)!==JSON.stringify(jobs))throw new Error('Cohort commands changed during execution');
   recheckReceipts();
   for(const job of jobs){
    if(active.receipts[job.id])continue;
    let result=active.finishing[job.id];
    if(!identityMatches(job)){
     releaseOwned(job);
     result={ack:identityHold(job,lanes[job.slot].status()),at:result?.at??now()};
     active.finishing[job.id]=result;
    }
    if(!result){
     if(!lanes[job.slot].status()&&!coldSlotClear(job)){
      result={ack:{id:job.id,status:'held',error:'Cold controller cannot adopt an existing native lane'},at:now()};
      active.finishing[job.id]=result;
     }
    }
    if(!result){
     try{const step=lanes[job.slot].step(job);if(!step.done)continue;result={ack:step.ack,at:now()};}
     catch(error){releaseOwned(job);result={ack:{id:job.id,status:'held',error:String(error)},at:now()};}
     active.finishing[job.id]=result;
    }
    const releaseOK=released(job);
    // The completion/cleanup tick can itself race a changed native reference.
    if(!identityMatches(job))result.ack=identityHold(job,result.ack.movement);
    if(!releaseOK&&now()-result.at<10000)continue;
    active.receipts[job.id]={...result.ack,actor_base_id:job.actor_base_id,slot:job.slot,release_verified:releaseOK&&identityMatches(job),
      seller_nearby:result.ack.status==='applied'&&releaseOK?sellerNearby(job):null,finished_at:now()};
   }
   const owned=jobs.filter(j=>!active.receipts[j.id]&&lanes[j.slot].status()?.ownedPackage===true).length;
   active.peak=Math.max(active.peak,owned);if(owned>=2)active.overlap++;
   active.done=jobs.every(j=>active.receipts[j.id]);
   if(active.done)active.result={id:command.id,status:Object.values(active.receipts).every(r=>r.status==='applied'&&r.release_verified)?'applied':'held',
    routines:jobs.map(j=>active.receipts[j.id]),concurrency:{peak_owned:active.peak,overlap_samples:active.overlap,
     attendance_overlap_samples:active.socialOverlap||0,speech_overlap_samples:active.speechOverlap||0}};
   return active.done?{done:true,ack:active.result}:{done:false};
  }
 };
}
if(typeof module!=='undefined')module.exports={createParallelRoutineController};
