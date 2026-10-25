// Offline actor/form adapter only. Real attendance/catalog/production modules
// generate receipts; no game process, native binary or provider is invoked.
const readline=require('node:readline');
const {createEconomyCatalogController}=require('../bridge/economy-catalog.js');
const {createOwnerWorkJobsController}=require('../bridge/owner-work-jobs.js');
const {createProductionController}=require('../bridge/production.js');
const {createActivityJobsController}=require('../bridge/activity-jobs.js');
const {createRestController}=require('../bridge/rest.js');
const {createPapyrusRouterController}=require('../bridge/papyrus-router.js');
const manifest=require('../config/economy-catalog.json');
const venues=require('../config/places.json');
const seed=JSON.parse(process.argv[2]),session=seed.session;
let game=seed.gameDays,desired={epoch:'unassigned',capacity:4,jobs:[]},restDesired={epoch:'unassigned',capacity:2,jobs:[]};
const calls=[],actors=new Map(),forms=new Map(),mappings=new Map();
for(const item of manifest.commodities){
 const form={item:item.id,getFormID:()=>item.native.local_form_id,getType:()=>({MISC:32,ALCH:46,INGR:30})[item.native.record_type]};
 forms.set(form.getFormID(),form);mappings.set(item.native.plugin.toLowerCase()+':'+form.getFormID(),form);
}
const value=n=>({value:n,getValue(){return this.value;},setValue(v){this.value=v;}});
const list=()=>({rows:[],getSize(){return this.rows.length;},getAt(i){return this.rows[i];},revert(){this.rows=[];},addForm(row){this.rows.push(row);}});
const slots=Array.from({length:128},(_,index)=>[
 {running:false,isRunning(){return this.running;},stop(){this.running=false;for(const actor of actors.values())if(actor.pkg===9000+index)actor.pkg=42;}},
 {getFormID:()=>9000+index},list(),list(),value(0),value(0),value(0)]);
const control=structuredClone(seed.resident_control);
for(const source of seed.residents){
 const row=structuredClone(source);
 const actor={row,pkg:row.activity.package_id,sit:0,furniture:0,
  getFormID:()=>row.id,getActorBase:()=>({getFormID:()=>row.baseId}),getCurrentPackage(){return {getFormID:()=>this.pkg};},
  getParentCell:()=>({getFormID:()=>77,isInterior:()=>false}),getWorldSpace:()=>({getFormID:()=>1}),
  is3DLoaded:()=>row.loaded!==false,isDead:()=>false,isChild:()=>false,hasKeyword:()=>true,evaluatePackage(){},
  getSitState(){return this.sit;},getFurnitureReference(){return this.furniture?seats.get(this.furniture):null;},
  isInCombat:()=>false,getCurrentScene:()=>null,getSleepState:()=>0,
  getPositionX:()=>row.x,getPositionY:()=>row.y,getPositionZ:()=>row.z,
  getItemCount(form){return this.row.inventory[form.item];},
  removeItem(form,count){calls.push({actor:row.id,item:form.item,amount:-count});this.row.inventory[form.item]-=count;},
  addItem(form,count){calls.push({actor:row.id,item:form.item,amount:count});this.row.inventory[form.item]+=count;}};
 actors.set(row.id,actor);
}
const seats=new Map(venues.venues.filter(v=>v.kind==='rest_bench').map(v=>[v.id,{
 getFormID:()=>v.id,is3DLoaded:()=>true,isDisabled:()=>false,isFurnitureInUse:()=>[...actors.values()].some(a=>a.furniture===v.id&&a.sit===3),
 getActorOwner:()=>null,getFactionOwner:()=>null,getPositionX:()=>500,getPositionY:()=>0,getPositionZ:()=>0,
 getParentCell:()=>({getFormID:()=>77,isInterior:()=>false}),getWorldSpace:()=>({getFormID:()=>1})}]));
