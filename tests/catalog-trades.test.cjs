const test=require('node:test'),assert=require('node:assert/strict');
const {createInventoryTransfers}=require('../bridge/inventory-transfers.js');
const {marketPolicyHash}=require('../bridge/market-policy.js');
const clone=x=>JSON.parse(JSON.stringify(x));

test('catalog commodity metadata is a defensive pure getter with no native calls',()=>{
 const {createEconomyCatalogController}=require('../bridge/economy-catalog.js');
 const catalog=createEconomyCatalogController(()=>{throw Error('Native binding must not be touched');});
 const first=catalog.commodities(),expected=clone(first);first[0].currency=!first[0].currency;first[0].native.local_form_id=0;
 assert.deepEqual(catalog.commodities(),expected);
});

function fixture(){
 let clock=100,session='trade-test',frame=0,permit,throwCall=0;
 const balances={buyer:{gold:100,bread:0,grain:0,ore:4},seller:{gold:10,bread:10,grain:10,ore:8}};
 const calls=[],queue=[],ids={buyer:100,seller:200},bases={buyer:101,seller:201};
 const positions={buyer:[0,0,0],seller:[100,0,0]},cells={buyer:42,seller:42},flags={buyer:{},seller:{}};
 const policy=clone(require('../config/market-policy.json'));policy.catalog_hash='a'.repeat(64);
 policy.goods.push({...clone(policy.goods[1]),commodity:'ore',legacy_retail_capability:null});
 const keys=Object.keys(balances.buyer).sort(),metadata=keys.map(id=>({id,currency:id==='gold'}));
 const forms=Object.fromEntries(keys.map(k=>[k,{item:k}]));
 const fresh=role=>{const born=frame;const actor={getFormID:()=>ids[role],getActorBase:()=>({getFormID:()=>bases[role]}),
  is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,hasKeyword:()=>true,
  getPositionX:()=>positions[role][0],getPositionY:()=>positions[role][1],getPositionZ:()=>positions[role][2],
  getParentCell:()=>({getFormID:()=>cells[role]}),
  getItemCount:form=>{assert.equal(born,frame,'stale item handle');return balances[role][form.item];},
  removeItem:(form,amount,silent,other)=>{assert.equal(born,frame,'stale transfer handle');assert.equal(silent,true);
   const to=other.getFormID()===100?'buyer':'seller';calls.push({from:role,to,item:form.item,amount});
   if(throwCall===calls.length)throw Error('native call exception');
   queue.push({from:role,to,item:form.item,amount,debit:false,credit:false});}};
  return Object.assign(actor,flags[role]);};
 const sp={Actor:{from:x=>x},Keyword:{from:x=>x},Game:{getFormEx:id=>id===100?fresh('buyer'):id===200?fresh('seller'):id===0x13794?{}:null}};
 const catalog={itemIds:()=>keys,commodities:()=>clone(metadata),status:()=>({available:true,type_verified:true,catalog_hash:'a'.repeat(64)}),resolve:()=>({available:true,type_verified:true,forms})};
 const options={catalog,marketPolicy:policy,session:()=>session};
 let controller=createInventoryTransfers(()=>sp,()=>clock,options);
 const contract={trade_id:'fixture-trade',catalog_hash:'a'.repeat(64),market_policy_hash:marketPolicyHash(policy),
  buyer:100,buyer_base_id:101,seller:200,seller_base_id:201,commodity:'ore',currency:'gold',quantity:3,unit_price:7,cost:21,
  origin_session:session,delivery_epoch:controller.status().epoch,before:clone(balances),after:clone(balances),
  consent_id:'operator-fixture',consent_hash:'c'.repeat(64)};
 const reprice=(commodity='ore',quantity=3,price=7)=>{Object.assign(contract,{commodity,quantity,unit_price:price,cost:quantity*price,before:clone(balances),after:clone(balances)});
  contract.after.buyer[commodity]+=quantity;contract.after.seller[commodity]-=quantity;contract.after.buyer.gold-=contract.cost;contract.after.seller.gold+=contract.cost;};reprice();
 const command=(phase='arm',change={})=>({kind:'inventory_trade',protocol:2,phase,id:contract.trade_id+'-'+phase,
  session,...clone(contract),...(phase==='deliver'?{permit}:{}),...change});
 return {balances,calls,queue,bases,positions,cells,flags,sp,catalog,policy,options,contract,command,reprice,
  get controller(){return controller;},next(){frame++;clock+=16;},time:n=>clock=n,session:s=>session=s,throws:n=>throwCall=n,
  replace(){controller=createInventoryTransfers(()=>sp,()=>clock,options);},
  arm(change={}){const result=controller.step(command('arm',change));if(result.ack?.permit)permit=result.ack.permit;return result;},
  deliver(change={}){return controller.step(command('deliver',change));},
  apply(side='both'){const entry=queue[0];if(!entry)return;
   if((side==='both'||side==='debit')&&!entry.debit){balances[entry.from][entry.item]-=entry.amount;entry.debit=true;}
   if((side==='both'||side==='credit')&&!entry.credit){balances[entry.to][entry.item]+=entry.amount;entry.credit=true;}
   if(entry.debit&&entry.credit)queue.shift();},
  finish(){for(let i=0;i<8;i++){const result=this.deliver();if(result.done)return result;this.apply();this.next();}throw Error('Trade did not settle');}};
}

