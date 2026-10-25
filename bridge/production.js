// Explicit recipe: 1 observed grain + qualified labour -> 2 bread.
// Agreed wages and attendance are bounded enterprise policy, never model code.
// Native handles are acquired on each frame. No automatic resource replenishment.
function createProductionController(platform,now=Date.now){
 let active=null;const ownerCommits=new Map();
 const items={gold:0xf,bread:0x65c97,grain:0x4b0ba};
 const equal=(a,b)=>Object.keys(a).every(r=>b[r]&&Object.keys(items).every(k=>a[r][k]===b[r][k]));
 const clone=x=>JSON.parse(JSON.stringify(x));
 function ownerAttendance(sp,c){
  const a=c.attendance;
  if(!a||typeof a.id!=='string'||!a.id.startsWith('owner-work-')||a.id.length>75||
     !Number.isInteger(a.slot)||a.slot<0||a.slot>=128||!Number.isInteger(a.serial)||a.serial<1||a.serial>16777215)return false;
  try{
   const get=n=>sp.Game.getFormFromFile(0x800+a.slot*16+n,'WhiterunCitizens.esp');
   const quest=sp.Quest.from(get(0)),pkg=get(1),actors=sp.FormList.from(get(2)),targets=sp.FormList.from(get(3));
   const request=sp.GlobalVariable.from(get(4)),ack=sp.GlobalVariable.from(get(5)),status=sp.GlobalVariable.from(get(6));
   return quest.isRunning()&&pkg.getFormID()===c.expected_package&&actors.getSize()===1&&targets.getSize()===1&&
    actors.getAt(0)?.getFormID()===c.actor&&targets.getAt(0)?.getFormID()===c.actor&&
    request.getValue()===a.serial&&ack.getValue()===a.serial&&status.getValue()===1;
  }catch(_){return false;}
 }
 return {
  reset(){active=null;ownerCommits.clear();},
  status(){return active?{id:active.id,actor:active.actor,expectedPackage:active.package,ownedPackage:!['complete','held'].includes(active.phase)&&active.attendance?.package_owned===true,phase:active.phase,workedMinutes:Math.round(active.days*14400)/10,requiredMinutes:active.minutes,wageGold:active.wage,attendance:active.attendance||null}:null;},
  commitOwnerRecipe(c,workJobs){
   const identityKeys=['job_id','actor','actor_base_id','slot','session','epoch','business_id','business_revision','recipe_id','policy_version','work_minutes'];
   const identity=Object.fromEntries(identityKeys.map(k=>[k,c[k]]));
   const signature=JSON.stringify([identity,c.id,c.attendance_token,c.before,c.after]);
   let record=ownerCommits.get(c.id),authorized=false;
   const fail=error=>{
    const noEffects=!record&&workJobs?.attestsNoEffects?.(c)===true;
    if(authorized||noEffects||record?.signature===signature){if(record)record.phase='held';workJobs?.commitFailed(c,error);}
    return {done:true,ack:{id:c.id,...identity,commit_id:c.id,attendance_token:c.attendance_token,status:'held',error,
     effects_issued:record?record.inputIssued===true:noEffects?false:null,no_effects_issued:noEffects,
     committed_inventory_verified:false,release_verified:false}};
   };
   if(c.kind!=='inventory_self_produce_commit'||!workJobs||typeof workJobs.authorizeCommit!=='function')return fail('Independent owner commit authority required');
   const permit=workJobs.authorizeCommit(c);if(!permit.ok)return fail(permit.error);
   authorized=true;
   if(record&&record.signature!==signature)return fail('Owner commit payload changed');
   if(record?.phase==='held')return fail('Owner recipe is held; do not repeat issued effects');
   if(record?.receipt)return {done:true,ack:clone(record.receipt)};
   if(permit.continuation&&!record)return fail('Owner effect witness was lost; inventory states cannot authorize replay');
   if(!record&&([...ownerCommits.values()].some(other=>other.phase!=='complete')||active&&active.phase!=='complete'&&(active.phase!=='held'||active.sent)))
    return fail('Another production command owns the inventory writer');
   if(c.recipe_id!=='bread_recipe'||!c.before||!c.after||[c.before,c.after].some(v=>Object.keys(v).join(',')!=='owner')||
      [c.before.owner,c.after.owner].some(v=>!v||Object.keys(v).sort().join(',')!=='bread,gold,grain'||Object.values(v).some(n=>!Number.isSafeInteger(n)||n<0))||
      c.before.owner.grain<1||c.after.owner.gold!==c.before.owner.gold||c.after.owner.grain!==c.before.owner.grain-1||c.after.owner.bread!==c.before.owner.bread+2)
    return fail('Owner commit must consume one grain, produce two bread and conserve gold');
   const sp=platform(),actor=sp.Actor.from(sp.Game.getFormEx(c.actor));
   if(!actor?.is3DLoaded()||actor.isDead()||actor.isChild()||(actor.getActorBase?.()||actor.getBaseObject?.())?.getFormID()!==c.actor_base_id)
    return fail('Owner commit actor identity unavailable');
   const forms=Object.fromEntries(Object.entries(items).map(([k,id])=>[k,sp.Game.getFormEx(id)]));
   if(Object.values(forms).some(f=>!f))return fail('Owner recipe forms unavailable');
   const actual={owner:Object.fromEntries(Object.entries(forms).map(([k,f])=>[k,actor.getItemCount(f)]))};
   if(Object.values(actual.owner).some(n=>!Number.isSafeInteger(n)||n<0))return fail('Owner inventory observation invalid');
   const inputUsed=clone(c.before);inputUsed.owner.grain--;
   if(!record){
    // In particular, actual==after is NOT success without this command's own
    // surviving effect witness. No cold save or unrelated inventory may mint proof.
    if(!equal(actual,c.before))return fail('Fresh owner input inventory differs; no effects issued');
    const consumed=workJobs.beginCommit(c);if(!consumed.ok)return fail(consumed.error);
    record={signature,phase:'committing_input',inputIssued:true,inputObserved:false,outputIssued:false,outputObserved:false,issuedAt:now(),attendance:consumed.attendance};
    ownerCommits.set(c.id,record);
    try{actor.removeItem(forms.grain,1,true,null);}catch(_){return fail('Owner grain call failed after permit consumption; reconcile inventory');}
    return {done:false};
   }
   if(equal(actual,c.after)){
    if(!record.inputIssued||!record.inputObserved||!record.outputIssued)return fail('Owner output exists without this command issuing it');
    record.outputObserved=true;
    if(!workJobs.commitVerified(c,actual))return fail('Owner effect proof cannot be attached to current job');
    record.phase='complete';record.receipt={id:c.id,...identity,commit_id:c.id,attendance_token:c.attendance_token,status:'applied',
     inventory:actual,effects_issued:true,committed_inventory_verified:true,release_verified:false,mechanism:'native_owner_recipe',animation_verified:false,
     attendance:record.attendance,effect_witness:{input_issued:true,input_observed:true,output_issued:true,output_observed:true}};
    return {done:true,ack:clone(record.receipt)};
   }
   if(!Number.isFinite(now())||now()<record.issuedAt||now()-record.issuedAt>5000)return fail('Owner recipe effect observation timed out; do not repeat');
   if(equal(actual,inputUsed)){
    if(!record.inputIssued)return fail('Owner input changed without a recorded effect');
    record.inputObserved=true;
    if(!record.outputIssued){
     if(!workJobs.commitProgress(c,'committing_output'))return fail('Owner recipe continuation no longer authorized');
     record.outputIssued=true;record.phase='committing_output';record.issuedAt=now();
     try{actor.addItem(forms.bread,2,true);}catch(_){return fail('Owner bread call failed after issue; reconcile inventory');}
    }
    return {done:false};
   }
   if(equal(actual,c.before)&&record.inputIssued&&!record.inputObserved&&!record.outputIssued)return {done:false};
   return fail('Owner inventory drifted during serialized recipe; reconciliation required');
  },
  step(c){
   if([...ownerCommits.values()].some(record=>record.phase!=='complete'))return {done:true,ack:{id:c.id,status:'held',no_effects_issued:true,error:'Independent owner recipe owns the inventory writer'}};
   const sp=platform(),fail=error=>{if(active?.id===c.id)active.phase='held';return {done:true,ack:{id:c.id,status:'held',error,work:this.status(),no_effects_issued:!!active&&active.id===c.id&&!active.sent}};};
   const own=c.kind==='inventory_self_produce',roles=own?['owner']:['worker','employer'],producer=own?'owner':'employer';
   if(!c.before||!c.after||[c.before,c.after].some(v=>Object.keys(v).sort().join(',')!==[...roles].sort().join(','))||!roles.every(r=>c.before[r]&&c.after[r]&&Object.keys(items).every(k=>Number.isInteger(c.before[r][k])&&c.before[r][k]>=0&&Number.isInteger(c.after[r][k])&&c.after[r][k]>=0)))return fail('Invalid production inventory contract');
   const supply=c.kind==='inventory_supply',expected=clone(c.before),wage=own?0:c.wage_gold===undefined?2:c.wage_gold;
   if(supply){expected.employer.grain+=2;}
   else{
    if(!['inventory_produce','inventory_self_produce'].includes(c.kind)||!Number.isInteger(c.work_minutes)||c.work_minutes<5||c.work_minutes>120||!Number.isInteger(wage)||wage<(own?0:1)||wage>20||!Number.isInteger(c.expected_package)||c.expected_package<=0||c.before[producer].grain<1||c.before[producer].gold<wage)return fail('Invalid work terms');
    if(own&&(!Number.isInteger(c.actor)||c.actor<=0||!Array.isArray(c.anchor)||c.anchor.length!==3||!c.anchor.every(Number.isFinite)||c.wage_gold!==undefined))return fail('Invalid owner work terms');
    expected[producer].grain--;expected[producer].bread+=2;
    if(!own){expected.employer.gold-=wage;expected.worker.gold+=wage;}
   }
   if((!own&&c.worker===c.employer)||!equal(expected,c.after))return fail('Invalid recipe or wage effect');
   const worker=sp.Actor.from(sp.Game.getFormEx(own?c.actor:c.worker)),employer=own?worker:sp.Actor.from(sp.Game.getFormEx(c.employer));
   if(!worker||!employer||[worker,employer].some(a=>!a.is3DLoaded()||a.isDead()||a.isChild()))return fail('Work participants unavailable');
   const forms=Object.fromEntries(Object.entries(items).map(([k,id])=>[k,sp.Game.getFormEx(id)]));
   if(Object.values(forms).some(f=>!f))return fail('Recipe forms unavailable');
   const read=a=>Object.fromEntries(Object.entries(forms).map(([k,f])=>[k,a.getItemCount(f)]));
   const actual=own?{owner:read(worker)}:{worker:read(worker),employer:read(employer)};
   if(equal(actual,c.after)){if(active?.id===c.id)active.phase='complete';return {done:true,ack:{id:c.id,status:'applied',inventory:actual,work:this.status(),mechanism:supply?'explicit_demo_import':own?'native_owner_recipe':'native_recipe_and_wage',animation_verified:false}};}
   if(!active||active.id!==c.id)active={id:c.id,actor:own?c.actor:c.worker,package:c.expected_package,phase:supply?'importing':'working',days:0,lastGame:null,sent:null,at:now(),minutes:c.work_minutes,wage};
   const inputUsed=clone(c.before);inputUsed[producer].grain--;
   const outputMade=clone(inputUsed);outputMade[producer].bread+=2;
   const stage=equal(actual,c.before)?'before':!supply&&equal(actual,inputUsed)?'input':!supply&&equal(actual,outputMade)?'output':'unexpected';
   if(stage==='unexpected')return fail('Unexpected inventory during work; reconciliation required');
   if(active.sent&&now()-active.sent.at>5000)return fail('Production effect timed out; no repeated attempt');
   const issue=(leg,fn)=>{if(!active.sent||active.sent.leg!==leg){active.sent={leg,at:now()};fn();}};
   if(supply){issue('import',()=>employer.addItem(forms.grain,2,true));return {done:false};}
   if(stage==='input'){active.phase='making_output';issue('output',()=>employer.addItem(forms.bread,2,true));return {done:false};}
   if(stage==='output'){active.phase='paying_wage';issue('wage',()=>employer.removeItem(forms.gold,wage,true,worker));return {done:false};}
   // Once input use is issued, don't reinterpret an asynchronous wait as new labour.
   if(active.sent)return {done:false};
   const pkg=worker.getCurrentPackage();
   const target=own?c.anchor:[employer.getPositionX(),employer.getPositionY(),employer.getPositionZ()];
   const gap=Math.hypot(worker.getPositionX()-target[0],worker.getPositionY()-target[1],worker.getPositionZ()-target[2]);
   active.attendance={distance:gap,package_owned:!!pkg&&pkg.getFormID()===c.expected_package,
     ...(own?{stationary_lease_verified:ownerAttendance(sp,c),hold_id:c.attendance?.id,slot:c.attendance?.slot,serial:c.attendance?.serial}:{})};
   if(own&&!active.attendance.stationary_lease_verified)return fail('Owned stationary work mailbox is not verified');
   if(!active.attendance.package_owned)return fail('Owned work attendance interrupted');
   if(!Number.isFinite(gap))return fail('Invalid work attendance distance');
   // A moving employer may briefly pull ahead. Only nearby attendance earns
   // work credit; travel time is discarded and the catch-up window is bounded.
   if(gap>(own?100:300)){
    active.phase='approaching_work';active.lastGame=null;
    if(active.absentSince===undefined)active.absentSince=now();
    if(now()-active.absentSince>30000)return fail('Work attendance did not resume within 30 seconds');
    return {done:false};
   }
   delete active.absentSince;active.phase='working';
   if(!sp.Utility||typeof sp.Utility.getCurrentGameTime!=='function')return fail('Game clock unavailable');
   const game=sp.Utility.getCurrentGameTime();
   if(!Number.isFinite(game))return fail('Invalid game clock');
   if(active.lastGame!==null){
    const delta=game-active.lastGame;
    // Clock jumps (waiting/loading) are not performed labour. Paused time adds zero.
    if(delta<0||delta>1/1440)return fail('Game clock jumped during work');
    active.days+=delta;
   }
   active.lastGame=game;
   if(active.days>=c.work_minutes/1440){active.phase='using_input';issue('input',()=>employer.removeItem(forms.grain,1,true,null));}
   return {done:false};
  }
 };
}
if(typeof module!=='undefined')module.exports={createProductionController};
