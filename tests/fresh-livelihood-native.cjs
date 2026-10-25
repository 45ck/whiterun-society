// Offline actor/form adapter only. Real attendance/catalog/production modules
// generate receipts; no game process, native binary or provider is invoked.
const readline=require('node:readline');
const {createEconomyCatalogController}=require('../bridge/economy-catalog.js');
const {createOwnerWorkJobsController}=require('../bridge/owner-work-jobs.js');
const {createProductionController}=require('../bridge/production.js');
const manifest=require('../config/economy-catalog.json');
const seed=JSON.parse(process.argv[2]),session=seed.session;
let game=seed.gameDays,desired={epoch:'unassigned',capacity:4,jobs:[]};
const calls=[],actors=new Map(),forms=new Map(),mappings=new Map();
for(const item of manifest.commodities){
 const form={item:item.id,getFormID:()=>item.native.local_form_id,getType:()=>({MISC:32,ALCH:46,INGR:30})[item.native.record_type]};
 forms.set(form.getFormID(),form);mappings.set(item.native.plugin.toLowerCase()+':'+form.getFormID(),form);
}
const value=n=>({value:n,getValue(){return this.value;},setValue(v){this.value=v;}});
const list=()=>({rows:[],getSize(){return this.rows.length;},getAt(i){return this.rows[i];}});
const slots=Array.from({length:128},(_,index)=>[
 {running:false,isRunning(){return this.running;},stop(){this.running=false;for(const actor of actors.values())if(actor.pkg===9000+index)actor.pkg=42;}},
 {getFormID:()=>9000+index},list(),list(),value(0),value(0),value(0)]);
const control=structuredClone(seed.resident_control);
for(const row of seed.residents){
 const actor={row:structuredClone(row),pkg:row.activity.package_id,
  getFormID:()=>row.id,getActorBase:()=>({getFormID:()=>row.baseId}),getCurrentPackage(){return {getFormID:()=>this.pkg};},
  getParentCell:()=>({getFormID:()=>77}),is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,
  isInCombat:()=>false,getCurrentScene:()=>null,getSleepState:()=>0,
  getPositionX:()=>row.x,getPositionY:()=>row.y,getPositionZ:()=>row.z,
  getItemCount(form){return this.row.inventory[form.item];},
  removeItem(form,count){calls.push({actor:row.id,item:form.item,amount:-count});this.row.inventory[form.item]-=count;},
  addItem(form,count){calls.push({actor:row.id,item:form.item,amount:count});this.row.inventory[form.item]+=count;}};
 actors.set(row.id,actor);
}
const platform={Actor:{from:value=>value},Quest:{from:value=>value},FormList:{from:value=>value},GlobalVariable:{from:value=>value},
 Utility:{getCurrentGameTime:()=>game},Game:{getFormEx:id=>actors.get(id)||forms.get(id),
 getFormFromFile:(id,file)=>file==='WhiterunCitizens.esp'?slots[Math.floor((id-0x800)/16)]?.[(id-0x800)%16]:mappings.get(file.toLowerCase()+':'+id)}};
// Evidence timestamps remain in the recent past while game time advances in
// deterministic half-minute samples. This is not wall-clock attendance proof.
const now=()=>Date.now()-1000;
const catalog=createEconomyCatalogController(()=>platform,manifest);
const manager=createOwnerWorkJobsController(()=>platform,now,{catalog});
const production=createProductionController(()=>platform,now,{catalog});
function tick(){manager.tick(desired,session,true,control);}
function state(result){return {result,session,gameDays:game,owner_work_jobs:manager.status(),economy_catalog:catalog.status(),
 resident_control:structuredClone(control),calls:structuredClone(calls),
 residents:[...actors.values()].map(actor=>({...structuredClone(actor.row),activity:{...actor.row.activity,package_id:actor.pkg}}))};}
tick();
readline.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line',line=>{try{
 const request=JSON.parse(line);let result=null;
 if(request.desired)desired=structuredClone(request.desired);
 if(request.gameDays!==undefined)game=request.gameDays;
 if(request.op==='start'){
  tick();result=manager.start(request.command,[]);
  if(result.ack?.accepted){const command=request.command,slot=slots[command.slot],actor=actors.get(command.actor);
   slot[0].running=true;slot[2].rows=[actor];slot[3].rows=[actor];slot[4].value=slot[5].value=slot[6].value=1;
   actor.pkg=9000+command.slot;
   Object.assign(control.activities.find(row=>row.actor===command.actor),{mode:'await_decision',target:command.actor,
    goal_id:'owner-work-'+command.job_id,work_hold_id:'owner-work-'+command.job_id});tick();
  }
 }else if(request.op==='earn'){
  for(let i=0;i<250&&!manager.status().receipts.length;i++){game+=.5/1440;tick();}
 }else if(request.op==='commit')result=production.commitOwnerRecipe(request.command,manager);
 else if(request.op==='release')tick();
 else if(request.op==='ack')result=manager.acknowledge(request.command);
 else if(request.op!=='state')throw Error('Unknown fixture operation');
 console.log(JSON.stringify(state(result)));
}catch(error){console.log(JSON.stringify({harness_error:String(error.stack||error)}));}});
