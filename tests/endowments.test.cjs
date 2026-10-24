const test=require('node:test'),assert=require('node:assert/strict');
const {createEndowmentController}=require('../bridge/endowments.js');
function fixture(){
 let clock=0,loaded=true,stock={gold:7,bread:0,grain:0},calls=[];
 const ids={15:'gold',0x65c97:'bread',0x4b0ba:'grain'};
 const actor={is3DLoaded:()=>loaded,isDead:()=>false,isChild:()=>false,hasKeyword:()=>true,
  getItemCount:f=>stock[ids[f]],addItem:(f,n)=>calls.push({item:ids[f],n})};
 const sp={storage:{},Actor:{from:x=>x},Keyword:{from:x=>x},Game:{getFormEx:id=>id===99?actor:id}};
 const command={id:'founding-resources-v1-99',source:'founding-resources-v1',actor:99,
  grant:{gold:20,bread:2,grain:0},before:{...stock},after:{gold:27,bread:2,grain:0}};
 const controller=createEndowmentController(()=>sp,()=>clock);
 return {command,controller,calls,stock,sp,step:()=>controller.step(command),time:n=>clock=n,loaded:v=>loaded=v,
  apply(){for(const c of calls.splice(0))stock[c.item]+=c.n;}};
}
test('each native addition is issued once and acknowledged only after observed counts',()=>{
 const f=fixture();for(let i=0;i<5;i++)assert.equal(f.step().done,false);
 assert.deepEqual(f.calls,[{item:'gold',n:20}]);f.apply();f.step();assert.deepEqual(f.calls,[{item:'bread',n:2}]);
 f.apply();assert.equal(f.step().ack.status,'applied');assert.deepEqual(f.stock,f.command.after);
});
test('hot reload between legs resumes without repeating delivered gold',()=>{
 const f=fixture();f.step();f.apply();f.controller.reset();f.step();
 assert.deepEqual(f.calls,[{item:'bread',n:2}]);f.apply();assert.equal(f.step().ack.status,'applied');
 f.controller.reset();assert.equal(f.step().ack.status,'applied');assert.equal(f.calls.length,0);
});
test('external drift and unexpected delivery order hold instead of topping up',()=>{
 const f=fixture();f.stock.gold++;assert.equal(f.step().ack.status,'held');assert.equal(f.calls.length,0);
 const g=fixture();g.stock.bread=2;assert.equal(g.step().ack.status,'held');assert.equal(g.calls.length,0);
});
test('an asynchronous timeout does not repeat the addition',()=>{
 const f=fixture();f.step();f.time(5001);assert.equal(f.step().ack.status,'held');assert.equal(f.calls.length,1);
});
test('a bridge hot reload retains an outstanding native addition instead of issuing it twice',()=>{
 const f=fixture();f.step();const replacement=createEndowmentController(()=>f.sp,()=>100);
 replacement.step(f.command);assert.equal(f.calls.length,1);
 f.apply();replacement.step(f.command);assert.deepEqual(f.calls,[{item:'bread',n:2}]);
});
test('unloaded native inventory delivery does not claim a physical action',()=>{
 const f=fixture();f.loaded(false);f.step();f.apply();f.step();f.apply();
 const result=f.step();assert.equal(result.ack.status,'applied');assert.equal(result.ack.loaded,false);assert.match(result.ack.scope,/no movement/);
});
test('missing adult classification and tampered contracts cannot mint resources',()=>{
 const f=fixture();f.sp.Keyword=null;assert.equal(f.step().ack.status,'held');assert.equal(f.calls.length,0);
 const g=fixture();g.command.grant.gold=10000;g.command.after.gold=10007;
 assert.equal(g.step().ack.status,'held');assert.equal(g.calls.length,0);
 const h=fixture();h.command.source='another-pool';assert.equal(h.step().ack.status,'held');
});
