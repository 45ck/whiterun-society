const test=require('node:test');
const assert=require('node:assert/strict');
const {createInventoryTransfers}=require('../bridge/inventory-transfers.js');
function setup() {
  const balances={100:{gold:9,bread:0,grain:0},200:{gold:10,bread:1,grain:0}};
  const calls=[];let frame=0,clock=0,defer=false;
  const queued=[];
  const fresh=id=>{
    if (id===15) return 'gold';if (id===0x65c97) return 'bread';if(id===0x4b0ba)return 'grain';
    const born=frame;
    return {id,is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,
      getItemCount:item=>{assert.equal(born,frame);return balances[id][item];},
      equipItem:(item,prevent,silent)=>{assert.equal(born,frame);assert.equal(prevent,false);assert.equal(silent,true);calls.push({id,item,consume:1});
        const apply=()=>{balances[id][item]--;};if(defer)queued.push(apply);else apply();},
      removeItem:(item,n,silent,other)=>{assert.equal(born,frame);calls.push({id,item,n,to:other.id});
        const apply=()=>{balances[id][item]-=n;balances[other.id][item]+=n;};if (defer) queued.push(apply);else apply();}};
  };
  const sp={Actor:{from:x=>x},Game:{getFormEx:fresh}};
  const catalog={itemIds:()=>['bread','gold','grain'],status:()=>({available:true,catalog_hash:'a'.repeat(64)}),resolve:()=>({available:true,forms:{gold:fresh(15),bread:fresh(0x65c97),grain:fresh(0x4b0ba)}})};
  const engine=createInventoryTransfers(()=>sp,()=>clock,{catalog});
  const command={catalog_hash:'a'.repeat(64),id:'one',kind:'inventory_trade',buyer:100,seller:200,quantity:1,cost:3,
    before:{buyer:{gold:9,bread:0,grain:0},seller:{gold:10,bread:1,grain:0}},after:{buyer:{gold:6,bread:1,grain:0},seller:{gold:13,bread:0,grain:0}}};
  return {balances,calls,engine,command,sp,catalog,next:()=>{frame++;clock+=16;},defer:()=>{defer=true;},flush:()=>{queued.splice(0).forEach(f=>f());},expire:()=>{clock+=6000;}};
}
test('two legs use fresh native handles and verify final balances',()=>{
  const h=setup();assert.equal(h.engine.step(h.command).done,false);h.next();
  assert.equal(h.engine.step(h.command).done,false);h.next();
  assert.equal(h.engine.step(h.command).ack.status,'applied');
  assert.deepEqual(h.calls,[{id:200,item:'bread',n:1,to:100},{id:100,item:'gold',n:3,to:200}]);
  h.engine.step(h.command);assert.equal(h.calls.length,2);
});
test('deferred native mutations are awaited without repeated removals',()=>{
  const h=setup();h.defer();h.engine.step(h.command);h.next();h.engine.step(h.command);
  assert.equal(h.calls.length,1);h.flush();h.next();h.engine.step(h.command);h.next();h.engine.step(h.command);
  assert.equal(h.calls.length,2);h.flush();h.next();assert.equal(h.engine.step(h.command).ack.status,'applied');
});
test('restart after the goods leg resumes payment without transferring goods twice',()=>{
  const h=setup();h.engine.step(h.command);h.engine.reset();h.next();h.engine.step(h.command);h.next();
  assert.equal(h.engine.step(h.command).ack.status,'applied');assert.equal(h.calls.length,2);
});
test('external inventory drift is held without forcing counts',()=>{
  const h=setup();h.balances[100].gold=8;
  assert.equal(h.engine.step(h.command).ack.status,'held');assert.equal(h.calls.length,0);
});
test('a lost native operation times out without charging a second time',()=>{
  const h=setup();h.defer();h.engine.step(h.command);h.expire();
  assert.equal(h.engine.step(h.command).ack.status,'held');assert.equal(h.calls.length,1);
});
test('wire key ordering does not change inventory equality',()=>{
  const h=setup();for (const field of ['before','after']) for(const role of ['buyer','seller']) {
    const v=h.command[field][role];h.command[field][role]={grain:v.grain,bread:v.bread,gold:v.gold};
  }
  h.engine.step(h.command);h.next();h.engine.step(h.command);h.next();
  assert.equal(h.engine.step(h.command).ack.status,'applied');
});

test('food use consumes one loaf with no gold change and does not repeat',()=>{
 const h=setup(),c={catalog_hash:'a'.repeat(64),id:'eat',actor:200,before:{gold:10,bread:1,grain:0},after:{gold:10,bread:0,grain:0}};
 assert.equal(h.engine.consume(c).done,false);h.next();
 assert.equal(h.engine.consume(c).ack.status,'applied');h.engine.consume(c);
 assert.deepEqual(h.balances[200],{gold:10,bread:0,grain:0});assert.equal(h.calls.length,1);
});

test('deferred food use waits once and holds uncertain effects',()=>{
 const h=setup(),c={catalog_hash:'a'.repeat(64),id:'eat',actor:200,before:{gold:10,bread:1,grain:0},after:{gold:10,bread:0,grain:0}};
 h.defer();h.engine.consume(c);h.next();h.engine.consume(c);assert.equal(h.calls.length,1);
 h.expire();assert.equal(h.engine.consume(c).ack.status,'held');assert.equal(h.calls.length,1);
});

test('loading an already-consumed state does not eat another loaf',()=>{
 const h=setup(),c={catalog_hash:'a'.repeat(64),id:'eat',actor:200,before:{gold:10,bread:2,grain:0},after:{gold:10,bread:1,grain:0}};
 h.engine.reset();assert.equal(h.engine.consume(c).ack.status,'applied');assert.equal(h.calls.length,0);
});

