// A quest alias supplies the managed resident's package stack. Only scalar IDs
// survive updates; every native handle is reacquired before use.
function createAgentRoutineController(platform,now=Date.now){
 let active=null,releaseStarted=null;
 const residents=[108186,108149,108156],routes=[];
 for(const actor of residents)for(const target of residents)if(actor!==target)routes.push({actor,target});
 const gap=(a,b)=>Math.hypot(a.getPositionX()-b.getPositionX(),a.getPositionY()-b.getPositionY(),a.getPositionZ()-b.getPositionZ());
 return {
  reset(){active=null;releaseStarted=null;},
  release(){
   const sp=platform();
   if(!sp.Quest)return;
   for(let i=0;i<routes.length;i++){
    const quest=sp.Quest.from(sp.Game.getFormFromFile(0x800+i*2,'WhiterunAgents.esp'));
    if(quest&&quest.isRunning())quest.stop();
   }
  },
  finish(command){
   const sp=platform();
   if(!releaseStarted||releaseStarted.id!==command.id){releaseStarted={id:command.id,at:now()};this.release();return {done:false};}
   const actor=sp.Actor.from(sp.Game.getFormEx(command.actor));
   if(!actor||!actor.is3DLoaded())return {done:true,ack:{id:command.id,status:'held',released:false,error:'Resident unavailable; package release is unverified'}};
   const current=actor&&actor.getCurrentPackage();
   const owned=routes.some((_,i)=>{
    const pkg=sp.Game.getFormFromFile(0x801+i*2,'WhiterunAgents.esp');
    return pkg&&current&&pkg.getFormID()===current.getFormID();
   });
   if(owned&&now()-releaseStarted.at<10000)return {done:false};
   if(active){active.phase=owned?'held':'released';active.ownedPackage=owned;}
   return {done:true,ack:{id:command.id,status:owned?'held':'applied',released:!owned}};
  },
  status(){return active?{...active}:null;},
  step(command){
   const sp=platform();
   const index=command.dynamic===true?0:routes.findIndex(r=>r.actor===command.actor&&r.target===command.target);
   if(index<0)return {done:true,ack:{id:command.id,status:'held',error:'Unsupported resident route'}};
   const quests=routes.map((_,i)=>sp.Quest.from(sp.Game.getFormFromFile(0x800+i*2,'WhiterunAgents.esp')));
   const quest=quests[index];
   const pkg=sp.Game.getFormFromFile(0x801+index*2,'WhiterunAgents.esp');
   const actor=sp.Actor.from(sp.Game.getFormEx(command.actor)),target=sp.Actor.from(sp.Game.getFormEx(command.target));
   const fail=message=>{
    if(quest&&quest.isRunning())quest.stop();
    if(active){active.phase='held';active.error=message;}
    return {done:true,ack:{id:command.id,status:'held',error:message,movement:this.status()}};
   };
   if(!quest||!pkg||!actor||!target||!actor.is3DLoaded()||!target.is3DLoaded())return fail('Routine plugin, resident or destination unavailable');
   if(command.actor===command.target)return fail('Resident cannot travel to itself');
   let actorAlias=null,targetAlias=null;
   if(command.dynamic===true){
    if(!sp.ReferenceAlias||typeof quest.getAlias!=='function')return fail('Dynamic alias API unavailable');
    actorAlias=sp.ReferenceAlias.from(quest.getAlias(0));targetAlias=sp.ReferenceAlias.from(quest.getAlias(1));
    // A stopped quest may not yet have instantiated its alias objects.
   }
   if(!active||active.id!==command.id){
    active={id:command.id,actor:command.actor,target:command.target,origin:command.origin||'test',method:'package',dynamic:command.dynamic===true,phase:'resetting',at:now(),startDistance:gap(actor,target),distance:gap(actor,target),expectedPackage:pkg.getFormID(),ownedPackage:false,hasOwnedPackage:false};
    for(const candidate of quests)if(candidate&&candidate.isRunning())candidate.stop();
    return {done:false};
   }
   active.distance=gap(actor,target);
   const current=actor.getCurrentPackage();
   active.enginePackage=current?current.getFormID():0;
   active.ownedPackage=active.enginePackage===active.expectedPackage;
   active.hasOwnedPackage=active.hasOwnedPackage||active.ownedPackage;
   if(active.phase==='releasing'){
    if(quest.isRunning()||active.ownedPackage){
     if(now()-active.releaseAt>10000)return fail('Routine release was not observed');
     return {done:false};
    }
    active.phase=active.outcome;
    actor.evaluatePackage();
    return {done:true,ack:{id:command.id,status:active.outcome,error:active.error,movement:this.status()}};
   }
   if(now()-active.at>120000){
    active.outcome='held';active.error='Owned route did not reach its destination';active.phase='releasing';active.releaseAt=now();quest.stop();return {done:false};
   }
   if(active.phase==='travelling'&&active.hasOwnedPackage&&!active.ownedPackage){
    active.outcome='held';active.error='Task interrupted by the engine; replanning required';
    active.phase='releasing';active.releaseAt=now();quest.stop();return {done:false};
   }
   if(active.phase==='resetting'){
    if(quests.some(q=>q&&q.isRunning()))return {done:false};
    const state=active;
    const started=quest.start();
    active.phase='starting';active.startRequestedAt=now();
    if(started&&typeof started.then==='function')started.then(value=>{state.startResult=value;state.startComplete=true;},()=>{state.startResult=false;state.startComplete=true;});
    else {active.startResult=started;active.startComplete=true;}
    return {done:false};
   }
   if(active.phase==='starting'){
    if(active.startComplete&&active.startResult===false)return fail('Routine quest refused to start');
    if(!quest.isRunning()||!active.startComplete)return {done:false};
    if(command.dynamic===true){
     if(!actorAlias||!targetAlias||typeof actorAlias.forceRefTo!=='function'||typeof targetAlias.forceRefTo!=='function'||typeof actorAlias.getReference!=='function'||typeof targetAlias.getReference!=='function'){
      if(now()-active.startRequestedAt>10000)return fail('Running quest reference aliases unavailable');
      return {done:false};
     }
     // Force each alias once, then observe the assignment on later updates.
     // Native handles are never retained across frames or asynchronous work.
     targetAlias.forceRefTo(target);actorAlias.forceRefTo(actor);
     active.phase='binding';active.bindingAt=now();return {done:false};
    }
    actor.evaluatePackage();active.phase='travelling';return {done:false};
   }
   if(active.phase==='binding'){
    if(!actorAlias||!targetAlias)return fail('Reference aliases disappeared during assignment');
    const boundActor=actorAlias.getReference(),boundTarget=targetAlias.getReference();
    active.boundActor=boundActor?boundActor.getFormID():0;active.boundTarget=boundTarget?boundTarget.getFormID():0;
    if(active.boundActor!==command.actor||active.boundTarget!==command.target){
     if(now()-active.bindingAt>10000)return fail('Dynamic alias assignment was not observed');
     return {done:false};
    }
    active.aliasesConfirmed=true;actor.evaluatePackage();active.phase='travelling';return {done:false};
   }
   if(command.dynamic===true&&active.phase==='travelling'){
    if(!actorAlias||!targetAlias)return fail('Reference aliases disappeared during travel');
    const boundActor=actorAlias.getReference(),boundTarget=targetAlias.getReference();
    if(!boundActor||!boundTarget||boundActor.getFormID()!==command.actor||boundTarget.getFormID()!==command.target)return fail('Dynamic alias ownership changed during travel');
   }
   if(active.phase==='travelling'&&active.hasOwnedPackage&&active.distance<=250){
    if(command.retain){active.phase='arrived';return {done:true,ack:{id:command.id,status:'applied',movement:this.status()}};}
    active.outcome='applied';active.phase='releasing';active.releaseAt=now();quest.stop();return {done:false};
   }
   return {done:false};
  }
 };
}
if(typeof module!=='undefined')module.exports={createAgentRoutineController};
