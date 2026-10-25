// Authored search space. Authorization requires validation against the installed
// catalog; a command may not substitute its own market policy.
const marketPolicyCanonical=typeof canonicalJson==='function'?canonicalJson:require('./economy-catalog.js').canonicalJson;
const marketPolicyDigest=typeof sha256==='function'?sha256:require('./economy-catalog.js').sha256;
function validateMarketPolicy(raw,catalogHash,itemMetadata){
 const fields=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join('|')===[...keys].sort().join('|');
 const id=value=>typeof value==='string'&&/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(value);
 const integer=(value,low,high)=>Number.isSafeInteger(value)&&value>=low&&value<=high;
 const whitespace=/^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]$/u;
 const text=value=>typeof value==='string'&&[...value].length>0&&[...value].length<=500&&!whitespace.test(value)&&!/[\u0000-\u001f\ud800-\udfff]/u.test(value);
 if(!fields(raw,['schema_version','id','catalog_hash','goods','provenance'])||raw.schema_version!==1||!id(raw.id)||!text(raw.provenance)||
    typeof catalogHash!=='string'||!/^[a-f0-9]{64}$/.test(catalogHash)||raw.catalog_hash!==catalogHash||
    !Array.isArray(itemMetadata)||!itemMetadata.length||itemMetadata.length>64||
    itemMetadata.some(row=>!row||!id(row.id)||typeof row.currency!=='boolean')||new Set(itemMetadata.map(row=>row.id)).size!==itemMetadata.length)
  throw new Error('Invalid market policy envelope or catalog binding');
 if(!Array.isArray(raw.goods)||!raw.goods.length||raw.goods.length>63)throw new Error('Invalid market goods list');
 const metadata=new Map(itemMetadata.map(row=>[row.id,row])),goods=new Set(),capabilities=new Set(['retail_goods']);
 for(const row of raw.goods){
  if(!fields(row,['commodity','legacy_retail_capability','max_quantity','quantity_choices','price_min','price_max','price_choices','reserve_mode'])||
     !metadata.has(row.commodity)||metadata.get(row.commodity).currency||goods.has(row.commodity))throw new Error('Invalid registered market commodity');
  goods.add(row.commodity);
  if(row.legacy_retail_capability!==null){
   if(!id(row.legacy_retail_capability)||capabilities.has(row.legacy_retail_capability))throw new Error('Invalid duplicate retail capability');
   capabilities.add(row.legacy_retail_capability);
  }
  if(!integer(row.max_quantity,1,10)||!integer(row.price_min,1,100)||!integer(row.price_max,row.price_min,100))throw new Error('Invalid market bounds');
  for(const [key,low,high] of [['quantity_choices',1,row.max_quantity],['price_choices',row.price_min,row.price_max]]){
   const values=row[key];
   if(!Array.isArray(values)||!values.length||values.some((value,index)=>!integer(value,low,high)||(index>0&&value<=values[index-1])))throw new Error('Invalid market choices');
  }
  if(!['existing_food_policy','seller_choice'].includes(row.reserve_mode)||(row.reserve_mode==='existing_food_policy'&&row.commodity!=='bread'))throw new Error('Invalid market reserve mode');
 }
 marketPolicyCanonical(raw);
 return JSON.parse(JSON.stringify(raw));
}
function marketPolicyHash(policy){return marketPolicyDigest(marketPolicyCanonical(policy));}
function marketGood(policy,commodity){
 const found=policy.goods.find(row=>row.commodity===commodity);
 if(!found)throw new Error('Commodity is not enabled by the market policy');
 return JSON.parse(JSON.stringify(found));
}
if(typeof module!=='undefined')module.exports={validateMarketPolicy,marketPolicyHash,marketGood};
