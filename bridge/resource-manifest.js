// Reviewed source policy only. Native callers validate against their installed
// catalog before retaining this defensive snapshot; commands cannot replace it.
const resourceManifestCanonical=typeof canonicalJson==='function'?canonicalJson:require('./economy-catalog.js').canonicalJson;
const resourceManifestDigest=typeof sha256==='function'?sha256:require('./economy-catalog.js').sha256;
function validateResourceManifest(manifest,catalogHash,itemIds){
 const fields=(value,wanted)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join('|')===[...wanted].sort().join('|');
 const integer=(value,min,max)=>Number.isSafeInteger(value)&&value>=min&&value<=max;
 const id=value=>typeof value==='string'&&/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(value);
 const whitespace=/^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]$/u;
 const text=value=>typeof value==='string'&&[...value].length>0&&[...value].length<=500&&!whitespace.test(value)&&!/[\u0000-\u001f\ud800-\udfff]/u.test(value);
 if(!fields(manifest,['schema_version','id','version','catalog_hash','capacity','default_grant','overrides','max_recipient_stock','provenance'])||
    manifest.schema_version!==1||!id(manifest.id)||!id(manifest.version)||!text(manifest.provenance)||
    typeof catalogHash!=='string'||!/^[a-f0-9]{64}$/.test(catalogHash)||manifest.catalog_hash!==catalogHash||
    !Array.isArray(itemIds)||!itemIds.length||itemIds.length>64||!itemIds.every(id)||new Set(itemIds).size!==itemIds.length)
  throw new Error('Invalid resource manifest envelope or catalog binding');
 const quantities=value=>fields(value,itemIds)&&Object.values(value).every(n=>integer(n,0,2147483647));
 if(!quantities(manifest.capacity)||!integer(manifest.max_recipient_stock,0,2147483647))throw new Error('Invalid resource capacity or stock limit');
 const grant=value=>quantities(value)&&Object.values(value).some(n=>n>0)&&itemIds.every(key=>value[key]<=manifest.capacity[key]);
 if(!grant(manifest.default_grant)||!Array.isArray(manifest.overrides)||manifest.overrides.length>128)
  throw new Error('Invalid default grant or resource override list');
 const selectors=new Set(['default']),actors=new Set();
 for(const override of manifest.overrides){
  if(!fields(override,['id','selector','grant','provenance'])||!id(override.id)||selectors.has(override.id)||!text(override.provenance)||
     !fields(override.selector,['actor','actor_base_id'])||!integer(override.selector.actor,1,0xffffffff)||
     !integer(override.selector.actor_base_id,1,0xffffffff)||actors.has(override.selector.actor)||!grant(override.grant))
   throw new Error('Invalid duplicate or aliased resource override');
  selectors.add(override.id);actors.add(override.selector.actor);
 }
 resourceManifestCanonical(manifest);
 return JSON.parse(JSON.stringify(manifest));
}
function resourceManifestHash(manifest){return resourceManifestDigest(resourceManifestCanonical(manifest));}
function selectResourceGrant(manifest,actor,actorBaseId){
 // Selection validates shape again. Catalog authorization belongs to the
 // earlier validateResourceManifest(..., installedHash, installedItemIds) call.
 manifest=validateResourceManifest(manifest,manifest?.catalog_hash,Object.keys(manifest?.capacity||{}));
 if(!Number.isSafeInteger(actor)||actor<=0||actor>0xffffffff||!Number.isSafeInteger(actorBaseId)||actorBaseId<=0||actorBaseId>0xffffffff)
  throw new Error('Invalid resource recipient identity');
 let selector_id='default',grant=manifest.default_grant;
 for(const override of manifest.overrides)if(override.selector.actor===actor){
  if(override.selector.actor_base_id!==actorBaseId)throw new Error('Resource recipient base identity differs from the authored selector');
  selector_id=override.id;grant=override.grant;break;
 }
 const payload={catalog_hash:manifest.catalog_hash,manifest_hash:resourceManifestHash(manifest),
  recipient:{actor,actor_base_id:actorBaseId},selector_id,grant};
 return {selector_id,grant:JSON.parse(JSON.stringify(grant)),grant_hash:resourceManifestDigest(resourceManifestCanonical(payload))};
}
if(typeof module!=='undefined')module.exports={validateResourceManifest,selectResourceGrant,resourceManifestHash};
