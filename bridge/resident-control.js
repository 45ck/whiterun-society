// Persistent low-priority agent continuity; short interactions own priority 95.
// This controller owns only WhiterunCitizens.esp quests. No native quest stops.
function createResidentControl(platform,now=Date.now){
 const file='WhiterunCitizens.esp',capacity=128;let activities=new Map(),recover=true,lastTick=-Infinity,active=false,error=null;
 function records(slot){const sp=platform(),get=n=>sp.Game.getFormFromFile?.(0x800+slot*16+n,file);return {sp,quest:sp.Quest?.from(get(0)),pkg:get(1),actor:sp.FormList?.from(get(2)),target:sp.FormList?.from(get(3)),request:sp.GlobalVariable?.from(get(4)),ack:sp.GlobalVariable?.from(get(5)),status:sp.GlobalVariable?.from(get(6)),pulse:sp.GlobalVariable?.from(get(7))};}
 function available(){try{const r=records(0),last=records(capacity-1);return !!(r.quest&&r.pkg&&r.pulse&&last.quest&&last.pulse);}catch(_){return false;}}
 function release(){if(!available())return;for(let slot=0;slot<capacity;slot++){const r=records(slot);if(r.quest?.isRunning())r.quest.stop();}activities.clear();active=false;}
 function validate(control){const rows=Object.values(control?.assignments||{});if(rows.length>capacity)throw Error('Continuity capacity exceeded');const slots=new Set(),actors=new Set();for(const row of rows){if(!Number.isInteger(row.actor)||row.actor<=0||!Number.isInteger(row.slot)||row.slot<0||row.slot>=capacity||!['await_decision','go_to'].includes(row.mode)||slots.has(row.slot)||actors.has(row.actor))throw Error('Invalid continuity assignment');if(row.mode==='go_to'&&(!Number.isInteger(row.target)||row.target<=0||row.target===row.actor||typeof row.goal_id!=='string'||row.goal_id.length>128))throw Error('Invalid standing destination');slots.add(row.slot);actors.add(row.actor);}return rows;}
 function sameSpace(a,b){const ac=a.getParentCell?.(),bc=b.getParentCell?.();if(!ac||!bc)return false;if(ac.getFormID()===bc.getFormID())return true;const aw=a.getWorldSpace?.(),bw=b.getWorldSpace?.();return ac.isInterior()===false&&bc.isInterior()===false&&!!aw&&!!bw&&aw.getFormID()===bw.getFormID();}
 return {
  reset(){activities.clear();recover=true;active=false;lastTick=-Infinity;error=null;},
  release,
  // Checkpoint writes may overlap many arrivals. Keep existing leases alive
  // without rebinding actors to a policy that has not committed yet.
  renew(residents,fresh){
   if(!fresh){if(active)release();return;}
   for(const a of activities.values()){
    if(a.phase==='failed'||a.loaded===false)continue;
    const row=residents.find(x=>x.id===a.actor&&x.isPerson===true);
    if(!row)continue;
    const r=records(a.slot),actor=r.sp.Actor.from(r.sp.Game.getFormEx(a.actor));
    if(!actor?.is3DLoaded()||nativeActivityBlocker(observeNativeActivity(actor)))continue;
    if(r.quest.isRunning()&&r.status.getValue()===1&&r.request.getValue()===a.serial&&r.ack.getValue()===a.serial&&
       r.actor.getSize()===1&&r.target.getSize()===1&&r.actor.getAt(0)?.getFormID()===a.actor&&r.target.getAt(0)?.getFormID()===a.target)
     r.pulse.setValue((r.pulse.getValue()%16777215)+1);
   }
  },
  status(){return {available:available(),goal_destinations:true,enabled:active,capacity,error,activities:Array.from(activities.values()).map(a=>({...a,phase:a.loaded===false?'unloaded':a.blocker?'blocked':a.phase}))};},
  tick(control,residents,fresh,foreground=[],publicSites=[]){
   if(now()-lastTick<250)return;lastTick=now();
   if(!available())return;
   if(recover){release();recover=false;return;}
   if(!fresh||!control?.enabled){if(active)release();return;}
   let rows;try{rows=validate(control);}catch(e){release();error=String(e);return;}
   error=null;active=true;const desired=new Set(rows.map(r=>r.actor));
   for(const [actor,a] of activities){if(!desired.has(actor)){const r=records(a.slot);if(r.quest.isRunning())r.quest.stop();activities.delete(actor);}}
   for(const row of rows){
    const loaded=residents.find(r=>r.id===row.actor&&r.isPerson===true),r=records(row.slot);
    let a=activities.get(row.actor);
    if(a&&a.slot!==row.slot){release();error='Resident slot changed during an active policy';return;}
    const targetId=row.mode==='go_to'?row.target:row.actor;
    if(a&&(a.target!==targetId||a.goal_id!==row.goal_id||a.mode!==row.mode)){if(r.quest.isRunning())r.quest.stop();activities.delete(row.actor);a=null;}
    if(!loaded){if(a){a.ownedPackage=null;a.loaded=false;}continue;}
    const actor=r.sp.Actor.from(r.sp.Game.getFormEx(row.actor));if(!actor?.is3DLoaded()||actor.isDead()||actor.isChild())continue;
    if(!a){a={actor:row.actor,slot:row.slot,mode:row.mode,target:targetId,goal_id:row.goal_id,loaded:true,phase:'resetting',expectedPackage:r.pkg.getFormID(),ownedPackage:false,began:now(),source:row.source||'deterministic continuity while awaiting a resident decision'};activities.set(row.actor,a);if(r.quest.isRunning())r.quest.stop();continue;}
    if(a.loaded===false){a.loaded=true;a.phase='resetting';if(r.quest.isRunning())r.quest.stop();}
    try{
     if(a.phase==='failed')continue;
     const destination=row.mode==='go_to'?r.sp.ObjectReference?.from(r.sp.Game.getFormEx(targetId)):actor;
     if(row.mode==='go_to'&&(!publicSites.some(p=>p.id===targetId)||!destination||destination.isDisabled?.()!==false||!sameSpace(actor,destination)))throw Error('Standing destination is no longer a valid public place');
     const current=actor.getCurrentPackage();a.enginePackage=current?.getFormID()||0;a.ownedPackage=a.enginePackage===a.expectedPackage;
     const blocker=nativeActivityBlocker(observeNativeActivity(actor));
     if(blocker){a.blocker=blocker;a.reason=blocker;a.movingSince=null;continue;}
     if(a.blocker){a.blocker=null;if(!r.quest.isRunning()){a.phase='resetting';a.began=now();}}
     a.reason=null;
     if(a.phase==='resetting'){
      if(r.quest.isRunning())continue;
      const serial=Math.max(r.request.getValue(),r.ack.getValue());if(!Number.isInteger(serial)||serial<0||serial>=16777215)throw Error('Invalid continuity serial');
      r.actor.revert();r.target.revert();r.actor.addForm(actor);r.target.addForm(destination);a.serial=serial+1;a.phase='mailbox';a.began=now();continue;
     }
     const matches=()=>r.actor.getSize()===1&&r.target.getSize()===1&&r.actor.getAt(0)?.getFormID()===row.actor&&r.target.getAt(0)?.getFormID()===targetId;
     if(a.phase==='mailbox'){
      if(!matches()){if(now()-a.began>5000)throw Error('Continuity mailbox not observed');continue;}
      r.status.setValue(0);r.request.setValue(a.serial);r.pulse.setValue((r.pulse.getValue()%16777215)+1);const started=r.quest.start();a.phase='binding';a.began=now();if(started&&typeof started.then==='function')started.then(ok=>{if(!ok)a.startFailed=true;},()=>{a.startFailed=true;});else if(started===false)a.startFailed=true;continue;
     }
     if(a.phase==='binding'){
      if(a.startFailed)throw Error('Continuity quest refused to start');
      if(r.ack.getValue()!==a.serial){if(now()-a.began>15000)throw Error('Continuity binding timed out');continue;}
      if(r.status.getValue()!==1||!matches())throw Error('Continuity references rejected');
      actor.evaluatePackage();a.phase='acquiring';a.began=now();
     }
     if(a.phase==='failed')continue;
     if(!r.quest.isRunning()||!matches()||r.request.getValue()!==a.serial||r.ack.getValue()!==a.serial||r.status.getValue()!==1){a.lease_diagnostic={running:r.quest.isRunning(),status:r.status.getValue(),request:r.request.getValue(),ack:r.ack.getValue(),mailbox_matches:matches()};throw Error('Continuity lease changed');}
     r.pulse.setValue((r.pulse.getValue()%16777215)+1);
     if(foreground.includes(row.actor)){a.phase='interaction_priority';a.began=now();a.movingSince=null;}
     else if(a.ownedPackage){
      a.phase='holding';a.last_owned_at=now();
      if(row.mode==='go_to'){
       a.distance=Math.hypot(actor.getPositionX()-destination.getPositionX(),actor.getPositionY()-destination.getPositionY(),actor.getPositionZ()-destination.getPositionZ());
       if(!Number.isFinite(a.distance))throw Error('Invalid destination coordinates');
       a.movingSince=a.movingSince??now();a.phase=a.distance<=200?'arrived':'travelling';
       if(a.phase==='travelling'&&now()-a.movingSince>180000)throw Error('Standing journey exceeded its time limit');
      }
     }
     else if(now()-a.began>15000){if(row.mode==='go_to')throw Error('Standing journey package was not acquired');a.phase='package_not_acquired';a.reason='Another package owns the actor';}
    }catch(e){if(r.quest.isRunning())r.quest.stop();a.phase='failed';a.error=String(e);a.ownedPackage=false;}
   }
  }
 };
}
if(typeof module!=='undefined')module.exports={createResidentControl};
