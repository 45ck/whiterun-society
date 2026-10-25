const test=require('node:test'),assert=require('node:assert/strict');
const {createProductionController}=require('../bridge/production.js');
const {createEconomyCatalogController}=require('../bridge/economy-catalog.js');
const manifest=require('../config/economy-catalog.json');
const binding=createEconomyCatalogController(()=>({}),manifest).identity('bread_recipe');
function ownerSetup(){const h=setup();h.c={id:'owner',kind:'inventory_self_produce',recipe_id:'bread_recipe',...binding,actor:2,expected_package:99,work_minutes:10,anchor:[0,0,0],attendance:{id:'owner-work-owner',slot:0,serial:1},before:{owner:structuredClone(h.balances[2])},after:{owner:{gold:5,bread:4,grain:1}}};return h;}
test('owner labour uses one account, no wages and two asynchronous recipe legs',()=>{
 const h=ownerSetup(),other=structuredClone(h.balances[1]);h.engine.step(h.c);assert.equal(h.engine.status().ownedPackage,true);
 for(let i=0;i<24;i++){h.next();h.engine.step(h.c);}
 assert.equal(h.engine.step(h.c).ack.mechanism,'native_owner_recipe');assert.deepEqual(h.balances[2],h.c.after.owner);assert.deepEqual(h.balances[1],other);assert.equal(h.calls.length,2);assert.equal(h.engine.status().ownedPackage,false);
 h.engine.reset();h.engine.step(h.c);assert.equal(h.calls.length,2);
});
test('owner input-only save resumes output once without a second input or any wage',()=>{
 const h=ownerSetup();h.balances[2].grain--;h.engine.step(h.c);h.next();assert.equal(h.engine.step(h.c).ack.status,'applied');assert.equal(h.calls.length,1);assert.deepEqual(h.balances[2],h.c.after.owner);
});
test('owner cannot manufacture gold, change the recipe, or count distant attendance',()=>{
 for(const [field,value] of [['gold',6],['bread',5],['grain',2]]){const h=ownerSetup();h.c.after.owner[field]=value;assert.equal(h.engine.step(h.c).ack.status,'held');assert.equal(h.calls.length,0);}
 const h=ownerSetup();h.c.anchor=[500,0,0];h.engine.step(h.c);for(let i=0;i<30;i++){h.next();h.engine.step(h.c);}assert.equal(h.engine.status().workedMinutes,0);h.advanceWall(31000);assert.equal(h.engine.step(h.c).ack.no_effects_issued,true);assert.equal(h.calls.length,0);
});
function setup(configuration=manifest){
 const balances={1:{gold:12,bread:0,grain:0},2:{gold:5,bread:2,grain:2}},calls=[],queue=[];
 let game=1,clock=0,owned=true,defer=false,frame=0,separation=0,ownerTarget=2,ownerSerial=1,ownerRunning=true;
 const form=id=>{
  if([15,0x65c97,0x4b0ba].includes(id))return {name:{15:'gold',[0x65c97]:'bread',[0x4b0ba]:'grain'}[id],getFormID:()=>id,getType:()=>({15:32,[0x65c97]:46,[0x4b0ba]:30}[id])};
  const born=frame,check=()=>assert.equal(born,frame);
  return {id,getFormID:()=>id,is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,getCurrentPackage:()=>({getFormID:()=>owned?99:88}),
   getPositionX:()=>id===1?separation:0,getPositionY:()=>0,getPositionZ:()=>0,getItemCount:k=>{check();return balances[id][k.name];},
   removeItem:(k,n,silent,to)=>{check();calls.push([id,k.name,-n,to?.id]);const f=()=>{balances[id][k.name]-=n;if(to)balances[to.id][k.name]+=n;};defer?queue.push(f):f();},
   addItem:(k,n)=>{check();calls.push([id,k.name,n]);const f=()=>{balances[id][k.name]+=n;};defer?queue.push(f):f();}};
 };
 const sp={Actor:{from:x=>x},Quest:{from:x=>x},FormList:{from:x=>x},GlobalVariable:{from:x=>x},
  Game:{getFormEx:form,getFormFromFile(id,file){if(file==='Skyrim.esm')return form(id);assert.equal(file,'WhiterunCitizens.esp');
   return [{isRunning:()=>ownerRunning},{getFormID:()=>99},{getSize:()=>1,getAt:()=>form(2)},
     {getSize:()=>1,getAt:()=>form(ownerTarget)},{getValue:()=>ownerSerial},{getValue:()=>1},{getValue:()=>1}][id-0x800];}},Utility:{getCurrentGameTime:()=>game}};
 const catalog=createEconomyCatalogController(()=>sp,configuration),engine=createProductionController(()=>sp,()=>clock,{catalog});
 const c={id:'work',kind:'inventory_produce',recipe_id:'bread_recipe',...catalog.identity('bread_recipe'),worker:1,employer:2,expected_package:99,work_minutes:30,
  before:structuredClone({worker:balances[1],employer:balances[2]}),after:{worker:{gold:14,bread:0,grain:0},employer:{gold:3,bread:4,grain:1}}};
 return {engine,c,balances,calls,sp,redirectOwner:n=>ownerTarget=n,ownerSerial:n=>ownerSerial=n,stopOwner:()=>ownerRunning=false,next:(minutes=.5)=>{frame++;game+=minutes/1440;clock+=100;},interrupt:()=>{owned=false;},
  separate:n=>{separation=n;},advanceWall:n=>{clock+=n;},defer:()=>{defer=true;},flush:()=>queue.splice(0).forEach(f=>f()),expire:()=>{clock+=6000;}};
}
function labour(h){h.engine.step(h.c);for(let i=0;i<62;i++){h.next();h.engine.step(h.c);}}
test('work consumes finite inputs and conserves wage after game-time attendance',()=>{
 const h=setup();h.engine.step(h.c);assert.equal(h.calls.length,0);labour(h);h.next();
 assert.equal(h.engine.step(h.c).ack.status,'applied');assert.deepEqual(h.balances[1],h.c.after.worker);assert.deepEqual(h.balances[2],h.c.after.employer);
 assert.equal(h.calls.length,3);h.engine.step(h.c);assert.equal(h.calls.length,3);
});
test('paused clock produces nothing and interrupted attendance pays nothing',()=>{
 const h=setup();for(let i=0;i<100;i++){h.next(0);h.engine.step(h.c);}assert.equal(h.calls.length,0);
 h.interrupt();assert.equal(h.engine.step(h.c).ack.status,'held');assert.equal(h.calls.length,0);
});
test('clock jump and absent game-clock binding cannot complete labour',()=>{
 const h=setup();h.engine.step(h.c);h.next(60);assert.equal(h.engine.step(h.c).ack.status,'held');
 h.engine.reset();delete h.sp.Utility;assert.equal(h.engine.step(h.c).ack.status,'held');assert.equal(h.calls.length,0);
});
test('each intermediate recipe stage resumes without duplicating inputs, output or wages',()=>{
 for(const stage of [1,2,3]){const h=setup();h.balances[2].grain--;
  if(stage>=2)h.balances[2].bread+=2;if(stage===3){h.balances[2].gold-=2;h.balances[1].gold+=2;}
  h.engine.reset();for(let i=0;i<3;i++){h.next();h.engine.step(h.c);}
  assert.deepEqual(h.balances[1],h.c.after.worker);assert.deepEqual(h.balances[2],h.c.after.employer);assert.equal(h.calls.length,3-stage);
 }
});
test('asynchronous effects are issued once and timeouts hold',()=>{
 const h=setup();h.defer();labour(h);assert.equal(h.calls.length,1);h.expire();assert.equal(h.engine.step(h.c).ack.status,'held');assert.equal(h.calls.length,1);
});
test('malformed contracts and external drift cannot mint goods or wages',()=>{
 const h=setup();h.c.after.worker.gold=100;assert.equal(h.engine.step(h.c).ack.status,'held');
 h.c.after.worker.gold=14;h.balances[2].bread++;assert.equal(h.engine.step(h.c).ack.status,'held');assert.equal(h.calls.length,0);
});
test('explicit supply imports exactly two grain and does not count as labour',()=>{
 const h=setup();h.c.kind='inventory_supply';h.c.after=structuredClone(h.c.before);h.c.after.employer.grain+=2;
 h.engine.step(h.c);h.next();assert.equal(h.engine.step(h.c).ack.mechanism,'explicit_demo_import');h.engine.reset();h.engine.step(h.c);
 assert.equal(h.calls.length,1);assert.equal(h.balances[2].grain,4);assert.equal(h.balances[2].gold,5);
});