test('trade capability binds reviewed policy catalog epoch and live witnesses',()=>{
 const f=fixture(),s=f.controller.status();assert.equal(s.available,true);assert.equal(s.protocol,2);
 assert.equal(s.market_policy_hash,f.contract.market_policy_hash);assert.equal(s.witness_durability,'live_controller_only');
});
test('fourth configured noncurrency commodity trades multiple units through two witnessed legs',()=>{
 const f=fixture();const arm=f.arm().ack;assert.equal(arm.phase,'armed');assert.equal(arm.accepted,true);assert.equal(arm.effects_issued,false);
 assert.deepEqual(arm.inventory,f.contract.before);assert.equal(f.calls.length,0);
 const ack=f.finish().ack;assert.equal(ack.status,'applied');assert.equal(ack.accepted,true);assert.deepEqual(ack.inventory,f.contract.after);
 assert.deepEqual(f.calls,[{from:'seller',to:'buyer',item:'ore',amount:3},{from:'buyer',to:'seller',item:'gold',amount:21}]);
 assert.deepEqual(ack.legs.map(({leg,item,amount,issued,observed})=>({leg,item,amount,issued,observed})),[
  {leg:'goods',item:'ore',amount:3,issued:true,observed:true},{leg:'payment',item:'gold',amount:21,issued:true,observed:true}]);
 assert.equal(ack.inventory.buyer.bread,0);assert.equal(ack.inventory.seller.grain,10);
});
for(const commodity of ['bread','grain'])test(commodity+' remains a connected protocol2 exchange',()=>{
 const f=fixture();f.reprice(commodity,2,3);f.arm();assert.equal(f.finish().ack.status,'applied');assert.equal(f.calls[0].item,commodity);
});
test('native handles are reacquired on every frame while deferred effects wait',()=>{
 const f=fixture();f.arm();f.deliver();for(let i=0;i<3;i++){f.next();f.deliver();}assert.equal(f.calls.length,1);
 f.apply();f.next();assert.equal(f.finish().ack.status,'applied');
});
for(const side of ['debit','credit'])test('goods '+side+' alone waits without paying or repeating goods',()=>{
 const f=fixture();f.arm();f.deliver();f.apply(side);f.next();assert.equal(f.deliver().done,false);assert.equal(f.calls.length,1);
 f.apply();f.next();f.deliver();assert.equal(f.calls.length,2);assert.equal(f.calls[1].item,'gold');
});
for(const side of ['debit','credit'])test('payment '+side+' alone does not certify a completed sale',()=>{
 const f=fixture();f.arm();f.deliver();f.apply();f.next();f.deliver();f.apply(side);f.next();
 assert.equal(f.deliver().done,false);assert.equal(f.calls.length,2);f.apply();assert.equal(f.deliver().ack.status,'applied');
});
test('regression of an already observed transfer side holds without replay',()=>{
 const f=fixture();f.arm();f.deliver();f.apply('debit');f.deliver();f.balances.seller.ore+=3;
 assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,1);
});
test('full afterstate without any native-issued witness cannot arm',()=>{
 const f=fixture();Object.assign(f.balances.buyer,f.contract.after.buyer);Object.assign(f.balances.seller,f.contract.after.seller);
 assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
});
test('matching goodsOnly after arming cannot infer a goods transfer or authorize payment',()=>{
 const f=fixture();f.arm();f.balances.seller.ore-=3;f.balances.buyer.ore+=3;
 assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,0);
});
test('missing arm cannot deliver even with a plausible permit',()=>{
 const f=fixture(),ack=f.deliver({permit:'f'.repeat(64)}).ack;assert.equal(ack.status,'held');assert.equal(ack.effects_issued,null);assert.equal(f.calls.length,0);
});
test('wrong permit cannot spend either purse',()=>{
 const f=fixture();f.arm();assert.equal(f.deliver({permit:'wrong'}).ack.status,'held');assert.equal(f.calls.length,0);
});
test('duplicate arm returns same permit and no repeated effects',()=>{
 const f=fixture(),arm=f.arm();f.next();assert.deepEqual(f.arm(),arm);assert.equal(f.calls.length,0);
});
test('complete receipt retains exact identity and never issues a third transfer',()=>{
 const f=fixture();f.arm();const ack=f.finish().ack;for(const [k,v] of Object.entries(f.contract))assert.deepEqual(ack[k],v,k);
 assert.deepEqual(f.deliver().ack,ack);assert.equal(f.calls.length,2);
});
test('returned receipt mutation cannot falsify retained proof',()=>{
 const f=fixture();f.arm();const ack=f.finish().ack;ack.legs[0].issued=false;ack.inventory.buyer.gold=0;
 assert.equal(f.deliver().ack.legs[0].issued,true);assert.equal(f.deliver().ack.inventory.buyer.gold,79);
});
test('late arm reports effects and preserves deliver completion receipt',()=>{
 const f=fixture();f.arm();const ack=f.finish().ack,late=f.arm().ack;
 assert.equal(late.status,'held');assert.equal(late.effects_issued,true);assert.equal(late.no_effects_issued,false);assert.deepEqual(f.deliver().ack,ack);
});
test('different immutable payload under same trade ID cannot reuse permit',()=>{
 const f=fixture();f.arm();assert.equal(f.deliver({consent_hash:'d'.repeat(64)}).ack.status,'held');assert.equal(f.finish().ack.status,'applied');
});
test('both purses are reserved until complete and cannot arm overlapping trade',()=>{
 const f=fixture();f.arm();assert.deepEqual(f.controller.reservedActors().sort(),[100,200]);
 assert.equal(f.arm({trade_id:'other',id:'other-arm'}).ack.status,'held');assert.equal(f.finish().ack.status,'applied');assert.deepEqual(f.controller.reservedActors(),[]);
});
for(const issue of [1,2])test('native exception on leg '+issue+' retains issued witness and both reservations',()=>{
 const f=fixture();f.arm();f.throws(issue);const ack=f.finish().ack;
 assert.equal(ack.status,'held');assert.equal(ack.effects_issued,true);assert.equal(ack.legs[issue-1].issued,true);
 const count=f.calls.length;f.deliver();assert.equal(f.calls.length,count);assert.deepEqual(f.controller.reservedActors().sort(),[100,200]);
});
test('partial debit timeout never retries and never pays',()=>{
 const f=fixture();f.arm();f.deliver();f.apply('debit');f.deliver();f.time(5101);const ack=f.deliver().ack;
 assert.equal(ack.status,'held');assert.equal(ack.legs[0].debit_observed,true);assert.equal(ack.legs[0].credit_observed,false);assert.equal(f.calls.length,1);
});
test('clock rollback cannot advance or repeat a leg',()=>{
 const f=fixture();f.arm();f.deliver();f.time(99);assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,1);
});
test('expired unused arm remains a no-effect hold',()=>{
 const f=fixture();f.arm();f.time(120101);const ack=f.deliver().ack;assert.equal(ack.status,'held');assert.equal(ack.no_effects_issued,true);assert.equal(f.calls.length,0);
});
test('reset before delivery rotates epoch and cannot reuse old permit',()=>{
 const f=fixture();f.arm();const old=f.controller.status().epoch;f.controller.reset();assert.notEqual(f.controller.status().epoch,old);
 assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,0);
});
test('cold reset after goods delivery cannot infer authority to charge payment',()=>{
 const f=fixture();f.arm();f.deliver();f.apply();f.controller.reset();assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,1);
});
test('new controller cannot certify an already complete afterstate',()=>{
 const f=fixture();f.arm();f.finish();f.replace();assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,2);
});
test('outer session rebinding cannot overwrite original grant authority',()=>{
 const f=fixture();f.arm();f.session('new-session');assert.equal(f.deliver({session:'new-session'}).ack.status,'held');assert.equal(f.calls.length,0);
});
for(const role of ['buyer','seller'])test(role+' base replacement before payment holds without a second transfer',()=>{
 const f=fixture();f.arm();f.deliver();f.apply();f.bases[role]++;
 assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,1);
});
test('catalog hash change holds before a native transfer',()=>{
 const f=fixture();f.arm();f.catalog.status=()=>({available:true,type_verified:true,catalog_hash:'b'.repeat(64)});
 assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,0);
});
test('unresolved native form type cannot arm',()=>{
 const f=fixture();f.catalog.resolve=()=>({available:true,type_verified:false,forms:{}});assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
});
for(const field of ['buyer','buyer_base_id','seller','seller_base_id'])test('invalid '+field+' rejects arm',()=>{
 const f=fixture();assert.equal(f.arm({[field]:true}).ack.status,'held');assert.equal(f.calls.length,0);
});
for(const change of [{quantity:0},{quantity:11},{unit_price:0},{unit_price:101},{cost:999},
 {commodity:'gold'},{currency:'ore'},{market_policy_hash:'b'.repeat(64)},{consent_id:''},{consent_hash:'bad'}])test('invalid bound trade '+JSON.stringify(change)+' cannot arm',()=>{
 const f=fixture();assert.equal(f.arm(change).ack.status,'held');assert.equal(f.calls.length,0);
});
test('unknown configured-but-not-advertised good cannot trade without market policy',()=>{
 const f=fixture();f.reprice('unregistered',1,1);assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
});
test('trade requires both classified adult loaded residents',()=>{
 for(const change of [{isDead:()=>true},{isChild:()=>true},{is3DLoaded:()=>false},{hasKeyword:()=>false}]){
  const f=fixture();Object.assign(f.flags.seller,change);assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
 }
});
test('out-of-range trade cannot arm and separation after goods cannot pay',()=>{
 const f=fixture();f.positions.seller[0]=501;assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
 const g=fixture();g.arm();g.deliver();g.apply();g.positions.seller[0]=501;assert.equal(g.deliver().ack.status,'held');assert.equal(g.calls.length,1);
});
test('nonfinite or absent native position is not proximity proof',()=>{
 const f=fixture();f.positions.seller[2]=NaN;assert.equal(f.arm().ack.status,'held');
 const g=fixture();g.flags.buyer.getPositionX=undefined;assert.equal(g.arm().ack.status,'held');
});
test('different or partially unavailable cell identities cannot arm',()=>{
 const f=fixture();f.cells.seller=43;assert.equal(f.arm().ack.status,'held');
 const g=fixture();g.flags.seller.getParentCell=undefined;assert.equal(g.arm().ack.status,'held');
});
test('without cell APIs nearby coordinates cannot prove the same physical space',()=>{
 const f=fixture();f.flags.buyer.getParentCell=undefined;f.flags.seller.getParentCell=undefined;assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
});
test('unrelated commodity drift is held even after issued goods',()=>{
 const f=fixture();f.arm();f.deliver();f.balances.buyer.bread++;assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,1);
});
test('full account missing or invalid counters never become zero',()=>{
 for(const value of [undefined,null,-1,NaN,2147483648]){const f=fixture();f.balances.seller.grain=value;assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);}
});
test('tampered unrelated after balance rejects conserved trade',()=>{
 const f=fixture();f.contract.after.buyer.bread++;assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
});
test('finite policy menu choices do not forbid bounded manual quantity or price',()=>{
 const f=fixture();f.reprice('ore',3,13);assert.equal(f.arm().ack.status,'applied');assert.equal(f.finish().ack.status,'applied');
});
test('constructor calls neither native catalog nor session before update',()=>{
 const f=fixture();let calls=0;f.catalog.status=()=>{calls++;throw Error('not on update');};
 createInventoryTransfers(()=>f.sp,()=>100,{...f.options,session:()=>{throw Error('early session');}});assert.equal(calls,0);
});
test('narrow matching permits never authorize another transfer kind or identity',()=>{
 const f=fixture();f.arm();assert.equal(f.controller.permitsCommand(f.command('deliver')),true);
 assert.equal(f.controller.permitsCommand({...f.command('deliver'),kind:'inventory_consume'}),false);
 assert.equal(f.controller.permitsCommand({...f.command('deliver'),seller:300}),false);
});
