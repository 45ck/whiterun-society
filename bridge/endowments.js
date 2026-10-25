// Native effect witnesses are LIVE ONLY. Durable reservations/receipts belong
// to the service checkpoint journal. Reset never reconstructs issued effects.
function createEndowmentController(platform,now=Date.now,options={}){
 const resourceApi=typeof validateResourceManifest==='function'?{validateResourceManifest,selectResourceGrant,resourceManifestHash}:require('./resource-manifest.js');
 const canonical=typeof canonicalJson==='function'?canonicalJson:require('./economy-catalog.js').canonicalJson;
 const digest=typeof sha256==='function'?sha256:require('./economy-catalog.js').sha256;
 const catalog=options.catalog,records=new Map(),recipients=new Map();
 const clone=value=>JSON.parse(JSON.stringify(value));
 const identityKeys=['grant_id','source','manifest_hash','catalog_hash','actor','actor_base_id','origin_session','delivery_epoch','selector_id','grant_hash','grant','before','after'];
 let generation=0,sequence=0,epoch,manifest,manifestHash,error,rawManifest;
 const rotate=()=>{epoch='resource-'+Date.now().toString(36)+'-'+(++generation)+'-'+Math.random().toString(36).slice(2);};
 rotate();
 try{rawManifest=clone(options.manifest);}catch(e){error='Resource manifest unavailable';}
 // Native catalog resolution is legal on update, not module construction.
 function ensureManifest(status){
  if(manifest||error)return;
  try{
   manifest=resourceApi.validateResourceManifest(rawManifest,status.catalog_hash,catalog.itemIds());
   manifestHash=resourceApi.resourceManifestHash(manifest);
  }catch(e){error=String(e.message||e);}
 }
 function identity(c){return Object.fromEntries(identityKeys.map(k=>[k,c[k]]));}
 function signature(c){try{return canonical(identity(c));}catch(_){return null;}}
 function stockValid(value,keys){return value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join('|')===keys.join('|')&&keys.every(k=>Number.isSafeInteger(value[k])&&value[k]>=0&&value[k]<=2147483647);}
 function equal(a,b,keys){return keys.every(k=>a[k]===b[k]);}
 function bound(c){
  return c&&c.protocol===2&&c.kind==='inventory_endowment'&&['arm','deliver'].includes(c.phase)
   &&typeof c.grant_id==='string'&&/^[A-Za-z0-9_-]{1,128}$/.test(c.grant_id)&&c.id===c.grant_id+'-'+c.phase
   &&typeof options.session==='function'&&typeof c.origin_session==='string'&&c.origin_session.length>0
   &&c.origin_session===options.session()&&c.session===c.origin_session&&c.delivery_epoch===epoch;
 }
 function grantValid(c,keys){
  if(!manifest||c.source!==manifest.id||c.manifest_hash!==manifestHash||c.catalog_hash!==manifest.catalog_hash
    ||!Number.isInteger(c.actor)||c.actor<1||c.actor>0xffffffff||!Number.isInteger(c.actor_base_id)||c.actor_base_id<1||c.actor_base_id>0xffffffff)return false;
  const selected=resourceApi.selectResourceGrant(manifest,c.actor,c.actor_base_id);
  return c.selector_id===selected.selector_id&&c.grant_hash===selected.grant_hash
   &&canonical(c.grant)===canonical(selected.grant)&&stockValid(c.before,keys)&&stockValid(c.after,keys)
   &&keys.every(k=>c.before[k]<=manifest.max_recipient_stock&&c.after[k]===c.before[k]+c.grant[k]);
 }
 function current(c,keys){
  const status=catalog.status(),resolved=catalog.resolve();
  if(status.available!==true||status.type_verified!==true||status.catalog_hash!==manifest.catalog_hash
    ||resolved.available!==true||resolved.type_verified!==true||keys.some(k=>!resolved.forms?.[k]))throw new Error('Resource catalog or resolved native types unavailable');
  const sp=platform(),actor=sp.Actor?.from(sp.Game.getFormEx(c.actor));
  if(!actor||actor.getFormID?.()!==c.actor||actor.isDead()||actor.isChild()
    ||(actor.getActorBase?.()||actor.getBaseObject?.())?.getFormID?.()!==c.actor_base_id)throw new Error('Resource recipient native reference or base identity unavailable');
  const keyword=sp.Keyword?.from(sp.Game.getFormEx(0x13794));
  if(!keyword||typeof actor.hasKeyword!=='function'||actor.hasKeyword(keyword)!==true)throw new Error('Resource recipient adult classification unavailable');
  const actual=Object.fromEntries(keys.map(k=>[k,actor.getItemCount(resolved.forms[k])]));
  if(!stockValid(actual,keys))throw new Error('Resource inventory observation unavailable');
  return {actor,actual,forms:resolved.forms};
 }
 function held(c,message,record,same,preserve=false){
  const known=record&&same,issued=known?record.legs.some(leg=>leg.issued):(!record&&c.phase==='arm'&&bound(c)?false:null);
  const ack={id:c.id,...identity(c),protocol:2,status:'held',phase:'held',accepted:false,error:message,
   effects_issued:issued,no_effects_issued:issued===false,legs:known?clone(record.legs):[],
   ...(known?{permit:record.permit}:{}),scope:'Native effect witnesses are live only; retained service reservation requires reconciliation'};
  if(known&&!preserve&&record.phase!=='complete'){record.phase='held';record.failure=clone(ack);}
  return {done:true,ack};
 }
 return {
  reset(){records.clear();recipients.clear();rotate();},
  status(){
   let available=false;
   try{const status=catalog?.status();ensureManifest(status);available=!!manifest&&status?.available===true&&status.type_verified===true&&status.catalog_hash===manifest.catalog_hash;}catch(_){}
   return {available,protocol:2,epoch,manifest_hash:manifestHash||null,catalog_hash:manifest?.catalog_hash||null,
    ...(error?{error}:{}),witness_durability:'live_controller_only',reserved_actors:this.reservedActors()};
  },
  reservedActors(){return [...new Set([...records.values()].filter(r=>r.phase!=='complete').map(r=>r.contract.actor))];},
  permitsCommand(c){const r=records.get(c?.grant_id);return !!r&&bound(c)&&r.signature===signature(c)&&(c.phase==='arm'||c.permit===r.permit);},
  step(c){
   c=c||{};const record=records.get(c.grant_id),sig=signature(c),same=!!record&&sig!==null&&record.signature===sig;
   const fail=message=>held(c,message,record,same);
   if(!bound(c))return fail('Legacy, changed-session or expired-epoch resource command; do not replay');
   if(sig===null)return fail('Resource contract is not canonical data');
   if(record&&!same)return fail('Resource grant identity or payload changed');
   let keys,view;
   try{
    ensureManifest(catalog.status());
    keys=catalog.itemIds().slice().sort();
    if(!keys.length||!grantValid(c,keys))return fail('Grant differs from the installed finite resource manifest');
    view=current(c,keys);
   }catch(e){return fail(String(e.message||e));}
   if(c.phase==='arm'&&record?.legs.some(leg=>leg.issued))
    return held(c,'Resource arm phase cannot recur after an effect was issued',record,same,true);
   if(record?.phase==='held')return {done:true,ack:{...clone(record.failure),id:c.id}};
   if(c.phase==='deliver'&&(!record||typeof c.permit!=='string'||c.permit!==record.permit))return fail('Resource delivery requires its retained exact arm permit');
   if(record?.receipt)return {done:true,ack:clone(c.phase==='arm'?record.armReceipt:record.receipt)};
   const clock=now();
   if(!Number.isFinite(clock)||clock<0||record&&clock<record.armedAt)return fail('Invalid resource delivery clock');
   if(c.phase==='arm'){
    if(record){
     if(clock-record.armedAt>120000)return fail('Resource arm permit expired before delivery');
     return {done:true,ack:clone(record.armReceipt)};
    }
    const recipient=c.actor;
    if(recipients.has(recipient))return fail('Recipient already owns a grant in this manifest epoch');
    if(records.size>=128)return fail('Resource journal capacity reached; no automatic eviction');
    // Secondary bound for this live epoch. The durable source pool is service-owned.
    if(keys.some(k=>[...records.values()].reduce((sum,r)=>sum+r.contract.grant[k],0)+c.grant[k]>manifest.capacity[k]))
     return fail('Live epoch resource reservations exceed manifest capacity');
    if(!equal(view.actual,c.before,keys))return fail('Fresh resource arm inventory differs; no effects issued');
    const permit=digest(canonical({epoch,sequence:++sequence,contract:identity(c)}));
    const legs=keys.filter(item=>c.grant[item]>0).map(item=>({item,amount:c.grant[item],issued:false,observed:false}));
    const armReceipt={id:c.id,...identity(c),protocol:2,status:'applied',accepted:true,phase:'armed',permit,
     effects_issued:false,no_effects_issued:true,legs:[],inventory:clone(view.actual)};
    records.set(c.grant_id,{contract:clone(identity(c)),signature:sig,permit,phase:'armed',armedAt:clock,legs,
     expected:clone(c.before),index:0,armReceipt:clone(armReceipt)});
    recipients.set(recipient,c.grant_id);
    return {done:true,ack:armReceipt};
   }
   if(record.phase==='armed'&&clock-record.armedAt>120000)return fail('Resource arm permit expired before delivery');
   if(record.phase==='delivering'&&(clock<record.issuedAt||clock-record.issuedAt>5000))return fail('Resource effect observation timed out; no blind retry');
   let leg=record.legs[record.index];
   if(leg.issued&&!leg.observed){
    const expectedAfter={...record.expected,[leg.item]:record.expected[leg.item]+leg.amount};
    if(equal(view.actual,expectedAfter,keys)){
     leg.observed=true;record.expected=expectedAfter;record.index++;
     if(record.index===record.legs.length){
      if(!record.legs.every(entry=>entry.issued&&entry.observed)||!equal(view.actual,c.after,keys))return fail('Resource terminal effect witness mismatch');
      record.phase='complete';record.receipt={id:c.id,...identity(c),protocol:2,status:'applied',accepted:true,phase:'complete',
       permit:record.permit,inventory:clone(view.actual),effects_issued:true,no_effects_issued:false,legs:clone(record.legs),
       loaded:typeof view.actor.is3DLoaded==='function'?view.actor.is3DLoaded():null,
       scope:'Verified native inventory import; no trade, earned income, productive labour, movement or animation claimed'};
      return {done:true,ack:clone(record.receipt)};
     }
     leg=record.legs[record.index];
    }else if(equal(view.actual,record.expected,keys))return {done:false};
    else return fail('Resource inventory drifted during issued delivery; reconcile without replay');
   }
   if(!equal(view.actual,record.expected,keys))return fail('Resource inventory differs before next authorized leg');
   // Mark issued BEFORE entering the native call, including calls that throw.
   leg.issued=true;record.phase='delivering';record.issuedAt=clock;
   try{view.actor.addItem(view.forms[leg.item],leg.amount,true);}catch(_){return fail('Resource native call failed after issue; reconcile without retry');}
   return {done:false};
  }
 };
}
if(typeof module!=='undefined')module.exports={createEndowmentController};
