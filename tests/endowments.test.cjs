const test=require('node:test'),assert=require('node:assert/strict');
const {createEndowmentController}=require('../bridge/endowments.js');
const {resourceManifestHash,selectResourceGrant}=require('../bridge/resource-manifest.js');
const clone=x=>JSON.parse(JSON.stringify(x));

function fixture({extra=false,single=false,override=false,tightCapacity=false}={}){
 let clock=100,session='test-session',loaded=true,base=88;
 const stock={gold:7,bread:0,grain:0,...(extra?{ore:4}:{})},calls=[],queue=[];
 const keys=Object.keys(stock).sort(),forms=Object.fromEntries(keys.map(k=>[k,{item:k}]));
 const manifest=clone(require('../config/resource-manifest.json'));manifest.catalog_hash='a'.repeat(64);
 if(extra){manifest.capacity.ore=20;manifest.default_grant.ore=0;}
 if(single){manifest.default_grant.bread=0;manifest.default_grant.grain=0;}
 if(tightCapacity)manifest.capacity={...manifest.default_grant};
 if(override)manifest.overrides=[{id:'fixture-selector',selector:{actor:99,actor_base_id:88},
  grant:{...manifest.default_grant,gold:5},provenance:'Explicit offline allocation override'}];
 const actor={getFormID:()=>99,getActorBase:()=>({getFormID:()=>base}),is3DLoaded:()=>loaded,
  isDead:()=>false,isChild:()=>false,hasKeyword:()=>true,getItemCount:f=>stock[f.item],
  addItem:(form,amount)=>{calls.push({item:form.item,amount});queue.push({item:form.item,amount});}};
 const sp={storage:{},Actor:{from:x=>x},Keyword:{from:x=>x},Game:{getFormEx:id=>id===99?actor:id===0x13794?{}:null}};
 const catalog={itemIds:()=>keys,status:()=>({available:true,type_verified:true,catalog_hash:manifest.catalog_hash}),
  resolve:()=>({available:true,type_verified:true,forms})};
 const options={catalog,manifest,session:()=>session};
 let controller=createEndowmentController(()=>sp,()=>clock,options);
 const selection=selectResourceGrant(manifest,99,88);
 const contract={grant_id:'fixture-grant',source:manifest.id,manifest_hash:resourceManifestHash(manifest),
  catalog_hash:manifest.catalog_hash,actor:99,actor_base_id:88,origin_session:session,
  delivery_epoch:controller.status().epoch,...selection,before:clone(stock),
  after:Object.fromEntries(keys.map(k=>[k,stock[k]+selection.grant[k]]))};
 let permit;
 const command=(phase='arm',changes={})=>({kind:'inventory_endowment',protocol:2,phase,id:contract.grant_id+'-'+phase,
  session,...clone(contract),...(phase==='deliver'?{permit}:{}),...changes});
 return {stock,calls,queue,actor,sp,catalog,manifest,options,contract,command,
  get controller(){return controller;},setBase:value=>base=value,setTime:value=>clock=value,setSession:value=>session=value,setLoaded:value=>loaded=value,
  replace(){controller=createEndowmentController(()=>sp,()=>clock,options);return controller;},
  arm(changes={}){const result=controller.step(command('arm',changes));if(result.ack?.permit)permit=result.ack.permit;return result;},
  deliver(changes={}){return controller.step(command('deliver',changes));},
  apply(){for(const call of queue.splice(0))stock[call.item]+=call.amount;},
  finish(){let result;for(let i=0;i<8;i++){result=this.deliver();if(result.done)return result;this.apply();}throw Error('Fixture never finished');}};
}

