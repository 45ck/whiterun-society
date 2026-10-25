// Attendance only. The existing Citizens self-target mailbox holds each owner;
// the global inventory writer separately consumes a session-bound work token.
function createOwnerWorkJobsController(platform,now=Date.now,options={}){
 const catalog=options.catalog||(typeof module!=='undefined'?require('./economy-catalog.js').createEconomyCatalogController(platform):null);
 const fields=['job_id','actor','actor_base_id','slot','session','epoch','business_id','business_revision','recipe_id','catalog_hash','recipe_hash','policy_version','work_minutes'];
 const jobs=new Map(),acknowledged=new Map();let desired=null,session=null,fresh=false,control=null,sequence=0,capacity=4;
 const copy=x=>JSON.parse(JSON.stringify(x));
 const text=x=>typeof x==='string'&&x.length>0&&x.length<=160;
 const identity=x=>Object.fromEntries(fields.map(k=>[k,k==='job_id'?x.job_id||x.id:k==='session'?x.job_session||x.session:x[k]]));
 const key=x=>JSON.stringify([x.session,x.epoch,x.job_id]);
 const same=(a,b)=>fields.every(k=>a[k]===b[k]);
 const valid=x=>text(x.job_id)&&x.job_id.length<=64&&text(x.session)&&text(x.epoch)&&text(x.business_id)&&text(x.policy_version)&&
  typeof x.recipe_id==='string'&&/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(x.recipe_id)&&[x.catalog_hash,x.recipe_hash].every(v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v))&&Number.isInteger(x.business_revision)&&x.business_revision>=0&&
  Number.isInteger(x.actor)&&x.actor>0&&Number.isInteger(x.actor_base_id)&&x.actor_base_id>0&&
  Number.isInteger(x.slot)&&x.slot>=0&&x.slot<128&&Number.isInteger(x.work_minutes)&&x.work_minutes>=5&&x.work_minutes<=120;
 const catalogBinding=x=>{const binding=catalog?.identity(x.recipe_id),recipe=catalog?.recipe(x.recipe_id);return !!binding&&binding.catalog_hash===x.catalog_hash&&binding.recipe_hash===x.recipe_hash&&
  x.work_minutes>=recipe.work_minutes.minimum&&x.work_minutes<=recipe.work_minutes.maximum;};
 const holdId=job=>'owner-work-'+job.job_id;
 function records(slot){const sp=platform(),get=n=>sp.Game.getFormFromFile?.(0x800+slot*16+n,'WhiterunCitizens.esp');
  return {sp,quest:sp.Quest?.from(get(0)),pkg:get(1),actors:sp.FormList?.from(get(2)),targets:sp.FormList?.from(get(3)),
   request:sp.GlobalVariable?.from(get(4)),ack:sp.GlobalVariable?.from(get(5)),status:sp.GlobalVariable?.from(get(6))};}
 function available(){try{return [0,127].every(slot=>{const r=records(slot);return r.quest&&r.pkg&&r.actors&&r.targets&&r.request&&r.ack&&r.status;});}catch(_){return false;}}
 function assignment(job){return Array.isArray(desired?.jobs)?desired.jobs.find(row=>same(identity(row),job)):null;}
 function current(job){return fresh&&job.session===session&&desired?.epoch===job.epoch&&!!assignment(job);}
 function inspect(job){
  try{
   const r=records(job.slot),actor=r.sp.Actor.from(r.sp.Game.getFormEx(job.actor));
   if(!actor?.is3DLoaded()||actor.isDead()||actor.isChild()||(actor.getActorBase?.()||actor.getBaseObject?.())?.getFormID()!==job.actor_base_id)return {error:'Owner identity or availability changed'};
   if(typeof actor.isInCombat!=='function'||actor.isInCombat()||typeof actor.getCurrentScene!=='function'||actor.getCurrentScene()||typeof actor.getSleepState!=='function'||actor.getSleepState()!==0)return {error:'Owner native activity is unsafe or unknown'};
   const position=[actor.getPositionX(),actor.getPositionY(),actor.getPositionZ()],game=r.sp.Utility?.getCurrentGameTime?.(),cell=actor.getParentCell?.()?.getFormID();
   if(!position.every(Number.isFinite)||!Number.isFinite(game)||game<0||!Number.isInteger(cell)||cell<=0)return {error:'Owner position, cell or game clock unavailable'};
   const row=control?.activities?.find(a=>a.actor===job.actor&&a.slot===job.slot);
   const serial=r.request?.getValue(),pkg=r.pkg?.getFormID();
   const owned=Number.isInteger(serial)&&serial>0&&serial<=16777215&&r.quest?.isRunning()&&r.actors?.getSize()===1&&r.targets?.getSize()===1&&
    r.actors.getAt(0)?.getFormID()===job.actor&&r.targets.getAt(0)?.getFormID()===job.actor&&r.ack?.getValue()===serial&&r.status?.getValue()===1&&
    actor.getCurrentPackage()?.getFormID()===pkg&&row?.work_hold_id===holdId(job)&&row.goal_id===holdId(job)&&row.mode==='await_decision'&&row.target===job.actor;
   return {owned,serial,expected_package:pkg,position,game,cell};
  }catch(_){return {error:'Native owner attendance bindings unavailable'};}
 }
 function receipt(job){return {...identity(job),phase:job.phase,attendance:job.attendance?copy(job.attendance):null,
  effects_issued:job.effectsIssued,committed_inventory_verified:job.committed===true,release_verified:job.releaseVerified===true,release_requested:job.releaseRequested===true,
  commit_id:job.commitId||null,error:job.error||null,...(job.inventory?{inventory:copy(job.inventory)}:{})};}
 function hold(job,error){
  job.error=error;job.phase='held';job.lastGame=null;
  if(job.effectsIssued===false)job.releaseRequested=true;
  if(job.attendance)job.attendance.token_valid=false;
 }
 function observeRelease(job){
  try{
   const r=records(job.slot),actor=r.sp.Actor.from(r.sp.Game.getFormEx(job.actor));
   // Never stop a mailbox that has been reassigned to a different resident.
   const bound=r.actors?.getSize()===1&&r.actors.getAt(0)?.getFormID()===job.actor;
   if(r.quest?.isRunning()&&bound)r.quest.stop();
   job.releaseVerified=!!actor?.is3DLoaded()&&!!r.quest&&!r.quest.isRunning()&&actor.getCurrentPackage()?.getFormID()!==r.pkg?.getFormID();
   if(job.releaseVerified&&job.committed&&!job.resetInvalidated)job.phase='complete';
  }catch(_){job.releaseVerified=false;}
 }
 function signature(c){return JSON.stringify([identity(c),c.id,c.attendance_token,c.before,c.after]);}
 function authorization(c,continuation=false){
  const row=identity(c),job=jobs.get(key(row));
  if(c.kind!=='inventory_self_produce_commit'||!valid(row)||c.session!==session||!job||!same(job,row)||!text(c.id)||c.attendance_token!==job.attendance?.token)
   return {ok:false,error:'Exact same-session owner attendance token required'};
  if(!catalogBinding(row)||catalog?.status().available!==true)return {ok:false,error:'Bound recipe catalog or verified native forms unavailable'};
  if(job.commitId){
   if(job.commitId!==c.id||job.commitSignature!==signature(c))return {ok:false,error:'Attendance token already bound to another recipe command'};
   if(job.phase==='held'||job.resetInvalidated)return {ok:false,error:'Owner recipe is quarantined for reconciliation'};
   if(!job.committed){const s=inspect(job),a=job.attendance;
    if(!current(job)||s.error||!s.owned||s.serial!==a.serial||s.expected_package!==a.expected_package||s.cell!==job.anchorCell||
       Math.hypot(...s.position.map((n,i)=>n-a.anchor[i]))>100||s.game<job.lastGame||s.game-job.lastGame>1/1440)
     return {ok:false,error:'Owner attendance changed during issued recipe; reconciliation required'};
   }
   return {ok:true,job,continuation:true};
  }
  if(continuation||job.phase!=='attendance_verified'||job.effectsIssued!==false||!current(job)||assignment(job)?.cancel_requested===true)
   return {ok:false,error:'Fresh unconsumed owner attendance is required'};
  const at=now(),a=job.attendance,s=inspect(job);
  if(!Number.isFinite(at)||at<a.ready_at||at>a.expires_at||s.error||!s.owned||s.serial!==a.serial||s.expected_package!==a.expected_package||
     s.cell!==job.anchorCell||Math.hypot(...s.position.map((n,i)=>n-a.anchor[i]))>100||s.game<job.lastGame||s.game-job.lastGame>1/1440)
   return {ok:false,error:'Owner attendance expired or changed before inventory commit'};
  return {ok:true,job,continuation:false};
 }
 return {
  reset(){for(const job of jobs.values()){
   hold(job,'Native session reset; elapsed work and permits are not restored');job.resetInvalidated=true;job.releaseRequested=true;
   if(job.effectsIssued!==false)job.effectsIssued=null;
   job.committed=false;delete job.inventory;job.worked=0;job.samples=0;
   if(job.attendance){job.attendance.worked_minutes=0;job.attendance.samples=0;}
  }desired=null;fresh=false;session=null;control=null;},
  reservedActors(){return [...jobs.values()].map(job=>job.actor);},
  ownsActor(actor){return [...jobs.values()].some(job=>job.actor===actor);},
  releasingActors(){return [...jobs.values()].filter(job=>job.releaseRequested||job.releaseVerified||job.session!==session).map(job=>job.actor);},
  holds(){return [...jobs.values()].filter(job=>!job.releaseRequested&&!job.releaseVerified&&job.session===session).map(job=>({id:job.job_id,actor:job.actor,slot:job.slot,intent:'owner_production',phase:'working'}));},
  permitsCommand(c){const row=identity(c),job=jobs.get(key(row));return c.kind==='inventory_self_produce_commit'&&valid(row)&&c.session===session&&
   !!job&&same(job,row)&&text(c.attendance_token)&&c.attendance_token===job.attendance?.token&&(!job.commitId||job.commitId===c.id&&job.commitSignature===signature(c));},
  attestsNoEffects(c){const row=identity(c),job=jobs.get(key(row));return c.kind==='inventory_self_produce_commit'&&valid(row)&&c.session===session&&
   !!job&&same(job,row)&&text(c.attendance_token)&&c.attendance_token===job.attendance?.token&&job.effectsIssued===false&&!job.commitId;},
  start(c,blockedActors=[]){
   const row=identity(c),fail=error=>({done:true,ack:{id:c.id,...row,status:'held',accepted:false,error,no_effects_issued:!jobs.has(key(row))&&!acknowledged.has(key(row))}});
   if(!valid(row)||c.session!==session||!current(row)||assignment(row)?.cancel_requested===true||assignment(row)?.phase==='held')return fail('Fresh matching owner-work assignment required');
   if(acknowledged.has(key(row)))return fail('Owner job was already acknowledged; no replay');
   const old=jobs.get(key(row));if(old){if(!same(old,row))return fail('Owner job identity changed');return {done:true,ack:{id:c.id,...row,status:'applied',accepted:true}};}
   if(!catalogBinding(row)||catalog?.status().available!==true)return fail('Exact recipe catalog and verified commodity forms required');
   if(!available()||jobs.size>=capacity)return fail('Configured owner-work capacity unavailable');
   if(blockedActors.includes(row.actor)||[...jobs.values()].some(job=>job.actor===row.actor||job.slot===row.slot||job.business_id===row.business_id))return fail('Owner actor, account, business or Citizens slot reserved');
   const citizen=control?.activities?.find(a=>a.actor===row.actor&&a.slot===row.slot);
   if(!citizen||!Number.isInteger(citizen.expectedPackage))return fail('Existing resident Citizens assignment required');
   const sample=inspect(row);if(sample.error)return fail(sample.error);
   jobs.set(key(row),{...row,phase:'acquiring',acceptedAt:now(),worked:0,samples:0,lastGame:null,attendance:null,
    effectsIssued:false,committed:false,releaseRequested:false,releaseVerified:false});
   return {done:true,ack:{id:c.id,...row,status:'applied',accepted:true}};
  },
  acknowledge(c){
   const row=identity(c),fail=error=>({done:true,ack:{id:c.id,...row,status:'held',acknowledged:false,error}});
   if(!valid(row)||c.session!==session)return fail('Current transport session and exact work identity required');
   const old=acknowledged.get(key(row));if(old){if(!same(old,row))return fail('Acknowledged owner identity changed');return {done:true,ack:{id:c.id,...row,status:'applied',acknowledged:true}};}
   const job=jobs.get(key(row));
   if(!job||!same(job,row)||!job.releaseVerified)return fail('Verified native release required before owner receipt acknowledgement');
   if(job.effectsIssued!==false&&!job.committed)return fail('Owner inventory effects remain unresolved; account reservation retained');
   acknowledged.set(key(row),row);jobs.delete(key(row));return {done:true,ack:{id:c.id,...row,status:'applied',acknowledged:true}};
  },
  authorizeCommit(c){const a=authorization(c);return {ok:a.ok,error:a.error,continuation:a.continuation,attendance:a.ok?copy(a.job.attendance):null};},
  beginCommit(c){
   const a=authorization(c);if(!a.ok)return {ok:false,error:a.error};
   if(a.continuation)return {ok:false,error:'Recipe command already consumed its attendance permit'};
   a.job.commitId=c.id;a.job.commitSignature=signature(c);a.job.effectsIssued=true;a.job.phase='committing_input';
   a.job.attendance.token_valid=false;
   return {ok:true,attendance:copy(a.job.attendance)};
  },
  commitProgress(c,phase){const a=authorization(c,true);if(a.ok)a.job.phase=phase;return a.ok;},
  commitVerified(c,inventory){const a=authorization(c,true);if(!a.ok)return false;
   a.job.committed=true;a.job.inventory=copy(inventory);a.job.phase='recipe_committed';a.job.releaseRequested=true;return true;},
  commitFailed(c,error){const job=jobs.get(key(identity(c)));if(job&&same(job,identity(c))&&(!job.commitId||job.commitId===c.id))hold(job,error);},
  tick(assignments,nativeSession,isFresh,citizens){
   if(session!==null&&session!==nativeSession)this.reset();session=nativeSession;desired=assignments;fresh=isFresh===true;control=citizens;
   capacity=Number.isInteger(assignments?.capacity)&&assignments.capacity>=1&&assignments.capacity<=128?assignments.capacity:4;
   // Cold restored jobs can clean up their exact slot but cannot reconstruct
   // labour or infer whether a pending native inventory call already ran.
   if(fresh&&Array.isArray(desired?.jobs))for(const item of desired.jobs){const row=identity(item);
    if(!valid(row)||jobs.has(key(row))||acknowledged.has(key(row))||[...jobs.values()].some(job=>job.slot===row.slot))continue;
    if(row.session===session&&(!item.phase||item.phase==='prepared'))continue;
    const noEffects=['prepared','running','acquiring','working','attendance_verified'].includes(item.phase);
    jobs.set(key(row),{...row,phase:'held',worked:0,samples:0,lastGame:null,attendance:null,effectsIssued:noEffects?false:null,
     committed:false,releaseRequested:true,releaseVerified:false,resetInvalidated:true,error:'Cold owner job has no surviving attendance or effect witness'});
   }
   for(const job of jobs.values()){
    if(job.releaseRequested){observeRelease(job);continue;}
    if(job.phase==='held')continue;
    const saved=assignment(job);
    if(!current(job)||saved?.cancel_requested===true||saved?.phase==='held'){hold(job,'Owner assignment withdrawn, stale or epoch changed');continue;}
    if(!catalogBinding(job)||catalog?.status().available!==true){hold(job,'Owner recipe catalog or native commodity binding changed');continue;}
    const elapsed=now()-job.acceptedAt;
    if(!Number.isFinite(elapsed)||elapsed<0||elapsed>Math.max(300000,job.work_minutes*60000)){hold(job,'Owner work lease elapsed or clock reversed');continue;}
    const s=inspect(job);
    if(s.error){hold(job,s.error);continue;}
    if(job.phase==='acquiring'){
     if(!s.owned){if(elapsed>30000)hold(job,'Owner self-target attendance not acquired within 30 seconds');continue;}
     job.attendance={token:null,slot:job.slot,serial:s.serial,expected_package:s.expected_package,anchor:s.position,
      worked_minutes:0,samples:0,ready_at:null,expires_at:null,token_valid:false};
     job.anchorCell=s.cell;job.phase='working';job.lastGame=null;
    }
    const a=job.attendance;
    if(!a||!s.owned||s.serial!==a.serial||s.expected_package!==a.expected_package||s.cell!==job.anchorCell||Math.hypot(...s.position.map((n,i)=>n-a.anchor[i]))>100){hold(job,'Owner stationary attendance interrupted');continue;}
    if(job.phase==='attendance_verified'){
     if(now()<a.ready_at||now()>a.expires_at){hold(job,'Owner attendance token expired before recipe commit');continue;}
    }
    if(job.lastGame!==null){const delta=s.game-job.lastGame;if(delta<0||delta>1/1440){hold(job,'Game clock jumped during owner attendance');continue;}
     if(job.phase==='working')job.worked+=delta*1440;
    }
    job.lastGame=s.game;
    if(job.phase==='working'){
     job.samples++;a.worked_minutes=job.worked;a.samples=job.samples;
     if(job.worked>=job.work_minutes&&job.samples>=2){job.phase='attendance_verified';a.ready_at=now();a.expires_at=now()+120000;
      a.token='owner-token-'+now().toString(36)+'-'+(++sequence)+'-'+Math.random().toString(36).slice(2);a.token_valid=true;
     }
    }
   }
  },
  status(){const economy=catalog?.status();return {available:available()&&economy?.available===true,catalog_hash:economy?.catalog_hash||null,recipe_hashes:economy?.recipe_hashes||{},capacity,citizens_capacity:128,epoch:desired?.epoch||null,session,
   jobs:[...jobs.values()].map(job=>({...identity(job),id:job.job_id,phase:job.phase,worked_minutes:job.worked,samples:job.samples,
    effects_issued:job.effectsIssued,committed_inventory_verified:job.committed,release_verified:job.releaseVerified,release_requested:job.releaseRequested===true})),
   receipts:[...jobs.values()].filter(job=>['attendance_verified','recipe_committed','complete','held'].includes(job.phase)).map(receipt),
   reserved_actors:this.reservedActors(),scope:'Observed stationary attendance; productive animation unverified; inventory commits are serialized separately'};}
 };
}
if(typeof module!=='undefined')module.exports={createOwnerWorkJobsController};
