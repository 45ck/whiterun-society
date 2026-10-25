const test=require('node:test'),assert=require('node:assert/strict');
const {createObserverCamera}=require('../bridge/observer-camera.js');
const {storyActor}=require('../bridge/observer-camera.js');
const {movieSubjects,movieFrame}=require('../bridge/observer-camera.js');

test('movie pair remains stable across speaker changes and excludes finished encounters',()=>{
 const rows=[7,8].map(id=>({id,isPerson:true}));
 for(const speaker of [7,8])assert.deepEqual(movieSubjects({conversation:{phase:'speaking',speakers:[8,7],current:{speaker}}},rows),[7,8]);
 for(const phase of ['held','complete'])assert.deepEqual(movieSubjects({plan:{phase,economic_pair:[7,8],actor:7}},rows),[]);
 assert.deepEqual(movieSubjects({plan:{phase:'travelling',actor:7,economic_pair:[7,99]}},rows),[7]);
});

test('movie composition frames both residents and keeps the same side when the speaker swaps',()=>{
 const a={id:7,x:0,y:0,z:0,heading:0},b={id:8,x:200,y:0,z:0,heading:180};
 const first=movieFrame([a,b],null,[100,-500,200]);
 assert.deepEqual(first.target,[100,0,80]);assert.deepEqual(first.position,[100,-250,230]);
 assert.deepEqual(movieFrame([b,a],first,[100,500,200]),first);
 assert.equal(first.collision,'unverified');
 const moved=movieFrame([{...a,x:100},{...b,x:300}],first);
 assert.deepEqual(moved.position,[200,-250,230]);
});

test('distant pairs follow the lead resident and invalid geometry cannot steer a camera',()=>{
 const a={id:7,x:0,y:0,z:0,heading:0},b={id:8,x:1000,y:0,z:0,heading:90};
 const shot=movieFrame([b,a]);assert.equal(shot.kind,'resident');assert.deepEqual(shot.ids,[8]);
 assert.equal(shot.position[0],1260);assert.equal(shot.position[2],200);
 assert.equal(movieFrame([]),null);assert.equal(movieFrame([{...a,z:NaN}]),null);
 assert.ok(movieFrame([a,{...b,x:650}]).offset.every(Number.isFinite));
 assert.equal(movieFrame([a,{...b,x:651}]).kind,'resident');
});
test('activity camera follows current speaker and respects manual override',()=>{
 const camera=createObserverCamera(),rows=[{id:7,isPerson:true},{id:8,isPerson:true}];
 assert.equal(camera.accept({mode:'story',request_id:'story'},rows,{}),true);
 assert.equal(camera.status().manual,false);assert.equal(camera.status().mode,'story');
 assert.equal(storyActor({conversation:{phase:'meeting',initiator:7}},rows),7);
 assert.equal(storyActor({conversation:{phase:'speaking',initiator:7,current:{speaker:8}}},rows),8);
 assert.equal(storyActor({conversation:{phase:'complete',initiator:7},plan:{phase:'travelling',actor:8}},rows),8);
 assert.equal(storyActor({plan:{phase:'economic_speaking',actor:7,economic_speech:{actor:8}}},rows),8);
 assert.equal(storyActor({conversation:{phase:'speaking',current:{speaker:9}}},rows),null);
 assert.equal(camera.accept({mode:'focus',id:7},rows,{'7':{}}),true);assert.equal(camera.status().manual,true);
});
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
 assert.deepEqual(camera.status(),before);assert.equal(camera.accept({mode:'free',distance:1200,panX:25000},[],{}),true);camera.reset();assert.equal(camera.status().manual,true);assert.equal(camera.status().mode,'free');
});

test('capture is restricted to explicit portrait/atlas requests and reset restores UI',()=>{
 const c=createObserverCamera(),rows=[{id:7,isPerson:true}],managed={'7':{}};
 assert.equal(c.accept({mode:'portrait',id:7,capture:true},rows,managed),true);assert.equal(c.status().capture,true);
 assert.equal(c.accept({mode:'portrait',id:9,capture:true},rows,managed),false);
 assert.equal(c.accept({mode:'free',capture:true},rows,managed),false);assert.equal(c.status().capture,true);
 c.reset();assert.equal(c.status().capture,false);assert.equal(c.status().mode,'free');
 assert.equal(c.accept({mode:'atlas',capture:true},rows,managed),true);assert.equal(c.accept({mode:'story'},rows,managed),true);assert.equal(c.status().capture,false);
});

test('a retained remote request cannot override later native clicks or replay after reset',()=>{
 const c=createObserverCamera(),rows=[{id:7,isPerson:true}],people={'7':{}};
 const remote={mode:'free',request_id:'remote-one'};assert.equal(c.acceptRemote(remote,rows,people),true);
 assert.equal(c.accept({mode:'focus',id:7},rows,people),true);
 assert.equal(c.acceptRemote(remote,rows,people),false);assert.equal(c.status().mode,'focus');assert.equal(c.status().id,7);
 c.reset();assert.equal(c.acceptRemote(remote,rows,people),false);assert.equal(c.status().capture,false);
 assert.equal(c.acceptRemote({mode:'story',request_id:'remote-two'},rows,people),true);assert.equal(c.status().mode,'story');
});

test('trade camera uses the negotiated pair instead of stale conversation participants',()=>{
 const {tradeCameraActors}=require('../bridge/observer-camera.js');
 const rows=[1,2,3,4].map(id=>({id,isPerson:true}));
 assert.deepEqual(tradeCameraActors({plan:{economic_pair:[3,4]},conversation:{phase:'complete',speakers:[1,2]}},rows),[3,4]);
 assert.deepEqual(tradeCameraActors({conversation:{phase:'complete',speakers:[1,2]}},rows),[]);
 assert.deepEqual(tradeCameraActors({conversation:{phase:'speaking',speakers:[1,2]}},rows),[1,2]);
 assert.deepEqual(tradeCameraActors({plan:{economic_pair:[3,99]}},rows),[]);
});