test('consumption rejects inventory drift and malformed effects before mutation',()=>{
 const h=setup(),c={catalog_hash:'a'.repeat(64),id:'eat',actor:200,before:{gold:10,bread:1,grain:0},after:{gold:9,bread:0,grain:0}};
 assert.equal(h.engine.consume(c).ack.status,'held');c.after.gold=10;h.balances[200].gold=11;
 assert.equal(h.engine.consume(c).ack.status,'held');assert.equal(h.calls.length,0);
});

function grainSetup(){
 const h=setup();Object.assign(h.balances[100],{grain:0});Object.assign(h.balances[200],{grain:3});
 h.command.commodity='grain';h.command.before.buyer.grain=0;h.command.before.seller.grain=3;
 h.command.after.buyer={gold:6,bread:0,grain:1};h.command.after.seller={gold:13,bread:1,grain:2};return h;
}

test('all live commodity handles come from the configured resolver',()=>{
 const h=setup(),native=h.sp.Game.getFormEx;
 h.sp.Game.getFormEx=id=>{assert.ok(![15,0x65c97,0x4b0ba].includes(id),'Executor used an embedded commodity form');return native(id);};
 h.engine.step(h.command);h.next();h.engine.step(h.command);h.next();
 assert.equal(h.engine.step(h.command).ack.status,'applied');assert.equal(h.calls.length,2);
});

test('missing changed or unavailable catalog cannot certify or mutate legacy trade or food intent',()=>{
 for(const change of [h=>delete h.command.catalog_hash,h=>h.command.catalog_hash='b'.repeat(64),
   h=>h.catalog.status=()=>({available:false,catalog_hash:'a'.repeat(64)}),
   h=>h.catalog.resolve=()=>({available:false,forms:{gold:'gold',bread:'bread'}})]){
  const h=setup();change(h);assert.equal(h.engine.step(h.command).ack.status,'held');assert.equal(h.calls.length,0);
  const c={id:'eat-invalid',actor:200,catalog_hash:h.command.catalog_hash,before:{gold:10,bread:1,grain:0},after:{gold:10,bread:0,grain:0}};
  assert.equal(h.engine.consume(c).ack.status,'held');assert.equal(h.calls.length,0);
 }
 const h=setup(),bare=createInventoryTransfers(()=>h.sp);assert.equal(bare.step(h.command).ack.status,'held');assert.equal(h.calls.length,0);
});

test('additional configured stock is conserved and unknown or drifting stock holds both transfer primitives',()=>{
 function expanded(){const h=setup(),resolve=h.catalog.resolve;
  h.catalog.itemIds=()=>['bread','gold','grain','ore'];h.catalog.resolve=()=>({available:true,forms:{...resolve().forms,ore:'ore'}});
  for(const actor of [100,200])h.balances[actor].ore=4;
  for(const side of ['before','after'])for(const role of ['buyer','seller'])h.command[side][role].ore=4;
  return h;}
 const h=expanded();h.engine.step(h.command);h.next();h.engine.step(h.command);h.next();
 assert.equal(h.engine.step(h.command).ack.status,'applied');assert.equal(h.balances[100].ore,4);assert.equal(h.balances[200].ore,4);
 for(const observed of [3,null]){const f=expanded();f.balances[200].ore=observed;
  assert.equal(f.engine.step(f.command).ack.status,'held');assert.equal(f.calls.length,0);
  const c={id:'food-full',actor:200,catalog_hash:f.command.catalog_hash,before:{gold:10,bread:1,grain:0,ore:4},after:{gold:10,bread:0,grain:0,ore:4}};
  assert.equal(f.engine.consume(c).ack.status,'held');assert.equal(f.calls.length,0);
 }
});
test('grain purchase transfers wheat and payment exactly once without consuming bread',()=>{
 const h=grainSetup();h.engine.step(h.command);h.next();h.engine.step(h.command);h.next();
 assert.deepEqual(h.engine.step(h.command).ack.inventory,h.command.after);
 h.engine.step(h.command);assert.deepEqual(h.calls,[{id:200,item:'grain',n:1,to:100},{id:100,item:'gold',n:3,to:200}]);
});
test('grain payment resumes after a goods-leg restart and awaits deferred effects',()=>{
 const h=grainSetup();h.defer();h.engine.step(h.command);h.next();h.engine.step(h.command);assert.equal(h.calls.length,1);
 h.flush();h.engine.reset();h.next();h.engine.step(h.command);h.next();h.engine.step(h.command);assert.equal(h.calls.length,2);
 h.flush();h.next();assert.equal(h.engine.step(h.command).ack.status,'applied');
});
test('grain trade holds if even the untraded bread inventory changes',()=>{
 const h=grainSetup();h.balances[200].bread++;
 assert.equal(h.engine.step(h.command).ack.status,'held');assert.equal(h.calls.length,0);
});
test('malformed contracts cannot mint stock, skip payment or change another commodity',()=>{
 for(const mutate of [c=>c.after.buyer.grain++,c=>c.after.seller.gold--,c=>c.after.buyer.bread++,
   c=>c.quantity=0,c=>c.cost=-1,c=>c.commodity='ore',c=>c.buyer=c.seller,c=>delete c.before.buyer.grain]){
  const h=grainSetup();mutate(h.command);assert.equal(h.engine.step(h.command).ack.status,'held');assert.equal(h.calls.length,0);
 }
});
