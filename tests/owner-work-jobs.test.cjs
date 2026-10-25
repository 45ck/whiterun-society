const test=require('node:test'),assert=require('node:assert/strict');
const {createOwnerWorkJobsController}=require('../bridge/owner-work-jobs.js');
const {createProductionController}=require('../bridge/production.js');
const {createEconomyCatalogController,validateEconomyCatalog}=require('../bridge/economy-catalog.js');
const manifest=require('../config/economy-catalog.json');

function fixture(count=2,capacity=4,configuration=manifest){
 let wall=1000,game=1,fresh=true,session='native-owner-session',defer=false;
 const verified=validateEconomyCatalog(configuration),recipe=configuration.recipes[0],forms=new Map(configuration.commodities.map(c=>[c.native.local_form_id,
  {name:c.id,getFormID:()=>c.native.local_form_id,getType:()=>({MISC:32,ALCH:46,INGR:30}[c.native.record_type])}]));
 const rows=Array.from({length:count},(_,i)=>({job_id:'dynamic-owner-'+i,actor:500+i,actor_base_id:1500+i,slot:i,session,
  epoch:'owner-epoch',business_id:'business-'+i,business_revision:3,recipe_id:recipe.id,catalog_hash:verified.catalog_hash,recipe_hash:verified.recipe_hashes[recipe.id],policy_version:'owner-production-v1:test',work_minutes:5,phase:'prepared'}));
 const actors=new Map(),calls=[],pending=[];
 const value=initial=>({value:initial,getValue(){return this.value;},setValue(n){this.value=n;}});
 const list=()=>({rows:[],getSize(){return this.rows.length;},getAt(i){return this.rows[i];}});
 const slots=Array.from({length:128},(_,i)=>{
  const quest={running:false,stuck:false,isRunning(){return this.running;},stop(){if(this.stuck)return;this.running=false;for(const a of actors.values())if(a.pkg===9000+i)a.pkg=42;}};
  return [quest,{getFormID:()=>9000+i},list(),list(),value(0),value(0),value(0)];
 });
 for(const row of rows){
  const a={id:row.actor,base:row.actor_base_id,pkg:42,x:row.actor*2,cell:77,loaded:true,combat:false,scene:null,sleep:0,inventory:Object.fromEntries(configuration.commodities.map(c=>[c.id,c.id==='gold'?12:c.id==='bread'?2:3])),
   getFormID(){return this.id;},getActorBase(){return {getFormID:()=>this.base};},getCurrentPackage(){return {getFormID:()=>this.pkg};},getParentCell(){return {getFormID:()=>this.cell};},
   is3DLoaded(){return this.loaded;},isDead:()=>false,isChild:()=>false,isInCombat(){return this.combat;},getCurrentScene(){return this.scene;},getSleepState(){return this.sleep;},
   getPositionX(){return this.x;},getPositionY:()=>0,getPositionZ:()=>0,getItemCount(item){return this.inventory[item.name];},
   removeItem(item,n){calls.push({actor:this.id,item:item.name,n:-n});const effect=()=>this.inventory[item.name]-=n;defer?pending.push(effect):effect();},
   addItem(item,n){calls.push({actor:this.id,item:item.name,n});const effect=()=>this.inventory[item.name]+=n;defer?pending.push(effect):effect();}};
  actors.set(a.id,a);
 }
 const sp={Actor:{from:x=>x},Quest:{from:x=>x},FormList:{from:x=>x},GlobalVariable:{from:x=>x},Utility:{getCurrentGameTime:()=>game},
  Game:{getFormEx:id=>forms.get(id)||actors.get(id),
   getFormFromFile:(id,file)=>{if(file!=='WhiterunCitizens.esp')return configuration.commodities.some(c=>c.native.plugin===file&&c.native.local_form_id===id)?forms.get(id):null;
    return slots[Math.floor((id-0x800)/16)]?.[(id-0x800)%16];}}};
 const control={activities:rows.map(row=>({actor:row.actor,slot:row.slot,expectedPackage:9000+row.slot,mode:'go_to',target:1234}))};
 let desired={epoch:'owner-epoch',capacity,jobs:rows};
 const catalog=createEconomyCatalogController(()=>sp,configuration),manager=createOwnerWorkJobsController(()=>sp,()=>wall,{catalog}),production=createProductionController(()=>sp,()=>wall,{catalog});
 const f={manager,production,rows,slots,actors,calls,control,sp,catalog,forms,
  tick(minutes=.5,ms=100){wall+=ms;game+=minutes/1440;manager.tick(desired,session,fresh,control);},
  start(row=rows[0],blocked=[]) {return manager.start({...row,id:'start-'+row.job_id},blocked).ack;},
  bind(row=rows[0]){const slot=slots[row.slot],a=actors.get(row.actor),r=control.activities.find(x=>x.actor===row.actor);
   slot[0].running=true;slot[2].rows=[a];slot[3].rows=[a];slot[4].value=1;slot[5].value=1;slot[6].value=1;a.pkg=9000+row.slot;
   Object.assign(r,{mode:'await_decision',target:row.actor,goal_id:'owner-work-'+row.job_id,work_hold_id:'owner-work-'+row.job_id});},
  earn(row=rows[0]){assert.equal(f.start(row).accepted,true);f.bind(row);f.tick(0);for(let i=0;i<15&&!f.receipt(row);i++)f.tick();assert.equal(f.receipt(row)?.phase,'attendance_verified');},
  receipt(row=rows[0]){return manager.status().receipts.find(r=>r.job_id===row.job_id);},
  command(row=rows[0]){const before={owner:structuredClone(actors.get(row.actor).inventory)},after=structuredClone(before);
   for(const [item,n] of Object.entries(recipe.inputs))after.owner[item]-=n;for(const [item,n] of Object.entries(recipe.outputs))after.owner[item]+=n;
   return {...row,id:'commit-'+row.job_id,kind:'inventory_self_produce_commit',attendance_token:f.receipt(row).attendance.token,before,after};},
  commit(c){return production.commitOwnerRecipe(c,manager);},
  ack(row=rows[0]){return manager.acknowledge({...row,id:'ack-'+row.job_id,session,job_session:row.session}).ack;},
  setDesired:d=>desired=d,setFresh:v=>fresh=v,setSession:v=>session=v,advanceWall:n=>wall+=n,defer:()=>defer=true,flush:()=>pending.splice(0).forEach(fn=>fn()),
  snapshot:()=>({wall,game})};
 f.tick(0,0);return f;
}

