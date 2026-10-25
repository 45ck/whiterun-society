const test=require('node:test'),assert=require('node:assert/strict');
const {createRestController}=require('../bridge/rest.js');
function fixture(options={}){
 let clock=0,game=1,x=2000,running=false,current=42,sit=0,furniture=0,occupied=false,combat=false,releasePackage=true,stopQuest=true;
 const requested=[];
 const actor={getFormID:()=>99,is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,hasKeyword:()=>true,isInCombat:()=>combat,
  getCurrentScene:()=>null,getSleepState:()=>0,
  getPositionX:()=>x,getPositionY:()=>0,getPositionZ:()=>0,getCurrentPackage:()=>({getFormID:()=>current}),evaluatePackage:()=>{},
  getSitState:()=>sit,getFurnitureReference:()=>furniture?{getFormID:()=>furniture}:null};
 const seat={getFormID:()=>0x8f15b,is3DLoaded:()=>true,getPositionX:()=>0,getPositionY:()=>0,getPositionZ:()=>0,isFurnitureInUse:()=>occupied};
 const list=()=>{let rows=[];return {revert:()=>rows=[],addForm:r=>rows.push(r),getSize:()=>rows.length,getAt:i=>rows[i]};};
 const variable=()=>{let v=0;return {getValue:()=>v,setValue:n=>v=n};};
 const quest={isRunning:()=>running,start:()=>{running=true;return true;},stop:()=>{if(stopQuest)running=false;if(releasePackage)current=42;}};
 const forms=[quest,{getFormID:()=>123},list(),list(),variable(),variable(),variable()];
 const sp={Game:{getFormFromFile:(id,file)=>{requested.push({id,file});return forms[id-0x800-(options.router?.offset||0)];},getFormEx:id=>id===99?actor:id===0x13794?{}:seat},
  Actor:{from:f=>f},ObjectReference:{from:f=>f},Keyword:{from:f=>f},Quest:{from:f=>f},FormList:{from:f=>f},GlobalVariable:{from:f=>f},Utility:{getCurrentGameTime:()=>game}};
 const controller=createRestController(()=>sp,()=>clock,undefined,options),command={id:'rest-one',kind:'rest_at_bench',actor:99,target:0x8f15b,rest_minutes:30};
 return {controller,command,actor,seat,forms,sp,requested,step:()=>controller.step(command),move:n=>x=n,time:n=>clock=n,retainQuest:v=>stopQuest=!v,
  tick:(m=.5)=>{clock+=100;game+=m/1440;},sit:(n=3,id=0x8f15b)=>{sit=n;furniture=id;},occupied:v=>occupied=v,combat:v=>combat=v,retain:v=>releasePackage=!v,
  start(){for(let i=0;i<3;i++)this.step();forms[5].setValue(forms[4].getValue());forms[6].setValue(1);this.step();current=123;},
  seated(){this.start();x=100;this.sit();this.step();}};
}
test('recovery requires thirty game minutes at the exact bench and verified release',()=>{
 const f=fixture();f.seated();for(let i=0;i<61;i++){f.tick();f.step();}
 const result=f.step();assert.equal(result.ack.status,'applied');assert.equal(result.ack.rest.exact_furniture_verified,true);assert.equal(result.ack.rest.release_verified,true);
 assert.ok(result.ack.rest.rested_minutes>=30);assert.ok(result.ack.rest.seated_samples>=60);
});

test('activity furniture router uses its independent file and offset without changing legacy defaults',()=>{
 const f=fixture({router:{file:'WhiterunActivities.esp',offset:0x100}});f.seated();
 for(let i=0;i<61;i++){f.tick();f.step();}assert.equal(f.step().ack.status,'applied');
 assert.ok(f.requested.length>0);assert.ok(f.requested.every(r=>r.file==='WhiterunActivities.esp'&&r.id>=0x900&&r.id<=0x906));
 const legacy=fixture();legacy.start();assert.ok(legacy.requested.every(r=>r.file==='WhiterunRest.esp'));
});

test('cancelled partial seated attendance releases as held without later rest credit',()=>{
 const f=fixture();f.seated();for(let i=0;i<10;i++){f.tick();f.step();}
 f.controller.cancel(f.command,'Assignment withdrawn');const result=f.step();assert.equal(result.ack.status,'held');
 assert.equal(result.ack.rest.release_verified,true);assert.ok(result.ack.rest.rested_minutes<30);
 for(let i=0;i<80;i++){f.tick();f.step();}assert.equal(f.step().ack.status,'held');
});

