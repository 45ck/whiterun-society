// Only scalar IDs cross updates. Papyrus owns alias handles and acknowledges
// both forced references before the bridge accepts package ownership.
function observeNativeActivity(actor){
 const result={scene_id:null,in_combat:null,sleep_state:null,package_id:null};
 try{if(typeof actor.getCurrentScene==='function'){const scene=actor.getCurrentScene();result.scene_id=scene?scene.getFormID():0;}}catch(_){}
 try{if(typeof actor.isInCombat==='function')result.in_combat=actor.isInCombat();}catch(_){}
 try{if(typeof actor.getSleepState==='function')result.sleep_state=actor.getSleepState();}catch(_){}
 try{if(typeof actor.getCurrentPackage==='function'){const pkg=actor.getCurrentPackage();result.package_id=pkg?pkg.getFormID():0;}}catch(_){}
 return result;
}
function nativeActivityBlocker(activity){
 if(!Number.isInteger(activity.scene_id)||activity.scene_id<0||typeof activity.in_combat!=='boolean'||
    !Number.isInteger(activity.sleep_state)||activity.sleep_state<0||activity.sleep_state>4)return 'activity_unknown';
 return activity.scene_id?'native_scene':activity.in_combat?'combat':activity.sleep_state?'sleep_transition':null;
}
function createPapyrusRouterController(platform,now=Date.now,options={}){
 let active=null;
 const file=options.file||'WhiterunRouter.esp';
 function records(){
  const sp=platform(),get=id=>sp.Game.getFormFromFile(id+(options.offset||0),file);
  return {sp,quest:sp.Quest?.from(get(0x800)),pkg:get(0x801),
   resident:sp.FormList?.from(get(0x802)),destination:sp.FormList?.from(get(0x803)),
   request:sp.GlobalVariable?.from(get(0x804)),ack:sp.GlobalVariable?.from(get(0x805)),status:sp.GlobalVariable?.from(get(0x806))};
 }
 const gap=(a,b)=>Math.hypot(a.getPositionX()-b.getPositionX(),a.getPositionY()-b.getPositionY(),a.getPositionZ()-b.getPositionZ());
 return {
  reset(){active=null;},
  available(){
   if(typeof platform().Game.getFormFromFile!=='function')return false;
   const r=records();return !!(r.quest&&r.pkg&&r.resident&&r.destination&&r.request&&r.ack&&r.status);
  },
  release(){const r=records();if(r.quest?.isRunning())r.quest.stop();},
  status(){return active?{...active}:null;},
  observeRelease(owned){if(active){active.phase=owned?'held':'released';active.ownedPackage=owned;}},
  step(command){
   const r=records(),sp=r.sp;
   const place=command.target_kind==='place';
   const actor=sp.Actor.from(sp.Game.getFormEx(command.actor)),target=options.furniture||place?sp.ObjectReference?.from(sp.Game.getFormEx(command.target)):sp.Actor.from(sp.Game.getFormEx(command.target));
   const fail=error=>{this.release();if(active){active.phase='held';active.error=error;}
    return {done:true,ack:{id:command.id,status:'held',error,movement:this.status()}};};
   if(!r.quest||!r.pkg||!r.resident||!r.destination||!r.request||!r.ack||!r.status)return fail('Papyrus router plugin unavailable');
   const placeValid=place&&options.placeObserver?.validTarget(actor,target)===true;
   if(!actor||!target||!actor.is3DLoaded()||(place?!placeValid:!target.is3DLoaded())||actor.isDead()||actor.isChild()||actor===target||command.actor===command.target)
    return fail('Loaded adult resident and distinct destination required');
   if(!active||active.id!==command.id){
    active={id:command.id,actor:command.actor,target:command.target,origin:command.origin||'test',method:'package',dynamic:true,
     adapter:'papyrus-mailbox',target_kind:place?'place':'resident',phase:'resetting',at:now(),startDistance:gap(actor,target),distance:gap(actor,target),
     expectedPackage:r.pkg.getFormID(),ownedPackage:false,hasOwnedPackage:false,aliasesConfirmed:false};
    this.release();return {done:false};
   }
   active.distance=gap(actor,target);
   const pkg=actor.getCurrentPackage();active.enginePackage=pkg?pkg.getFormID():0;
   active.ownedPackage=active.enginePackage===active.expectedPackage;
   active.hasOwnedPackage=active.hasOwnedPackage||active.ownedPackage;
   active.activity=observeNativeActivity(actor);
   if(active.phase==='releasing'){
    if(r.quest.isRunning()||active.ownedPackage){
     if(now()-active.releaseAt>10000)return fail('Papyrus route release was not observed');
     return {done:false};
    }
    active.phase=active.outcome;actor.evaluatePackage();
    return {done:true,ack:{id:command.id,status:active.outcome,error:active.error,movement:this.status()}};
   }
   const releaseAs=(outcome,error)=>{active.outcome=outcome;active.error=error;active.phase='releasing';active.releaseAt=now();this.release();return {done:false};};
   const blocker=nativeActivityBlocker(active.activity);
   if(blocker){active.failureReason=blocker;return releaseAs('held','Resident unavailable: '+blocker);}
   if(now()-active.at>120000)return releaseAs('held','Papyrus route timed out');
   if(active.phase==='resetting'){
    if(r.quest.isRunning())return {done:false};
    const serial=Math.max(r.request.getValue(),r.ack.getValue());
    if(!Number.isInteger(serial)||serial<0||serial>=16777215)return fail('Invalid or exhausted router serial');
    // Separate one-entry lists avoid depending on FormList insertion order.
    r.resident.revert();r.destination.revert();r.resident.addForm(actor);r.destination.addForm(target);
    active.serial=serial+1;active.phase='mailbox';active.mailboxAt=now();return {done:false};
   }
   const mailboxMatches=()=>r.resident.getSize()===1&&r.destination.getSize()===1&&
    r.resident.getAt(0)?.getFormID()===command.actor&&r.destination.getAt(0)?.getFormID()===command.target;
   if(active.phase==='mailbox'){
    if(!mailboxMatches()){
     if(now()-active.mailboxAt>5000)return fail('Router reference mailbox write was not observed');
     return {done:false};
    }
    r.status.setValue(0);r.request.setValue(active.serial);
    if(r.request.getValue()!==active.serial)return fail('Router request write was not observed');
    const state=active,result=r.quest.start();active.phase='starting';active.startAt=now();
    if(result&&typeof result.then==='function')result.then(ok=>{state.startComplete=true;state.startResult=ok;},()=>{state.startComplete=true;state.startResult=false;});
    else {active.startComplete=true;active.startResult=result;}
    return {done:false};
   }
   if(active.phase==='starting'){
    if(active.startComplete&&active.startResult===false)return fail('Router quest refused to start');
    if(now()-active.startAt>15000)return fail('Papyrus alias acknowledgement timed out');
    if(r.ack.getValue()!==active.serial)return {done:false};
    if(r.status.getValue()!==1||!r.quest.isRunning())return fail('Papyrus rejected reference binding');
    if(!mailboxMatches())return fail('Router mailbox changed during binding');
    active.aliasesConfirmed=true;active.phase='travelling';active.acquisitionAt=now();actor.evaluatePackage();return {done:false};
   }
   if(active.phase==='travelling'){
    if(!mailboxMatches()||r.request.getValue()!==active.serial||r.ack.getValue()!==active.serial||r.status.getValue()!==1||!r.quest.isRunning())
     return releaseAs('held','Router lease or mailbox changed during travel');
    if(active.hasOwnedPackage&&!active.ownedPackage)return releaseAs('held','Task interrupted by the engine; replanning required');
    if(!active.hasOwnedPackage&&now()-active.acquisitionAt>15000){
     active.failureReason='package_not_acquired';return releaseAs('held','Engine did not grant the requested package within 15 seconds');
    }
    const seated=!options.furniture||(typeof actor.getSitState==='function'&&actor.getSitState()===3);
    if(active.hasOwnedPackage&&active.distance<=250&&seated){
     if(command.retain){active.phase='arrived';return {done:true,ack:{id:command.id,status:'applied',movement:this.status()}};}
     return releaseAs('applied');
    }
   }
   return {done:false};
  }
 };
}
if(typeof module!=='undefined')module.exports={createPapyrusRouterController,observeNativeActivity,nativeActivityBlocker};
