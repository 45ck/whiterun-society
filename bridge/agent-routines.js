// A quest alias supplies the managed resident's package stack. Only scalar IDs
// survive updates; every native handle is reacquired before use.
function createAgentRoutineController(platform,now=Date.now){
 let active=null;
 const residents=[108186,108149,108156],routes=[];
 for(const actor of residents)for(const target of residents)if(actor!==target)routes.push({actor,target});
 const gap=(a,b)=>Math.hypot(a.getPositionX()-b.getPositionX(),a.getPositionY()-b.getPositionY(),a.getPositionZ()-b.getPositionZ());
 return {
  reset(){active=null;},
  release(){
   const sp=platform();
   if(!sp.Quest)return;
   for(let i=0;i<routes.length;i++){
    const quest=sp.Quest.from(sp.Game.getFormFromFile(0x800+i*2,'WhiterunAgents.esp'));
    if(quest&&quest.isRunning())quest.stop();
   }
  },
  status(){return active?{...active}:null;},
  step(command){
   const sp=platform();
   const index=routes.findIndex(r=>r.actor===command.actor&&r.target===command.target);
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
   if(!active||active.id!==command.id){
    active={id:command.id,actor:command.actor,target:command.target,method:'package',phase:'resetting',at:now(),startDistance:gap(actor,target),distance:gap(actor,target),expectedPackage:pkg.getFormID(),ownedPackage:false,hasOwnedPackage:false};
    for(const candidate of quests)if(candidate&&candidate.isRunning())candidate.stop();
    return {done:false};
   }
   active.distance=gap(actor,target);
   const current=actor.getCurrentPackage();
   active.enginePackage=current?current.getFormID():0;
   active.ownedPackage=active.enginePackage===active.expectedPackage;
   active.hasOwnedPackage=active.hasOwnedPackage||active.ownedPackage;
   if(active.phase==='releasing'){
    if(quest.isRunning()){
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
    if(!quest.isRunning()||!active.startComplete)return {done:false};
    actor.evaluatePackage();active.phase='travelling';return {done:false};
   }
   if(active.phase==='travelling'&&active.hasOwnedPackage&&active.distance<=250){
    active.outcome='applied';active.phase='releasing';active.releaseAt=now();quest.stop();return {done:false};
   }
   return {done:false};
  }
 };
}
if(typeof module!=='undefined')module.exports={createAgentRoutineController};
