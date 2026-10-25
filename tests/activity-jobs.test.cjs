const test=require('node:test'),assert=require('node:assert/strict');
const {createActivityJobsController}=require('../bridge/activity-jobs.js');
function fixture(){
 let clock=0,baseId=801;const lanes=[],optionsSeen=[];
 const platform={Actor:{from:x=>x},Game:{getFormEx:()=>({getActorBase:()=>({getFormID:()=>baseId})})}};
 const c=createActivityJobsController(()=>platform,()=>clock,null,{restFactory:(_p,_n,_c,options)=>{
  optionsSeen.push(options);let state=null;
  const lane={ticks:0,ready:true,released:true,releaseCount:0,finish:false,throwNext:false,
   available:()=>true,released:()=>lane.ready,release(){lane.releaseCount++;},reset(){state=null;lane.finish=false;},
   cancel(command,error){state={...state,actor:command.actor,target:command.target,phase:'releasing',error};lane.cancelled=true;},
   status:()=>state,step(command){lane.ticks++;if(lane.throwNext){lane.throwNext=false;throw Error('test native failure');}
    state={...state,actor:command.actor,target:command.target,phase:lane.cancelled?'releasing':'resting',rested_minutes:lane.finish?30:0,seated_samples:lane.finish?61:1,exact_furniture_verified:true};
    if(!lane.finish&&!lane.cancelled)return {done:false};
    state.phase=lane.cancelled||!lane.releaseVerified?'held':'applied';state.release_verified=lane.releaseVerified;
    return {done:true,ack:{id:command.id,status:state.phase,rest:{...state}}};},releaseVerified:true};
  lanes.push(lane);return lane;
 }});
 const a={job_id:'rest-a',actor:501,target:701,slot:0,session:'native-a',epoch:'epoch-1',rest_minutes:30};
 const b={job_id:'rest-b',actor:502,target:702,slot:1,session:'native-a',epoch:'epoch-1',rest_minutes:30};
 let desired={epoch:'epoch-1',jobs:[a,b]},session='native-a';
 const f={c,lanes,optionsSeen,a,b,tick:(fresh=true)=>{clock+=20;c.tick(desired,session,fresh);},start:(job=a,blocked=[])=>c.start({...job,id:'start-'+job.job_id},blocked).ack,
  ack:(job=a)=>c.acknowledge({...job,id:'ack-'+job.job_id}).ack,setDesired:d=>desired=d,setSession:s=>session=s,setBase:id=>baseId=id};
 f.tick();return f;
}
test('each furniture slot gets its independent plugin offset',()=>{
 const f=fixture();assert.deepEqual(f.optionsSeen,[{router:{file:'WhiterunActivities.esp',offset:0}},{router:{file:'WhiterunActivities.esp',offset:0x100}}]);
});
test('admission immediately acknowledges while both jobs tick independently',()=>{
 const f=fixture();assert.equal(f.start().accepted,true);assert.equal(f.start(f.b).accepted,true);
 assert.deepEqual(f.lanes.map(l=>l.ticks),[0,0]);f.tick();assert.deepEqual(f.lanes.map(l=>l.ticks),[1,1]);
 f.lanes[0].finish=true;f.tick();f.tick();assert.equal(f.lanes[0].ticks,2);assert.equal(f.lanes[1].ticks,3);
 assert.equal(f.c.status().receipts[0].status,'applied');assert.equal(f.c.status().jobs[1].phase,'resting');
});
test('terminal receipts reserve actor and slot until exact durable acknowledgement',()=>{
 const f=fixture();f.start();f.lanes[0].finish=true;f.tick();
 assert.equal(f.c.ownsActor(501),true);assert.equal(f.c.status().receipts.length,1);
 assert.equal(f.ack({...f.a,actor:999}).status,'held');assert.equal(f.ack({...f.a,epoch:'other'}).status,'held');
 assert.equal(f.c.status().receipts.length,1);assert.equal(f.ack().acknowledged,true);
 assert.equal(f.c.ownsActor(501),false);assert.equal(f.c.status().receipts.length,0);assert.equal(f.ack().acknowledged,true);
 assert.equal(f.start().status,'held');assert.equal(f.start().no_effects_issued,false);
});
test('missing admission and early receipt acknowledgement cannot fabricate completion',()=>{
 const f=fixture();assert.equal(f.ack().acknowledged,false);f.start();assert.equal(f.ack().acknowledged,false);
 assert.equal(f.c.status().receipts.length,0);assert.equal(f.c.ownsActor(501),true);
});
test('conflicting actor, furniture and slot cannot start; unrelated job remains intact',()=>{
 for(const field of ['actor','target','slot']){
  const f=fixture();f.start();const other={...f.b,[field]:f.a[field]};f.setDesired({epoch:'epoch-1',jobs:[f.a,other]});f.tick();
  const result=f.start(other);assert.equal(result.accepted,false);assert.equal(result.no_effects_issued,true);
  assert.equal(f.c.status().jobs.length,1);assert.equal(f.c.status().jobs[0].job_id,f.a.job_id);
 }
});
test('stale assignments, invalid durations and foreground actor ownership reject without native work',()=>{
 const f=fixture();assert.equal(f.start(f.a,[501]).accepted,false);assert.equal(f.start({...f.a,rest_minutes:60}).accepted,false);
 assert.equal(f.start({...f.a,session:'old'}).accepted,false);f.tick(false);assert.equal(f.start().accepted,false);
 assert.equal(f.lanes[0].ticks,0);assert.equal(f.c.status().jobs.length,0);
});
test('an accepted duplicate returns original admission without restarting elapsed rest',()=>{
 const f=fixture();f.start();f.tick();const ticks=f.lanes[0].ticks;
 assert.equal(f.start().accepted,true);assert.equal(f.lanes[0].ticks,ticks);assert.equal(f.c.status().jobs.length,1);
});
test('withdrawal or changed epoch cancels attendance and never reports applied rest',()=>{
 for(const change of ['withdraw','epoch','stale']){
  const f=fixture();f.start();f.tick();if(change==='withdraw')f.setDesired({epoch:'epoch-1',jobs:[]});
  if(change==='epoch')f.setDesired({epoch:'epoch-2',jobs:[f.a]});f.tick(change!=='stale');
  assert.equal(f.c.status().receipts[0].status,'held');assert.equal(f.c.status().receipts[0].rest.release_verified,true);
  assert.equal(f.c.ownsActor(501),true);assert.equal(f.ack().acknowledged,true);
 }
});
test('unverified native release retains reservation; later release remains held',()=>{
 const f=fixture();f.start();f.lanes[0].finish=true;f.lanes[0].releaseVerified=false;f.tick();
 assert.equal(f.c.status().receipts[0].status,'held');assert.equal(f.ack().acknowledged,false);
 f.lanes[0].cancelled=true;f.lanes[0].releaseVerified=true;f.tick();
 assert.equal(f.c.status().receipts[0].status,'held');assert.equal(f.ack().acknowledged,true);
});
test('session reset discards elapsed qualification and accepts only separately identified old receipt acknowledgement',()=>{
 const f=fixture();f.setDesired({epoch:'epoch-1',jobs:[f.a]});f.start();f.tick();f.c.reset();f.setSession('native-b');f.tick();
 const receipt=f.c.status().receipts[0];assert.equal(receipt.status,'held');assert.equal(receipt.session,'native-a');
 assert.equal(f.ack().acknowledged,false);
 assert.equal(f.ack({...f.a,session:'native-b',job_session:'native-a'}).acknowledged,true);
 assert.equal(f.c.status().jobs.length,0);assert.equal(f.start().accepted,false);
});
test('startup refuses admission until old native package release is observed',()=>{
 const f=fixture();f.c.reset();f.lanes[1].ready=false;f.tick();assert.equal(f.c.status().recovering,true);
 assert.equal(f.start().accepted,false);f.lanes[1].ready=true;f.tick();assert.equal(f.start().accepted,true);
});
test('native failure cancels only the affected job while the disjoint slot advances',()=>{
 const f=fixture();f.start();f.start(f.b);f.lanes[0].throwNext=true;f.tick();f.tick();
 assert.equal(f.c.status().receipts[0].status,'held');assert.equal(f.lanes[1].ticks,2);
 assert.equal(f.c.status().jobs.find(j=>j.job_id===f.b.job_id).phase,'resting');
});

