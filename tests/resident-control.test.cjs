const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const {observeNativeActivity,nativeActivityBlocker}=require('../bridge/papyrus-router.js');
const createResidentControl=vm.runInNewContext(fs.readFileSync(require.resolve('../bridge/resident-control.js'),'utf8')+';createResidentControl',{observeNativeActivity,nativeActivityBlocker});
function fixture(){
 let clock=0,current=42,scene=0,loaded=true;
 const actor={getFormID:()=>7,is3DLoaded:()=>loaded,isDead:()=>false,isChild:()=>false,
  getCurrentPackage:()=>({getFormID:()=>current}),evaluatePackage(){},getCurrentScene:()=>scene?{getFormID:()=>scene}:null,isInCombat:()=>false,getSleepState:()=>0};
 const list=()=>{let items=[];return {revert:()=>items=[],addForm:f=>items.push(f),getSize:()=>items.length,getAt:i=>items[i]};};
 const global=()=>{let value=0;return {getValue:()=>value,setValue:n=>value=n};};
 const slots=Array.from({length:128},(_,i)=>{let running=false;return [{isRunning:()=>running,start:()=>{running=true;return true;},stop:()=>{running=false;}},{getFormID:()=>9000+i},list(),list(),global(),global(),global(),global()];});
 const sp={Game:{getFormFromFile:(id,file)=>{assert.equal(file,'WhiterunCitizens.esp');return slots[Math.floor((id-0x800)/16)]?.[(id-0x800)%16];},getFormEx:()=>actor},Quest:{from:f=>f},FormList:{from:f=>f},GlobalVariable:{from:f=>f},Actor:{from:f=>f}};
 const controller=createResidentControl(()=>sp,()=>clock),control={enabled:true,assignments:{7:{actor:7,slot:0,mode:'await_decision'}}};
 const f={controller,control,forms:slots[0],slots,actor,package:n=>current=n,scene:n=>scene=n,loaded:n=>loaded=n,
  step(fresh=true,foreground=[]){clock+=1000;controller.tick(control,loaded?[{id:7,isPerson:true}]:[],fresh,foreground);},
  status:()=>controller.status().activities[0],
  bind(){slots[0][5].setValue(slots[0][4].getValue());slots[0][6].setValue(1);},
  start(){for(let i=0;i<4;i++)this.step();},
  hold(){this.start();this.bind();this.step();current=9000;this.step();}};return f;
}
test('standby needs mailbox acknowledgement and observed package ownership',()=>{
 const f=fixture();f.start();f.package(9000);f.step();assert.equal(f.status().phase,'binding');
 f.bind();f.step();assert.equal(f.status().phase,'holding');assert.equal(f.status().ownedPackage,true);
 assert.equal(f.forms[2].getAt(0),f.actor);assert.equal(f.forms[3].getAt(0),f.actor);
});
test('foreground interaction temporarily supersedes continuity without stopping its quest',()=>{
 const f=fixture();f.hold();f.package(99);f.step(true,[7]);assert.equal(f.status().phase,'interaction_priority');assert.equal(f.status().ownedPackage,false);assert.equal(f.forms[0].isRunning(),true);
 f.package(9000);f.step();assert.equal(f.status().phase,'holding');
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
test('invalid duplicate slots release control instead of controlling the wrong actor',()=>{
 const f=fixture();f.hold();f.control.assignments[8]={actor:8,slot:0,mode:'await_decision'};f.step();assert.equal(f.forms[0].isRunning(),false);assert.match(f.controller.status().error,/Invalid/);
});
test('a competing package is reported as unacquired and never counted as standby',()=>{
 const f=fixture();f.start();f.bind();f.step();for(let i=0;i<17;i++)f.step();assert.equal(f.status().phase,'package_not_acquired');assert.equal(f.status().ownedPackage,false);
});
test('recovery clears saved leases before accepting fresh standing assignments',()=>{
 const f=fixture();f.hold();f.controller.reset();f.step();assert.equal(f.forms[0].isRunning(),false);assert.equal(f.controller.status().activities.length,0);
});
