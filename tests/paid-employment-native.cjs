// Offline native API adapter: actual catalog and paid-work controllers generate
// all attendance/effect receipts. No game process or fabricated success receipt.
const readline=require('node:readline');
const {createEconomyCatalogController}=require('../bridge/economy-catalog.js');
const {createPaidEmploymentController}=require('../bridge/paid-employment.js');
const {createInventoryTransfers}=require('../bridge/inventory-transfers.js');
const seed=JSON.parse(process.argv[2]),manifest=JSON.parse(process.argv[3]);
const marketPolicy=JSON.parse(process.argv[4]);
let game=seed.gameDays,clock=Date.now()-1000,session=seed.session,desired=null;
let dropCredit=false;
const calls=[],actors=new Map(),forms=new Map(),mappings=new Map();
const keyword={getFormID:()=>0x13794};
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
for(const source of seed.residents){
 const row=structuredClone(source);
 const actor={row,pkg:row.activity.package_id,
  getFormID:()=>row.id,getActorBase:()=>({getFormID:()=>row.baseId}),getCurrentPackage(){return {getFormID:()=>this.pkg};},
  getParentCell:()=>({getFormID:()=>row.cell_id||77}),is3DLoaded:()=>row.loaded!==false,isDead:()=>row.isDead===true,isChild:()=>row.isChild===true,
  isInCombat:()=>false,getCurrentScene:()=>null,getSleepState:()=>0,
  hasKeyword:value=>value===keyword,
  getPositionX:()=>row.x,getPositionY:()=>row.y,getPositionZ:()=>row.z,
  getItemCount(form){return row.inventory[form.item];},
  removeItem(form,count,silent,recipient){calls.push({actor:row.id,item:form.item,amount:-count,
    ...(recipient?{recipient:recipient.getFormID()}: {})});row.inventory[form.item]-=count;
    if(recipient)recipient.row.inventory[form.item]+=count;},
  addItem(form,count){calls.push({actor:row.id,item:form.item,amount:count});if(!(dropCredit&&form.item==='gold'))row.inventory[form.item]+=count;}};
 actors.set(row.id,actor);
}
const platform={Actor:{from:value=>value},Quest:{from:value=>value},FormList:{from:value=>value},GlobalVariable:{from:value=>value},Keyword:{from:value=>value===keyword?value:null},
 Utility:{getCurrentGameTime:()=>game},Game:{getFormEx:id=>id===0x13794?keyword:actors.get(id)||forms.get(id),
 getFormFromFile:(id,file)=>file==='WhiterunCitizens.esp'?slots[Math.floor((id-0x800)/16)]?.[(id-0x800)%16]:mappings.get(file.toLowerCase()+':'+id)}};
const catalog=createEconomyCatalogController(()=>platform,manifest);
let manager=createPaidEmploymentController(()=>platform,()=>clock,{catalog});
const trade=createInventoryTransfers(()=>platform,()=>clock,{catalog,marketPolicy,session:()=>session});
desired={epoch:manager.status().epoch,capacity:4,jobs:[]};
function tick(){manager.tick(desired,session,true,control);}
function state(result){return {result,session,gameDays:game,paid_employment:manager.status(),trade_execution:trade.status(),economy_catalog:catalog.status(),
 resident_control:structuredClone(control),calls:structuredClone(calls),
 residents:[...actors.values()].map(actor=>({...structuredClone(actor.row),activity:{...actor.row.activity,package_id:actor.pkg}}))};}
tick();
readline.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line',line=>{try{
 const request=JSON.parse(line);let result=null;
 if(request.desired)desired=structuredClone(request.desired);
 if(request.gameDays!==undefined)game=request.gameDays;
 if(request.op==='start'){
  tick();result=manager.start(request.command,request.blockedActors||[]);
  if(result.ack?.accepted){const c=request.command,slot=slots[c.slot],actor=actors.get(c.worker);
   slot[0].running=true;slot[2].rows=[actor];slot[3].rows=[actor];slot[4].value=slot[5].value=slot[6].value=1;
   actor.pkg=9000+c.slot;
   Object.assign(control.activities.find(row=>row.actor===c.worker),{mode:'await_decision',target:c.worker,
    goal_id:'paid-work-'+c.job_id,work_hold_id:'paid-work-'+c.job_id});tick();
  }
 }else if(request.op==='earn'){
  for(let i=0;i<250&&!manager.status().receipts.some(row=>row.phase==='attendance_verified');i++){game+=.5/1440;clock+=1;tick();}
 }else if(request.op==='commit')result=manager.commit(request.command);
 else if(request.op==='trade')result=trade.step(request.command);
 else if(request.op==='release')tick();
 else if(request.op==='ack')result=manager.acknowledge(request.command);
 else if(request.op==='reset')manager.reset();
 else if(request.op==='cold_restart'){manager=createPaidEmploymentController(()=>platform,()=>clock,{catalog});tick();}
 else if(request.op==='drop_credit')dropCredit=true;
 else if(request.op==='advance_clock')clock+=request.milliseconds;
 else if(request.op==='replace_identity')actors.get(request.actor).row.baseId=request.baseId;
 else if(request.op!=='state')throw Error('Unknown fixture operation');
 console.log(JSON.stringify(state(result)));
}catch(error){console.log(JSON.stringify({harness_error:String(error.stack||error)}));}});
