// Reviewed configuration supplies native identities and finite transformations.
// Language/decision commands may select a recipe, never supply native form IDs.
function canonicalJson(value){
 if(value===null||typeof value==='boolean')return JSON.stringify(value);
 if(typeof value==='string'){if(/[\ud800-\udfff]/u.test(value))throw new Error('Unpaired surrogate is not canonical text');return JSON.stringify(value);}
 if(typeof value==='number'){if(!Number.isSafeInteger(value))throw new Error('Catalog numbers must be safe integers');return JSON.stringify(value);}
 if(Array.isArray(value))return '['+value.map(canonicalJson).join(',')+']';
 if(value&&typeof value==='object'&&Object.getPrototypeOf(value)===Object.prototype)
  return '{'+Object.keys(value).sort().map(k=>{if(!/^[A-Za-z_][A-Za-z0-9_-]*$/.test(k))throw new Error('Canonical object keys must be ASCII identifiers');return JSON.stringify(k)+':'+canonicalJson(value[k]);}).join(',')+'}';
 throw new Error('Catalog contains unsupported data');
}
function sha256(text){
 const bytes=[];for(const character of text){const c=character.codePointAt(0);
  if(c<=0x7f)bytes.push(c);else if(c<=0x7ff)bytes.push(0xc0|(c>>6),0x80|(c&63));
  else if(c<=0xffff)bytes.push(0xe0|(c>>12),0x80|((c>>6)&63),0x80|(c&63));
  else bytes.push(0xf0|(c>>18),0x80|((c>>12)&63),0x80|((c>>6)&63),0x80|(c&63));}
 const bits=bytes.length*8;bytes.push(0x80);while(bytes.length%64!==56)bytes.push(0);
 for(let i=7;i>=0;i--)bytes.push(i>=4?0:(bits>>>(i*8))&255);
 const h=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
 const k=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
 const rotate=(x,n)=>(x>>>n)|(x<<(32-n));
 for(let offset=0;offset<bytes.length;offset+=64){const w=[];
  for(let i=0;i<16;i++)w[i]=(bytes[offset+4*i]<<24)|(bytes[offset+4*i+1]<<16)|(bytes[offset+4*i+2]<<8)|bytes[offset+4*i+3];
  for(let i=16;i<64;i++){const a=w[i-15],b=w[i-2];w[i]=(w[i-16]+(rotate(a,7)^rotate(a,18)^(a>>>3))+w[i-7]+(rotate(b,17)^rotate(b,19)^(b>>>10)))|0;}
  let [a,b,c,d,e,f,g,z]=h;
  for(let i=0;i<64;i++){const t1=(z+(rotate(e,6)^rotate(e,11)^rotate(e,25))+((e&f)^(~e&g))+k[i]+w[i])|0;
   const t2=((rotate(a,2)^rotate(a,13)^rotate(a,22))+((a&b)^(a&c)^(b&c)))|0;
   z=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0;}
  [a,b,c,d,e,f,g,z].forEach((v,i)=>h[i]=(h[i]+v)|0);
 }
 return h.map(n=>(n>>>0).toString(16).padStart(8,'0')).join('');
}
function validateEconomyCatalog(manifest){
 const keys=(o,wanted)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).sort().join('|')===[...wanted].sort().join('|');
 const id=x=>typeof x==='string'&&/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(x);
 const whitespace=/^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028-\u2029\u202f\u205f\u3000]|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028-\u2029\u202f\u205f\u3000]$/u;
 const text=(x,limit=500)=>typeof x==='string'&&[...x].length>0&&[...x].length<=limit&&!whitespace.test(x)&&!/[\u0000-\u001f\ud800-\udfff]/u.test(x);
 if(!keys(manifest,['schema_version','version','commodities','recipes'])||manifest.schema_version!==1||!id(manifest.version)||
    !Array.isArray(manifest.commodities)||manifest.commodities.length<1||manifest.commodities.length>64||
    !Array.isArray(manifest.recipes)||manifest.recipes.length<1||manifest.recipes.length>128)throw new Error('Invalid economy catalog envelope');
 const commodities={},recipes={},mappings=new Set(),currency=[];
 for(const item of manifest.commodities){
  if(!keys(item,['id','label','native','currency','provenance'])||!id(item.id)||Object.hasOwn(commodities,item.id)||!text(item.label,120)||!text(item.provenance)||typeof item.currency!=='boolean'||
     !keys(item.native,['plugin','local_form_id','record_type'])||!['MISC','ALCH','INGR'].includes(item.native.record_type)||typeof item.native.plugin!=='string'||!/^[A-Za-z0-9][A-Za-z0-9 _.-]{0,119}\.(esm|esp|esl)$/i.test(item.native.plugin)||item.native.plugin.includes('..')||
     !Number.isSafeInteger(item.native.local_form_id)||item.native.local_form_id<1||item.native.local_form_id>0xffffff)throw new Error('Invalid or duplicate catalog commodity');
  const mapping=item.native.plugin.toLowerCase()+':'+item.native.local_form_id;
  if(mappings.has(mapping))throw new Error('Commodity native mapping aliases another account');mappings.add(mapping);
  commodities[item.id]=JSON.parse(JSON.stringify(item));if(item.currency)currency.push(item.id);
 }
 if(currency.length!==1||currency[0]!=='gold')throw new Error('Catalog v1 requires exactly the gold currency account');
 for(const recipe of manifest.recipes){
  if(!keys(recipe,['id','version','inputs','outputs','work_minutes','provenance'])||!id(recipe.id)||Object.hasOwn(recipes,recipe.id)||!Number.isSafeInteger(recipe.version)||recipe.version<1||recipe.version>1000000||!text(recipe.provenance)||
     !keys(recipe.work_minutes,['minimum','default','maximum'])||!Object.values(recipe.work_minutes).every(Number.isSafeInteger)||recipe.work_minutes.minimum<5||recipe.work_minutes.maximum>120||
     recipe.work_minutes.minimum>recipe.work_minutes.default||recipe.work_minutes.default>recipe.work_minutes.maximum)throw new Error('Invalid catalog recipe');
  const input=Object.entries(recipe.inputs||{}),output=Object.entries(recipe.outputs||{});
  if(input.length!==1||output.length!==1||input[0][0]===output[0][0]||[...input,...output].some(([name,n])=>!Object.hasOwn(commodities,name)||commodities[name].currency||!Number.isSafeInteger(n)||n<1||n>1000))throw new Error('Recipe must transform one finite noncurrency input into one distinct output');
  recipes[recipe.id]=JSON.parse(JSON.stringify(recipe));
 }
 const catalog_hash=sha256(canonicalJson(manifest)),recipe_hashes={};for(const recipe of Object.values(recipes))
  recipe_hashes[recipe.id]=sha256(canonicalJson({catalog_hash,recipe}));
 return {catalog_hash,recipe_hashes,commodities,recipes,version:manifest.version};
}
function createEconomyCatalogController(platform,manifest){
 // CommonJS tests and CLI use the same checked-in file; native deploy injects it.
 if(manifest===undefined&&typeof module!=='undefined')manifest=require('../config/economy-catalog.json');
 let catalog,error;try{catalog=validateEconomyCatalog(manifest);}catch(e){error=String(e.message||e);}
 const clone=x=>JSON.parse(JSON.stringify(x));
 return {
  identity(recipeId){return catalog&&Object.hasOwn(catalog.recipes,recipeId)?{catalog_hash:catalog.catalog_hash,recipe_hash:catalog.recipe_hashes[recipeId]}:null;},
  recipe(recipeId){return catalog&&Object.hasOwn(catalog.recipes,recipeId)?clone(catalog.recipes[recipeId]):null;},
  itemIds(){return catalog?Object.keys(catalog.commodities).sort():[];},
  resolve(){
   if(!catalog)return {available:false,forms:{},errors:{catalog:error||'Catalog unavailable'},type_verified:false};
   const sp=platform(),forms={},errors={},seen=new Set();let typeVerified=true;
   // Skyrim FormType values verified against the owned SKSE FormType source.
   const types={MISC:['MiscObject',32],INGR:['Ingredient',30],ALCH:['Potion',46]};
   for(const [name,item] of Object.entries(catalog.commodities))try{
    const form=sp.Game.getFormFromFile?.(item.native.local_form_id,item.native.plugin),actual=form?.getFormID?.();
    if(!form||!Number.isInteger(actual)||actual<=0||actual>0xffffffff||((actual>>>24)===0xfe?actual&0xfff:actual&0xffffff)!==item.native.local_form_id)throw new Error('Native form unavailable or local identity mismatch');
    if(seen.has(actual))throw new Error('Resolved native form aliases another commodity');seen.add(actual);
    if(typeof sp.Game.getFormEx==='function'&&sp.Game.getFormEx(actual)?.getFormID?.()!==actual)throw new Error('Native identity roundtrip mismatch');
    const [className,typeNumber]=types[item.native.record_type],cast=sp[className]?.from;
    if(typeof cast!=='function'&&typeof form.getType!=='function'){typeVerified=false;throw new Error('Native record type verification unavailable');}
    if(typeof cast==='function'&&!sp[className].from(form)||typeof form.getType==='function'&&form.getType()!==typeNumber)throw new Error('Native record type differs from catalog');
    forms[name]=form;
   }catch(e){errors[name]=String(e.message||e);}
   return {available:Object.keys(errors).length===0,forms,errors,type_verified:typeVerified&&Object.keys(errors).length===0};
  },
  readInventory(actor){const resolved=this.resolve(),inventory={};for(const name of this.itemIds()){
   let n=null;try{if(resolved.forms[name])n=actor.getItemCount(resolved.forms[name]);}catch(_){}
   inventory[name]=Number.isSafeInteger(n)&&n>=0&&n<=2147483647?n:null;
  }return inventory;},
  validateOwnerCommand(command){
   const identity=this.identity(command.recipe_id),recipe=this.recipe(command.recipe_id),names=this.itemIds();
   const fail=message=>({ok:false,error:message});
   if(!identity||command.catalog_hash!==identity.catalog_hash||command.recipe_hash!==identity.recipe_hash)return fail('Recipe or catalog binding mismatch');
   if(!Number.isInteger(command.work_minutes)||command.work_minutes<recipe.work_minutes.minimum||command.work_minutes>recipe.work_minutes.maximum)return fail('Recipe attendance outside catalog bounds');
   if(!command.before||!command.after||[command.before,command.after].some(x=>Object.keys(x).join(',')!=='owner')||
      [command.before.owner,command.after.owner].some(x=>!x||Object.keys(x).sort().join('|')!==names.join('|')||Object.values(x).some(n=>!Number.isSafeInteger(n)||n<0||n>2147483647)))return fail('Complete observed owner account required');
   const [input,inputCount]=Object.entries(recipe.inputs)[0],[output,outputCount]=Object.entries(recipe.outputs)[0],expected=clone(command.before);
   expected.owner[input]-=inputCount;expected.owner[output]+=outputCount;
   if(expected.owner[input]<0||!Number.isSafeInteger(expected.owner[output])||expected.owner[output]>2147483647||names.some(k=>expected.owner[k]!==command.after.owner[k]))return fail('Owner transformation differs from catalog or changes unrelated balances');
   return {ok:true,input,inputCount,output,outputCount,recipe,items:names};
  },
  status(){const resolved=this.resolve();return {available:resolved.available,catalog_hash:catalog?.catalog_hash||null,version:catalog?.version||null,
   recipe_hashes:catalog?clone(catalog.recipe_hashes):{},item_ids:this.itemIds(),errors:resolved.errors,type_verified:resolved.type_verified};}
 };
}
if(typeof module!=='undefined')module.exports={canonicalJson,sha256,validateEconomyCatalog,createEconomyCatalogController};