test('advertises exact manifest catalog epoch and live-only durability',()=>{
 const f=fixture(),status=f.controller.status();assert.equal(status.available,true);assert.equal(status.protocol,2);
 assert.equal(status.manifest_hash,f.contract.manifest_hash);assert.equal(status.catalog_hash,f.contract.catalog_hash);
 assert.equal(status.witness_durability,'live_controller_only');assert.deepEqual(status.reserved_actors,[]);
});
test('arm issues no resources and reserves exact recipient',()=>{
 const f=fixture(),ack=f.arm().ack;assert.equal(ack.phase,'armed');assert.equal(ack.accepted,true);
 assert.equal(ack.no_effects_issued,true);assert.equal(ack.effects_issued,false);assert.deepEqual(ack.legs,[]);
 assert.equal(ack.permit.length,64);assert.equal(f.calls.length,0);assert.deepEqual(f.controller.reservedActors(),[99]);
});
test('duplicate arm preserves exact permit without refreshing the grant',()=>{
 const f=fixture(),first=f.arm();f.setTime(200);assert.deepEqual(f.arm(),first);assert.equal(f.calls.length,0);
});
test('each positive leg is issued once and observed before advancing',()=>{
 const f=fixture();f.arm();for(let i=0;i<5;i++)assert.equal(f.deliver().done,false);
 assert.deepEqual(f.calls,[{item:'bread',amount:2}]);f.apply();f.deliver();assert.equal(f.calls.length,2);
 f.apply();f.deliver();assert.equal(f.calls.length,3);f.apply();const ack=f.deliver().ack;
 assert.equal(ack.status,'applied');assert.equal(ack.phase,'complete');assert.deepEqual(ack.inventory,f.contract.after);
 assert.deepEqual(ack.legs,[{item:'bread',amount:2,issued:true,observed:true},{item:'gold',amount:20,issued:true,observed:true},{item:'grain',amount:2,issued:true,observed:true}]);
 assert.deepEqual(f.controller.reservedActors(),[]);
});
test('all immutable contract fields are echoed on final receipt',()=>{
 const f=fixture();f.arm();const ack=f.finish().ack;for(const [key,value] of Object.entries(f.contract))assert.deepEqual(ack[key],value,key);
});
test('retained final receipt repeats without any further write',()=>{
 const f=fixture();f.arm();const ack=f.finish().ack,count=f.calls.length;
 f.stock.bread--;assert.deepEqual(f.deliver().ack,ack);assert.equal(f.calls.length,count);
});
test('returned receipt mutation cannot rewrite retained receipt',()=>{
 const f=fixture();f.arm();const ack=f.finish().ack;ack.legs[0].observed=false;ack.inventory.gold=999;
 assert.equal(f.deliver().ack.legs[0].observed,true);assert.equal(f.deliver().ack.inventory.gold,27);
});
test('unrelated final balances cannot arm or prove a grant',()=>{
 const f=fixture();Object.assign(f.stock,f.contract.after);const ack=f.arm().ack;
 assert.equal(ack.status,'held');assert.equal(ack.no_effects_issued,true);assert.equal(f.calls.length,0);
});
test('unrelated final balances after arm cannot infer issued effects',()=>{
 const f=fixture();f.arm();Object.assign(f.stock,f.contract.after);const ack=f.deliver().ack;
 assert.equal(ack.status,'held');assert.equal(ack.effects_issued,false);assert.equal(f.calls.length,0);
});
test('delivery without retained arm is unknown rather than no-effect authority',()=>{
 const f=fixture();const ack=f.deliver({permit:'forged'}).ack;
 assert.equal(ack.status,'held');assert.equal(ack.effects_issued,null);assert.equal(ack.no_effects_issued,false);assert.equal(f.calls.length,0);
});
test('wrong permit cannot issue any resource',()=>{
 const f=fixture();f.arm();assert.equal(f.deliver({permit:'wrong'}).ack.status,'held');assert.equal(f.calls.length,0);
 assert.deepEqual(f.controller.reservedActors(),[99]);
});
test('wrong phase-specific command ID is rejected',()=>{
 const f=fixture();assert.equal(f.arm({id:'wrong'}).ack.status,'held');assert.equal(f.calls.length,0);
});
test('legacy commands are held even when complete final stock is present',()=>{
 const f=fixture();Object.assign(f.stock,f.contract.after);
 assert.equal(f.controller.step({...f.command(),protocol:1}).ack.status,'held');assert.equal(f.calls.length,0);
});
test('reset rotates epoch and rejects old arm before any write',()=>{
 const f=fixture(),old=f.controller.status().epoch;f.arm();f.controller.reset();
 assert.notEqual(f.controller.status().epoch,old);assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
});
test('reset after partial effect cannot resume from matching intermediate stock',()=>{
 const f=fixture();f.arm();f.deliver();f.apply();f.controller.reset();const ack=f.deliver().ack;
 assert.equal(ack.status,'held');assert.equal(ack.effects_issued,null);assert.equal(f.calls.length,1);
});
test('cold controller cannot use platform storage to reconstruct grant authority',()=>{
 const f=fixture();f.arm();f.deliver();f.apply();f.replace();
 assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,1);
});
test('old session remains rejected even when outer command session is rebound',()=>{
 const f=fixture();f.arm();f.setSession('new');assert.equal(f.deliver({session:'new'}).ack.status,'held');assert.equal(f.calls.length,0);
});
test('completed delivery cannot be re-certified after controller reset',()=>{
 const f=fixture();f.arm();f.finish();const count=f.calls.length;f.controller.reset();assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,count);
});
test('reusing grant ID with changed contract does not poison the original permit',()=>{
 const f=fixture();f.arm();assert.equal(f.deliver({before:{gold:8,bread:0,grain:0}}).ack.status,'held');
 assert.equal(f.finish().ack.status,'applied');
});
test('another grant ID for the same recipient cannot arm twice',()=>{
 const f=fixture();f.arm();assert.equal(f.arm({grant_id:'second',id:'second-arm'}).ack.status,'held');assert.equal(f.calls.length,0);
});
test('completed recipient remains in one-grant registry',()=>{
 const f=fixture();f.arm();f.finish();assert.equal(f.arm({grant_id:'second',id:'second-arm'}).ack.status,'held');assert.equal(f.calls.length,3);
});
test('replacement native base before first effect is rejected',()=>{
 const f=fixture();f.arm();f.setBase(89);assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,0);
});
test('replacement native base cannot obtain a retained complete receipt',()=>{
 const f=fixture();f.arm();f.finish();f.setBase(89);assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,3);
});
test('wrong native reference cannot impersonate selected actor',()=>{
 const f=fixture();f.actor.getFormID=()=>100;assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
});
for(const field of ['isDead','isChild'])test(field+' actor rejects arm',()=>{
 const f=fixture();f.actor[field]=()=>true;assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
});
test('missing adult keyword proof rejects arm',()=>{
 const f=fixture();f.actor.hasKeyword=()=>false;assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
});
test('unloaded inventory grant does not claim movement or animation',()=>{
 const f=fixture();f.setLoaded(false);f.arm();const ack=f.finish().ack;assert.equal(ack.loaded,false);assert.match(ack.scope,/no trade.*movement or animation/);
});
test('native call throwing after issue is held and never automatically retried',()=>{
 const f=fixture();f.arm();f.actor.addItem=()=>{f.calls.push({attempt:true});throw Error('native failed');};
 const ack=f.deliver().ack;assert.equal(ack.status,'held');assert.equal(ack.effects_issued,true);assert.equal(ack.legs[0].issued,true);
 assert.equal(ack.legs[0].observed,false);f.deliver();assert.equal(f.calls.length,1);assert.deepEqual(f.controller.reservedActors(),[99]);
});
test('delayed native effect waits without repeating the call',()=>{
 const f=fixture();f.arm();f.deliver();f.setTime(1000);f.deliver();assert.equal(f.calls.length,1);
 f.apply();f.deliver();assert.equal(f.calls.length,2);
});
test('effect timeout retains ambiguous issued witness and actor reservation',()=>{
 const f=fixture();f.arm();f.deliver();f.setTime(5101);const ack=f.deliver().ack;
 assert.equal(ack.status,'held');assert.equal(ack.effects_issued,true);f.apply();f.deliver();assert.equal(f.calls.length,1);
 assert.deepEqual(f.controller.status().reserved_actors,[99]);
});
test('clock reversal cannot advance or repeat an issued leg',()=>{
 const f=fixture();f.arm();f.deliver();f.setTime(99);assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,1);
});
test('nonfinite clock cannot arm',()=>{
 const f=fixture();f.setTime(NaN);assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
});
test('expired arm remains a proved no-effect hold',()=>{
 const f=fixture();f.arm();f.setTime(120101);const ack=f.deliver().ack;
 assert.equal(ack.status,'held');assert.equal(ack.no_effects_issued,true);assert.equal(f.calls.length,0);
});
test('unexpected later-leg stock cannot be inferred as delivery',()=>{
 const f=fixture();f.arm();f.deliver();f.stock.gold+=20;assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,1);
});
test('additional catalog balances preserved and monitored on every leg',()=>{
 const f=fixture({extra:true});f.arm();assert.equal(f.finish().ack.inventory.ore,4);
 const g=fixture({extra:true});g.arm();g.deliver();g.stock.ore--;assert.equal(g.deliver().ack.status,'held');assert.equal(g.calls.length,1);
});
for(const value of [null,NaN,-1,2147483648])test('invalid observed count '+String(value)+' never counts as zero',()=>{
 const f=fixture();f.stock.bread=value;assert.equal(f.arm().ack.status,'held');assert.equal(f.calls.length,0);
});
test('missing catalog form rejects arm',()=>{
 const f=fixture();f.catalog.resolve=()=>({available:true,type_verified:true,forms:{}});assert.equal(f.arm().ack.status,'held');
});
test('unverified native form types reject arm',()=>{
 const f=fixture();f.catalog.resolve=()=>({available:true,type_verified:false,forms:{}});assert.equal(f.arm().ack.status,'held');
});
test('catalog change after arm holds without inventory effects',()=>{
 const f=fixture();f.arm();f.catalog.status=()=>({available:true,type_verified:true,catalog_hash:'b'.repeat(64)});
 assert.equal(f.deliver().ack.status,'held');assert.equal(f.calls.length,0);
});
test('altered manifest grant/hash/selector cannot supply arbitrary resources',()=>{
 for(const change of [{manifest_hash:'b'.repeat(64)},{grant_hash:'b'.repeat(64)},{selector_id:'invented'},
   {grant:{bread:2,gold:100,grain:2},after:{bread:2,gold:107,grain:2}}]){
  const f=fixture();assert.equal(f.arm(change).ack.status,'held');assert.equal(f.calls.length,0);
 }
});
test('reviewed override uses exact actor and base selector',()=>{
 const f=fixture({override:true});assert.equal(f.contract.selector_id,'fixture-selector');f.arm();assert.equal(f.finish().ack.inventory.gold,12);
});
test('zero quantity legs are not issued and single-leg grants still require observation',()=>{
 const f=fixture({single:true});f.arm();assert.equal(f.deliver().done,false);assert.equal(f.calls.length,1);
 f.apply();const ack=f.deliver().ack;assert.deepEqual(ack.legs,[{item:'gold',amount:20,issued:true,observed:true}]);
});
test('mutating original manifest object does not rewrite installed allocation',()=>{
 const f=fixture();f.manifest.default_grant.gold=999;f.arm();assert.equal(f.finish().ack.inventory.gold,27);
});
test('payload mutation after arm cannot alter stored allocation',()=>{
 const f=fixture();const arm=f.command();f.controller.step(arm);arm.grant.gold=999;
 assert.equal(f.controller.step(arm).ack.status,'held');assert.equal(f.calls.length,0);
});
test('narrow permit authorization cannot bypass another inventory command',()=>{
 const f=fixture();f.arm();assert.equal(f.controller.permitsCommand(f.command('deliver')),true);
 assert.equal(f.controller.permitsCommand({...f.command('deliver'),kind:'inventory_trade'}),false);
 assert.equal(f.controller.permitsCommand({...f.command('deliver'),actor:100}),false);
});
test('missing manifest stays unavailable and cannot arm',()=>{
 const f=fixture(),controller=createEndowmentController(()=>f.sp,()=>100,{catalog:f.catalog,session:()=>f.command().session});
 assert.equal(controller.status().available,false);assert.equal(controller.step(f.command()).ack.status,'held');assert.equal(f.calls.length,0);
});

