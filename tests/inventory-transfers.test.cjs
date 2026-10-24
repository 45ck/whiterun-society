const test=require('node:test');
const assert=require('node:assert/strict');
const {createInventoryTransfers}=require('../bridge/inventory-transfers.js');
function setup() {
  const balances={100:{gold:9,bread:0},200:{gold:10,bread:1}};
  const calls=[];let frame=0,clock=0,defer=false;
  const queued=[];
  const fresh=id=>{
    if (id===15) return 'gold';if (id===0x65c97) return 'bread';
    const born=frame;
    return {id,is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,
      getItemCount:item=>{assert.equal(born,frame);return balances[id][item];},
      removeItem:(item,n,silent,other)=>{assert.equal(born,frame);calls.push({id,item,n,to:other.id});
        const apply=()=>{balances[id][item]-=n;balances[other.id][item]+=n;};if (defer) queued.push(apply);else apply();}};
  };
  const sp={Actor:{from:x=>x},Game:{getFormEx:fresh}};
  const engine=createInventoryTransfers(()=>sp,()=>clock);
  const command={id:'one',kind:'inventory_trade',buyer:100,seller:200,quantity:1,cost:3,
    before:{buyer:{gold:9,bread:0},seller:{gold:10,bread:1}},after:{buyer:{gold:6,bread:1},seller:{gold:13,bread:0}}};
  return {balances,calls,engine,command,sp,next:()=>{frame++;clock+=16;},defer:()=>{defer=true;},flush:()=>{queued.splice(0).forEach(f=>f());},expire:()=>{clock+=6000;}};
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
    const v=h.command[field][role];h.command[field][role]={bread:v.bread,gold:v.gold};
  }
  h.engine.step(h.command);h.next();h.engine.step(h.command);h.next();
  assert.equal(h.engine.step(h.command).ack.status,'applied');
});