function lane(packageId){const row=[null,{getFormID:()=>packageId},list(),list(),value(0),value(0),value(0)];
 row[0]={running:false,isRunning(){return this.running;},start(){this.running=true;
  row[5].value=row[4].value;row[6].value=1;const actor=row[2].rows[0],target=row[3].rows[0];
  if(actor){actor.pkg=packageId;actor.row.x=target.getPositionX();actor.row.y=target.getPositionY();actor.row.z=target.getPositionZ();
   if(seats.has(target.getFormID())){actor.sit=3;actor.furniture=target.getFormID();}}
  return true;},stop(){this.running=false;for(const actor of actors.values())if(actor.pkg===packageId){actor.pkg=42;actor.sit=0;actor.furniture=0;}}};return row;}
const furnitureLanes=[lane(11000),lane(11001)],chatLane=lane(12000),keyword={};
const platform={Actor:{from:value=>value},ObjectReference:{from:value=>value},Keyword:{from:value=>value},
 Quest:{from:value=>value},FormList:{from:value=>value},GlobalVariable:{from:value=>value},
 Utility:{getCurrentGameTime:()=>game},Game:{getFormEx:id=>id===0x13794?keyword:actors.get(id)||seats.get(id)||forms.get(id),
 getFormFromFile:(id,file)=>file==='WhiterunCitizens.esp'?slots[Math.floor((id-0x800)/16)]?.[(id-0x800)%16]:
  file==='WhiterunActivities.esp'?furnitureLanes[Math.floor((id-0x800)/0x100)]?.[(id-0x800)%0x100]:
  file==='WhiterunRouter.esp'?chatLane[id-0x800]:mappings.get(file.toLowerCase()+':'+id)}};
// Evidence timestamps remain in the recent past while game time advances in
// deterministic half-minute samples. This is not wall-clock attendance proof.
const now=()=>Date.now()-1000;
const catalog=createEconomyCatalogController(()=>platform,manifest);
const manager=createOwnerWorkJobsController(()=>platform,now,{catalog});
const production=createProductionController(()=>platform,now,{catalog});
const activities=createActivityJobsController(()=>platform,now,venues);
const sensors=createRestController(()=>platform,now,venues,{router:{file:'WhiterunActivities.esp',offset:0}});
const chat=createPapyrusRouterController(()=>platform,now);
function tick(){manager.tick(desired,session,true,control);activities.tick(restDesired,session,true);}
function state(result){return {result,session,gameDays:game,owner_work_jobs:manager.status(),activity_jobs:activities.status(),
 rest:sensors.sense([...actors.values()].map(actor=>actor.row)),economy_catalog:catalog.status(),
 resident_control:structuredClone(control),calls:structuredClone(calls),
 residents:[...actors.values()].map(actor=>({...structuredClone(actor.row),
 space:{cell:actor.getParentCell().getFormID(),interior:actor.getParentCell().isInterior(),world:actor.getWorldSpace().getFormID()},
 activity:{...actor.row.activity,package_id:actor.pkg}}))};}
tick();
readline.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line',line=>{try{
 const request=JSON.parse(line);let result=null;
 if(request.desired)desired=structuredClone(request.desired);
 if(request.restDesired)restDesired=structuredClone(request.restDesired);
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
  for(let i=0;i<(request.samples||72);i++){game+=.5/1440;tick();}
 }else if(request.op==='commit')result=production.commitOwnerRecipe(request.command,manager);
 else if(request.op==='rest_start'){tick();result=activities.start(request.command,[]);tick();}
 else if(request.op==='rest_ack')result=activities.acknowledge(request.command);
 else if(request.op==='chat_start'){for(let i=0;i<10;i++){result=chat.step(request.command);if(result.done)break;}}
 else if(request.op==='chat_release'){chat.release();result={done:true,ack:{id:request.command.id,status:chatLane[0].isRunning()?'held':'applied',released:!chatLane[0].isRunning()}};}
 else if(request.op==='replace_identity')actors.get(request.actor).row.baseId=request.baseId;
 else if(request.op==='release')tick();
 else if(request.op==='ack')result=manager.acknowledge(request.command);
 else if(request.op!=='state')throw Error('Unknown fixture operation');
 console.log(JSON.stringify(state(result)));
}catch(error){console.log(JSON.stringify({harness_error:String(error.stack||error)}));}});
