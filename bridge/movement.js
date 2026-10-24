// The plan chooses a destination; Skyrim supplies navmesh pathfinding/animation.
function createMovementController(platform, now=Date.now) {
  let active=null;
  const distance=(a,b)=>Math.hypot(a.getPositionX()-b.getPositionX(),a.getPositionY()-b.getPositionY(),a.getPositionZ()-b.getPositionZ());
  return {
    reset(){active=null;},
    status(){return active ? {id:active.id,actor:active.actor,target:active.target,method:active.method,phase:active.phase,distance:active.distance,startDistance:active.startDistance} : null;},
    step(command){
      const sp=platform();
      const actor=sp.Actor.from(sp.Game.getFormEx(command.actor)),target=sp.Actor.from(sp.Game.getFormEx(command.target));
      const finish=(status,error)=>{if(active){active.phase=status;if(active.method==='offset'&&actor&&actor.is3DLoaded())actor.clearKeepOffsetFromActor();}return {done:true,ack:{id:command.id,status,error,movement:this.status()}};};
      if(!actor||!target||!actor.is3DLoaded()||!target.is3DLoaded()||actor.isDead()||target.isDead()) return finish('held','Actor or destination unavailable');
      const gap=distance(actor,target);
      if(!active||active.id!==command.id){
        active={id:command.id,actor:command.actor,target:command.target,method:command.method||'path',startDistance:gap,distance:gap,phase:'walking',at:now(),finished:false};
        if(gap<=225)return finish('applied','Already within interaction range; no walking claimed');
        if(active.method==='offset'){
          if(typeof actor.keepOffsetFromActor!=='function')return finish('held','Native approach controller unavailable');
          actor.keepOffsetFromActor(target,0,-160,0,0,0,0,200,100);
          return {done:false};
        }
        if(typeof actor.pathToReference!=='function')return finish('held','Native pathfinding unavailable');
        const issued=active;
        const result=actor.pathToReference(target,0.5);
        if(result&&typeof result.then==='function') result.then(success=>{issued.finished=true;issued.success=success;}).catch(()=>{issued.finished=true;issued.success=false;});
        else return finish('held','Expected latent pathfinding result');
      }
      active.distance=gap;
      if(gap<=225)return finish('applied');
      if(active.finished||now()-active.at>45000){
        actor.evaluatePackage();
        return finish('held','Destination not reached; route needs a new plan');
      }
      return {done:false};
    }
  };
}
if(typeof module!=='undefined')module.exports={createMovementController};
