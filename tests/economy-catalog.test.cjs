const test=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {canonicalJson,sha256,validateEconomyCatalog,createEconomyCatalogController}=require('../bridge/economy-catalog.js');
const manifest=require('../config/economy-catalog.json');
function setup(configuration=manifest){
 const forms=new Map(configuration.commodities.map(c=>[c.native.local_form_id,{getFormID:()=>c.native.local_form_id,getType:()=>({MISC:32,ALCH:46,INGR:30}[c.native.record_type])}]));
 const sp={Game:{getFormFromFile:(id,file)=>configuration.commodities.some(c=>c.native.local_form_id===id&&c.native.plugin===file)?forms.get(id):null,getFormEx:id=>forms.get(id)}};
 return {forms,sp,catalog:createEconomyCatalogController(()=>sp,configuration)};
}
test('canonical hashing is UTF8, sorted keys and independently matches SHA256',()=>{
 for(const value of ['', 'abc', 'Grain 🌾 café', 'x'.repeat(1000),canonicalJson(manifest)])assert.equal(sha256(value),crypto.createHash('sha256').update(value,'utf8').digest('hex'));
 const verified=validateEconomyCatalog(manifest);
 assert.equal(verified.catalog_hash,crypto.createHash('sha256').update(canonicalJson(manifest)).digest('hex'));
 assert.equal(verified.recipe_hashes.bread_recipe,crypto.createHash('sha256').update(canonicalJson({catalog_hash:verified.catalog_hash,recipe:manifest.recipes[0]})).digest('hex'));
 assert.equal(canonicalJson({z:1,a:{b:2,a:3}}),'{"a":{"a":3,"b":2},"z":1}');
 for(const value of [1.5,Infinity,{bad_key:undefined},{'non ascii 🌾':1},'\ud800'])assert.throws(()=>canonicalJson(value));
});
test('strict schema rejects untrusted fields, aliases, invalid counts and currency creation',()=>{
 for(const change of [c=>c.extra=true,c=>c.commodities[0].native.extra=true,c=>c.commodities[1].native={...c.commodities[0].native,plugin:'SKYRIM.ESM'},
  c=>c.recipes[0].inputs={},c=>c.recipes[0].outputs={gold:2},c=>c.recipes[0].outputs={grain:2},c=>c.recipes[0].inputs.grain=0,
  c=>c.recipes[0].inputs.grain=1001,c=>c.recipes[0].work_minutes.minimum=0,c=>c.recipes[0].version=1000001,
  c=>c.commodities[0].label=' white space ',c=>c.commodities[0].native.record_type='NPC_',c=>c.commodities[0].native.plugin='../Bad.esp']){
  const copy=structuredClone(manifest);change(copy);assert.throws(()=>validateEconomyCatalog(copy));
 }
});
test('uppercase and hyphen IDs and Unicode labels follow the same canonical contract',()=>{
 const copy=structuredClone(manifest);copy.recipes[0].id='Recipe-Alternate';copy.commodities[1].label='🌾'.repeat(120);
 assert.ok(validateEconomyCatalog(copy).recipe_hashes['Recipe-Alternate']);copy.commodities[1].label+='🌾';assert.throws(()=>validateEconomyCatalog(copy));
});
test('positive-input positive-labour recycling cycles are allowed without a profitability claim',()=>{
 const copy=structuredClone(manifest);copy.recipes.push({...structuredClone(copy.recipes[0]),id:'recycle',inputs:{bread:2},outputs:{grain:1}});
 assert.ok(validateEconomyCatalog(copy).recipes.recycle);
});
test('verified plugin-local forms expose complete inventory and unknown is null',()=>{
 const f=setup();assert.equal(f.catalog.status().available,true);assert.equal(f.catalog.status().type_verified,true);
 assert.deepEqual(f.catalog.readInventory({getItemCount:()=>7}),{bread:7,gold:7,grain:7});
 f.forms.delete(15);assert.equal(f.catalog.status().available,false);assert.equal(f.catalog.readInventory({getItemCount:()=>7}).gold,null);
 assert.equal(f.catalog.readInventory({getItemCount:()=>NaN}).bread,null);
});
test('runtime type, local identity, alias and roundtrip failures are unavailable',()=>{
 for(const change of [f=>f.forms.get(15).getType=()=>43,f=>f.forms.get(15).getFormID=()=>16,
  f=>delete f.forms.get(15).getType,f=>f.sp.Game.getFormEx=()=>null]){
  const f=setup();change(f);assert.equal(f.catalog.status().available,false);
 }
 const copy=structuredClone(manifest);copy.commodities[1].native={...copy.commodities[0].native,plugin:'Other.esp'};
 const f=setup(copy);assert.equal(f.catalog.status().available,false);
});
test('specific class casts can verify type when generic getType is unavailable',()=>{
 const f=setup();for(const form of f.forms.values())delete form.getType;
 f.sp.MiscObject={from:form=>form.getFormID()===15?form:null};f.sp.Potion={from:form=>form.getFormID()===0x65c97?form:null};f.sp.Ingredient={from:form=>form.getFormID()===0x4b0ba?form:null};
 assert.equal(f.catalog.status().available,true);f.sp.Potion.from=()=>null;assert.equal(f.catalog.status().available,false);
});
test('immutable catalog authority rejects changed deltas, missing balances and stale hashes',()=>{
 const f=setup(),identity=f.catalog.identity('bread_recipe');
 const c={recipe_id:'bread_recipe',...identity,work_minutes:5,before:{owner:{gold:7,bread:0,grain:2}},after:{owner:{gold:7,bread:2,grain:1}}};
 assert.equal(f.catalog.validateOwnerCommand(c).ok,true);
 for(const change of [x=>x.catalog_hash='old',x=>x.recipe_hash='wrong',x=>x.after.owner.gold++,x=>delete x.before.owner.gold,
  x=>x.after.owner.grain=2,x=>x.work_minutes=4,x=>x.before.owner.bread=2147483647]){
  const other=structuredClone(c);change(other);assert.equal(f.catalog.validateOwnerCommand(other).ok,false);
 }
 const source=structuredClone(manifest),isolated=setup(source);source.recipes[0].outputs.bread=100;
 assert.equal(isolated.catalog.recipe('bread_recipe').outputs.bread,2);
});
