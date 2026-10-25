const test=require('node:test'),assert=require('node:assert/strict');
const {createObserverCamera}=require('../bridge/observer-camera.js');
const {storyActor}=require('../bridge/observer-camera.js');
const {movieSubjects,movieFrame}=require('../bridge/observer-camera.js');

test('movie view is the default and manual RTS remains an explicit override',()=>{
 const camera=createObserverCamera();assert.equal(camera.status().mode,'story');assert.equal(camera.status().manual,false);
 camera.accept({mode:'free'},[],{});assert.equal(camera.status().manual,true);
 camera.reset();assert.equal(camera.status().mode,'story');assert.equal(camera.status().manual,false);
});

test('movie view can follow an active independent journey without inventing a tour',()=>{
 const rows=[{id:7,isPerson:true},{id:8,isPerson:true}],society={routine_batch:{phase:'travelling',members:[{actor:99,phase:'travelling'},{actor:7,phase:'complete'},{actor:8,phase:'travelling'}]}};
 assert.equal(storyActor(society,rows),8);assert.deepEqual(movieSubjects(society,rows),[8]);
 society.conversation={phase:'speaking',current:{speaker:7}};assert.equal(storyActor(society,rows),7);
 society.conversation.phase='complete';society.routine_batch.phase='complete';assert.equal(storyActor(society,rows),null);
});

test('movie pair remains stable across speaker changes and excludes finished encounters',()=>{
 const rows=[7,8].map(id=>({id,isPerson:true}));
 for(const speaker of [7,8])assert.deepEqual(movieSubjects({conversation:{phase:'speaking',speakers:[8,7],current:{speaker}}},rows),[7,8]);
 for(const phase of ['held','complete'])assert.deepEqual(movieSubjects({plan:{phase,economic_pair:[7,8],actor:7}},rows),[]);
 assert.deepEqual(movieSubjects({plan:{phase:'travelling',actor:7,economic_pair:[7,99]}},rows),[7]);
});

test('movie composition frames both residents and keeps the same side when the speaker swaps',()=>{
 const a={id:7,x:0,y:0,z:0,heading:0},b={id:8,x:200,y:0,z:0,heading:180};
 const first=movieFrame([a,b],null,[100,-500,200]);
 assert.deepEqual(first.target,[100,0,80]);assert.deepEqual(first.position,[100,-150,600]);
 assert.deepEqual(movieFrame([b,a],first,[100,500,200]),first);
 assert.equal(first.collision,'unverified');
 const moved=movieFrame([{...a,x:100},{...b,x:300}],first);
 assert.deepEqual(moved.position,[200,-150,600]);
});

test('distant pairs follow the lead resident and invalid geometry cannot steer a camera',()=>{
 const a={id:7,x:0,y:0,z:0,heading:0},b={id:8,x:1000,y:0,z:0,heading:90};
 const shot=movieFrame([b,a]);assert.equal(shot.kind,'resident');assert.deepEqual(shot.ids,[8]);
 assert.equal(shot.position[0],1180);assert.equal(shot.position[2],610);
 assert.equal(movieFrame([]),null);assert.equal(movieFrame([{...a,z:NaN}]),null);
 assert.ok(movieFrame([a,{...b,x:650}]).offset.every(Number.isFinite));
 assert.equal(movieFrame([a,{...b,x:651}]).kind,'resident');
});

test('a resident turning in place does not orbit the movie camera',()=>{
 const actor={id:7,x:100,y:200,z:0,heading:0};
 const first=movieFrame([actor]);
 const turned=movieFrame([{...actor,heading:180}],first);
 assert.deepEqual(turned.offset,first.offset);assert.deepEqual(turned.position,first.position);
 const moved=movieFrame([{...actor,x:200,heading:270}],turned);
 assert.deepEqual(moved.offset,first.offset);assert.equal(moved.position[0],first.position[0]+100);
 assert.equal(moved.collision,'unverified');assert.equal(moved.profile,'subject-relative-elevated-v3');
});

test('unqualified camera geometry uses a steep subject-relative fallback without claiming clearance',()=>{
 const a={id:701,x:9000,y:8000,z:300,heading:45},b={id:702,x:9650,y:8000,z:300,heading:200};
 for(const rows of [[a],[a,b]]){
  const shot=movieFrame(rows);assert.ok(shot.offset[2]/Math.hypot(...shot.offset.slice(0,2))>1.4);
  assert.equal(shot.collision,'unverified');assert.equal(shot.geometry_query,'unavailable');assert.equal(shot.occlusion_strategy,'elevated_fallback');
  assert.deepEqual(shot.position,shot.target.map((v,i)=>v+shot.offset[i]));
 }
});

test('upgrading an old close shot keeps its bearing while raising and shortening the camera offset',()=>{
 const actor={id:7,x:100,y:200,z:0,heading:180};
 const old={key:'7',kind:'resident',offset:[260,0,110],profile:'subject-relative-v2'};
 const next=movieFrame([actor],old);assert.ok(Math.abs(next.offset[0]-180)<1e-8);assert.ok(Math.abs(next.offset[1])<1e-8);
 assert.ok(next.offset[2]>old.offset[2]);
 for(let i=0;i<100;i++){
  const repeated=movieFrame([{...actor,heading:i*3}],next);assert.deepEqual(repeated.offset,next.offset);
 }
});

test('new movie subjects recompose and invalid prior bearings cannot steer the camera',()=>{
 const actor={id:7,x:0,y:0,z:0,heading:0},first=movieFrame([actor]);
 const next={...actor,id:8,heading:180},newShot=movieFrame([next],first);
 assert.deepEqual(newShot,movieFrame([next]));
 for(const offset of [[NaN,260,110],[0,0,110],[1,2]]){
  assert.deepEqual(movieFrame([next],{...newShot,offset}),movieFrame([next]));
 }
 const pair=movieFrame([actor,{...next,x:200}]);
 assert.deepEqual(movieFrame([actor],pair),movieFrame([actor]));
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
 assert.deepEqual(camera.status(),before);assert.equal(camera.accept({mode:'free',distance:1200,panX:25000},[],{}),true);camera.reset();assert.equal(camera.status().manual,false);assert.equal(camera.status().mode,'story');
});

test('capture is restricted to explicit portrait/atlas requests and reset restores UI',()=>{
 const c=createObserverCamera(),rows=[{id:7,isPerson:true}],managed={'7':{}};
 assert.equal(c.accept({mode:'portrait',id:7,capture:true},rows,managed),true);assert.equal(c.status().capture,true);
 assert.equal(c.accept({mode:'portrait',id:9,capture:true},rows,managed),false);
 assert.equal(c.accept({mode:'free',capture:true},rows,managed),false);assert.equal(c.status().capture,true);
 c.reset();assert.equal(c.status().capture,false);assert.equal(c.status().mode,'story');
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
