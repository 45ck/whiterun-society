const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const {observeNativeActivity,nativeActivityBlocker}=require('../bridge/papyrus-router.js');
const createResidentControl=vm.runInNewContext(fs.readFileSync(require.resolve('../bridge/resident-control.js'),'utf8')+';createResidentControl',{observeNativeActivity,nativeActivityBlocker});
function fixture(){
 let clock=0,current=42,scene=0,loaded=true,x=0;
 const cell={getFormID:()=>1,isInterior:()=>false};
 const destination={getFormID:()=>500,isDisabled:()=>false,getParentCell:()=>cell,getPositionX:()=>1000,getPositionY:()=>0,getPositionZ:()=>0};
 const actor={getFormID:()=>7,is3DLoaded:()=>loaded,isDead:()=>false,isChild:()=>false,
  getCurrentPackage:()=>({getFormID:()=>current}),evaluatePackage(){},getCurrentScene:()=>scene?{getFormID:()=>scene}:null,isInCombat:()=>false,getSleepState:()=>0,getParentCell:()=>cell,getPositionX:()=>x,getPositionY:()=>0,getPositionZ:()=>0};
 const list=()=>{let items=[];return {revert:()=>items=[],addForm:f=>items.push(f),getSize:()=>items.length,getAt:i=>items[i]};};
 const global=()=>{let value=0;return {getValue:()=>value,setValue:n=>value=n};};
 const slots=Array.from({length:128},(_,i)=>{let running=false;return [{isRunning:()=>running,start:()=>{running=true;return true;},stop:()=>{running=false;}},{getFormID:()=>9000+i},list(),list(),global(),global(),global(),global()];});
 const sp={Game:{getFormFromFile:(id,file)=>{assert.equal(file,'WhiterunCitizens.esp');return slots[Math.floor((id-0x800)/16)]?.[(id-0x800)%16];},getFormEx:id=>id===500?destination:actor},Quest:{from:f=>f},FormList:{from:f=>f},GlobalVariable:{from:f=>f},Actor:{from:f=>f},ObjectReference:{from:f=>f}};
 const controller=createResidentControl(()=>sp,()=>clock),control={enabled:true,assignments:{7:{actor:7,slot:0,mode:'await_decision'}}};
 const f={controller,control,forms:slots[0],slots,actor,destination,sites:[{id:500}],position:n=>x=n,package:n=>current=n,scene:n=>scene=n,loaded:n=>loaded=n,
  step(fresh=true,foreground=[],ownerWork=null){clock+=1000;controller.tick(control,loaded?[{id:7,isPerson:true}]:[],fresh,foreground,this.sites,ownerWork);},
  status:()=>controller.status().activities[0],
  bind(){slots[0][5].setValue(slots[0][4].getValue());slots[0][6].setValue(1);},
  start(){for(let i=0;i<4;i++)this.step();},
  hold(){this.start();this.bind();this.step();current=9000;this.step();}};return f;
}

test('personal destination uses its own mailbox and reports genuine arrival distance',()=>{
 const f=fixture();f.control.assignments[7]={actor:7,slot:0,mode:'go_to',target:500,goal_id:'goal'};
 f.hold();assert.equal(f.forms[3].getAt(0),f.destination);assert.equal(f.status().phase,'travelling');assert.equal(f.status().distance,1000);
 f.position(850);f.step();assert.equal(f.status().phase,'arrived');assert.equal(f.status().goal_id,'goal');
 f.control.assignments[7].mode='await_decision';f.step();assert.equal(f.forms[0].isRunning(),false);
});

test('unobserved destination fails without moving or endlessly rebinding',()=>{
 const f=fixture();f.control.assignments[7]={actor:7,slot:0,mode:'go_to',target:500,goal_id:'goal'};f.sites=[];
 f.start();assert.equal(f.status().phase,'failed');assert.equal(f.forms[0].isRunning(),false);f.step();assert.equal(f.status().phase,'failed');
});

test('foreground attendance suspends journey progress and arrival claims',()=>{
 const f=fixture();f.control.assignments[7]={actor:7,slot:0,mode:'go_to',target:500,goal_id:'goal'};f.hold();
 f.position(900);f.package(99);f.step(true,[7]);assert.equal(f.status().phase,'interaction_priority');assert.equal(f.forms[0].isRunning(),true);
 f.package(9000);f.step();assert.equal(f.status().phase,'arrived');
});

test('unreachable personal destination expires and releases its own quest',()=>{
 const f=fixture();f.control.assignments[7]={actor:7,slot:0,mode:'go_to',target:500,goal_id:'goal'};f.hold();
 for(let i=0;i<182;i++)f.step();assert.equal(f.status().phase,'failed');assert.equal(f.forms[0].isRunning(),false);
});
test('standby needs mailbox acknowledgement and observed package ownership',()=>{
 const f=fixture();f.start();f.package(9000);f.step();assert.equal(f.status().phase,'binding');
 f.bind();f.step();assert.equal(f.status().phase,'holding');assert.equal(f.status().ownedPackage,true);
 assert.equal(f.forms[2].getAt(0),f.actor);assert.equal(f.forms[3].getAt(0),f.actor);
});
test('foreground interaction temporarily supersedes continuity without stopping its quest',()=>{
 const f=fixture();f.hold();f.package(99);f.step(true,[7]);assert.equal(f.status().phase,'interaction_priority');assert.equal(f.status().ownedPackage,false);assert.equal(f.forms[0].isRunning(),true);
 f.package(9000);f.step();assert.equal(f.status().phase,'holding');
});