function armAnother(f,actor,base=88){
 const previous=f.sp.Game.getFormEx;
 f.sp.Game.getFormEx=id=>id===actor?{...f.actor,getFormID:()=>actor,getActorBase:()=>({getFormID:()=>base})}:previous(id);
 const id='another-'+actor,selected=selectResourceGrant(f.manifest,actor,base);
 return f.controller.step({...f.command(),grant_id:id,id:id+'-arm',actor,actor_base_id:base,...selected,
  before:clone(f.stock),after:Object.fromEntries(Object.keys(f.stock).map(k=>[k,f.stock[k]+selected.grant[k]]))});
}
test('native per-epoch reservations cannot exceed configured aggregate capacity',()=>{
 const f=fixture();f.arm();for(let actor=100;actor<149;actor++)assert.equal(armAnother(f,actor).ack.status,'applied');
 assert.match(armAnother(f,149).ack.error,/capacity/);assert.equal(f.controller.reservedActors().length,50);
 assert.equal(f.calls.length,0);
});
test('completed records still consume native per-epoch capacity',()=>{
 const f=fixture({tightCapacity:true});f.arm();f.finish();assert.deepEqual(f.controller.reservedActors(),[]);
 assert.match(armAnother(f,100).ack.error,/capacity/);assert.equal(f.calls.length,3);
});
test('ambiguous issued holds retain finite capacity reservation',()=>{
 const f=fixture({tightCapacity:true});f.arm();f.deliver();f.setTime(5101);f.deliver();
 assert.match(armAnother(f,100).ack.error,/capacity/);assert.equal(f.calls.length,1);
});
test('a new base cannot obtain a second grant for the same native reference',()=>{
 const f=fixture();f.arm();f.setBase(89);
 const selected=selectResourceGrant(f.manifest,99,89);
 const ack=f.arm({grant_id:'replacement',id:'replacement-arm',actor_base_id:89,...selected}).ack;
 assert.match(ack.error,/already owns/);assert.equal(f.calls.length,0);assert.deepEqual(f.controller.reservedActors(),[99]);
});
test('constructor makes no native catalog or session calls before update',()=>{
 const f=fixture();let reads=0;const original=f.catalog.status;
 f.catalog.status=()=>{reads++;return original();};
 const controller=createEndowmentController(()=>f.sp,()=>100,{catalog:f.catalog,manifest:f.manifest,
  session:()=>{throw Error('Session must not be read at construction');}});
 assert.equal(reads,0);assert.equal(controller.status().available,true);assert.equal(reads,1);
});
test('late arm during delivery reports issued effects and preserves live continuation witness',()=>{
 const f=fixture();f.arm();f.deliver();const ack=f.arm().ack;
 assert.equal(ack.status,'held');assert.equal(ack.effects_issued,true);assert.equal(ack.no_effects_issued,false);
 assert.equal(f.calls.length,1);f.apply();assert.equal(f.finish().ack.status,'applied');
});
test('late arm cannot misstate no effects or destroy a retained completion receipt',()=>{
 const f=fixture();f.arm();const complete=f.finish().ack,count=f.calls.length,late=f.arm().ack;
 assert.equal(late.status,'held');assert.equal(late.effects_issued,true);assert.equal(late.no_effects_issued,false);
 assert.deepEqual(f.deliver().ack,complete);assert.equal(f.calls.length,count);
});
test('rejected replacement base does not erase historical completion evidence',()=>{
 const f=fixture();f.arm();const complete=f.finish().ack;f.setBase(89);
 assert.equal(f.deliver().ack.status,'held');f.setBase(88);assert.deepEqual(f.deliver().ack,complete);assert.equal(f.calls.length,3);
});
