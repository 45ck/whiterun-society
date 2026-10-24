const test=require('node:test'),assert=require('node:assert/strict');
const {createObserverCamera}=require('../bridge/observer-camera.js');
test('any positively classified initialized loaded resident can be followed',()=>{
 const camera=createObserverCamera();assert.equal(camera.accept({mode:'focus',id:99,request_id:'view-one'},[{id:99,isPerson:true}],{'99':{}}),true);
 assert.equal(camera.status().id,99);assert.equal(camera.status().request_id,'view-one');assert.equal(camera.status().manual,true);
});
test('unknown unloaded and non-person IDs cannot steer follow camera',()=>{
 for(const [rows,managed] of [[[],{'99':{}}],[[{id:99,isPerson:false}],{'99':{}}],[[{id:99,isPerson:true}],{}]])assert.equal(createObserverCamera().accept({mode:'focus',id:99},rows,managed),false);
});
test('invalid camera parameters cannot partially mutate the current view',()=>{
 const camera=createObserverCamera(),before=camera.status();
 for(const value of [Infinity,NaN,0,4001,'800'])assert.equal(camera.accept({mode:'free',distance:value},[],{}),false);
 assert.deepEqual(camera.status(),before);assert.equal(camera.accept({mode:'free',distance:1200,panX:25000},[],{}),true);camera.reset();assert.equal(camera.status().manual,false);
});