test('explicit work pool defaults to four and does not consume furniture slots',()=>{
 const f=fixture(5);for(const row of f.rows.slice(0,4))assert.equal(f.start(row).accepted,true);
 assert.equal(f.start(f.rows[4]).accepted,false);assert.equal(f.manager.status().capacity,4);assert.equal(f.manager.status().citizens_capacity,128);
 assert.equal(f.calls.length,0);assert.equal(f.manager.holds().length,4);
});
test('configured pool capacity applies independently of resident slot number',()=>{
 const f=fixture(3,1);assert.equal(f.start(f.rows[2]).accepted,true);assert.equal(f.start().accepted,false);assert.equal(f.manager.holds()[0].slot,2);
});
test('two independently admitted owners qualify attendance without inventory effects',()=>{
 const f=fixture();for(const row of f.rows){assert.equal(f.start(row).accepted,true);f.bind(row);}f.tick(0);
 for(let i=0;i<11;i++)f.tick();assert.equal(f.manager.status().receipts.length,2);
 for(const row of f.rows){const r=f.receipt(row);assert.equal(r.phase,'attendance_verified');assert.ok(r.attendance.worked_minutes>=5);assert.ok(r.attendance.samples>=2);
  assert.equal(r.effects_issued,false);assert.equal(r.committed_inventory_verified,false);assert.equal(r.release_verified,false);}
 assert.equal(f.calls.length,0);assert.deepEqual(f.actors.get(500).inventory,{gold:12,bread:2,grain:3});
});
test('an owned travelling package cannot earn work until its exact self-target hold is observed',()=>{
 const f=fixture();f.start();f.actors.get(500).pkg=9000;for(let i=0;i<10;i++)f.tick();
 assert.equal(f.manager.status().jobs[0].worked_minutes,0);assert.equal(f.receipt(),undefined);
 f.bind();f.tick(0);assert.equal(f.manager.status().jobs[0].phase,'working');
});
test('acquisition timeout and paused time create no labour or goods',()=>{
 const f=fixture();f.start();f.advanceWall(30001);f.tick(0);assert.equal(f.receipt().phase,'held');assert.equal(f.calls.length,0);
 const g=fixture();g.start();g.bind();for(let i=0;i<100;i++)g.tick(0);assert.equal(g.manager.status().jobs[0].worked_minutes,0);assert.equal(g.receipt(),undefined);
});
test('serial, mailbox, base, displacement, combat and clock changes invalidate attendance',()=>{
 for(const disturb of [f=>f.slots[0][4].value++,f=>f.slots[0][3].rows=[f.actors.get(501)],f=>f.actors.get(500).base++,
  f=>f.actors.get(500).x+=101,f=>f.actors.get(500).combat=true,f=>f.tick(-1),f=>f.tick(60)]){
  const f=fixture();f.start();f.bind();f.tick(0);f.tick();disturb(f);f.tick(0);assert.equal(f.receipt().phase,'held');assert.equal(f.calls.length,0);
 }
});
test('admission requires fresh identity and rejects busy actors and conflicting accounts',()=>{
 const f=fixture();assert.equal(f.start(f.rows[0],[500]).accepted,false);f.actors.get(500).base++;
 assert.equal(f.start().accepted,false);f.actors.get(500).base--;assert.equal(f.start().accepted,true);
 assert.equal(f.start().accepted,true);assert.equal(f.manager.status().jobs.length,1);
 const duplicate={...f.rows[1],actor:500,actor_base_id:1500};f.setDesired({epoch:'owner-epoch',jobs:[...f.rows,duplicate]});f.tick(0);
 assert.equal(f.start(duplicate).accepted,false);
});
test('single-use token authorizes exactly two recipe legs then separate release and acknowledgement',()=>{
 const f=fixture();f.earn();const c=f.command();assert.equal(f.commit(c).done,false);assert.deepEqual(f.calls,[{actor:500,item:'grain',n:-1}]);
 assert.equal(f.commit(c).done,false);const result=f.commit(c);assert.equal(result.ack.status,'applied');assert.equal(result.ack.release_verified,false);
 assert.equal(result.ack.committed_inventory_verified,true);assert.equal(result.ack.mechanism,'native_owner_recipe');assert.equal(result.ack.animation_verified,false);
 assert.deepEqual(f.actors.get(500).inventory,c.after.owner);assert.equal(f.receipt().phase,'recipe_committed');assert.equal(f.manager.ownsActor(500),true);
 assert.equal(f.ack().acknowledged,false);f.tick(0);assert.equal(f.receipt().phase,'complete');assert.equal(f.receipt().release_verified,true);
 assert.equal(f.manager.ownsActor(500),true);assert.equal(f.ack().acknowledged,true);assert.equal(f.manager.ownsActor(500),false);
 assert.equal(f.commit(c).ack.status,'held');assert.equal(f.calls.length,2);
});
test('ready owners commit serially while independent attendance remains qualified',()=>{
 const f=fixture();f.earn(f.rows[0]);f.earn(f.rows[1]);const a=f.command(),b=f.command(f.rows[1]);
 for(let i=0;i<3;i++)f.commit(a);assert.equal(f.calls.length,2);assert.equal(f.receipt(f.rows[1]).phase,'attendance_verified');
 for(let i=0;i<3;i++)f.commit(b);assert.equal(f.calls.length,4);assert.deepEqual(f.actors.get(501).inventory,b.after.owner);
});
test('writer rejects interleaved recipe commands without spending the second account',()=>{
 const f=fixture();f.earn(f.rows[0]);f.earn(f.rows[1]);const a=f.command(),b=f.command(f.rows[1]);f.commit(a);
 const denied=f.commit(b);assert.equal(denied.ack.status,'held');assert.equal(denied.ack.no_effects_issued,true);assert.equal(f.actors.get(501).inventory.grain,3);
 f.commit(a);assert.equal(f.commit(a).ack.status,'applied');assert.equal(f.calls.length,2);
});
test('wrong token, identity and recipe cannot mint goods or consume another job token',()=>{
 for(const change of [c=>c.attendance_token='wrong',c=>c.business_revision++,c=>c.actor_base_id++,c=>c.session='old',c=>c.after.owner.gold++]){
  const f=fixture();f.earn();const c=f.command();change(c);assert.equal(f.commit(c).ack.status,'held');assert.equal(f.calls.length,0);
 }
});
test('coincidental after inventory is not production without its own issued witness',()=>{
 const f=fixture();f.earn();const c=f.command();f.actors.get(500).inventory=structuredClone(c.after.owner);
 const result=f.commit(c);assert.equal(result.ack.status,'held');assert.equal(result.ack.committed_inventory_verified,false);assert.equal(f.calls.length,0);
});
test('expired same-job token attests no effects and can cleanly release its reservation',()=>{
 const f=fixture();f.earn();const c=f.command();f.advanceWall(120001);
 assert.equal(f.manager.permitsCommand(c),true);const result=f.commit(c);assert.equal(result.ack.status,'held');assert.equal(result.ack.no_effects_issued,true);
 assert.equal(result.ack.effects_issued,false);assert.equal(f.calls.length,0);f.tick(0);assert.equal(f.receipt().release_verified,true);assert.equal(f.ack().acknowledged,true);
});
test('asynchronous native legs issue once; duplicate completed commit returns its original receipt',()=>{
 const f=fixture();f.earn();const c=f.command();f.defer();f.commit(c);for(let i=0;i<5;i++)f.commit(c);assert.equal(f.calls.length,1);
 f.flush();f.commit(c);for(let i=0;i<5;i++)f.commit(c);assert.equal(f.calls.length,2);f.flush();const result=f.commit(c);
 assert.equal(result.ack.status,'applied');assert.deepEqual(f.commit(c),result);assert.equal(f.calls.length,2);
});
test('timeout after issued input is quarantined and never repeats or frees account',()=>{
 const f=fixture();f.earn();const c=f.command();f.defer();f.commit(c);f.advanceWall(5001);
 const held=f.commit(c);assert.equal(held.ack.status,'held');assert.equal(held.ack.no_effects_issued,false);assert.equal(held.ack.effects_issued,true);
 f.flush();f.commit(c);assert.equal(f.calls.length,1);assert.equal(f.ack().acknowledged,false);assert.equal(f.manager.ownsActor(500),true);
});
test('losing native effect witness cannot infer and replay partial or completed inventory',()=>{
 for(const steps of [1,2,3]){
  const f=fixture();f.earn();const c=f.command();for(let i=0;i<steps;i++)f.commit(c);const count=f.calls.length;f.production.reset();
  const result=f.commit(c);assert.equal(result.ack.status,'held');assert.equal(result.ack.no_effects_issued,false);assert.equal(f.calls.length,count);
 }
});
test('cancelled unconsumed attendance releases but consumed token remains quarantined',()=>{
 const f=fixture();f.earn();f.rows[0].cancel_requested=true;f.tick(0);f.tick(0);assert.equal(f.receipt().phase,'held');assert.equal(f.ack().acknowledged,true);
 const g=fixture();g.earn();const c=g.command();g.commit(c);g.rows[0].cancel_requested=true;g.tick(0);
 assert.equal(g.receipt().phase,'held');assert.equal(g.receipt().effects_issued,true);assert.equal(g.ack().acknowledged,false);assert.equal(g.calls.length,1);
});
test('cold running jobs release with zero credit while cold pending effects remain quarantined',()=>{
 for(const phase of ['running','recipe_prepared']){
  const f=fixture();f.rows[0].phase=phase;f.bind();f.tick(0);const r=f.receipt();assert.equal(r.phase,'held');assert.equal(r.attendance,null);assert.equal(r.release_verified,true);
  assert.equal(r.effects_issued,phase==='running'?false:null);assert.equal(f.ack().acknowledged,phase==='running');assert.equal(f.calls.length,0);
 }
});
test('session reset invalidates attendance and old receipts require explicit original session identity',()=>{
 const f=fixture();f.earn();const oldToken=f.receipt().attendance.token;f.manager.reset();f.setSession('new-native-session');f.tick(0);
 assert.equal(f.receipt().phase,'held');assert.equal(f.receipt().attendance.token_valid,false);assert.equal(f.receipt().attendance.token,oldToken);
 assert.equal(f.ack().acknowledged,true);assert.equal(f.calls.length,0);
});
test('held release cannot free a slot while its native quest still owns the actor',()=>{
 const f=fixture();f.earn();f.slots[0][0].stuck=true;f.rows[0].cancel_requested=true;f.tick(0);f.tick(0);
 assert.equal(f.receipt().release_verified,false);assert.equal(f.ack().acknowledged,false);
 f.slots[0][0].stuck=false;f.tick(0);assert.equal(f.ack().acknowledged,true);
});

