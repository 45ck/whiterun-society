const test=require('node:test'),assert=require('node:assert/strict');
const {createRtsCamera}=require('../ui/rts-camera.js');
test('RTS panning follows orientation and rotation preserves position',()=>{
 const c=createRtsCamera(),start=c.status();c.step('north');assert.ok(c.status().panY>start.panY);
 const position=[c.status().panX,c.status().panY];c.step('right');assert.deepEqual([c.status().panX,c.status().panY],position);
 assert.equal(c.status().yaw,-165);assert.equal(c.status().mode,'free');
});

test('first RTS gesture starts from observed pose and empty drags do not snap the camera',()=>{
 const c=createRtsCamera(),sample={mode:'free',distance:1200,elevation:900,yaw:225,panX:24000,panY:-8000,request_id:'remote-1'};
 assert.equal(c.observe(sample),true);const before=c.status();
 assert.equal(c.step('drag',0,0),null);assert.deepEqual(c.status(),before);
 const moved=c.step('east');assert.equal(moved.yaw,-135);assert.equal(moved.distance,1200);assert.equal(moved.elevation,900);
 assert.ok(moved.panX<sample.panX);assert.ok(moved.panY>sample.panY);
});

test('older camera samples cannot undo rapid local gestures before acknowledgement',()=>{
 const c=createRtsCamera(),sample={...c.status(),request_id:'remote-1'};c.observe(sample);
 const one=c.step('in'),two=c.step('in');
 assert.equal(c.observe(sample),false);assert.equal(c.observe(one),false);assert.equal(c.status().distance,two.distance);
 assert.equal(c.observe(two),true);assert.equal(c.status().distance,two.distance);
 assert.equal(c.observe(one),false);assert.equal(c.status().distance,two.distance);
 c.step('right');assert.equal(c.observe({...sample,request_id:'remote-2'}),true,'new remote command can take over');
 assert.equal(c.status().yaw,-180);
});

test('invalid observations cannot partially change the camera and mode changes release pending input',()=>{
 const c=createRtsCamera(),before=c.status();
 assert.equal(c.observe({...before,panX:NaN}),false);assert.deepEqual(c.status(),before);
 c.step('in');assert.equal(c.observe({mode:'focus',id:7}),false);
 assert.equal(c.observe({...before,request_id:null}),true);assert.deepEqual(c.status(),before);
});
test('RTS wheel and drag cannot leave validated native camera bounds',()=>{
 const c=createRtsCamera();for(let i=0;i<200;i++){c.step('out');c.step('east');c.step('drag',1e9,-1e9);}
 const v=c.status();assert.ok(v.distance<=4000&&v.elevation<=2500);assert.ok(v.panX>=17000&&v.panX<=30000&&v.panY>=-15000&&v.panY<=1000);
 for(let i=0;i<200;i++)c.step('in');assert.equal(c.status().distance,100);assert.equal(c.status().elevation,40);
 const before=c.status();assert.equal(c.step('drag',NaN,0),null);assert.equal(c.step('attack'),null);assert.deepEqual(c.status(),before);
});