test('custom agreed wage and duration govern attendance, output and payment',()=>{
 const h=setup();h.c.wage_gold=4;h.c.work_minutes=5;h.c.after.worker.gold=16;h.c.after.employer.gold=1;
 h.engine.step(h.c);for(let i=0;i<8;i++){h.next();h.engine.step(h.c);}assert.equal(h.calls.length,0);
 assert.equal(h.engine.status().requiredMinutes,5);assert.equal(h.engine.status().wageGold,4);
 for(let i=0;i<8;i++){h.next();h.engine.step(h.c);}
 assert.equal(h.engine.step(h.c).ack.status,'applied');assert.equal(h.balances[1].gold,16);assert.equal(h.balances[2].gold,1);
 assert.equal(h.calls.length,3);h.engine.reset();h.engine.step(h.c);assert.equal(h.calls.length,3);
});

test('invalid or unaffordable custom production terms cannot start effects',()=>{
 for(const [field,value] of [['wage_gold',0],['wage_gold',21],['wage_gold',true],['wage_gold',6],['work_minutes',4],['work_minutes',121],['work_minutes',5.5]]){
  const h=setup();h.c[field]=value;assert.equal(h.engine.step(h.c).ack.status,'held');assert.equal(h.calls.length,0);
 }
});

test('custom wage resumes partial output without repeating production',()=>{
 const h=setup();h.c.wage_gold=3;h.c.work_minutes=15;h.c.after.worker.gold=15;h.c.after.employer.gold=2;
 h.balances[2].grain--;h.balances[2].bread+=2;
 h.engine.step(h.c);h.next();assert.equal(h.engine.step(h.c).ack.status,'applied');
 assert.equal(h.calls.length,1);assert.equal(h.balances[1].gold,15);
});

