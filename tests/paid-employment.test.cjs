const test=require('node:test'),assert=require('node:assert/strict');
const {createPaidEmploymentController}=require('../bridge/paid-employment.js');
const {createEconomyCatalogController,validateEconomyCatalog}=require('../bridge/economy-catalog.js');
const manifest=require('../config/economy-catalog.json');
function fixture(configuration=manifest){
 let wall=1000,game=1,fresh=true,session='paid-session',defer=false,throwLeg=null,throwAfterLeg=null,dropLeg=null;
 const calls=[],pending=[],actors=new Map(),forms=new Map(configuration.commodities.map(c=>[c.native.local_form_id,
  {name:c.id,getFormID:()=>c.native.local_form_id,getType:()=>({MISC:32,ALCH:46,INGR:30}[c.native.record_type])}]));
 const value=n=>({value:n,getValue(){return this.value;},setValue(n){this.value=n;}}),list=()=>({rows:[],getSize(){return this.rows.length;},getAt(i){return this.rows[i];}});
 const slots=Array.from({length:128},(_,i)=>[{running:false,stuck:false,isRunning(){return this.running;},stop(){calls.push({kind:'stop',slot:i});if(!this.stuck){this.running=false;for(const a of actors.values())if(a.pkg===9000+i)a.pkg=42;}}},
  {getFormID:()=>9000+i},list(),list(),value(0),value(0),value(0)]);
 for(const id of [501,502]){
  const a={id,base:id+1000,loaded:true,pkg:42,x:100,cell:77,combat:false,scene:null,sleep:0,inventory:Object.fromEntries(configuration.commodities.map(c=>[c.id,20])),
   getFormID(){return this.id;},getActorBase(){return {getFormID:()=>this.base};},is3DLoaded(){return this.loaded;},isDead:()=>false,isChild:()=>false,
   getCurrentPackage(){return {getFormID:()=>this.pkg};},getParentCell(){return {getFormID:()=>this.cell};},getPositionX(){return this.x;},getPositionY:()=>0,getPositionZ:()=>0,
   isInCombat(){return this.combat;},getCurrentScene(){return this.scene;},getSleepState(){return this.sleep;},getItemCount(item){return this.inventory[item.name];},
   removeItem(item,n){effect(this,item,-n);},addItem(item,n){effect(this,item,n);}};actors.set(id,a);
 }
 function effect(actor,item,delta){const index=calls.filter(c=>c.kind==='effect').length;
  calls.push({kind:'effect',actor:actor.id,item:item.name,delta});if(index===throwLeg)throw Error('Native effect failed');
  if(index===dropLeg)return;const fn=()=>actor.inventory[item.name]+=delta;defer?pending.push(fn):fn();if(index===throwAfterLeg)throw Error('Native effect applied before exception');
 }
 const sp={Actor:{from:x=>x},Quest:{from:x=>x},FormList:{from:x=>x},GlobalVariable:{from:x=>x},Utility:{getCurrentGameTime:()=>game},Game:{
  getFormEx:id=>forms.get(id)||actors.get(id),getFormFromFile:(id,file)=>file==='WhiterunCitizens.esp'?slots[Math.floor((id-0x800)/16)]?.[(id-0x800)%16]:configuration.commodities.some(c=>c.native.plugin===file&&c.native.local_form_id===id)?forms.get(id):null}};
 const catalog=createEconomyCatalogController(()=>sp,configuration),manager=createPaidEmploymentController(()=>sp,()=>wall,{catalog});
 const recipe=configuration.recipes[0],binding=validateEconomyCatalog(configuration),before={worker:structuredClone(actors.get(501).inventory),employer:structuredClone(actors.get(502).inventory)},after=structuredClone(before);
 for(const [item,n] of Object.entries(recipe.inputs))after.employer[item]-=n;for(const [item,n] of Object.entries(recipe.outputs))after.employer[item]+=n;
 after.employer.gold-=3;after.worker.gold+=3;
 const row={protocol:2,job_id:'paid-job',worker:501,worker_base_id:1501,employer:502,employer_base_id:1502,slot:0,session,epoch:manager.status().epoch,
  business_id:'bakery-fixture',business_revision:3,recipe_id:recipe.id,catalog_hash:binding.catalog_hash,recipe_hash:binding.recipe_hashes[recipe.id],terms_hash:'a'.repeat(64),consent_hash:'b'.repeat(64),
  work_minutes:5,wage_gold:3,currency:'gold',expected_package:9000,anchor:[100,0,0],cell_id:77,before,after,phase:'prepared'};
 const control={activities:[{actor:501,slot:0,expectedPackage:9000,mode:'go_to',target:999}]};let desired={epoch:row.epoch,capacity:4,jobs:[row]};
 const f={manager,row,actors,slots,control,sp,catalog,calls,forms,
  tick(minutes=.5,ms=100){wall+=ms;game+=minutes/1440;manager.tick(desired,session,fresh,control);},
  start:()=>manager.start({...row,id:'start-paid',kind:'paid_work_start'}),
  bind(){const slot=slots[0],a=actors.get(501);slot[0].running=true;slot[2].rows=[a];slot[3].rows=[a];slot[4].value=7;slot[5].value=7;slot[6].value=1;a.pkg=9000;
   Object.assign(control.activities[0],{mode:'await_decision',target:501,goal_id:'paid-work-paid-job',work_hold_id:'paid-work-paid-job'});},
  earn(){assert.equal(f.start().ack.accepted,true);f.bind();f.tick(0);for(let i=0;i<12;i++)f.tick();assert.equal(f.receipt().phase,'attendance_verified');},
  receipt:()=>manager.status().receipts.find(r=>r.job_id===row.job_id),
  command:()=>({...structuredClone(row),id:'commit-paid',commit_id:'commit-paid',kind:'inventory_paid_work_commit',attendance_token:f.receipt().attendance.token}),
  ack:()=>manager.acknowledge({...row,id:'ack-paid',kind:'paid_work_ack_receipt'}),
  commit:c=>manager.commit(c),effects:()=>calls.filter(c=>c.kind==='effect'),
  defer:()=>defer=true,flush:()=>pending.splice(0).forEach(fn=>fn()),throwLeg:n=>throwLeg=n,throwAfterLeg:n=>throwAfterLeg=n,dropLeg:n=>dropLeg=n,
  advance:n=>wall+=n,setFresh:v=>fresh=v,setSession:v=>session=v,setDesired:v=>desired=v};
 f.tick(0,0);return f;
}