test('cold recovery retains a held release receipt for saved running work without restarting elapsed time',()=>{
 const f=fixture();f.setDesired({epoch:'epoch-1',jobs:[{...f.a,phase:'running'}]});f.tick();
 const receipt=f.c.status().receipts[0];assert.equal(receipt.status,'held');assert.equal(receipt.rest.rested_minutes,0);
 assert.equal(f.lanes[0].cancelled,true);assert.equal(f.ack().acknowledged,true);
});

test('cold old-session prepared job is released and separately acknowledged with original identity',()=>{
 const f=fixture();f.setSession('new-session');f.setDesired({epoch:'epoch-1',jobs:[{...f.a,phase:'prepared'}]});f.tick();
 assert.equal(f.c.status().receipts[0].status,'held');assert.equal(f.c.status().receipts[0].session,f.a.session);
 assert.equal(f.ack({...f.a,session:'new-session',job_session:f.a.session}).acknowledged,true);
});

test('saved actor base identity is checked at admission and throughout live attendance',()=>{
 const f=fixture(),job={...f.a,actor_base_id:801};f.setDesired({epoch:'epoch-1',jobs:[job]});f.tick();
 f.setBase(999);assert.equal(f.start(job).accepted,false);assert.equal(f.lanes[0].ticks,0);
 f.setBase(801);assert.equal(f.start(job).accepted,true);f.tick();f.setBase(999);f.tick();
 assert.equal(f.c.status().receipts[0].status,'held');assert.match(f.c.status().receipts[0].error,/identity/);
 assert.equal(f.ack({...job,actor_base_id:999}).acknowledged,false);assert.equal(f.ack(job).acknowledged,true);
});
