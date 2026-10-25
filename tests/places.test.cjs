const test=require('node:test'),assert=require('node:assert/strict');
const {createPlaceObserver,validateVenueCatalog}=require('../bridge/places.js');
const {createPapyrusRouterController}=require('../bridge/papyrus-router.js');
function fixture(){
 let actorWorld=1,interior=false,disabled=false;
 const ref={getFormID:()=>0x2be1b,getParentCell:()=>({getFormID:()=>10,isInterior:()=>false}),getWorldSpace:()=>({getFormID:()=>1}),
  getPositionX:()=>1,getPositionY:()=>2,getPositionZ:()=>3,isDisabled:()=>disabled,is3DLoaded:()=>false};
 const actor={...ref,getFormID:()=>99,is3DLoaded:()=>true,getParentCell:()=>({isInterior:()=>interior}),
  getWorldSpace:()=>({getFormID:()=>actorWorld})};
 const sp={ObjectReference:{from:x=>x},Actor:{from:x=>x},Game:{getFormEx:id=>id===99?actor:ref}};
 return {actor,ref,sp,observer:createPlaceObserver(()=>sp),world:x=>actorWorld=x,inside:()=>interior=true,disable:()=>disabled=true};
}
test('invisible public marker remains a destination without requiring a person there',()=>{
 const f=fixture(),p=f.observer.sense([{id:99,isPerson:true}])[0];
 assert.equal(p.available,true);assert.deepEqual(p.eligible_actors,[99]);assert.deepEqual(p.position,[1,2,3]);
 assert.equal(f.observer.validTarget(f.actor,f.ref),true);
 assert.deepEqual(p.space,{cell:10,interior:false,world:1});assert.equal(p.catalog_version,'whiterun-venues-v1');
});

test('catalogue changes offered references without resident-name branches',()=>{
 const f=fixture(),catalog=structuredClone(require('../config/places.json'));
 catalog.version='different-town';catalog.venues=[{...catalog.venues[0],id:500,name:'New square'}];
 const other={...f.ref,getFormID:()=>500};f.sp.Game.getFormEx=id=>id===99?f.actor:id===500?other:null;
 const observer=createPlaceObserver(()=>f.sp,catalog),p=observer.sense([{id:99,isPerson:true}]);
 assert.equal(p.length,1);assert.equal(p[0].id,500);assert.deepEqual(p[0].eligible_actors,[99]);
 assert.equal(observer.validTarget(f.actor,f.ref),false);assert.equal(observer.validTarget(f.actor,other),true);
 catalog.venues=[];assert.equal(observer.sense([]).length,1); // immutable deployed catalogue
 assert.equal(createPlaceObserver(()=>f.sp,catalog).sense([]).length,0);
});

test('invalid venue IDs, duplicate references, kinds and access declarations are rejected',()=>{
 const catalog=require('../config/places.json');
 for(const change of [{id:0},{id:1.5},{id:0x100000000},{kind:'teleport'},{access:'private'},{provenance:''}])
  assert.throws(()=>validateVenueCatalog({...catalog,venues:[{...catalog.venues[0],...change}]}),/Invalid venue/);
 assert.throws(()=>validateVenueCatalog({...catalog,venues:[catalog.venues[0],catalog.venues[0]]}),/Invalid venue/);
 assert.throws(()=>validateVenueCatalog({...catalog,venues:[{...catalog.venues[1],access:'public'}]}),/Invalid venue/);
});
test('other worldspaces, interiors, disabled references and unknown forms cannot be destinations',()=>{
 const f=fixture();f.world(2);assert.equal(f.observer.validTarget(f.actor,f.ref),false);
 f.world(1);f.inside();assert.equal(f.observer.validTarget(f.actor,f.ref),false);
 const g=fixture();g.disable();assert.equal(g.observer.sense([])[0].available,false);
 const h=fixture();assert.equal(h.observer.validTarget(h.actor,{...h.ref,getFormID:()=>42}),false);
});
test('unknown native API availability fails closed without fabricating coordinates',()=>{
 const f=fixture();f.ref.getWorldSpace=undefined;
 assert.equal(f.observer.sense([{id:99,isPerson:true}])[0].available,false);
});
test('place commands require the explicit public destination validator',()=>{
 const f=fixture();f.sp.Game.getFormFromFile=()=>({getFormID:()=>123});
 f.sp.Quest={from:()=>({isRunning:()=>false})};f.sp.FormList={from:x=>x};f.sp.GlobalVariable={from:x=>x};
 f.actor.isDead=()=>false;f.actor.isChild=()=>false;
 const command={id:'place',actor:99,target:0x2be1b,target_kind:'place'};
 const missing=createPapyrusRouterController(()=>f.sp);
 assert.equal(missing.step(command).ack.status,'held');
 const allowed=createPapyrusRouterController(()=>f.sp,()=>0,{placeObserver:f.observer});
 assert.equal(allowed.step(command).done,false);assert.equal(allowed.status().target_kind,'place');
});