test('a consumed token rejects a second commit id without disturbing its legitimate in-flight command',()=>{
 const f=fixture();f.earn();const c=f.command();f.commit(c);
 assert.equal(f.commit({...c,id:'second-commit'}).ack.status,'held');assert.equal(f.calls.length,1);
 assert.equal(f.manager.permitsCommand({...c,id:'second-commit'}),false);f.commit(c);assert.equal(f.commit(c).ack.status,'applied');assert.equal(f.calls.length,2);
});

test('external output after our grain removal is not mistaken for our own issued bread effect',()=>{
 const f=fixture();f.earn();const c=f.command();f.commit(c);f.actors.get(500).inventory.bread+=2;
 const result=f.commit(c);assert.equal(result.ack.status,'held');assert.equal(result.ack.committed_inventory_verified,false);assert.equal(f.calls.length,1);
 assert.equal(f.ack().acknowledged,false);
});

test('held owner account cannot be bypassed by an unrelated inventory command',()=>{
 const f=fixture();f.earn();const c=f.command();assert.equal(f.manager.permitsCommand({...c,kind:'inventory_consume'}),false);
 assert.equal(f.manager.permitsCommand({...c,actor:501}),false);assert.equal(f.manager.permitsCommand({...c,attendance_token:'other'}),false);
});