test('native-lazy constructor does not acquire game handles',()=>{
 let calls=0;createPaidEmploymentController(()=>{calls++;throw Error('early native call');},()=>1,{catalog:{}});assert.equal(calls,0);
});
test('qualified paid worker earns attendance without inventory effects',()=>{
 const f=fixture();f.earn();assert.equal(f.effects().length,0);const r=f.receipt();
 assert.equal(r.effects_issued,false);assert.ok(r.attendance.worked_minutes>=5);assert.equal(r.attendance.serial,7);
 assert.deepEqual(r.attendance.anchor,f.row.anchor);assert.equal(r.attendance.cell_id,77);
 assert.deepEqual(f.manager.reservedActors(),[501,502]);assert.equal(f.manager.holds()[0].intent,'paid_employment');
});
test('valid blocked start echoes immutable contract for service hold without claiming no effects',()=>{
 const f=fixture(),c={...f.row,id:'start-paid',kind:'paid_work_start'},ack=f.manager.start(c,[501]).ack;
 assert.equal(ack.status,'held');assert.equal(ack.accepted,false);assert.equal(ack.job_id,c.job_id);assert.equal(ack.worker_base_id,c.worker_base_id);
 assert.equal(ack.employer_base_id,c.employer_base_id);assert.equal(ack.epoch,c.epoch);assert.equal(ack.terms_hash,c.terms_hash);
 assert.deepEqual(ack.before,c.before);assert.deepEqual(ack.after,c.after);assert.equal(ack.effects_issued,null);assert.equal(ack.no_effects_issued,false);
 assert.equal(f.manager.status().jobs.length,0);assert.equal(f.effects().length,0);
});
test('malformed start keeps command id but never asserts an authoritative contract or no-effect proof',()=>{
 const f=fixture(),c={...f.row,id:'start-paid',kind:'paid_work_start',worker_base_id:0},ack=f.manager.start(c).ack;
 assert.equal(ack.id,c.id);assert.equal(ack.status,'held');assert.equal(ack.worker_base_id,undefined);assert.equal(ack.before,undefined);
 assert.equal(ack.effects_issued,null);assert.equal(ack.no_effects_issued,false);assert.equal(f.effects().length,0);
});
test('repeated start rechecks actual participant identity instead of accepting a stale job cache',()=>{
 const f=fixture();assert.equal(f.start().ack.accepted,true);f.actors.get(502).base++;
 assert.equal(f.start().ack.accepted,false);assert.equal(f.effects().length,0);
});
test('all four issued and observed stages precede payment, then release and acknowledgement',()=>{
 const f=fixture();f.earn();const c=f.command();for(let i=0;i<4;i++)assert.equal(f.commit(c).done,false);
 const end=f.commit(c);assert.equal(end.ack.status,'applied');assert.equal(end.ack.phase,'effects_verified');
 assert.equal(end.ack.output_verified,true);assert.equal(end.ack.wage_debit_verified,true);assert.equal(end.ack.wages_verified,true);assert.equal(end.ack.release_verified,false);
 assert.deepEqual(end.ack.legs.map(l=>[l.leg,l.issued,l.observed]),['input','output','wage_debit','wage_credit'].map(l=>[l,true,true]));
 assert.deepEqual(end.ack.legs[0].before,c.before);assert.deepEqual(end.ack.legs[3].after,c.after);assert.deepEqual(end.ack.inventory,c.after);
 assert.equal(f.effects().length,4);assert.equal(f.ack().ack.acknowledged,false);f.tick(0);
 assert.equal(f.receipt().phase,'complete');assert.equal(f.receipt().release_verified,true);assert.equal(f.ack().ack.acknowledged,true);assert.deepEqual(f.manager.reservedActors(),[]);
 assert.deepEqual(f.ack().ack.before,c.before);assert.equal(f.ack().ack.worker_base_id,c.worker_base_id);
 assert.equal(f.commit(c).ack.status,'held');assert.equal(f.effects().length,4);
});
test('paused time and unacquired travelling packages cannot earn labour',()=>{
 const f=fixture();f.start();f.actors.get(501).pkg=9000;for(let i=0;i<12;i++)f.tick();assert.equal(f.receipt(),undefined);
 f.bind();for(let i=0;i<30;i++)f.tick(0);assert.equal(f.receipt(),undefined);assert.equal(f.effects().length,0);
});
test('worker and employer identity, anchor, lease, activity and clock changes hold attendance',()=>{
 for(const change of [f=>f.actors.get(501).base++,f=>f.actors.get(502).base++,f=>f.actors.get(501).x+=101,f=>f.actors.get(501).cell++,
  f=>f.actors.get(501).combat=true,f=>f.slots[0][4].value++,f=>f.slots[0][3].rows=[f.actors.get(502)],f=>f.tick(2),f=>f.tick(-1)]){
  const f=fixture();f.start();f.bind();f.tick(0);change(f);f.tick(0);assert.equal(f.receipt().phase,'held');assert.equal(f.effects().length,0);
 }
});
test('wrong immutable contract or token cannot spend any account',()=>{
 for(const change of [c=>c.employer_base_id++,c=>c.worker_base_id++,c=>c.business_revision++,c=>c.terms_hash='c'.repeat(64),c=>c.consent_hash='c'.repeat(64),
  c=>c.slot++,c=>c.anchor[0]++,c=>c.cell_id++,c=>c.currency='bread',c=>c.wage_gold++,c=>c.after.worker.grain++,c=>c.attendance_token='wrong',c=>c.commit_id='different']){
  const f=fixture();f.earn();const c=f.command();change(c);assert.equal(f.commit(c).ack.status,'held');assert.equal(f.effects().length,0);
 }
});
test('coincidental final or partial inventory cannot reconstruct effects',()=>{
 for(const final of [false,true]){const f=fixture();f.earn();const c=f.command();
  if(final){f.actors.get(501).inventory=structuredClone(c.after.worker);f.actors.get(502).inventory=structuredClone(c.after.employer);}
  else f.actors.get(502).inventory.grain--;
  const held=f.commit(c);assert.equal(held.ack.status,'held');assert.equal(held.ack.effects_issued,false);assert.equal(f.effects().length,0);
 }
});
test('deferred effects are issued once and each exact intermediate state is required',()=>{
 const f=fixture();f.earn();f.defer();const c=f.command();
 for(let leg=0;leg<4;leg++){for(let i=0;i<3;i++)assert.equal(f.commit(c).done,false);assert.equal(f.effects().length,leg+1);f.flush();}
 assert.equal(f.commit(c).ack.status,'applied');assert.equal(f.commit(c).ack.status,'applied');assert.equal(f.effects().length,4);
});
test('native call throw at each leg retains issued witness and never retries',()=>{
 for(let leg=0;leg<4;leg++){
  const f=fixture();f.earn();const c=f.command();f.throwLeg(leg);for(let i=0;i<leg;i++)f.commit(c);
  const held=f.commit(c);assert.equal(held.ack.status,'held');assert.equal(held.ack.legs[leg].issued,true);assert.equal(held.ack.legs[leg].observed,false);
  assert.equal(held.ack.effects_issued,true);for(let i=0;i<3;i++)f.commit(c);assert.equal(f.effects().length,leg+1);
  assert.equal(f.ack().ack.acknowledged,false);assert.deepEqual(f.manager.reservedActors(),[501,502]);
 }
});
test('output exists and wage debit occurs without wage credit: distinct partial proof and no compensation',()=>{
 const f=fixture();f.earn();const c=f.command();f.dropLeg(3);for(let i=0;i<4;i++)f.commit(c);f.advance(5001);
 const held=f.commit(c).ack;assert.equal(held.status,'held');assert.equal(held.output_verified,true);assert.equal(held.wage_debit_verified,true);assert.equal(held.wages_verified,false);
 assert.equal(held.legs[3].issued,true);assert.equal(held.legs[3].observed,false);assert.equal(f.effects().length,4);
 assert.equal(f.actors.get(501).inventory.gold,c.before.worker.gold);assert.equal(f.actors.get(502).inventory.gold,c.after.employer.gold);
 f.commit(c);assert.equal(f.effects().length,4);assert.equal(f.ack().ack.acknowledged,false);
});
test('effect applied before native exception is reported as observed inventory, never inferred completed witness',()=>{
 const f=fixture();f.earn();const c=f.command();f.throwAfterLeg(0);
 const held=f.commit(c).ack;assert.equal(held.status,'held');assert.equal(held.legs[0].issued,true);assert.equal(held.legs[0].observed,false);
 assert.deepEqual(held.inventory,held.legs[0].after);assert.equal(held.effects_verified,false);assert.equal(f.effects().length,1);
 f.commit(c);assert.equal(f.effects().length,1);
});
test('unrelated account drift during a leg holds both purses',()=>{
 const f=fixture();f.earn();const c=f.command();f.commit(c);f.actors.get(501).inventory.bread++;
 assert.equal(f.commit(c).ack.status,'held');assert.equal(f.effects().length,1);assert.deepEqual(f.manager.reservedActors(),[501,502]);
});
test('native reset after each issued stage invalidates permits and never reconstructs from balances',()=>{
 for(let step=0;step<=5;step++){const f=fixture();f.earn();const c=f.command();for(let i=0;i<step;i++)f.commit(c);const count=f.effects().length,epoch=f.manager.status().epoch;
  f.manager.reset();assert.notEqual(f.manager.status().epoch,epoch);assert.equal(f.commit(c).ack.status,'held');assert.equal(f.effects().length,count);
  assert.equal(f.ack().ack.acknowledged,false);assert.deepEqual(f.manager.reservedActors(),[501,502]);
 }
});
test('cold restored jobs cannot issue effects or manufacture no-effect proof',()=>{
 const f=fixture();f.earn();const c=f.command(),cold=createPaidEmploymentController(()=>f.sp,()=>1234,{catalog:f.catalog});
 cold.tick({epoch:f.row.epoch,jobs:[{...f.row,phase:'committing_output'}]},f.row.session,true,f.control);
 const r=cold.status().receipts[0];assert.equal(r.phase,'held');assert.equal(r.effects_issued,null);assert.equal(r.no_effects_issued,false);
 assert.equal(cold.commit(c).ack.status,'held');assert.equal(f.effects().length,0);assert.equal(cold.status().reserved_actors.length,2);
});
test('same ID with changed payload never gets completed cached success',()=>{
 const f=fixture();f.earn();const c=f.command();for(let i=0;i<5;i++)f.commit(c);
 const changed=structuredClone(c);changed.after.worker.grain++;assert.equal(f.commit(changed).ack.status,'held');assert.equal(f.effects().length,4);
 f.actors.get(501).base++;assert.equal(f.commit(c).ack.status,'held');assert.equal(f.effects().length,4);
});
test('cleanup never stops a reassigned lease or claims release while its package remains',()=>{
 const f=fixture();f.earn();const c=f.command();for(let i=0;i<5;i++)f.commit(c);
 f.slots[0][4].value=99;f.tick(0);assert.equal(f.slots[0][0].running,true);assert.equal(f.receipt().release_verified,false);assert.equal(f.ack().ack.acknowledged,false);
});
test('stuck exact cleanup preserves economic completion while release stays unproved',()=>{
 const f=fixture();f.earn();const c=f.command();for(let i=0;i<5;i++)f.commit(c);f.slots[0][0].stuck=true;f.tick(0);
 assert.equal(f.receipt().output_verified,true);assert.equal(f.receipt().wages_verified,true);assert.equal(f.receipt().release_verified,false);assert.equal(f.ack().ack.acknowledged,false);
});
test('actor replacement after release cannot acknowledge and free reserved accounts',()=>{
 const f=fixture();f.earn();const c=f.command();for(let i=0;i<5;i++)f.commit(c);f.tick(0);assert.equal(f.receipt().release_verified,true);
 f.actors.get(502).base++;assert.equal(f.ack().ack.acknowledged,false);assert.deepEqual(f.manager.reservedActors(),[501,502]);
});
test('changed native session and stale assignment cannot continue settlement',()=>{
 for(const change of [f=>f.setSession('new-session'),f=>f.setFresh(false),f=>f.row.cancel_requested=true]){
  const f=fixture();f.earn();const c=f.command();f.commit(c);change(f);f.tick(0);assert.equal(f.commit(c).ack.status,'held');assert.equal(f.effects().length,1);
 }
});
test('catalog-driven renamed recipe and commodities use the same four leg protocol',()=>{
 const config=structuredClone(manifest);config.commodities.find(c=>c.id==='grain').id='flour';config.commodities.find(c=>c.id==='bread').id='loaf';
 config.recipes=[{...config.recipes[0],id:'makeLoaves',inputs:{flour:2},outputs:{loaf:3}}];
 const f=fixture(config);f.earn();const c=f.command();for(let i=0;i<4;i++)f.commit(c);const end=f.commit(c);
 assert.equal(end.ack.status,'applied');assert.deepEqual(end.ack.legs.map(l=>[l.item,l.amount]),[['flour',2],['loaf',3],['gold',3],['gold',3]]);
});
