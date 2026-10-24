const test=require('node:test'),assert=require('node:assert/strict');
const {createProductionController}=require('../bridge/production.js');
function setup(){
 const balances={1:{gold:12,bread:0,grain:0},2:{gold:5,bread:2,grain:2}},calls=[],queue=[];
 let game=1,clock=0,owned=true,defer=false,frame=0;
 const form=id=>{
  if(id===15)return 'gold';if(id===0x65c97)return 'bread';if(id===0x4b0ba)return 'grain';
  const born=frame,check=()=>assert.equal(born,frame);
  return {id,is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,getCurrentPackage:()=>({getFormID:()=>owned?99:88}),
   getPositionX:()=>0,getPositionY:()=>0,getPositionZ:()=>0,getItemCount:k=>{check();return balances[id][k];},
   removeItem:(k,n,silent,to)=>{check();calls.push([id,k,-n,to?.id]);const f=()=>{balances[id][k]-=n;if(to)balances[to.id][k]+=n;};defer?queue.push(f):f();},
   addItem:(k,n)=>{check();calls.push([id,k,n]);const f=()=>{balances[id][k]+=n;};defer?queue.push(f):f();}};
 };
 const sp={Actor:{from:x=>x},Game:{getFormEx:form},Utility:{getCurrentGameTime:()=>game}};
 const engine=createProductionController(()=>sp,()=>clock);
 const c={id:'work',kind:'inventory_produce',worker:1,employer:2,expected_package:99,work_minutes:30,
  before:structuredClone({worker:balances[1],employer:balances[2]}),after:{worker:{gold:14,bread:0,grain:0},employer:{gold:3,bread:4,grain:1}}};
 return {engine,c,balances,calls,sp,next:(minutes=.5)=>{frame++;game+=minutes/1440;clock+=100;},interrupt:()=>{owned=false;},
  defer:()=>{defer=true;},flush:()=>queue.splice(0).forEach(f=>f()),expire:()=>{clock+=6000;}};
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
