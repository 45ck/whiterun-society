// Explicit recipe: 1 observed grain + qualified labour -> 2 bread, wage 2 gold.
// Native handles are acquired on each frame. No automatic resource replenishment.
function createProductionController(platform,now=Date.now){
 let active=null;
 const items={gold:0xf,bread:0x65c97,grain:0x4b0ba};
 const equal=(a,b)=>['worker','employer'].every(r=>Object.keys(items).every(k=>a[r][k]===b[r][k]));
 const clone=x=>JSON.parse(JSON.stringify(x));
 return {
  reset(){active=null;},
  status(){return active?{id:active.id,phase:active.phase,workedMinutes:Math.round(active.days*14400)/10,requiredMinutes:30}:null;},
  step(c){
   const sp=platform(),fail=error=>({done:true,ack:{id:c.id,status:'held',error,work:this.status()}});
   if(!c.before||!c.after||!['worker','employer'].every(r=>c.before[r]&&c.after[r]&&Object.keys(items).every(k=>Number.isInteger(c.before[r][k])&&c.before[r][k]>=0&&Number.isInteger(c.after[r][k])&&c.after[r][k]>=0)))return fail('Invalid production inventory contract');
   const supply=c.kind==='inventory_supply',expected=clone(c.before);
   if(supply){expected.employer.grain+=2;}
   else{
    if(c.kind!=='inventory_produce'||c.work_minutes!==30||!Number.isInteger(c.expected_package)||c.before.employer.grain<1||c.before.employer.gold<2)return fail('Invalid work terms');
    expected.employer.grain--;expected.employer.bread+=2;expected.employer.gold-=2;expected.worker.gold+=2;
   }
   if(c.worker===c.employer||!equal(expected,c.after))return fail('Invalid recipe or wage effect');
   const worker=sp.Actor.from(sp.Game.getFormEx(c.worker)),employer=sp.Actor.from(sp.Game.getFormEx(c.employer));
   if(!worker||!employer||[worker,employer].some(a=>!a.is3DLoaded()||a.isDead()||a.isChild()))return fail('Work participants unavailable');
   const forms=Object.fromEntries(Object.entries(items).map(([k,id])=>[k,sp.Game.getFormEx(id)]));
   if(Object.values(forms).some(f=>!f))return fail('Recipe forms unavailable');
   const read=a=>Object.fromEntries(Object.entries(forms).map(([k,f])=>[k,a.getItemCount(f)]));
   const actual={worker:read(worker),employer:read(employer)};
   if(equal(actual,c.after))return {done:true,ack:{id:c.id,status:'applied',inventory:actual,work:this.status(),mechanism:supply?'explicit_demo_import':'native_recipe_and_wage',animation_verified:false}};
   if(!active||active.id!==c.id)active={id:c.id,phase:supply?'importing':'working',days:0,lastGame:null,sent:null,at:now()};
   const inputUsed=clone(c.before);inputUsed.employer.grain--;
   const outputMade=clone(inputUsed);outputMade.employer.bread+=2;
   const stage=equal(actual,c.before)?'before':!supply&&equal(actual,inputUsed)?'input':!supply&&equal(actual,outputMade)?'output':'unexpected';
   if(stage==='unexpected')return fail('Unexpected inventory during work; reconciliation required');
   if(active.sent&&now()-active.sent.at>5000)return fail('Production effect timed out; no repeated attempt');
   const issue=(leg,fn)=>{if(!active.sent||active.sent.leg!==leg){active.sent={leg,at:now()};fn();}};
   if(supply){issue('import',()=>employer.addItem(forms.grain,2,true));return {done:false};}
   if(stage==='input'){active.phase='making_output';issue('output',()=>employer.addItem(forms.bread,2,true));return {done:false};}
   if(stage==='output'){active.phase='paying_wage';issue('wage',()=>employer.removeItem(forms.gold,2,true,worker));return {done:false};}
   // Once input use is issued, don't reinterpret an asynchronous wait as new labour.
   if(active.sent)return {done:false};
   const pkg=worker.getCurrentPackage();
   const gap=Math.hypot(worker.getPositionX()-employer.getPositionX(),worker.getPositionY()-employer.getPositionY(),worker.getPositionZ()-employer.getPositionZ());
   if(!pkg||pkg.getFormID()!==c.expected_package||gap>300)return fail('Owned work attendance interrupted');
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
   if(active.days>=30/1440){active.phase='using_input';issue('input',()=>employer.removeItem(forms.grain,1,true,null));}
   return {done:false};
  }
 };
}
if(typeof module!=='undefined')module.exports={createProductionController};
