// Eight independent Papyrus mailboxes. Native object handles never cross frames.
function createParallelRoutineController(platform,now=Date.now){
 const makeRouter=typeof createPapyrusRouterController==='function'?createPapyrusRouterController:require('./papyrus-router.js').createPapyrusRouterController;
 const makePlaces=typeof createPlaceObserver==='function'?createPlaceObserver:require('./places.js').createPlaceObserver;
 const places=makePlaces(platform),file='WhiterunLanes.esp';
 const lanes=Array.from({length:8},(_,slot)=>makeRouter(platform,now,{file,offset:slot*0x10,placeObserver:places}));
 let active=null;
 function released(job){
  const sp=platform(),actor=sp.Actor.from(sp.Game.getFormEx(job.actor)),quest=sp.Quest.from(sp.Game.getFormFromFile(0x800+job.slot*0x10,file));
  if(!actor?.is3DLoaded()||!quest||quest.isRunning())return false;
  const pkg=actor.getCurrentPackage(),owned=sp.Game.getFormFromFile(0x801+job.slot*0x10,file);
  return !!owned&&(!pkg||pkg.getFormID()!==owned.getFormID());
 }
 function sellerNearby(job){
  const sp=platform(),actor=sp.Actor.from(sp.Game.getFormEx(job.actor)),seller=sp.Actor.from(sp.Game.getFormEx(108149)),place=sp.ObjectReference.from(sp.Game.getFormEx(job.target));
  if(!actor?.is3DLoaded()||!seller?.is3DLoaded()||!places.validTarget(seller,place))return false;
  return Math.hypot(actor.getPositionX()-seller.getPositionX(),actor.getPositionY()-seller.getPositionY(),actor.getPositionZ()-seller.getPositionZ())<=300;
 }
 return {
  available(){return lanes.every(lane=>lane.available());},
  release(){for(const lane of lanes)if(lane.available())lane.release();},
  reset(){active=null;for(const lane of lanes)lane.reset();},
  status(){return {available:this.available(),capacity:8,id:active?.id,peak_owned:active?.peak||0,overlap_samples:active?.overlap||0,
   activities:active?active.jobs.map(j=>({slot:j.slot,actor:j.actor,target:j.target,...(active.receipts[j.id]||lanes[j.slot].status())})):[]};},
  step(command){
   const jobs=command.jobs;
   if(!Array.isArray(jobs)||!jobs.length||jobs.length>8||jobs.some(j=>!j||!Number.isInteger(j.slot)||j.slot<0||j.slot>=8||!Number.isInteger(j.actor)||j.target!==0x2be1b||j.target_kind!=='place'||typeof j.id!=='string')||
       new Set(jobs.map(j=>j.slot)).size!==jobs.length||new Set(jobs.map(j=>j.actor)).size!==jobs.length||new Set(jobs.map(j=>j.id)).size!==jobs.length)
    return {done:true,ack:{id:command.id,status:'held',error:'Invalid independent routing allocation',routines:[]}};
   if(!active||active.id!==command.id){
    if(active&&!active.done)throw new Error('Cannot replace an executing cohort');
    active={id:command.id,jobs:jobs.map(j=>({...j})),receipts:{},finishing:{},peak:0,overlap:0};
   }
   if(JSON.stringify(active.jobs)!==JSON.stringify(jobs))throw new Error('Cohort commands changed during execution');
   for(const job of jobs){
    if(active.receipts[job.id])continue;
    let result=active.finishing[job.id];
    if(!result){
     try{const step=lanes[job.slot].step(job);if(!step.done)continue;result={ack:step.ack,at:now()};}
     catch(error){lanes[job.slot].release();result={ack:{id:job.id,status:'held',error:String(error)},at:now()};}
     active.finishing[job.id]=result;
    }
    const releaseOK=released(job);
    if(!releaseOK&&now()-result.at<10000)continue;
    active.receipts[job.id]={...result.ack,slot:job.slot,release_verified:releaseOK,
      seller_nearby:result.ack.status==='applied'&&releaseOK?sellerNearby(job):null,finished_at:now()};
   }
   const owned=jobs.filter(j=>!active.receipts[j.id]&&lanes[j.slot].status()?.ownedPackage===true).length;
   active.peak=Math.max(active.peak,owned);if(owned>=2)active.overlap++;
   active.done=jobs.every(j=>active.receipts[j.id]);
   return active.done?{done:true,ack:{id:command.id,status:Object.values(active.receipts).every(r=>r.status==='applied'&&r.release_verified)?'applied':'held',
    routines:jobs.map(j=>active.receipts[j.id]),concurrency:{peak_owned:active.peak,overlap_samples:active.overlap}}}:{done:false};
  }
 };
}
if(typeof module!=='undefined')module.exports={createParallelRoutineController};
