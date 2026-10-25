// Embedded by the deployer; receives a getter because native bindings may refresh.
function createInventoryTransfers(platform, now=Date.now, options={}) {
  const issued=new Map(); // Legacy food use remains a separate protocol.
  const trade=createCatalogTradeController(platform,now,options);
  const catalog=options.catalog;
  const itemIds=()=>typeof catalog?.itemIds==='function'?catalog.itemIds().slice().sort():[];
  const validInventory=(value,keys)=>value&&typeof value==='object'&&Object.keys(value).sort().join('|')===keys.join('|')&&keys.every(k=>Number.isSafeInteger(value[k])&&value[k]>=0&&value[k]<=2147483647);
  function resolveForms(command,keys){
    if(!catalog||typeof catalog.status!=='function'||typeof catalog.resolve!=='function')return null;
    const status=catalog.status();
    if(status.available!==true||typeof command.catalog_hash!=='string'||command.catalog_hash!==status.catalog_hash)return null;
    const resolved=catalog.resolve();
    if(resolved.available!==true||keys.some(key=>!resolved.forms?.[key]))return null;
    return Object.fromEntries(keys.map(key=>[key,resolved.forms[key]]));
  }
  return {
    reset(){issued.clear();trade.reset();},
    consume(command) {
      const sp=platform(),fail=error=>({done:true,ack:{id:command.id,status:'held',error}});
      const before=command.before,after=command.after,keys=itemIds();
      if(!['gold','bread'].every(k=>keys.includes(k))||!validInventory(before,keys)||!validInventory(after,keys)||
         before.bread<1||keys.some(k=>after[k]!==before[k]-(k==='bread'?1:0)))return fail('Invalid complete food-use contract');
      const actor=sp.Actor.from(sp.Game.getFormEx(command.actor));
      if(!actor||!actor.is3DLoaded()||actor.isDead()||actor.isChild()||typeof actor.equipItem!=='function')return fail('Food-use actor unavailable');
      const forms=resolveForms(command,keys);
      if(!forms)return fail('Food-use catalog binding or resolved forms unavailable');
      const {bread,gold}=forms;
      const actual=Object.fromEntries(keys.map(k=>[k,actor.getItemCount(forms[k])]));
      if(!validInventory(actual,keys))return fail('Food-use inventory observation unavailable');
      const matches=expected=>keys.every(k=>actual[k]===expected[k]);
      if(matches(after)){
        issued.delete(command.id);
        return {done:true,ack:{id:command.id,status:'applied',inventory:actual,catalog_hash:command.catalog_hash,mechanism:'native_equip_food'}};
      }
      if(!matches(before))return fail('Unexpected inventory during consumption');
      const sent=issued.get(command.id);
      if(sent&&now()-sent.at>5000)return fail('Native food use timed out; no repeated attempt');
      if(!sent){issued.set(command.id,{leg:'consume',at:now()});actor.equipItem(bread,false,true);}
      return {done:false};
    },
    step(command) {return trade.step(command);},
    status(){return trade.status();},
    reservedActors(){return trade.reservedActors();},
    permitsCommand(command){return trade.permitsCommand(command);}
  };
}
// Two witnessed native transfers; checkpoints retain permits and accounting.
// These native witnesses are live-only and cannot be restored from balances.
function createCatalogTradeController(platform,now,options){
 const api=typeof validateMarketPolicy==='function'?{validateMarketPolicy,marketPolicyHash,marketGood}:require('./market-policy.js');
 const canonical=typeof canonicalJson==='function'?canonicalJson:require('./economy-catalog.js').canonicalJson;
 const digest=typeof sha256==='function'?sha256:require('./economy-catalog.js').sha256;
 const catalog=options.catalog,records=new Map(),clone=x=>JSON.parse(JSON.stringify(x));
 const fields=['trade_id','catalog_hash','market_policy_hash','buyer','buyer_base_id','seller','seller_base_id','commodity','currency','quantity','unit_price','cost','origin_session','delivery_epoch','before','after','consent_id','consent_hash'];
 const identity=c=>Object.fromEntries(fields.map(k=>[k,c[k]]));
 const signature=c=>{try{return canonical(identity(c));}catch(_){return null;}};
 let epoch,generation=0,sequence=0,rawPolicy,policy,policyHash,error;
 const rotate=()=>{epoch='trade-'+Date.now().toString(36)+'-'+(++generation)+'-'+Math.random().toString(36).slice(2);};rotate();
 try{rawPolicy=clone(options.marketPolicy);}catch(_){error='Market policy unavailable';}
 function initialize(status){if(policy||error)return;try{
  policy=api.validateMarketPolicy(rawPolicy,status.catalog_hash,catalog.commodities());policyHash=api.marketPolicyHash(policy);
 }catch(e){error=String(e.message||e);}}
 const validId=id=>Number.isInteger(id)&&id>0&&id<=0xffffffff;
 const validAccount=(x,keys)=>x&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).sort().join('|')===keys.join('|')&&keys.every(k=>Number.isSafeInteger(x[k])&&x[k]>=0&&x[k]<=2147483647);
 const validPair=(x,keys)=>x&&Object.keys(x).sort().join('|')==='buyer|seller'&&['buyer','seller'].every(role=>validAccount(x[role],keys));
 const equal=(a,b,keys)=>['buyer','seller'].every(role=>keys.every(k=>a[role][k]===b[role][k]));
 function bound(c){return c.kind==='inventory_trade'&&c.protocol===2&&['arm','deliver'].includes(c.phase)
  &&typeof c.trade_id==='string'&&/^[A-Za-z0-9_-]{1,128}$/.test(c.trade_id)&&c.id===c.trade_id+'-'+c.phase
  &&typeof c.origin_session==='string'&&c.origin_session.length>0&&typeof options.session==='function'
  &&c.origin_session===options.session()&&c.session===c.origin_session&&c.delivery_epoch===epoch;}
 function validate(c,keys){
  if(!policy||c.catalog_hash!==policy.catalog_hash||c.market_policy_hash!==policyHash||!['buyer','seller'].every(r=>validId(c[r])&&validId(c[r+'_base_id']))||c.buyer===c.seller)return false;
  const goods=api.marketGood(policy,c.commodity),metadata=catalog.commodities(),currency=metadata.filter(row=>row.currency===true);
  if(!goods||currency.length!==1||c.currency!==currency[0].id||!metadata.some(row=>row.id===c.commodity&&row.currency===false))return false;
  if(!Number.isInteger(c.quantity)||c.quantity<1||c.quantity>goods.max_quantity||!Number.isInteger(c.unit_price)||c.unit_price<goods.price_min||c.unit_price>goods.price_max||c.cost!==c.quantity*c.unit_price||!Number.isSafeInteger(c.cost))return false;
  if(typeof c.consent_id!=='string'||!/^[A-Za-z0-9_-]{1,128}$/.test(c.consent_id)||typeof c.consent_hash!=='string'||!/^[a-f0-9]{64}$/.test(c.consent_hash))return false;
  if(!validPair(c.before,keys)||!validPair(c.after,keys))return false;
  const expected=clone(c.before);expected.seller[c.commodity]-=c.quantity;expected.buyer[c.commodity]+=c.quantity;
  expected.buyer[c.currency]-=c.cost;expected.seller[c.currency]+=c.cost;
  return validPair(expected,keys)&&equal(expected,c.after,keys);
 }
 function sense(c,keys){
  const status=catalog.status(),resolved=catalog.resolve();
  if(status.available!==true||status.type_verified!==true||status.catalog_hash!==c.catalog_hash||resolved.available!==true||resolved.type_verified!==true||keys.some(k=>!resolved.forms?.[k]))throw Error('Trade catalog native forms or types unavailable');
  const sp=platform(),actors={},positions=[];const keyword=sp.Keyword?.from(sp.Game.getFormEx(0x13794));
  if(!keyword)throw Error('Trade adult classification unavailable');
  for(const role of ['buyer','seller']){
   const a=sp.Actor?.from(sp.Game.getFormEx(c[role]));
   if(!a||a.getFormID?.()!==c[role]||!a.is3DLoaded()||a.isDead()||a.isChild()||a.hasKeyword?.(keyword)!==true
    ||(a.getActorBase?.()||a.getBaseObject?.())?.getFormID?.()!==c[role+'_base_id'])throw Error('Trade participant identity or loaded adult state unavailable');
   const position=['X','Y','Z'].map(axis=>a['getPosition'+axis]?.());
   if(position.some(n=>typeof n!=='number'||!Number.isFinite(n)))throw Error('Trade participant position unqualified');
   positions.push(position);actors[role]=a;
  }
  if(Math.hypot(...positions[0].map((n,i)=>n-positions[1][i]))>500)throw Error('Trade participants are outside interaction range');
  const first=actors.buyer.getParentCell?.()?.getFormID?.(),second=actors.seller.getParentCell?.()?.getFormID?.();
  if(!validId(first)||first!==second)throw Error('Trade participants do not share a verified cell');
  const actual=Object.fromEntries(['buyer','seller'].map(role=>[role,Object.fromEntries(keys.map(k=>[k,actors[role].getItemCount(resolved.forms[k])]))]));
  if(!validPair(actual,keys))throw Error('Trade inventory observation unavailable');
  return {actors,actual,forms:resolved.forms};
 }
 function fail(c,message,record,same,preserve=false){
  const known=record&&same,issued=known?record.legs.some(l=>l.issued):(!record&&c.phase==='arm'&&bound(c)?false:null);
  const ack={id:c.id,...identity(c),protocol:2,status:'held',accepted:false,phase:'held',error:message,
   effects_issued:issued,no_effects_issued:issued===false,legs:known?clone(record.legs):[],...(known?{permit:record.permit}:{})};
  if(known&&!preserve&&record.phase!=='complete'){record.phase='held';record.failure=clone(ack);}
  return {done:true,ack};
 }
 return {
  reset(){records.clear();rotate();},
  reservedActors(){return [...new Set([...records.values()].filter(r=>r.phase!=='complete').flatMap(r=>[r.contract.buyer,r.contract.seller]))];},
  permitsCommand(c){const r=records.get(c?.trade_id);return !!r&&bound(c)&&r.signature===signature(c)&&(c.phase==='arm'||c.permit===r.permit);},
  status(){let available=false;try{const status=catalog.status();initialize(status);available=!!policy&&status.available===true&&status.type_verified===true&&status.catalog_hash===policy.catalog_hash;}catch(_){}
   return {available,protocol:2,epoch,catalog_hash:policy?.catalog_hash||null,market_policy_hash:policyHash||null,reserved_actors:this.reservedActors(),witness_durability:'live_controller_only',...(error?{error}:{})};},
  step(c){
   c=c||{};const record=records.get(c.trade_id),sig=signature(c),same=!!record&&sig!==null&&record.signature===sig;
   const reject=message=>fail(c,message,record,same);
   if(!bound(c)||sig===null)return reject('Legacy, changed-session, expired-epoch or malformed trade cannot execute');
   if(record&&!same)return reject('Trade identity or payload changed');
   let keys,view;
   try{initialize(catalog.status());keys=catalog.itemIds().slice().sort();if(!keys.length||!validate(c,keys))return reject('Trade differs from reviewed market policy or conserved accounts');view=sense(c,keys);}
   catch(e){return reject(String(e.message||e));}
   if(c.phase==='arm'&&record?.legs.some(l=>l.issued))return fail(c,'Trade arm cannot recur after an issued transfer',record,same,true);
   if(record?.phase==='held')return {done:true,ack:{...clone(record.failure),id:c.id}};
   if(c.phase==='deliver'&&(!record||typeof c.permit!=='string'||c.permit!==record.permit))return reject('Trade delivery requires the retained exact arm permit');
   if(record?.receipt)return {done:true,ack:clone(record.receipt)};
   const clock=now();if(!Number.isFinite(clock)||clock<0||record&&clock<record.armedAt)return reject('Invalid trade clock');
   if(c.phase==='arm'){
    if(record){if(clock-record.armedAt>120000)return reject('Trade arm permit expired');return {done:true,ack:clone(record.armReceipt)};}
    if([...records.values()].some(r=>r.phase!=='complete'&&[r.contract.buyer,r.contract.seller].some(id=>id===c.buyer||id===c.seller)))return reject('Another trade reserves a participant purse');
    if(!equal(view.actual,c.before,keys))return reject('Fresh trade arm stock differs; no effects issued');
    const permit=digest(canonical({epoch,sequence:++sequence,contract:identity(c)}));
    const armReceipt={id:c.id,...identity(c),protocol:2,status:'applied',accepted:true,phase:'armed',permit,inventory:clone(view.actual),effects_issued:false,no_effects_issued:true,legs:[]};
    const legs=[{leg:'goods',item:c.commodity,amount:c.quantity,issued:false,observed:false},{leg:'payment',item:c.currency,amount:c.cost,issued:false,observed:false}];
    records.set(c.trade_id,{contract:clone(identity(c)),signature:sig,permit,phase:'armed',armedAt:clock,index:0,expected:clone(c.before),legs,armReceipt:clone(armReceipt)});
    return {done:true,ack:armReceipt};
   }
   if(record.phase==='armed'&&clock-record.armedAt>120000)return reject('Trade arm permit expired');
   if(record.phase==='delivering'&&(clock<record.issuedAt||clock-record.issuedAt>5000))return reject('Trade transfer observation timed out; do not resend');
   let leg=record.legs[record.index],from=record.index===0?'seller':'buyer',to=record.index===0?'buyer':'seller';
   if(leg.issued&&!leg.observed){
    const matches=[];
    for(const debit of [false,true])for(const credit of [false,true]){
     const expected=clone(record.expected);if(debit)expected[from][leg.item]-=leg.amount;if(credit)expected[to][leg.item]+=leg.amount;
     if(equal(view.actual,expected,keys))matches.push({debit,credit,expected});
    }
    if(matches.length!==1)return reject('Trade inventory drifted outside the issued current leg');
    const state=matches[0];
    if(leg.debit_observed&&!state.debit||leg.credit_observed&&!state.credit)return reject('Observed transfer side regressed; reconcile without replay');
    leg.debit_observed=state.debit;leg.credit_observed=state.credit;
    if(!state.debit||!state.credit)return {done:false};
    leg.observed=true;record.expected=state.expected;record.index++;
    if(record.index===2){
     if(!equal(view.actual,c.after,keys)||!record.legs.every(l=>l.issued&&l.observed&&l.debit_observed&&l.credit_observed))return reject('Trade final witness mismatch');
     record.phase='complete';record.receipt={id:c.id,...identity(c),protocol:2,status:'applied',accepted:true,phase:'complete',permit:record.permit,
      inventory:clone(view.actual),effects_issued:true,no_effects_issued:false,legs:clone(record.legs),mechanism:'native_catalog_trade',scope:'Witnessed inventory exchange; consent provenance remains service-owned'};
     return {done:true,ack:clone(record.receipt)};
    }
    leg=record.legs[record.index];from='buyer';to='seller';
   }
   if(!equal(view.actual,record.expected,keys))return reject('Trade stock changed before the authorized leg');
   leg.issued=true;record.phase='delivering';record.issuedAt=clock;
   try{view.actors[from].removeItem(view.forms[leg.item],leg.amount,true,view.actors[to]);}
   catch(_){return reject('Native transfer failed after issue; reconcile without retry');}
   return {done:false};
  }
 };
}
if (typeof module!=='undefined') module.exports={createInventoryTransfers};