test('reset after verified output cannot recertify the previous save inventory or unlock its account',()=>{
 const f=fixture();f.earn();const c=f.command();for(let i=0;i<3;i++)f.commit(c);assert.equal(f.receipt().committed_inventory_verified,true);
 f.manager.reset();f.production.reset();f.setSession('new-native-session');f.tick(0);
 const r=f.receipt();assert.equal(r.phase,'held');assert.equal(r.effects_issued,null);assert.equal(r.committed_inventory_verified,false);
 assert.equal(r.attendance.worked_minutes,0);assert.equal(r.release_verified,true);assert.equal(f.ack().acknowledged,false);
 assert.equal(f.commit(c).ack.status,'held');assert.equal(f.calls.length,2);
});

function syntheticRecipe(){
 const result=structuredClone(manifest);
 for(const [i,name] of ['raw_material','finished_material','keepsake'].entries())result.commodities.push({id:name,label:name,
  native:{plugin:'TestFixture.esp',local_form_id:0x101+i,record_type:'MISC'},currency:false,provenance:'Synthetic test fixture; not an installed game material'});
 result.recipes.unshift({id:'fixture_refine',version:1,inputs:{raw_material:2},outputs:{finished_material:3},
  work_minutes:{minimum:5,default:5,maximum:120},provenance:'Synthetic bounded recipe fixture, not game crafting evidence'});
 return result;
}

