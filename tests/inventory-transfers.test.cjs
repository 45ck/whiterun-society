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

test('legacy trade rejects without native effects',()=>{const h=setup();assert.equal(h.engine.step(h.command).ack.status,'held');assert.equal(h.calls.length,0);});

test('legacy food still rejects missing changed and unavailable catalog proofs',()=>{
 for(const change of [h=>delete h.command.catalog_hash,h=>h.command.catalog_hash='b'.repeat(64),
  h=>h.catalog.status=()=>({available:false,catalog_hash:'a'.repeat(64)}),
  h=>h.catalog.resolve=()=>({available:false,forms:{gold:'gold',bread:'bread'}})]){
  const h=setup();change(h);
  const c={id:'eat-invalid',actor:200,catalog_hash:h.command.catalog_hash,before:{gold:10,bread:1,grain:0},after:{gold:10,bread:0,grain:0}};
  assert.equal(h.engine.consume(c).ack.status,'held');assert.equal(h.calls.length,0);
 }
});
test('legacy food preserves additional catalog balances and rejects unknown or drifting stock',()=>{
 for(const observed of [4,3,null]){
  const h=setup(),resolve=h.catalog.resolve;
  h.catalog.itemIds=()=>['bread','gold','grain','ore'];h.catalog.resolve=()=>({available:true,forms:{...resolve().forms,ore:'ore'}});
  h.balances[200].ore=observed;
  const c={id:'food-full',actor:200,catalog_hash:h.command.catalog_hash,before:{gold:10,bread:1,grain:0,ore:4},after:{gold:10,bread:0,grain:0,ore:4}};
  const result=h.engine.consume(c);
  if(observed===4){assert.equal(result.done,false);h.next();assert.equal(h.engine.consume(c).ack.status,'applied');assert.equal(h.balances[200].ore,4);}
  else{assert.equal(result.ack.status,'held');assert.equal(h.calls.length,0);}
 }
});
