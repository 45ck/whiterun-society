// Two independently ticked, receipt-retaining furniture lanes. Admission is a
// short command; seated elapsed time belongs only to this native session.
function createActivityJobsController(platform,now=Date.now,catalog,options={}){
 const factory=options.restFactory||(typeof createRestController==='function'?createRestController:require('./rest.js').createRestController);
 const capacity=2,lanes=Array.from({length:capacity},(_,slot)=>factory(platform,now,catalog,{router:{file:'WhiterunActivities.esp',offset:slot*0x100}}));
 const jobs=new Map(),acknowledged=new Map();let desired=null,currentSession=null,fresh=false,recover=true;
 const clone=value=>JSON.parse(JSON.stringify(value));
 const token=v=>typeof v==='string'&&v.length>0&&v.length<=160;
 const fields=['job_id','actor','target','slot','session','epoch','rest_minutes','actor_base_id'];
 const identity=row=>({job_id:row.job_id||row.id,actor:row.actor,target:row.target,slot:row.slot,session:row.job_session||row.session,epoch:row.epoch,rest_minutes:row.rest_minutes,
  ...(row.actor_base_id===undefined?{}:{actor_base_id:row.actor_base_id})});
 const matches=(a,b)=>fields.every(key=>a[key]===b[key]);
 const valid=row=>token(row.job_id)&&token(row.session)&&token(row.epoch)&&Number.isInteger(row.actor)&&row.actor>0&&
  Number.isInteger(row.target)&&row.target>0&&row.actor!==row.target&&Number.isInteger(row.slot)&&row.slot>=0&&row.slot<capacity&&row.rest_minutes===30&&
  (row.actor_base_id===undefined||Number.isInteger(row.actor_base_id)&&row.actor_base_id>0);
 const key=row=>JSON.stringify([row.session,row.epoch,row.job_id]);
 function available(){try{return lanes.every(lane=>lane.available());}catch(_){return false;}}
 function saved(row){return fresh&&desired?.epoch===row.epoch&&Array.isArray(desired.jobs)&&desired.jobs.some(item=>matches(identity(item),row));}
 function command(job){return {id:job.job_id,kind:'rest_at_bench',actor:job.actor,target:job.target,rest_minutes:job.rest_minutes,actor_base_id:job.actor_base_id};}
 function actorIdentityMatches(row){
  if(row.actor_base_id===undefined)return true;
  try{const sp=platform(),actor=sp.Actor.from(sp.Game.getFormEx(row.actor));return (actor?.getActorBase?.()||actor?.getBaseObject?.())?.getFormID()===row.actor_base_id;}catch(_){return false;}
 }
 function cancel(job,reason){
  if(job.cancelled)return;
  job.cancelled=true;job.phase='releasing';job.error=reason;
  lanes[job.slot].cancel(command(job),reason);
  if(job.receipt)job.receipt={...job.receipt,status:'held',error:reason};
 }
 // Keep actor/seat reservations through durable receipt acknowledgement.
 function reservation(job){return true;}
 function finish(job,ack){
  job.phase=job.cancelled?'held':ack.status;
  job.receipt={...identity(job),status:job.phase,rest:ack.rest||lanes[job.slot].status(),error:job.error||ack.error||null};
 }
 return {
  reset(){
   // Keep identities and receipts in memory until acknowledged. A game load
   // cancels rather than restores elapsed work from the prior session.
   for(const job of jobs.values())cancel(job,'Native session reset; prior elapsed rest is not recoverable');
   desired=null;fresh=false;currentSession=null;recover=true;
  },
  release(){for(const lane of lanes)lane.release();},
  ownsActor(actor){return [...jobs.values()].some(job=>job.actor===actor&&reservation(job));},
  ownsTarget(target){return [...jobs.values()].some(job=>job.target===target&&reservation(job));},
  reservedActors(){return [...jobs.values()].filter(reservation).map(job=>job.actor);},
  start(input,blockedActors=[]){
   const row=identity(input),fail=error=>({done:true,ack:{id:input.id,status:'held',accepted:false,
    no_effects_issued:!jobs.has(key(row))&&!acknowledged.has(key(row)),error,...row}});
   if(!valid(row)||input.session!==currentSession||row.session!==currentSession||!saved(row))return fail('Fresh matching activity assignment and native session required');
   if(acknowledged.has(key(row)))return fail('Activity identity was already acknowledged; no replay');
   const existing=jobs.get(key(row));
   if(existing){
    if(!matches(existing,row))return fail('Activity identity changed');
    return {done:true,ack:{id:input.id,status:'applied',accepted:true,...row}};
   }
   if(!available()||recover)return fail('Activity furniture lanes unavailable or recovering');
   if(!actorIdentityMatches(row))return fail('Observed actor base identity differs from saved activity assignment');
   if(blockedActors.includes(row.actor))return fail('Another native task owns the actor');
   if([...jobs.values()].some(job=>job.slot===row.slot||reservation(job)&&(job.actor===row.actor||job.target===row.target)))
    return fail('Activity actor, furniture or slot is reserved');
   lanes[row.slot].reset();
   jobs.set(key(row),{...row,phase:'accepted',accepted_at:now(),cancelled:false,receipt:null});
   return {done:true,ack:{id:input.id,status:'applied',accepted:true,...row}};
  },
  acknowledge(input){
   const row=identity(input),fail=error=>({done:true,ack:{id:input.id,status:'held',acknowledged:false,error}});
   if(!valid(row)||input.session!==currentSession)return fail('Matching current-session receipt identity required');
   const previous=acknowledged.get(key(row));
   if(previous){if(!matches(previous,row))return fail('Acknowledged identity changed');return {done:true,ack:{id:input.id,status:'applied',acknowledged:true,...row}};}
   const job=jobs.get(key(row));
   if(!job||!matches(job,row)||!job.receipt)return fail('Exact terminal activity receipt required');
   if(job.receipt.rest?.release_verified!==true)return fail('Activity native release remains unverified');
   acknowledged.set(key(row),row);jobs.delete(key(row));lanes[row.slot].reset();
   return {done:true,ack:{id:input.id,status:'applied',acknowledged:true,...row}};
  },
  tick(assignments,session,isFresh){
   if(currentSession!==null&&currentSession!==session)for(const job of jobs.values())cancel(job,'Native session changed; elapsed rest invalidated');
   currentSession=session;desired=assignments;fresh=isFresh===true;
   if(recover){this.release();recover=!lanes.every(lane=>{try{return lane.released();}catch(_){return false;}});}
   // A hot reload has no trustworthy elapsed clock. Reconcile saved live work
   // as held and release its exact slot, rather than silently restarting it.
   if(fresh&&Array.isArray(desired?.jobs))for(const item of desired.jobs){
    const row=identity(item);
    if(!valid(row)||jobs.has(key(row))||acknowledged.has(key(row))||[...jobs.values()].some(job=>job.slot===row.slot))continue;
    if(row.session===session&&!['accepted','running','travelling','resting','releasing','held','complete','applied'].includes(item.phase))continue;
    const job={...row,phase:'releasing',accepted_at:null,cancelled:false,receipt:null,recovered_without_elapsed:true};
    lanes[row.slot].reset();jobs.set(key(row),job);cancel(job,'Saved activity recovered without native elapsed evidence; no rest recovery');
   }
   for(const job of jobs.values()){
    if(job.receipt?.rest?.release_verified===true&&!job.cancelled)continue;
    if(job.session!==session||!saved(job))cancel(job,'Activity assignment withdrawn, stale or epoch changed');
    if(!job.cancelled&&!actorIdentityMatches(job))cancel(job,'Actor base identity changed during activity');
    if(job.receipt?.rest?.release_verified===true)continue;
    try{
     const result=lanes[job.slot].step(command(job));
     job.phase=lanes[job.slot].status()?.phase||job.phase;
     if(result.done)finish(job,result.ack);
    }catch(error){
     cancel(job,'Native activity error: '+String(error).slice(0,160));
    }
   }
  },
  status(){return {available:available(),capacity,recovering:recover,epoch:desired?.epoch||null,session:currentSession,
   jobs:[...jobs.values()].map(job=>({...identity(job),id:job.job_id,phase:job.phase,rest:clone(lanes[job.slot].status()),cancelled:job.cancelled})),
   receipts:[...jobs.values()].filter(job=>job.receipt).map(job=>clone(job.receipt)),reserved_actors:this.reservedActors(),
   scope:'Native seated attendance and release receipts; no inventory or fatigue mutation in the bridge'};}
 };
}
if(typeof module!=='undefined')module.exports={createActivityJobsController};