test('release needs stopped quest as well as loss of package; late release remains held',()=>{
 const f=fixture();f.seated();f.retainQuest(true);for(let i=0;i<61;i++){f.tick();f.step();}
 assert.equal(f.step().done,false);f.time(20000);assert.equal(f.step().ack.status,'held');assert.equal(f.controller.released(),false);
 f.retainQuest(false);const result=f.step();assert.equal(result.ack.status,'held');assert.equal(result.ack.rest.release_verified,true);
});

test('a cold cancelled slot cannot report release while its old package is still owned',()=>{
 const f=fixture();f.seated();f.controller.reset();f.retain(true);f.controller.cancel(f.command,'Reload');
 assert.equal(f.step().done,false);f.time(20000);assert.equal(f.step().ack.rest.release_verified,false);
});

test('negative game time and reused actor base identity stop attendance',()=>{
 const f=fixture();f.seated();f.tick(-1);f.step();assert.equal(f.step().ack.status,'held');
 const g=fixture();g.command.actor_base_id=888;g.actor.getActorBase=()=>({getFormID:()=>999});
 g.step();assert.equal(g.step().ack.status,'held');assert.equal(g.controller.status().rested_minutes,0);
});
test('proximity and an owned package do not count as seated attendance',()=>{
 const f=fixture();f.start();f.move(100);for(let i=0;i<50;i++){f.tick();f.step();}
 assert.equal(f.controller.status().rested_minutes,0);assert.equal(f.controller.status().phase,'travelling');
});
test('occupied benches and combat prevent starting the break',()=>{
 const f=fixture();f.occupied(true);f.step();assert.equal(f.step().ack.status,'held');
 const g=fixture();g.combat(true);g.step();assert.equal(g.step().ack.status,'held');
});
test('wrong furniture and interrupted sitting stop recovery',()=>{
 const f=fixture();f.seated();f.sit(3,12345);f.tick();f.step();assert.equal(f.step().ack.status,'held');
 const g=fixture();g.seated();g.sit(0);g.tick();g.step();assert.equal(g.step().ack.status,'held');
});
test('paused clock adds no rest and waiting jumps are rejected',()=>{
 const f=fixture();f.seated();for(let i=0;i<100;i++){f.tick(0);f.step();}assert.equal(f.controller.status().rested_minutes,0);
 f.tick(60);f.step();assert.equal(f.step().ack.status,'held');
});
test('release cannot be claimed while the owned package remains',()=>{
 const f=fixture();f.seated();f.retain(true);for(let i=0;i<61;i++){f.tick();f.step();}
 assert.equal(f.step().done,false);f.time(20000);assert.equal(f.step().ack.status,'held');assert.equal(f.controller.status().release_verified,false);
});
test('an unavailable exact furniture sensor cannot start qualified rest',()=>{
 const f=fixture();delete f.actor.getFurnitureReference;f.step();assert.equal(f.step().ack.status,'held');
});

test('bench catalogue controls offered references and exposes observed space and ownership scope',()=>{
 const f=fixture(),catalog=structuredClone(require('../config/places.json'));
 catalog.venues=[{...catalog.venues.find(v=>v.kind==='rest_bench'),id:500,name:'New bench'}];
 f.seat.getFormID=()=>500;f.seat.getParentCell=()=>({getFormID:()=>10,isInterior:()=>false});f.seat.getWorldSpace=()=>({getFormID:()=>1});
 const c=createRestController(()=>f.sp,()=>0,catalog),sites=c.sense([]).sites;
 assert.equal(sites.length,1);assert.equal(sites[0].id,500);assert.deepEqual(sites[0].space,{cell:10,interior:false,world:1});
 assert.equal(sites[0].ownership,'authored_unowned_not_sensed');
 c.step(f.command);assert.equal(c.step(f.command).ack.status,'held');
 f.seat.getActorOwner=()=>({getFormID:()=>33});f.seat.getFactionOwner=()=>null;assert.equal(c.sense([]).sites.length,0);
 f.seat.getActorOwner=()=>null;assert.equal(c.sense([]).sites[0].ownership,'native_unowned');
 f.seat.isDisabled=()=>true;assert.equal(c.sense([]).sites.length,0);
});