test('catching up to a moving employer earns no attendance credit',()=>{
 const h=setup();h.engine.step(h.c);h.next();h.engine.step(h.c);
 assert.equal(h.engine.status().workedMinutes,.5);
 h.separate(400);for(let i=0;i<20;i++){h.next();assert.equal(h.engine.step(h.c).done,false);}
 assert.equal(h.engine.status().phase,'approaching_work');assert.equal(h.engine.status().workedMinutes,.5);
 h.separate(200);h.next();h.engine.step(h.c);assert.equal(h.engine.status().workedMinutes,.5);
 h.next();h.engine.step(h.c);assert.equal(h.engine.status().workedMinutes,1);assert.equal(h.calls.length,0);
});

test('failed attendance can prove no effects but an issued mutation cannot',()=>{
 const h=setup();h.engine.step(h.c);h.separate(400);h.engine.step(h.c);h.advanceWall(30001);
 const result=h.engine.step(h.c);assert.equal(result.ack.status,'held');assert.equal(result.ack.no_effects_issued,true);assert.equal(h.calls.length,0);
 assert.equal(result.ack.catalog_hash,h.c.catalog_hash);assert.equal(result.ack.recipe_hash,h.c.recipe_hash);assert.equal(result.ack.recipe_id,h.c.recipe_id);
 const mutated=setup();mutated.defer();labour(mutated);mutated.expire();
 assert.equal(mutated.engine.step(mutated.c).ack.no_effects_issued,false);
});


test('an owned travelling package cannot earn owner labour without its self-target lease',()=>{
 const h=ownerSetup();h.redirectOwner(1);
 const result=h.engine.step(h.c);assert.equal(result.ack.status,'held');assert.equal(result.ack.no_effects_issued,true);
 assert.equal(h.engine.status().workedMinutes,0);assert.equal(h.calls.length,0);
 assert.equal(h.engine.status().attendance.stationary_lease_verified,false);
});

test('owner lease serial changes and quest release interrupt before inventory effects',()=>{
 for(const disturb of [h=>h.ownerSerial(2),h=>h.stopOwner(),h=>delete h.c.attendance]){
  const h=ownerSetup();h.engine.step(h.c);h.next();h.engine.step(h.c);assert.equal(h.engine.status().workedMinutes,.5);
  disturb(h);h.next();const result=h.engine.step(h.c);
  assert.equal(result.ack.status,'held');assert.equal(result.ack.no_effects_issued,true);assert.equal(h.calls.length,0);
 }
});

test('paid production derives approved input and output quantities from the catalog',()=>{
 const custom=structuredClone(manifest);custom.recipes[0].inputs.grain=2;custom.recipes[0].outputs.bread=3;
 const h=setup(custom);h.c.after.employer.grain=0;h.c.after.employer.bread=5;labour(h);h.next();
 const result=h.engine.step(h.c);assert.equal(result.ack.status,'applied');assert.equal(result.ack.recipe_hash,h.c.recipe_hash);
 assert.deepEqual(h.calls.map(c=>c.slice(1,3)),[['grain',-2],['bread',3],['gold',-2]]);
 assert.equal(h.balances[1].gold+h.balances[2].gold,17);
});

test('paid, legacy owner and explicit supply cannot infer success or write without catalog identity',()=>{
 for(const kind of ['inventory_produce','inventory_self_produce','inventory_supply'])for(const field of ['catalog_hash',...kind==='inventory_supply'?[]:['recipe_hash','recipe_id']]){
  const h=kind==='inventory_self_produce'?ownerSetup():setup();h.c.kind=kind;delete h.c[field];
  if(kind==='inventory_supply'){h.c.after=structuredClone(h.c.before);h.c.after.employer.grain+=2;}
  assert.equal(h.engine.step(h.c).ack.status,'held');assert.equal(h.calls.length,0);
  if(kind==='inventory_self_produce')h.balances[2]=structuredClone(h.c.after.owner);
  else{h.balances[1]=structuredClone(h.c.after.worker);h.balances[2]=structuredClone(h.c.after.employer);}
  assert.equal(h.engine.step(h.c).ack.status,'held');assert.equal(h.calls.length,0);
 }
});
