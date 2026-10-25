// Explicit recipe: 1 observed grain + qualified labour -> 2 bread.
// Agreed wages and attendance are bounded enterprise policy, never model code.
// Native handles are acquired on each frame. No automatic resource replenishment.
function createProductionController(platform,now=Date.now){
 let active=null;
 const items={gold:0xf,bread:0x65c97,grain:0x4b0ba};
 const equal=(a,b)=>Object.keys(a).every(r=>b[r]&&Object.keys(items).every(k=>a[r][k]===b[r][k]));
 const clone=x=>JSON.parse(JSON.stringify(x));
 return {
  reset(){active=null;},
  status(){return active?{id:active.id,actor:active.actor,expectedPackage:active.package,ownedPackage:!['complete','held'].includes(active.phase)&&active.attendance?.package_owned===true,phase:active.phase,workedMinutes:Math.round(active.days*14400)/10,requiredMinutes:active.minutes,wageGold:active.wage,attendance:active.attendance||null}:null;},
  step(c){
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
   active.attendance={distance:gap,package_owned:!!pkg&&pkg.getFormID()===c.expected_package};
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
