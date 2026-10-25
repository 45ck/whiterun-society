// Paid labour owns its own live attendance, settlement permit and effect journal.
// Native handles never survive a call; inventory appearances never recreate proof.
function createPaidEmploymentController(platform,now=Date.now,options={}){
 const catalog=options.catalog||(typeof module!=='undefined'?require('./economy-catalog.js').createEconomyCatalogController(platform):null);
 const fields=['protocol','job_id','worker','worker_base_id','employer','employer_base_id','slot','session','epoch','business_id','business_revision','recipe_id','catalog_hash','recipe_hash','terms_hash','consent_hash','work_minutes','wage_gold','currency','expected_package','anchor','cell_id','before','after'];
 const jobs=new Map(),acknowledged=new Map();let session=null,desired=null,control=null,fresh=false,capacity=4,sequence=0;
 const copy=x=>JSON.parse(JSON.stringify(x)),text=x=>typeof x==='string'&&x.length>0&&x.length<=160;
 const uint=x=>Number.isInteger(x)&&x>0&&x<=0xffffffff,amount=x=>Number.isSafeInteger(x)&&x>=0&&x<=2147483647;
 const digest=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
 const canonical=x=>JSON.stringify(x&&typeof x==='object'?Array.isArray(x)?x.map(v=>JSON.parse(canonical(v))):Object.fromEntries(Object.keys(x).sort().map(k=>[k,JSON.parse(canonical(x[k]))])):x);
 const identity=c=>Object.fromEntries(fields.map(k=>[k,c[k]]));
 const signature=c=>canonical(identity(c));
 const same=(a,b)=>{try{return signature(a)===signature(b);}catch(_){return false;}};
 const key=c=>JSON.stringify([c.session,c.epoch,c.job_id]);
 const newEpoch=()=>`paid-${now().toString(36)}-${++sequence}-${Math.random().toString(36).slice(2)}`;
 let epoch=newEpoch();
 function valid(c){
  if(!c||typeof c!=='object'||Array.isArray(c))return false;
  const names=catalog?.itemIds()||[],recipe=catalog?.recipe(c.recipe_id),binding=catalog?.identity(c.recipe_id);
  if(c.protocol!==2||!text(c.job_id)||c.job_id.length>64||!text(c.session)||!text(c.epoch)||!text(c.business_id)||!text(c.recipe_id)||
    ![c.worker,c.worker_base_id,c.employer,c.employer_base_id,c.expected_package,c.cell_id].every(uint)||c.worker===c.employer||
    !Number.isInteger(c.slot)||c.slot<0||c.slot>=128||!Number.isInteger(c.business_revision)||c.business_revision<0||
    ![c.catalog_hash,c.recipe_hash,c.terms_hash,c.consent_hash].every(digest)||!binding||binding.catalog_hash!==c.catalog_hash||binding.recipe_hash!==c.recipe_hash||
    !Number.isInteger(c.work_minutes)||c.work_minutes<recipe.work_minutes.minimum||c.work_minutes>recipe.work_minutes.maximum||
    !amount(c.wage_gold)||c.wage_gold<1||!catalog.commodities().some(item=>item.id===c.currency&&item.currency===true)||
    !Array.isArray(c.anchor)||c.anchor.length!==3||!c.anchor.every(Number.isFinite))return false;
  for(const accounts of [c.before,c.after]){
   if(!accounts||Object.keys(accounts).sort().join('|')!=='employer|worker')return false;
   for(const role of ['employer','worker'])if(!accounts[role]||Object.keys(accounts[role]).sort().join('|')!==names.join('|')||!names.every(n=>amount(accounts[role][n])))return false;
  }
  const expected=copy(c.before);
  for(const [item,n] of Object.entries(recipe.inputs))expected.employer[item]-=n;
  for(const [item,n] of Object.entries(recipe.outputs))expected.employer[item]+=n;
  expected.employer[c.currency]-=c.wage_gold;expected.worker[c.currency]+=c.wage_gold;
  return Object.values(expected).every(account=>Object.values(account).every(amount))&&canonical(expected)===canonical(c.after);
 }
 function records(slot){const sp=platform(),get=n=>sp.Game.getFormFromFile?.(0x800+slot*16+n,'WhiterunCitizens.esp');
  return {sp,quest:sp.Quest?.from(get(0)),pkg:get(1),actors:sp.FormList?.from(get(2)),targets:sp.FormList?.from(get(3)),
   request:sp.GlobalVariable?.from(get(4)),ack:sp.GlobalVariable?.from(get(5)),status:sp.GlobalVariable?.from(get(6))};}
 function available(){try{return catalog?.status().available===true&&[0,127].every(slot=>{const r=records(slot);return r.quest&&r.pkg&&r.actors&&r.targets&&r.request&&r.ack&&r.status;});}catch(_){return false;}}
 function actors(c){const sp=platform(),out={};for(const role of ['worker','employer']){
  const a=sp.Actor.from(sp.Game.getFormEx(c[role]));
  if(!a?.is3DLoaded()||a.isDead()||a.isChild()||(a.getActorBase?.()||a.getBaseObject?.())?.getFormID?.()!==c[role+'_base_id'])throw Error('Paid participant identity or availability changed');
  out[role]=a;
 }return out;}
 function accounts(c){const resolved=catalog.resolve();if(!resolved.available)throw Error('Paid catalog native forms unavailable');
  const a=actors(c),inventory={};for(const role of ['worker','employer']){
   inventory[role]=Object.fromEntries(catalog.itemIds().map(item=>[item,a[role].getItemCount(resolved.forms[item])]));
   if(!Object.values(inventory[role]).every(amount))throw Error('Paid inventory observation invalid');
  }return {inventory,actors:a,forms:resolved.forms};}
 function assignment(c){return desired?.jobs?.find(row=>same(row,c));}
 const current=c=>fresh&&c.session===session&&c.epoch===epoch&&desired?.epoch===epoch&&!!assignment(c);
 function inspect(c){
  const r=records(c.slot),a=actors(c).worker;
  if(typeof a.isInCombat!=='function'||a.isInCombat()||typeof a.getCurrentScene!=='function'||a.getCurrentScene()||typeof a.getSleepState!=='function'||a.getSleepState()!==0)throw Error('Worker native activity unsafe or unknown');
  const position=[a.getPositionX(),a.getPositionY(),a.getPositionZ()],game=r.sp.Utility?.getCurrentGameTime?.(),cell=a.getParentCell?.()?.getFormID?.();
  if(!position.every(Number.isFinite)||!Number.isFinite(game)||game<0||cell!==c.cell_id||Math.hypot(...position.map((n,i)=>n-c.anchor[i]))>100)throw Error('Worker anchor, cell or game clock changed');
  const serial=r.request?.getValue(),row=control?.activities?.find(row=>row.actor===c.worker&&row.slot===c.slot),hold='paid-work-'+c.job_id;
  const owned=uint(serial)&&serial<=16777215&&r.quest?.isRunning()&&r.pkg?.getFormID()===c.expected_package&&a.getCurrentPackage()?.getFormID()===c.expected_package&&
   r.actors?.getSize()===1&&r.targets?.getSize()===1&&r.actors.getAt(0)?.getFormID()===c.worker&&r.targets.getAt(0)?.getFormID()===c.worker&&
   r.ack?.getValue()===serial&&r.status?.getValue()===1&&row?.work_hold_id===hold&&row.goal_id===hold&&row.mode==='await_decision'&&row.target===c.worker;
  return {owned,serial,game};
 }
 function hold(job,error){job.phase='held';job.error=error;if(job.effects_issued===false)job.release_requested=true;if(job.attendance)job.attendance.token_valid=false;}
 function release(job){
  try{const r=records(job.slot),a=actors(job).worker,serial=job.attendance?.serial;
   const exact=uint(serial)&&r.pkg?.getFormID()===job.expected_package&&r.actors?.getSize()===1&&r.targets?.getSize()===1&&
    r.actors.getAt(0)?.getFormID()===job.worker&&r.targets.getAt(0)?.getFormID()===job.worker&&r.request?.getValue()===serial&&r.ack?.getValue()===serial;
   if(r.quest?.isRunning()&&exact)r.quest.stop();
   job.release_verified=!!r.quest&&!r.quest.isRunning()&&a.getCurrentPackage()?.getFormID()!==job.expected_package;
   if(job.release_verified&&job.effects_verified&&!job.invalidated)job.phase='complete';
  }catch(_){job.release_verified=false;}
 }
 function receipt(job){return {...copy(identity(job)),phase:job.phase,attendance:job.attendance?copy(job.attendance):null,
  commit_id:job.commit_id||null,attendance_token:job.attendance?.token||null,effects_issued:job.effects_issued,
  no_effects_issued:job.effects_issued===false,output_verified:job.output_verified===true,wage_debit_verified:job.wage_debit_verified===true,
  wages_verified:job.wages_verified===true,effects_verified:job.effects_verified===true,release_verified:job.release_verified===true,
  release_requested:job.release_requested===true,legs:copy(job.legs||[]),inventory:job.inventory?copy(job.inventory):null,error:job.error||null,
  animation_verified:false,mechanism:'native_paid_employment_v2'};}
 function live(job){if(!current(job)||job.invalidated||assignment(job)?.cancel_requested||assignment(job)?.phase==='held'||!valid(job))throw Error('Paid assignment withdrawn, changed or stale');
  const s=inspect(job),a=job.attendance,at=now();
  if(!a||!s.owned||s.serial!==a.serial||!Number.isFinite(at)||at<a.ready_at||at>a.expires_at||job.lastGame===null||s.game<job.lastGame||s.game-job.lastGame>1/1440)throw Error('Paid attendance token expired or exact lease changed');
 }
 function makeLegs(c){const recipe=catalog.recipe(c.recipe_id),definitions=[
  ...Object.entries(recipe.inputs).map(([item,n])=>['input','employer',item,-n]),
  ...Object.entries(recipe.outputs).map(([item,n])=>['output','employer',item,n]),
  ['wage_debit','employer',c.currency,-c.wage_gold],['wage_credit','worker',c.currency,c.wage_gold]];
  let stage=copy(c.before);return definitions.map(([leg,role,item,delta])=>{const before=copy(stage);stage[role][item]+=delta;
   return {leg,role,item,amount:Math.abs(delta),issued:false,observed:false,before,after:copy(stage)};});}
 return {
  reset(){for(const job of jobs.values()){hold(job,'Native reset invalidated live paid permits; reconcile existing effects');job.invalidated=true;
   if(job.effects_issued!==false)job.effects_issued=null;job.effects_verified=false;job.release_requested=true;}
   epoch=newEpoch();acknowledged.clear();desired=null;session=null;fresh=false;control=null;},
  reservedActors(){return [...new Set([...jobs.values()].flatMap(j=>[j.worker,j.employer]))];},
  ownsActor(actor){return this.reservedActors().includes(actor);},
  releasingActors(){return [...jobs.values()].filter(j=>j.release_requested).map(j=>j.worker);},
  holds(){return [...jobs.values()].filter(j=>!j.release_requested&&!j.release_verified&&!j.invalidated&&j.session===session&&j.phase!=='held').map(j=>({id:j.job_id,actor:j.worker,actor_base_id:j.worker_base_id,slot:j.slot,intent:'paid_employment',phase:'working'}));},
  permitsCommand(c){const job=jobs.get(key(c));return !!job&&same(job,c)&&c.session===session&&c.epoch===epoch&&['paid_work_start','paid_work_ack_receipt','inventory_paid_work_commit'].includes(c.kind)&&
   (c.kind!=='inventory_paid_work_commit'||c.attendance_token===job.attendance?.token&&(!job.commit_id||job.commit_id===c.id&&job.commit_signature===canonical([signature(c),c.id,c.attendance_token])));},
  start(c,blockedActors=[]){
   // A valid rejected contract must remain attributable so the service can
   // quarantine it instead of repeatedly dispatching its prepared start.
   // Attribution is not evidence that an older process issued no effects.
   const fail=error=>{let pins={};try{if(valid(c))pins=copy(identity(c));}catch(_){}
    return {done:true,ack:{...pins,id:c?.id,status:'held',accepted:false,error,effects_issued:null,no_effects_issued:false}};};
   try{
    if(c.kind!=='paid_work_start'||!text(c.id)||!valid(c)||!current(c)||assignment(c)?.phase==='held'||assignment(c)?.cancel_requested)return fail('Fresh exact paid assignment required');
    if(acknowledged.has(key(c)))return fail('Paid job already acknowledged; no replay');
    const old=jobs.get(key(c));if(old){actors(c);return same(old,c)&&!old.invalidated&&old.phase!=='held'?{done:true,ack:{id:c.id,...copy(identity(old)),status:'applied',accepted:true}}:fail('Paid job identity changed or is held');}
    if(!available()||jobs.size>=capacity||[...jobs.values()].some(j=>[j.worker,j.employer].some(id=>[c.worker,c.employer].includes(id))||j.slot===c.slot||j.business_id===c.business_id)||blockedActors.some(id=>[c.worker,c.employer].includes(id)))return fail('Paid participants, business, slot or capacity reserved');
    const row=control?.activities?.find(row=>row.actor===c.worker&&row.slot===c.slot);
    if(row?.expectedPackage!==c.expected_package)throw Error('Existing worker Citizens slot required');
    inspect(c);if(canonical(accounts(c).inventory)!==canonical(c.before))throw Error('Paid start account balances changed');
    const job={...copy(identity(c)),phase:'acquiring',accepted_at:now(),lastGame:null,worked:0,samples:0,attendance:null,effects_issued:false,legs:[],release_requested:false,release_verified:false};
    jobs.set(key(c),job);return {done:true,ack:{id:c.id,...copy(identity(job)),status:'applied',accepted:true}};
   }catch(e){return fail(String(e.message||e));}
  },
  commit(c){
   const job=jobs.get(key(c)),exact=!!job&&same(job,c),fail=error=>{
    if(exact){hold(job,error);try{job.inventory=accounts(job).inventory;}catch(_){job.inventory=null;}}
    return {done:true,ack:{...(exact?receipt(job):{}),id:c.id,status:'held',error,...(!exact?{effects_issued:null,no_effects_issued:false}:{} )}};
   };
   try{
    if(c.kind!=='inventory_paid_work_commit'||!text(c.id)||c.commit_id!==c.id||!valid(c)||!exact||c.session!==session||c.epoch!==epoch||job.invalidated||job.phase==='held'||c.attendance_token!==job.attendance?.token)return fail('Exact live paid settlement permit required');
    const sig=canonical([signature(c),c.id,c.attendance_token]);
    if(job.commit_id&&job.commit_signature!==sig)return fail('Paid token bound to another settlement command');
    // Completed duplicates require unchanged identities and accounts, not a stale ID cache.
    if(job.effects_verified){if(!current(job))return fail('Paid completed assignment is stale');actors(job);if(canonical(accounts(job).inventory)!==canonical(job.after))return fail('Paid completed accounts changed');return {done:true,ack:{...receipt(job),id:c.id,status:'applied'}};}
    live(job);
    if(!job.commit_id){
     if(job.phase!=='attendance_verified'||job.effects_issued!==false)throw Error('Unconsumed paid attendance required');
     if([...jobs.values()].some(j=>j!==job&&j.commit_id&&!j.effects_verified))throw Error('Another paid settlement owns the inventory writer');
     if(canonical(accounts(job).inventory)!==canonical(job.before))throw Error('Paid accounts changed before first issued effect');
     job.commit_id=c.id;job.commit_signature=sig;job.attendance.token_valid=false;job.legs=makeLegs(job);
    }
    const read=accounts(job);job.inventory=read.inventory;
    const leg=job.legs.find(l=>!l.observed);
    if(leg.issued){
     if(canonical(read.inventory)===canonical(leg.after)){
      leg.observed=true;if(leg.leg==='output')job.output_verified=true;if(leg.leg==='wage_debit')job.wage_debit_verified=true;if(leg.leg==='wage_credit')job.wages_verified=true;
     }else if(canonical(read.inventory)!==canonical(leg.before))throw Error('Paid account drift during issued leg');
     else if(!Number.isFinite(now())||now()<leg.issued_at||now()-leg.issued_at>5000)throw Error('Paid issued leg observation timed out');
     else return {done:false};
    }
    const next=job.legs.find(l=>!l.observed);
    if(!next){job.effects_verified=true;job.phase='effects_verified';job.release_requested=true;return {done:true,ack:{...receipt(job),id:c.id,status:'applied'}};}
    if(canonical(read.inventory)!==canonical(next.before))throw Error('Paid stage balances differ from frozen contract');
    // Persist the call witness in this live journal BEFORE crossing the native boundary.
    next.issued=true;next.issued_at=now();job.effects_issued=true;job.phase='committing_'+next.leg;
    const target=read.actors[next.role],form=read.forms[next.item];
    if(['input','wage_debit'].includes(next.leg))target.removeItem(form,next.amount,true,null);else target.addItem(form,next.amount,true);
    return {done:false};
   }catch(e){return fail(String(e.message||e));}
  },
  acknowledge(c){const job=jobs.get(key(c)),old=acknowledged.get(key(c));
   const fail=error=>({done:true,ack:{id:c.id,status:'held',acknowledged:false,error}});
   if(c.kind!=='paid_work_ack_receipt'||!valid(c)||c.session!==session||c.epoch!==epoch)return fail('Exact current paid receipt identity required');
   if(old)return same(old,c)?{done:true,ack:{...copy(identity(old)),id:c.id,status:'applied',acknowledged:true}}:fail('Acknowledged contract changed');
   if(!job||!same(job,c)||job.invalidated||!job.release_verified||(!job.effects_verified&&job.effects_issued!==false))return fail('Verified paid effects or known no-effects and exact release required');
   // Re-observe release; an old receipt cannot free a replaced actor/account.
   release(job);if(!job.release_verified)return fail('Paid release identity or package changed before acknowledgement');
   try{if(job.effects_verified&&canonical(accounts(job).inventory)!==canonical(job.after))return fail('Paid accounts changed before acknowledgement');}catch(e){return fail(String(e.message||e));}
   acknowledged.set(key(c),copy(identity(job)));jobs.delete(key(c));return {done:true,ack:{id:c.id,...copy(identity(job)),status:'applied',acknowledged:true}};
  },
  tick(assignments,nativeSession,isFresh,citizens){
   if(session!==null&&session!==nativeSession)this.reset();session=nativeSession;desired=assignments;fresh=isFresh===true;control=citizens;
   capacity=Number.isInteger(assignments?.capacity)&&assignments.capacity>=1&&assignments.capacity<=128?assignments.capacity:4;
   if(fresh&&Array.isArray(assignments?.jobs))for(const c of assignments.jobs){
    if(!valid(c)||jobs.has(key(c))||acknowledged.has(key(c))||c.phase==='prepared'&&c.session===session&&c.epoch===epoch)continue;
    jobs.set(key(c),{...copy(identity(c)),phase:'held',worked:0,samples:0,lastGame:null,attendance:null,legs:[],effects_issued:null,invalidated:true,
     release_requested:false,release_verified:false,error:'Cold paid job has no surviving attendance or effect journal'});
   }
   for(const job of jobs.values()){
    if(job.release_requested){release(job);continue;}
    if(job.phase==='held')continue;
    try{
     if(!current(job)||assignment(job)?.cancel_requested||assignment(job)?.phase==='held'||!valid(job)||!available())throw Error('Paid assignment withdrawn or catalog unavailable');
     const elapsed=now()-job.accepted_at;if(!Number.isFinite(elapsed)||elapsed<0||elapsed>Math.max(300000,job.work_minutes*60000))throw Error('Paid lease elapsed or wall clock reversed');
     const s=inspect(job);
     if(job.phase==='acquiring'){
      if(!s.owned){if(elapsed>30000)throw Error('Worker stationary lease acquisition timed out');continue;}
      job.attendance={token:null,slot:job.slot,serial:s.serial,expected_package:job.expected_package,anchor:copy(job.anchor),cell_id:job.cell_id,
       worked_minutes:0,samples:0,ready_at:null,expires_at:null,token_valid:false};job.phase='working';
     }
     const a=job.attendance;if(!s.owned||s.serial!==a.serial)throw Error('Paid worker exact lease interrupted');
     if(job.lastGame!==null){const delta=s.game-job.lastGame;if(delta<0||delta>1/1440)throw Error('Paid attendance game clock jumped');if(job.phase==='working')job.worked+=delta*1440;}
     job.lastGame=s.game;
     if(job.phase==='working'){
      job.samples++;a.worked_minutes=job.worked;a.samples=job.samples;
      if(job.worked>=job.work_minutes&&job.samples>=2){job.phase='attendance_verified';a.ready_at=now();a.expires_at=now()+120000;
       a.token=`paid-token-${epoch}-${++sequence}`;a.token_valid=true;}
     }else if(now()<a.ready_at||now()>a.expires_at)throw Error('Paid attendance permit expired');
    }catch(e){hold(job,String(e.message||e));}
   }
  },
  status(){return {available:available(),protocol:2,epoch,session,capacity,catalog_hash:catalog?.status().catalog_hash||null,
   jobs:[...jobs.values()].map(receipt),receipts:[...jobs.values()].filter(j=>j.phase!=='acquiring'&&j.phase!=='working').map(receipt),reserved_actors:this.reservedActors(),
   scope:'Stationary hired-worker attendance and witnessed account effects; working animation and workstation access unverified'};}
 };
}
if(typeof module!=='undefined')module.exports={createPaidEmploymentController};
