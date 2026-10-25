// Authored breaks at existing unowned benches inspected in Skyrim.esm.
// No teleport, inventory mutation, forced animation, or sleep claim.
function createRestController(platform,now=Date.now,catalog){
 const configure=typeof configuredVenueCatalog==='function'?configuredVenueCatalog:require('./places.js').configuredVenueCatalog;
 const observeSpace=typeof venueSpace==='function'?venueSpace:require('./places.js').venueSpace;
 const configured=configure(catalog),sites= configured.venues.filter(v=>v.kind==='rest_bench'),seats=sites.map(v=>v.id);
 const makeRouter=typeof createPapyrusRouterController==='function'?createPapyrusRouterController:require('./papyrus-router.js').createPapyrusRouterController;
 const router=makeRouter(platform,now,{file:'WhiterunRest.esp',furniture:true});
 let active=null;
 const position=a=>[a.getPositionX(),a.getPositionY(),a.getPositionZ()];
 const getSeat=id=>platform().ObjectReference?.from(platform().Game.getFormEx(id));
 const ownership=seat=>{
  try{if(typeof seat.getActorOwner!=='function'||typeof seat.getFactionOwner!=='function')return 'authored_unowned_not_sensed';
   return seat.getActorOwner()||seat.getFactionOwner()?'owned':'native_unowned';
  }catch(_){return 'unknown';}
 };
 return {
  reset(){active=null;router.reset();},
  release(){if(typeof platform().Game.getFormFromFile==='function')router.release();},
  status(){return active?{...active,route:router.status()}:null;},
  sense(residents){
   const sp=platform(),sites=[],sensors={};
   if(!sp.ObjectReference||typeof sp.Game.getFormFromFile!=='function')return {available:false,sites,sensors};
   for(const site of configured.venues.filter(v=>v.kind==='rest_bench')){
    const id=site.id,seat=getSeat(id);if(!seat||seat.getFormID()!==id||!seat.is3DLoaded()||seat.isDisabled?.()===true)continue;
    const owner=ownership(seat);if(owner==='owned'||owner==='unknown')continue;
    const coordinates=position(seat);if(!coordinates.every(Number.isFinite))continue;
    const occupancyKnown=typeof seat.isFurnitureInUse==='function';
    sites.push({...site,position:coordinates,space:observeSpace(seat),loaded:true,catalog_version:configured.version,source:configured.knowledge,ownership:owner,
     occupancy_known:occupancyKnown,occupied:occupancyKnown?seat.isFurnitureInUse(false):null});
   }
   for(const row of residents){
    if(row.isPerson!==true)continue;
    const actor=sp.Actor.from(sp.Game.getFormEx(row.id));if(!actor)continue;
    sensors[row.id]={sit_available:typeof actor.getSitState==='function',furniture_reference_available:typeof actor.getFurnitureReference==='function',
     sit_state:typeof actor.getSitState==='function'?actor.getSitState():null,
     furniture:typeof actor.getFurnitureReference==='function'?actor.getFurnitureReference()?.getFormID()||0:null};
   }
   return {available:router.available(),sites,sensors,activity:this.status()};
  },
  step(command){
   if(active?.id===command.id&&['applied','held'].includes(active.phase))return {done:true,ack:{id:command.id,status:active.phase,error:active.error,rest:this.status()}};
   const sp=platform(),actor=sp.Actor.from(sp.Game.getFormEx(command.actor)),seat=getSeat(command.target);
   const end=(outcome,error)=>{if(!active)active={id:command.id,actor:command.actor,target:command.target,rested_minutes:0,seated_samples:0};
    active.outcome=outcome;active.error=error;active.phase='releasing';active.releaseAt=now();router.release();return {done:false};};
   if(active?.phase==='releasing'){
    const packageId=actor?.getCurrentPackage()?.getFormID();
    const expected=router.status()?.expectedPackage;
    const owned=expected&&packageId===expected;
    if(owned&&now()-active.releaseAt<10000)return {done:false};
    active.release_verified=!!actor&&!owned;
    router.observeRelease(!!owned);
    active.phase=owned?'held':active.outcome;
    return {done:true,ack:{id:command.id,status:owned?'held':active.outcome,error:active.error,rest:this.status()}};
   }
   if(command.kind!=='rest_at_bench'||command.rest_minutes!==30||!seats.includes(command.target)||command.actor===command.target)
    return end('held','Invalid bounded rest contract');
   if(!actor||!seat||!actor.is3DLoaded()||!seat.is3DLoaded()||actor.isDead()||actor.isChild()||typeof actor.getSitState!=='function'||typeof actor.getFurnitureReference!=='function')
    return end('held','Loaded adult, bench and sitting sensor required');
   if(seat.getFormID()!==command.target||seat.isDisabled?.()===true||['owned','unknown'].includes(ownership(seat)))return end('held','Registered unowned bench required');
   const keyword=sp.Keyword?.from(sp.Game.getFormEx(0x13794));
   if(!keyword||!actor.hasKeyword(keyword)||typeof actor.isInCombat!=='function'||actor.isInCombat())return end('held','Rest classification or safety check failed');
   if(!active||active.id!==command.id){
    active={id:command.id,actor:command.actor,target:command.target,phase:'travelling',began:now(),rested_minutes:0,seated_samples:0,lastGame:null};
    const ownSeat=actor.getSitState()===3&&actor.getFurnitureReference()?.getFormID()===command.target;
    if(typeof seat.isFurnitureInUse!=='function'||(seat.isFurnitureInUse(false)&&!ownSeat))return end('held','Bench occupancy unavailable or already in use');
   }
   if(now()-active.began>290000)return end('held','Rest lease expired before completion');
   if(active.phase==='travelling'){
    const result=router.step({...command,retain:true,origin:'resident_decision'});
    if(!result.done)return {done:false};
    if(result.ack.status!=='applied')return end('held',result.ack.error||'Rest arrival failed');
    active.phase='resting';
   }
   const gap=Math.hypot(...position(actor).map((n,i)=>n-position(seat)[i]));
   const expected=router.status().expectedPackage;
   const exact=typeof actor.getFurnitureReference==='function'?actor.getFurnitureReference()?.getFormID()===command.target:null;
   if(actor.getCurrentPackage()?.getFormID()!==expected||actor.getSitState()!==3||gap>250||exact===false)
    return end('held','Owned seated attendance interrupted');
   const day=sp.Utility?.getCurrentGameTime?.();
   if(!Number.isFinite(day))return end('held','Rest game clock unavailable');
   if(active.lastGame!==null){const delta=day-active.lastGame;
    if(delta<0||delta>1/1440)return end('held','Game clock jumped during rest');
    active.rested_minutes+=delta*1440;
   }
   active.lastGame=day;active.seated_samples++;active.exact_furniture_verified=exact===true;
   if(active.rested_minutes>=command.rest_minutes)return end('applied');
   return {done:false};
  }
 };
}
if(typeof module!=='undefined')module.exports={createRestController};