test('independent activity yields only its actor immediately and preserves the saved personal destination',()=>{
 const f=fixture();f.control.assignments[7]={actor:7,slot:0,mode:'go_to',target:500,goal_id:'personal-goal'};f.hold();
 const saved=JSON.stringify(f.control);f.slots[1][0].start();f.controller.yieldActors([7]);
 assert.equal(f.forms[0].isRunning(),false);assert.equal(f.slots[1][0].isRunning(),true);
 assert.equal(f.controller.status().activities.length,0);assert.equal(JSON.stringify(f.control),saved);
 f.controller.renew([{id:7,isPerson:true}],true);assert.equal(f.forms[0].isRunning(),false);
 f.start();f.bind();f.step();f.package(9000);f.step();assert.equal(f.status().goal_id,'personal-goal');assert.equal(f.status().phase,'travelling');
});
test('stale service releases only our own plugin quests',()=>{
 const f=fixture();f.hold();f.step(false);assert.equal(f.forms[0].isRunning(),false);assert.equal(f.controller.status().enabled,false);assert.equal(f.controller.status().activities.length,0);
});
test('native scene stops lease renewal and is reported rather than claimed as agent work',()=>{
 const f=fixture();f.hold();const pulse=f.forms[7].getValue();f.scene(888);f.step();assert.equal(f.status().phase,'blocked');assert.equal(f.forms[7].getValue(),pulse);
 f.forms[0].stop();f.scene(0);f.step();assert.equal(f.status().phase,'mailbox');
});
test('unloaded resident loses ownership evidence and must rebind after loading',()=>{
 const f=fixture();f.hold();f.loaded(false);f.step();assert.equal(f.status().phase,'unloaded');assert.equal(f.status().ownedPackage,null);
 f.loaded(true);f.step();assert.equal(f.status().phase,'mailbox');
});
test('mailbox tampering fails and stops our quest without retry loops',()=>{
 const f=fixture();f.hold();f.forms[3].revert();f.step();assert.equal(f.status().phase,'failed');assert.equal(f.forms[0].isRunning(),false);
 f.step();assert.equal(f.status().phase,'failed');
});

test('checkpoint-only renewal keeps a verified lease alive without rebinding changed goals',()=>{
 const f=fixture();f.hold();const serial=f.forms[4].getValue(),pulse=f.forms[7].getValue();
 f.control.assignments[7]={actor:7,slot:0,mode:'go_to',target:500,goal_id:'not-committed'};
 f.controller.renew([{id:7,isPerson:true}],true);
 assert.equal(f.forms[7].getValue(),pulse+1);assert.equal(f.forms[4].getValue(),serial);assert.equal(f.forms[3].getAt(0),f.actor);
 f.forms[3].revert();f.controller.renew([{id:7,isPerson:true}],true);assert.equal(f.forms[7].getValue(),pulse+1);
 f.controller.renew([{id:7,isPerson:true}],false);assert.equal(f.forms[0].isRunning(),false);
});
test('invalid duplicate slots release control instead of controlling the wrong actor',()=>{
 const f=fixture();f.hold();f.control.assignments[8]={actor:8,slot:0,mode:'await_decision'};f.step();assert.equal(f.forms[0].isRunning(),false);assert.match(f.controller.status().error,/Invalid/);
});
test('a competing package is reported as unacquired and never counted as standby',()=>{
 const f=fixture();f.start();f.bind();f.step();for(let i=0;i<17;i++)f.step();assert.equal(f.status().phase,'package_not_acquired');assert.equal(f.status().ownedPackage,false);
});
test('recovery clears saved leases before accepting fresh standing assignments',()=>{
 const f=fixture();f.hold();f.controller.reset();f.step();assert.equal(f.forms[0].isRunning(),false);assert.equal(f.controller.status().activities.length,0);
});


test('owner work rebinds a travelling continuity slot to self and restores its saved journey',()=>{
 const f=fixture();f.control.assignments[7]={actor:7,slot:0,mode:'go_to',target:500,goal_id:'goal'};f.hold();
 const oldSerial=f.forms[4].getValue(),saved=JSON.stringify(f.control),work={id:'bake',actor:7,intent:'owner_production',phase:'ready_to_self_work'};
 f.step(true,[7],work);assert.equal(f.forms[0].isRunning(),false);assert.equal(f.status().ownedPackage,false);
 assert.equal(f.status().work_hold_id,'owner-work-bake');assert.equal(f.status().suspended_goal_id,'goal');
 for(let i=0;i<2;i++)f.step(true,[7],work);f.bind();f.step(true,[7],work);
 assert.equal(f.status().phase,'work_holding');assert.equal(f.forms[3].getAt(0),f.actor);assert.ok(f.forms[4].getValue()>oldSerial);
 assert.equal(JSON.stringify(f.control),saved);assert.equal(f.status().mode,'await_decision');
 work.phase='working';f.step(true,[7],work);assert.equal(f.status().phase,'work_holding');
 work.phase='complete';f.step(true,[],work);assert.equal(f.forms[0].isRunning(),false);assert.equal(f.status().goal_id,'goal');
 for(let i=0;i<2;i++)f.step();f.bind();f.step();assert.equal(f.status().phase,'travelling');assert.equal(f.forms[3].getAt(0),f.destination);
});

test('held owner intent releases its override without cancelling the saved goal',()=>{
 const f=fixture();f.hold();const work={id:'held-work',actor:7,intent:'owner_production',phase:'ready_to_self_work'};
 f.step(true,[7],work);assert.equal(f.status().work_hold_id,'owner-work-held-work');
 work.phase='held';f.step(true,[],work);assert.equal(f.status().work_hold_id,null);assert.equal(f.forms[0].isRunning(),false);
});
