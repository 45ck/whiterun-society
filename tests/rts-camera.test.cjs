const test=require('node:test'),assert=require('node:assert/strict');
const {createRtsCamera}=require('../ui/rts-camera.js');
test('RTS panning follows orientation and rotation preserves position',()=>{
 const c=createRtsCamera(),start=c.status();c.step('north');assert.ok(c.status().panY>start.panY);
 const position=[c.status().panX,c.status().panY];c.step('right');assert.deepEqual([c.status().panX,c.status().panY],position);
 assert.equal(c.status().yaw,-165);assert.equal(c.status().mode,'free');
});
test('RTS wheel and drag cannot leave validated native camera bounds',()=>{
 const c=createRtsCamera();for(let i=0;i<200;i++){c.step('out');c.step('east');c.step('drag',1e9,-1e9);}
 const v=c.status();assert.ok(v.distance<=4000&&v.elevation<=2500);assert.ok(v.panX>=17000&&v.panX<=30000&&v.panY>=-15000&&v.panY<=1000);
 for(let i=0;i<200;i++)c.step('in');assert.equal(c.status().distance,100);assert.equal(c.status().elevation,40);
 const before=c.status();assert.equal(c.step('drag',NaN,0),null);assert.equal(c.step('attack'),null);assert.deepEqual(c.status(),before);
});