test('additional approved recipe uses exact configured quantities and preserves every unrelated balance',()=>{
 const f=fixture(1,4,syntheticRecipe());f.earn();const c=f.command(),before=structuredClone(f.actors.get(500).inventory);
 for(let i=0;i<3;i++)f.commit(c);
 assert.deepEqual(f.calls,[{actor:500,item:'raw_material',n:-2},{actor:500,item:'finished_material',n:3}]);
 const after=f.actors.get(500).inventory;assert.equal(after.raw_material,before.raw_material-2);assert.equal(after.finished_material,before.finished_material+3);
 for(const item of ['gold','bread','grain','keepsake'])assert.equal(after[item],before[item]);
 const receipt=f.commit(c).ack;assert.equal(receipt.status,'applied');assert.equal(receipt.catalog_hash,f.rows[0].catalog_hash);assert.equal(receipt.recipe_hash,f.rows[0].recipe_hash);
});

test('catalog and recipe hashes are attendance identity, not editable effect suggestions',()=>{
 for(const field of ['catalog_hash','recipe_hash']){
  const f=fixture();f.rows[0][field]='0'.repeat(64);assert.equal(f.start().accepted,false);assert.equal(f.calls.length,0);
  const g=fixture();g.earn();const command=g.command();command[field]='f'.repeat(64);assert.equal(g.commit(command).ack.status,'held');assert.equal(g.calls.length,0);
 }
 const f=fixture();delete f.rows[0].catalog_hash;assert.equal(f.start().accepted,false);
});

test('missing or mistyped catalog forms reject admission and unknown balances never become zero',()=>{
 const f=fixture();f.forms.delete(0x4b0ba);assert.equal(f.catalog.status().available,false);assert.equal(f.catalog.readInventory(f.actors.get(500)).grain,null);
 assert.equal(f.start().accepted,false);assert.equal(f.calls.length,0);
 const g=fixture();g.forms.get(0x65c97).getType=()=>32;assert.equal(g.start().accepted,false);
});

test('unrelated omitted or altered commodity cannot be hidden in generic owner commit',()=>{
 for(const mutate of [c=>delete c.before.owner.keepsake,c=>c.after.owner.keepsake++,c=>c.after.owner.gold++,c=>c.after.owner.finished_material++]){
  const f=fixture(1,4,syntheticRecipe());f.earn();const c=f.command();mutate(c);
  assert.equal(f.commit(c).ack.status,'held');assert.equal(f.calls.length,0);
 }
});

test('form loss after input issue quarantines account and cannot manufacture or replay output',()=>{
 const f=fixture(1,4,syntheticRecipe());f.earn();const c=f.command();f.commit(c);f.forms.delete(0x102);
 const held=f.commit(c);assert.equal(held.ack.status,'held');assert.equal(held.ack.effects_issued,true);assert.equal(held.ack.no_effects_issued,false);
 assert.equal(f.calls.length,1);assert.equal(f.ack().acknowledged,false);assert.equal(f.manager.ownsActor(500),true);
 f.commit(c);assert.equal(f.calls.length,1);
});
