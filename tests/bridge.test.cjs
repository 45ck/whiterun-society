const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const catalogManifest=require('../config/economy-catalog.json');
const source = fs.readFileSync(path.join(__dirname,'../bridge/whiterun-society.js'),'utf8')
  .replace('__ECONOMY_CATALOG_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/economy-catalog.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__ECONOMY_CATALOG_MANIFEST__',JSON.stringify(catalogManifest))
  .replace('__RESIDENT_CONTROL_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/resident-control.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__SCENE_HANDOFF_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/scene-handoffs.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__CONVERSATION_ATTENDANCE_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/conversation-attendance.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__OBSERVER_CAMERA_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/observer-camera.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__MARKET_POLICY_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/market-policy.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__MARKET_POLICY__',JSON.stringify(require('../config/market-policy.json')))
  .replace('__TRANSFER_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/inventory-transfers.js'),'utf8').split('\nif (typeof module')[0])
  .replace('__RESOURCE_MANIFEST_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/resource-manifest.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__RESOURCE_MANIFEST__',JSON.stringify(require('../config/resource-manifest.json')))
  .replace('__ENDOWMENT_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/endowments.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__PRODUCTION_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/production.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__MOVEMENT_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/movement.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__PAPYRUS_ROUTER_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/papyrus-router.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__PLACE_FACTORY__','const WHITERUN_VENUE_CATALOG='+JSON.stringify(require('../config/places.json'))+';\n'+fs.readFileSync(path.join(__dirname,'../bridge/places.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__PARALLEL_ROUTINES_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/parallel-routines.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__REST_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/rest.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__ACTIVITY_JOBS_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/activity-jobs.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__OWNER_WORK_JOBS_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/owner-work-jobs.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__PAID_EMPLOYMENT_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/paid-employment.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__ROUTINE_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/agent-routines.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__SPEECH_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/speech.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__BRIDGE_CONFIG__',JSON.stringify({port:17841,token:'test-only'}));

function harness(nativeGlobal=false,activityRestFactory=null,residentFactory=null,endowmentFactory=null,transferFactory=null,paidFactory=null) {
  const handlers = new Map(), notifications=[], requests=[], looks=[], nativeReads=[];
  let respond=()=>null,clock=10000,presentation=null;
  const actor={getFormID:()=>123,getDisplayName:()=> 'Test NPC',is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,
    getPositionX:()=>1,getPositionY:()=>2,getPositionZ:()=>3,setLookAt:(...args)=>looks.push(args)};
  const cell={getName:()=> 'Test cell',getFormID:()=>107135,getNumRefs:filter=>{assert.equal(filter,43);return 1;},getNthRef:()=>actor};
  const player={getFormID:()=>20,getParentCell:()=>cell,is3DLoaded:()=>true,setGhost:()=>{},getPositionX:()=>0,getPositionY:()=>0,getPositionZ:()=>0};
  const itemForms=Object.fromEntries(catalogManifest.commodities.map(item=>[item.native.local_form_id,{getFormID:()=>item.native.local_form_id,getType:()=>({MISC:32,ALCH:46,INGR:30})[item.native.record_type]}]));
  const sp={storage:{},on:(event,fn)=>{handlers.set(event,fn);return event;},once:(event,fn)=>{handlers.set(event,fn);return event;},
    unsubscribe:key=>handlers.delete(key), Actor:{from:value=>value},Game:{getPlayer:()=>player,getFormEx:id=>{nativeReads.push(id);return id===123?actor:itemForms[id]||null;}},
    enableFreeCamera:()=>{},setFreeCameraPosition:()=>{},
    Debug:{notification:text=>notifications.push(text)},getPlatformVersion:()=> 'mock',printConsole:()=>{},writeLogs:()=>{},
    HttpClient:class { post(route,options) { const body=JSON.parse(options.body);requests.push(body);return Promise.resolve({status:200,body:JSON.stringify({command:respond(body),presentation})}); } }};
  sp.Game.getFormFromFile=(id,file)=>{nativeReads.push([id,file]);return file==='Skyrim.esm'?itemForms[id]||null:null;};
  let compiled=activityRestFactory?source.replace('const activityJobs=createActivityJobsController(()=>sp);','const activityJobs=createActivityJobsController(()=>sp,Date.now,undefined,{restFactory:activityRestFactory});'):source;
  if(residentFactory)compiled=compiled.replace('const residentControl=createResidentControl(()=>sp);','const residentControl=residentFactory();');
  if(endowmentFactory)compiled=compiled.replace(/const endowments=createEndowmentController\([^;]+;/,'const endowments=endowmentFactory(()=>session);');
  if(transferFactory)compiled=compiled.replace(/const transfers=createInventoryTransfers\([^;]+;/,'const transfers=transferFactory(()=>session);');
  if(paidFactory)compiled=compiled.replace(/const paidEmployment=createPaidEmploymentController\([^;]+;/,'const paidEmployment=paidFactory();');
  const context=vm.createContext({...nativeGlobal?{skyrimPlatform:sp}:{require:()=>sp},Date:{now:()=>clock},activityRestFactory,residentFactory,endowmentFactory,transferFactory,paidFactory});
  vm.runInContext(compiled,context);
  return {handlers,notifications,requests,looks,nativeReads,player,actor,sp,cell,advance:(ms=2100)=>{clock+=ms;},setResponse:fn=>{respond=fn;},setPresentation:value=>{presentation=value;},reload:()=>vm.runInContext(compiled,context)};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function checkpointFixture(h){
 const original=h.sp.Game.getFormFromFile,marker={getValue:()=>0};h.sp.GlobalVariable={from:value=>value};
 h.sp.Game.getFormFromFile=(id,file)=>file==='WhiterunSociety.esp'&&id===0x800?marker:original(id,file);
}

test('held paid worker cannot restore a saved journey while both accounts stay reserved',async()=>{
 for(const origin of ['native','saved','partial_ack']){
  const ticks=[],yielded=[],job={worker:123,employer:124,phase:'held',effects_issued:true,release_verified:false};
  if(origin==='partial_ack')job.receipt_acknowledged=true;
  const control=()=>({reset(){},yieldActors(ids){yielded.push([...ids]);},status:()=>({}),renew(){},
   tick(saved,_residents,_fresh,actors){ticks.push({saved:structuredClone(saved),actors:[...actors]});}});
  const paid=()=>({reset(){},tick(){},holds:()=>[],releasingActors:()=>[],
   reservedActors:()=>origin==='native'?[123,124]:[],status:()=>({jobs:origin==='native'?[job]:[]})});
  const h=harness(false,null,control,null,null,paid);checkpointFixture(h);
  const assignments={'0':{actor:123,mode:'go_to',target:900},'1':{actor:124,mode:'await_decision'}};
  h.setPresentation({society:{checkpoint:0,paid_employment:{jobs:origin!=='native'?[job]:[]},town:{resident_control:{assignments}}}});
  for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
  assert.ok(yielded.some(ids=>ids.includes(123)),origin+' worker must yield the stale hold');
  assert.equal(ticks.at(-1).saved.assignments['0'],undefined,origin+' worker must not rebind its saved journey');
  assert.equal(ticks.at(-1).saved.assignments['1'].actor,124,'Employer keeps its separate stationary assignment');
  assert.ok([123,124].every(id=>ticks.at(-1).actors.includes(id)),'Both account activity exclusions remain');
  assert.equal(assignments['0'].target,900,'Saved goal history is not rewritten');
 }
});

test('prepared paid admission retains the worker continuity slot before a native hold exists',async()=>{
 const ticks=[],yielded=[];
 const control=()=>({reset(){},yieldActors(ids){yielded.push([...ids]);},status:()=>({}),renew(){},tick(saved){ticks.push(structuredClone(saved));}});
 const paid=()=>({reset(){},tick(){},holds:()=>[],releasingActors:()=>[],reservedActors:()=>[],status:()=>({jobs:[]})});
 const h=harness(false,null,control,null,null,paid);checkpointFixture(h);
 h.setPresentation({society:{checkpoint:0,paid_employment:{jobs:[{worker:123,employer:124,phase:'prepared'}]},
  town:{resident_control:{assignments:{'0':{actor:123,slot:0,mode:'go_to',target:900}}}}}});
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.equal(ticks.at(-1).assignments['0'].slot,0);
 assert.equal(yielded.some(ids=>ids.includes(123)),false);
});

test('held conversation cleanup keeps every possible participant out of standing tasks',async()=>{
 const blocked=[];const control=()=>({reset(){},yieldActors(){},status:()=>({}),renew(){},tick(_saved,_residents,_fresh,actors){blocked.push(Array.from(actors));}});
 const h=harness(false,null,control);
 checkpointFixture(h);
 h.setPresentation({society:{checkpoint:0,conversation:{phase:'held',release_required:true,cleanup_review_required:true,
  meeting_route:{actor:123,target:124},initiator:125,partner:126,speakers:[127,128],scenario:{participants:[129,130]}}}});
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.deepEqual(blocked.at(-1).sort((a,b)=>a-b),[123,124,125,126,127,128,129,130]);
});

test('unknown held cleanup identity blocks managed and observed actors even with malformed speakers',async()=>{
 const blocked=[];const control=()=>({reset(){},yieldActors(){},status:()=>({}),renew(){},tick(_saved,_residents,_fresh,actors){blocked.push(Array.from(actors));}});
 const h=harness(false,null,control);
 checkpointFixture(h);
 h.setPresentation({society:{checkpoint:0,conversation:{phase:'held',cleanup_review_required:true,speakers:{}},
  town:{residents:{'125':{}},resident_control:{assignments:{'0':{actor:124}}}}}});
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.deepEqual(blocked.at(-1).sort((a,b)=>a-b),[123,124,125]);
});

test('quarantined conversation rejects a new background journey before acquiring its package',async()=>{
 const h=harness();h.setPresentation({society:{checkpoint:0,conversation:{phase:'held',release_required:true,speakers:[123,124]}}});
 h.setResponse(body=>({id:'blocked-background',kind:'background_routines',session:body.session,origin_session:body.session,
  checkpoint:0,members:[{actor:123,target:124}]}));
 for(let i=0;i<4;i++){h.handlers.get('update')();await settle();h.advance();}
 const receipt=h.requests.find(row=>row.ack?.id==='blocked-background')?.ack;
 assert.equal(receipt?.status,'failed');assert.match(receipt.error,/Unverified conversation cleanup/);
});

test('partial cleanup identities reserve all managed actors while retaining unobserved hints',async()=>{
 for(const identity of [{speakers:[900]}, {initiator:900,meeting_route:{target:901}},
                       {speakers:[900,901],scenario:{}}, {speakers:{},meeting_route:{actor:900,target:901}}]){
  const blocked=[];const control=()=>({reset(){},yieldActors(){},status:()=>({}),renew(){},tick(_saved,_residents,_fresh,actors){blocked.push(Array.from(actors));}});
  const h=harness(false,null,control);checkpointFixture(h);
  h.setPresentation({society:{checkpoint:0,conversation:{phase:'held',release_required:true,...identity},town:{residents:{'124':{}}}}});
  for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
  assert.deepEqual(blocked.at(-1).sort((a,b)=>a-b),identity.speakers?.length===1?[123,124,900]:[123,124,900,901]);
 }
});

test('accepted background rest jobs tick while a disjoint native meal uses the foreground command channel',async()=>{
 const lanes=[];
 const factory=()=>{let state=null;const lane={ticks:0,available:()=>true,released:()=>true,release(){},reset(){state=null;},cancel(){},status:()=>state,
  step(command){lane.ticks++;state={actor:command.actor,target:command.target,phase:'resting',rested_minutes:lane.ticks/2};return {done:false};}};lanes.push(lane);return lane;};
 const h=harness(false,factory);let bread=1,equipCalls=0,queue=null;
 const food={getFormID:()=>0x65c97,getType:()=>46},gold={getFormID:()=>0xf,getType:()=>32},grain={getFormID:()=>0x4b0ba,getType:()=>30};
 const eater={getFormID:()=>200,is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,
  getItemCount:form=>form===food?bread:10,equipItem:()=>{equipCalls++;bread=0;}};
 h.sp.Game.getFormEx=id=>id===123?h.actor:id===200?eater:id===0x65c97?food:id===0xf?gold:id===0x4b0ba?grain:null;
 const checkpoint={getValue:()=>1};h.sp.GlobalVariable={from:f=>f};
 h.sp.Game.getFormFromFile=(id,file)=>file==='WhiterunSociety.esp'&&id===0x800?checkpoint:file==='Skyrim.esm'?({[0x65c97]:food,[0xf]:gold,[0x4b0ba]:grain})[id]||null:null;
 h.setResponse(body=>{
  if(!queue){
   const jobs=[{job_id:'parallel-a',actor:123,target:586075,slot:0,session:body.session,epoch:'epoch',rest_minutes:30},
               {job_id:'parallel-b',actor:124,target:586076,slot:1,session:body.session,epoch:'epoch',rest_minutes:30}];
   h.setPresentation({society:{checkpoint:1,activity_jobs:{epoch:'epoch',jobs}}});
   queue=jobs.map(job=>({...job,id:'start-'+job.job_id,kind:'activity_start_rest',checkpoint:1}));
   queue.push({id:'disjoint-meal',kind:'inventory_consume',actor:200,session:body.session,checkpoint:1,catalog_hash:body.economy_catalog.catalog_hash,before:{bread:1,gold:10,grain:10},after:{bread:0,gold:10,grain:10}});
  }
  if(body.ack?.id===queue[0]?.id)queue.shift();
  return queue[0]||null;
 });
 for(let i=0;i<8;i++){h.handlers.get('update')();await settle();h.advance();}
 const observations=h.requests,meal=observations.find(r=>r.ack?.id==='disjoint-meal'&&r.ack.status==='applied');
 assert.ok(meal,JSON.stringify(observations.map(r=>r.ack)));assert.equal(equipCalls,1);assert.equal(bread,0);
 assert.equal(meal.activity_jobs.jobs.length,2);assert.ok(meal.activity_jobs.jobs.every(j=>j.phase==='resting'));
 assert.ok(lanes.every(l=>l.ticks>2));assert.equal(meal.activity_jobs.receipts.length,0);
});

test('a repeated completed command redelivers its original acknowledgement without repeating its effect',async()=>{
 const h=harness();let next='first';
 h.setResponse(body=>({id:next,kind:'notify',session:body.session}));
 h.handlers.get('update')();await settle();
 h.advance();h.handlers.get('update')();await settle();
 const original=JSON.parse(JSON.stringify(h.requests.at(-1).ack));assert.equal(original.id,'first');
 next='second';h.advance();h.handlers.get('update')();await settle();
 h.advance();h.handlers.get('update')();await settle();assert.equal(h.requests.at(-1).ack.id,'second');
 next='first';h.advance();h.handlers.get('update')();await settle();
 h.advance();h.handlers.get('update')();await settle();
 assert.deepEqual(JSON.parse(JSON.stringify(h.requests.at(-1).ack)),original);
 assert.equal(h.notifications.filter(x=>x.includes('command received')).length,2);
});

test('native activity reports actual scene identity and unknown API availability',async()=>{
  const h=harness();h.actor.getCurrentScene=()=>({getFormID:()=>888});
  h.actor.isInCombat=()=>false;h.actor.getSleepState=()=>0;
  h.handlers.get('update')();await settle();
  assert.deepEqual(JSON.parse(JSON.stringify(h.requests[0].residents[0].activity)),
    {scene_id:888,in_combat:false,sleep_state:0,package_id:null});
  h.actor.getCurrentScene=undefined;h.advance();h.handlers.get('update')();await settle();
  assert.equal(h.requests.at(-1).residents[0].activity.scene_id,null);
});

test('heartbeat is built from observed game state',async()=>{
  const h=harness();h.handlers.get('update')();await settle();
  assert.equal(h.requests[0].player.cell,'Test cell');
  assert.equal(h.requests[0].ready,true);
  assert.equal(h.requests[0].residents[0].id,123);
  assert.equal(h.requests[0].selected.id,123);
  assert.equal(h.requests[0].economy_catalog.available,true);
  assert.equal(h.requests[0].economy_catalog.type_verified,true);
  assert.deepEqual(h.requests[0].residents[0].inventory,{bread:null,gold:null,grain:null});
});

test('unresolved catalog form stays unavailable rather than reporting an empty inventory',async()=>{
  const h=harness();h.actor.getItemCount=()=>9;
  const resolve=h.sp.Game.getFormFromFile;
  h.sp.Game.getFormFromFile=(id,file)=>id===0x4b0ba?null:resolve(id,file);
  h.handlers.get('update')();await settle();
  assert.equal(h.requests[0].economy_catalog.available,false);
  assert.deepEqual(h.requests[0].residents[0].inventory,{bread:9,gold:9,grain:null});
});

test('experimental perception follows observed residents without a fixed cast or knowledge grant',async()=>{
  const h=harness();h.actor.hasKeyword=()=>true;h.actor.hasLOS=()=>true;h.actor.getAngleZ=()=>0;
  h.sp.Keyword={from:()=>({})};
  h.handlers.get('update')();await settle();
  assert.deepEqual(Object.keys(h.requests[0].perception),['123']);
  assert.equal(h.requests[0].perception['123'].available,false);
  assert.deepEqual(h.requests[0].perception['123'].visible,[]);
  h.actor.is3DLoaded=()=>false;h.advance();h.handlers.get('update')();await settle();
  assert.deepEqual(h.requests.at(-1).perception,{});
});

test('social coordinates include native cell and world identity',async()=>{
  const h=harness();h.cell.isInterior=()=>false;h.actor.getParentCell=()=>h.cell;
  h.actor.getWorldSpace=()=>({getFormID:()=>77});
  h.handlers.get('update')();await settle();
  assert.deepEqual(JSON.parse(JSON.stringify(h.requests[0].residents[0].space)),{cell:107135,interior:false,world:77});
  h.actor.getParentCell=()=>null;h.advance();h.handlers.get('update')();await settle();
  assert.equal(h.requests.at(-1).residents[0].space,null);
});

test('accounting observations do not turn an unloaded actor into a visible resident',async()=>{
  const h=harness();
  h.actor.hasKeyword=()=>true;h.actor.getItemCount=()=>2;
  h.sp.Keyword={from:x=>x};
  const unseen={...h.actor,getFormID:()=>124,is3DLoaded:()=>false,getItemCount:()=>7};
  h.sp.Actor.from=value=>value===h.actor||value===unseen?value:null;
  h.sp.Game.getFormEx=id=>id===123?h.actor:id===124?unseen:{getFormID:()=>id};
  const original=h.requests;
  h.setPresentation({society:{checkpoint:0,town:{residents:{'124':{id:124}}}}});
  h.handlers.get('update')();await settle();h.advance();h.handlers.get('update')();await settle();
  const observation=original.at(-1);
  assert.equal(observation.residents.some(a=>a.id===124),false);
  assert.deepEqual(JSON.parse(JSON.stringify(observation.inventory_observations)),[{id:124,isPerson:true,loaded:false,baseId:null,inventory:{gold:7,bread:7,grain:7}}]);
});
test('commands are applied on update, never in HTTP callback',async()=>{
  const h=harness();h.handlers.get('activate')({caster:h.player,target:h.actor});
  h.setResponse(body=>({id:'a',kind:'look_at_player',session:body.session}));
  h.handlers.get('update')();await settle();assert.equal(h.looks.length,0);
  h.handlers.get('update')();assert.equal(h.looks.length,1);
  h.handlers.get('update')();assert.equal(h.looks.length,1);
});
test('a load discards pending commands from the previous session',async()=>{
  const h=harness();h.setResponse(body=>({id:'a',kind:'notify',session:body.session}));
  h.handlers.get('update')();await settle();h.handlers.get('preLoadGame')();
  h.handlers.get('update')();
  assert.ok(h.notifications.every(message=>!message.includes('command received')));
});

test('native global and same-context hot reload work without require',()=>{
  const h=harness(true);h.reload();h.handlers.get('update')();assert.equal(h.requests.length,1);
});

test('loading without a player model or cell cannot announce readiness',()=>{
  const h=harness();h.player.is3DLoaded=()=>false;h.handlers.get('update')();
  h.player.is3DLoaded=()=>true;h.player.getParentCell=()=>null;h.handlers.get('update')();
  assert.equal(h.requests.length,0);assert.equal(h.notifications.length,0);
});

test('empty town reports waiting instead of observer ready',()=>{
  const h=harness();h.cell.getNumRefs=()=>0;h.handlers.get('update')();
  assert.equal(h.requests[0].ready,false);assert.equal(h.requests[0].selected,null);
});
test('hot reload unsubscribes the previous controller',()=>{
  const h=harness();const old=h.handlers.get('update');
  h.reload();assert.notEqual(h.handlers.get('update'),old);assert.equal(h.handlers.size,8);
});

test('loaded IDs discover actors beyond the player cell',()=>{
  const h=harness();h.cell.getNumRefs=()=>0;
  h.sp.getLoadedActorIds=()=>[123];h.handlers.get('update')();
  assert.equal(h.requests[0].selected.id,123);
});

test('cold startup rebuilds the native class table after the cell loads',()=>{
  const h=harness();const resolve=h.sp.Game.getFormEx;delete h.sp.Game.getFormEx;
  h.sp.addNativeExports=()=>{h.sp.Game.getFormEx=resolve;return h.sp;};
  h.handlers.get('update')();assert.equal(h.requests.length,0);
  h.handlers.get('tick')();h.handlers.get('update')();assert.equal(h.requests[0].ready,true);
});

test('a command resolves a new native handle on its application frame',async()=>{
  const h=harness();let frame=0;
  const fresh=()=>{const born=frame;return new Proxy(h.actor,{get(target,key){
    const value=target[key];return typeof value==='function'? (...args)=>{assert.equal(frame,born,'expired native handle');return value(...args);}:value;
  }});};
  h.cell.getNthRef=fresh;h.sp.Game.getFormEx=fresh;
  h.setResponse(body=>({id:'pooled',kind:'look_at_player',session:body.session}));
  h.handlers.get('update')();await settle();frame++;
  h.handlers.get('update')();assert.equal(h.looks.length,1);
});

test('camera messages use managed loaded residents and resolve on the update',async()=>{
  const h=harness();const positions=[],rotations=[];
  h.sp.setFreeCameraPosition=p=>positions.push(p);h.sp.setFreeCameraRotation=r=>rotations.push(r);
  h.actor.getAngleZ=()=>0;h.actor.hasKeyword=()=>true;h.sp.Keyword={from:x=>x};
  h.sp.Game.getFormEx=id=>id===123?h.actor:id===0x13794?{}:null;
  h.setPresentation({society:{town:{residents:{'123':{}}}}});
  h.handlers.get('update')();await settle();positions.length=0;
  h.handlers.get('browserMessage')({arguments:[{type:'society-camera',mode:'focus',id:123,yaw:0,distance:200,elevation:100}]});
  assert.equal(positions.length,0);
  h.handlers.get('update')();assert.deepEqual(Array.from(positions[0]),[1,202,183]);
  h.handlers.get('browserMessage')({arguments:[{type:'society-camera',mode:'focus',id:999}]});
  h.handlers.get('update')();assert.deepEqual(Array.from(positions[1]),[1,202,183]);
  h.handlers.get('browserMessage')({arguments:[{type:'society-camera',mode:'market',automatic:true}]});
  h.handlers.get('update')();assert.deepEqual(Array.from(positions[2]),[1,202,183]);
  h.handlers.get('browserMessage')({arguments:[{type:'society-camera-release'}]});
  h.handlers.get('update')();assert.notDeepEqual(Array.from(positions[3]),[1,202,183]);
  assert.ok(rotations.flat().every(Number.isFinite));
});

test('movie view holds an ended shot and manual RTS overrides automatic following',async()=>{
 const h=harness(),positions=[];
 h.sp.setFreeCameraPosition=p=>positions.push(Array.from(p));h.sp.setFreeCameraRotation=()=>{};
 h.actor.getAngleZ=()=>0;h.actor.hasKeyword=()=>true;h.sp.Keyword={from:x=>x};
 h.sp.Game.getFormEx=id=>id===123?h.actor:id===0x13794?{}:null;
 const present=phase=>({society:{town:{residents:{'123':{}}},plan:{phase,actor:123}}});
 h.setPresentation(present('travelling'));h.handlers.get('update')();await settle();
 h.handlers.get('browserMessage')({arguments:[{type:'society-camera',mode:'story'}]});
 h.handlers.get('update')();assert.deepEqual(positions.at(-1),[1,182,613]);
 h.setPresentation(present('complete'));h.advance();h.handlers.get('update')();await settle();
 h.actor.getPositionX=()=>900;h.handlers.get('update')();assert.deepEqual(positions.at(-1),[1,182,613]);
 h.handlers.get('browserMessage')({arguments:[{type:'society-camera',mode:'free',panX:24000,panY:-7000,yaw:0,distance:1000,elevation:900}]});
 h.handlers.get('update')();assert.deepEqual(positions.at(-1),[24000,-6000,-2420]);
 h.setPresentation(present('travelling'));h.advance();h.handlers.get('update')();await settle();h.handlers.get('update')();
 assert.deepEqual(positions.at(-1),[24000,-6000,-2420]);
});

test('checkpoint binding compares the actual marker before writing',async()=>{
  const h=harness();let marker=3,writes=0;
  h.sp.Game.getFormFromFile=()=>({});
  h.sp.GlobalVariable={from:()=>({getValue:()=>marker,setValue:v=>{writes++;marker=v;}})};
  h.setResponse(body=>({id:'checkpoint-4',kind:'bind_checkpoint',session:body.session,expected:3,next:4}));
  h.handlers.get('update')();await settle();assert.equal(writes,0);
  marker=2;h.handlers.get('update')();assert.equal(writes,0);assert.equal(marker,2);
});

test('loading blocks native observations until load completion',()=>{
  const h=harness();h.handlers.get('preLoadGame')();h.handlers.get('update')();
  assert.equal(h.requests.length,0);
  h.handlers.get('postLoadGame')();h.handlers.get('update')();assert.equal(h.requests.length,1);
});

test('release acknowledgements wait for the owned package to actually disappear',async()=>{
 const h=harness();let current={getFormID:()=>99};
 h.sp.Game.getFormFromFile=()=>({getFormID:()=>99});
 h.sp.GlobalVariable={from:()=>({getValue:()=>3})};
 h.sp.Quest={from:()=>({isRunning:()=>false})};
 h.actor.getCurrentPackage=()=>current;
 h.setResponse(body=>({id:'release-one',kind:'release_routine',actor:123,checkpoint:3,session:body.session}));
 h.handlers.get('update')();await settle();h.handlers.get('update')();
 h.advance();h.handlers.get('update')();await settle();
 assert.equal(h.requests.at(-1).ack,null);
 current=null;h.advance();h.handlers.get('update')();await settle();
 assert.equal(h.requests.at(-1).ack.status,'applied');
 assert.equal(h.requests.at(-1).ack.released,true);
});

test('consent and thinking retain active cadence while idle towns stay quiet',async()=>{
 for(const phase of ['choose','consent','reconsider','thinking','economic_speaking']){
  const h=harness();h.setPresentation({society:{plan:{phase}}});
  h.handlers.get('update')();await settle();h.advance(349);h.handlers.get('update')();assert.equal(h.requests.length,1);
  h.advance(1);h.handlers.get('update')();await settle();assert.equal(h.requests.length,2,phase);
  assert.equal(h.requests[1].transport.cadence_ms,350);
 }
 const idle=harness();idle.setPresentation({society:{plan:{phase:'complete'}}});
 idle.handlers.get('update')();await settle();idle.advance(350);idle.handlers.get('update')();assert.equal(idle.requests.length,1);
 idle.advance(1650);idle.handlers.get('update')();assert.equal(idle.requests.length,2);
});

test('checkpoint acknowledgement is expedited once without replay or idle flooding',async()=>{
 const h=harness();let marker=3,writes=0;
 h.sp.Game.getFormFromFile=()=>({});
 h.sp.GlobalVariable={from:()=>({getValue:()=>marker,setValue:v=>{writes++;marker=v;}})};
 h.setResponse(body=>body.ack?null:{id:'checkpoint-4',kind:'bind_checkpoint',session:body.session,expected:3,next:4});
 h.handlers.get('update')();await settle();h.advance(20);h.handlers.get('update')();
 assert.equal(writes,1);assert.equal(h.requests.length,1);
 h.advance(80);h.handlers.get('update')();h.handlers.get('update')();assert.equal(h.requests.length,2);
 await settle();assert.equal(h.requests[1].ack.status,'applied');assert.equal(h.requests[1].transport.cadence_ms,100);
 assert.equal(h.requests[1].transport.previous_request_interval_ms,100);
 h.advance(100);h.handlers.get('update')();assert.equal(h.requests.length,2);assert.equal(writes,1);
});

test('checkpoint progress polls quickly even before a native acknowledgement exists',async()=>{
 const h=harness();h.setPresentation({society:{transition:{next:4},error:null}});
 h.handlers.get('update')();await settle();h.advance(100);h.handlers.get('update')();await settle();
 assert.equal(h.requests.length,2);assert.equal(h.requests[1].transport.cadence_ms,100);
});

test('RTS initialization disables player actions and tolerates unavailable control telemetry',async()=>{
 const h=harness(),calls=[];h.sp.Game.disablePlayerControls=(...args)=>calls.push(args);
 h.sp.Game.isMovementControlsEnabled=()=>false;h.sp.Game.isFightingControlsEnabled=()=>{throw Error('unavailable');};
 h.handlers.get('update')();await settle();
 assert.deepEqual(calls,[[true,true,true,true,true,false,true,true,0]]);
 assert.equal(h.requests[0].player_controls.movement,false);assert.equal(h.requests[0].player_controls.fighting,null);
 h.advance();h.handlers.get('update')();await settle();assert.equal(calls.length,1);
});

test('in-game play request is carried to service and discarded on game load',async()=>{
 const h=harness();h.handlers.get('browserMessage')({arguments:[{type:'society-director',action:'play'}]});
 h.handlers.get('update')();await settle();assert.equal(h.requests[0].director_control.action,'play');
 h.handlers.get('preLoadGame')();h.handlers.get('postLoadGame')();h.advance();h.handlers.get('update')();await settle();assert.equal(h.requests.at(-1).director_control,null);
});

test('browser focus is applied after page readiness across update frames, once per load',async()=>{
  const h=harness(),focus=[];
  h.sp.setTextsVisibility=()=>{};
  h.sp.browser={loadUrl:()=>{},setVisible:()=>{},setFocused:value=>focus.push(value),executeJavaScript:()=>{}};
  h.handlers.get('update')();await settle();assert.deepEqual(focus,[true]);
  h.handlers.get('browserMessage')({arguments:[{type:'society-ui-health',rts:true}]});
  assert.deepEqual(focus,[true]);
  h.handlers.get('update')();assert.deepEqual(focus,[true,false]);
  h.handlers.get('update')();assert.deepEqual(focus,[true,false,true]);
  h.handlers.get('update')();assert.deepEqual(focus,[true,false,true]);
  h.handlers.get('preLoadGame')();h.handlers.get('postLoadGame')();
  h.handlers.get('update')();assert.deepEqual(focus,[true,false,true,true]);
  h.handlers.get('browserMessage')({arguments:[{type:'society-ui-health',rts:true}]});
  h.handlers.get('update')();h.handlers.get('update')();
  assert.deepEqual(focus,[true,false,true,true,false,true]);
  h.handlers.get('buttonEvent')({code:66,isDown:true});
  h.handlers.get('browserMessage')({arguments:[{type:'society-ui-health',rts:true}]});
  h.handlers.get('update')();h.handlers.get('update')();
  assert.equal(focus.at(-1),false,'heartbeat must not steal focus after F8 releases it');
  assert.equal(focus.length,7);
});

test('focused browser release survives heartbeat and native F8 can restore focus',async()=>{
 const h=harness(),focus=[];
 h.sp.setTextsVisibility=()=>{};
 h.sp.browser={loadUrl:()=>{},setVisible:()=>{},setFocused:v=>focus.push(v),executeJavaScript:()=>{}};
 h.handlers.get('update')();await settle();
 h.handlers.get('browserMessage')({arguments:[{type:'society-ui-health',rts:true}]});
 h.handlers.get('update')();h.handlers.get('update')();
 h.handlers.get('browserMessage')({arguments:[{type:'society-ui-focus',focused:false}]});
 assert.equal(focus.at(-1),false);
 h.handlers.get('update')();assert.equal(focus.at(-1),false);
 h.handlers.get('buttonEvent')({code:66,isDown:true});assert.equal(focus.at(-1),true);
});


test('resource protocol status is published with a ready session and reset epoch',async()=>{
 const sessions=[];let epoch=1;
 const factory=getSession=>{sessions.push(getSession());return {
  reservedActors:()=>[],reset(){epoch++;},step(){throw Error('not used');},
  status:()=>({protocol:2,epoch:'epoch-'+epoch,manifest_hash:'manifest',catalog_hash:'catalog',available:true})};};
 const h=harness(false,null,null,factory);h.handlers.get('update')();await settle();
 assert.equal(typeof sessions[0],'string');assert.ok(sessions[0]);
 assert.equal(h.requests[0].resource_import.protocol,2);
 assert.equal(h.requests[0].resource_import.manifest_hash,'manifest');
 assert.equal(h.requests[0].resource_import.catalog_hash,'catalog');
 assert.equal(h.requests[0].resource_import.available,true);
 const old=h.requests[0].resource_import.epoch;
 h.advance();h.handlers.get('preLoadGame')();h.handlers.get('postLoadGame')();h.handlers.get('update')();
 assert.notEqual(h.requests.at(-1).resource_import.epoch,old);
});

test('every repeated resource ID reaches identity validation including changed payloads',async()=>{
 const received=[];
 const factory=()=>({reservedActors:()=>[],reset(){},status:()=>({protocol:2}),step(command){
  received.push({...command});return {done:true,ack:{id:command.id,status:command.contract==='original'?'armed':'held'}};}});
 const h=harness(false,null,null,factory);checkpointFixture(h);let contract='original';
 h.setResponse(body=>({id:'grant-arm',kind:'inventory_endowment',phase:'arm',protocol:2,actor:123,session:body.session,checkpoint:0,contract}));
 h.handlers.get('update')();await settle();h.advance();h.handlers.get('update')();await settle();
 contract='changed';h.advance();h.handlers.get('update')();await settle();h.advance();h.handlers.get('update')();await settle();
 assert.ok(received.length>=3);assert.equal(received.at(-1).contract,'changed');
 assert.equal(h.requests.at(-1).ack.status,'held');
});

test('resource commands bypass an unrelated cached ID and do not cache thrown failure',async()=>{
 let calls=0;
 const factory=()=>({reservedActors:()=>[],reset(){},status:()=>({protocol:2}),step(command){
  calls++;if(calls===1)throw Error('first contract rejected');return {done:true,ack:{id:command.id,status:'armed'}};}});
 const h=harness(false,null,null,factory);checkpointFixture(h);let kind='notify';
 h.setResponse(body=>({id:'reused-id',kind,phase:'arm',protocol:2,actor:123,session:body.session,checkpoint:0}));
 for(let i=0;i<2;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.equal(h.notifications.length,1);kind='inventory_endowment';
 for(let i=0;i<4;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.ok(calls>=2);assert.equal(h.requests.at(-1).ack.status,'armed');
});

test('armed and pending resource actors yield standing control and reject unrelated movement',async()=>{
 const blocked=[],yielded=[];
 const control=()=>({reset(){},yieldActors(ids){yielded.push([...ids]);},status:()=>({}),renew(){},tick(_saved,_residents,_fresh,actors){blocked.push([...actors]);}});
 const factory=()=>({reservedActors:()=>[123],reset(){},status:()=>({protocol:2}),step(){throw Error('not used');}});
 const h=harness(false,null,control,factory);checkpointFixture(h);
 h.setPresentation({society:{checkpoint:0,resource_delivery:{status:'pending',command:{kind:'inventory_endowment',actor:124}}}});
 h.setResponse(body=>({id:'conflicting-walk',kind:'walk_to',actor:123,target:124,checkpoint:0,session:body.session}));
 for(let i=0;i<4;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.ok(blocked.at(-1).includes(123)&&blocked.at(-1).includes(124));
 assert.ok(yielded.some(ids=>ids.includes(123)&&ids.includes(124)));
 assert.match(h.requests.at(-1).ack.error,/Pending resource grant/);
});


test('held saved imports retain quarantine after native reset and malformed identities cover the census',async()=>{
 for(const delivery of [
  {status:'held',command:{kind:'inventory_endowment',actor:124}},
  {status:'held',command:{kind:'inventory_endowment',actor:null},recipient:{actor:126}}
 ]){
  const blocked=[];
  const control=()=>({reset(){},yieldActors(){},status:()=>({}),renew(){},tick(_saved,_residents,_fresh,actors){blocked.push([...actors]);}});
  const factory=()=>({reservedActors:()=>[],reset(){},status:()=>({protocol:2,reserved_actors:[]}),step(){throw Error('not used');}});
  const h=harness(false,null,control,factory);checkpointFixture(h);
  h.handlers.get('preLoadGame')();h.handlers.get('postLoadGame')();
  h.setPresentation({society:{checkpoint:0,resource_delivery:delivery,people:{'124':{}},town:{residents:{'125':{}}}}});
  for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
  assert.ok(blocked.at(-1).includes(124));
  if(delivery.command.actor===null)for(const id of [123,125,126])assert.ok(blocked.at(-1).includes(id));
 }
});

test('malformed native reservation identity conservatively blocks managed and observed residents',async()=>{
 const blocked=[];
 const control=()=>({reset(){},yieldActors(){},status:()=>({}),renew(){},tick(_saved,_residents,_fresh,actors){blocked.push([...actors]);}});
 const factory=()=>({reservedActors:()=>[],reset(){},status:()=>({protocol:2,reserved_actors:'unknown'}),step(){throw Error('not used');}});
 const h=harness(false,null,control,factory);checkpointFixture(h);
 h.setPresentation({society:{checkpoint:0,people:{'124':{}},town:{residents:{'125':{}}}}});
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.deepEqual(blocked.at(-1).sort((a,b)=>a-b),[123,124,125]);
});


test('real resource controller advertises reviewed hashes and rotates epoch without constructor native reads',async()=>{
 const manifest=require('../config/resource-manifest.json');
 const {resourceManifestHash}=require('../bridge/resource-manifest.js');
 const h=harness();
 assert.equal(h.nativeReads.length,0,'native forms may only resolve inside update/native handlers');
 h.handlers.get('update')();await settle();
 const before=h.requests[0].resource_import;
 assert.equal(before.protocol,2);assert.equal(before.available,true);
 assert.equal(before.manifest_hash,resourceManifestHash(manifest));
 assert.equal(before.catalog_hash,manifest.catalog_hash);
 assert.deepEqual(before.reserved_actors,[]);
 h.advance();h.handlers.get('preLoadGame')();h.handlers.get('postLoadGame')();h.handlers.get('update')();await settle();
 const after=h.requests.at(-1).resource_import;
 assert.notEqual(after.epoch,before.epoch);
 assert.equal(after.manifest_hash,before.manifest_hash);
 assert.notEqual(h.requests.at(-1).session,h.requests[0].session);
});


function mockTradeController(overrides={}) {
 return {reset(){},status:()=>({protocol:2,epoch:'mock-trade-epoch',available:true,reserved_actors:[]}),
  reservedActors:()=>[],permitsCommand:()=>false,step:command=>({done:true,ack:{id:command.id,status:'armed'}}),
  consume:command=>({done:true,ack:{id:command.id,status:'applied'}}),...overrides};
}

test('trade protocol status and initialized session reach the controller and reset',async()=>{
 let epoch=1;const sessions=[];
 const h=harness(false,null,null,null,getSession=>{sessions.push(getSession());return mockTradeController({reset(){epoch++;},
  status:()=>({protocol:2,epoch:'trade-'+epoch,available:true,catalog_hash:'catalog',market_policy_hash:'policy',reserved_actors:[]})});});
 h.handlers.get('update')();await settle();const before=h.requests[0].trade_execution;
 assert.ok(sessions[0]);assert.equal(before.protocol,2);assert.equal(before.market_policy_hash,'policy');
 assert.equal(before.catalog_hash,'catalog');assert.equal(before.available,true);
 h.advance();h.handlers.get('preLoadGame')();h.handlers.get('postLoadGame')();h.handlers.get('update')();await settle();
 assert.notEqual(h.requests.at(-1).trade_execution.epoch,before.epoch);
});

test('trade arm and deliver replays bypass cached IDs and revalidate changed contracts',async()=>{
 const calls=[];
 const h=harness(false,null,null,null,()=>mockTradeController({step(command){calls.push({...command});
  return {done:true,ack:{id:command.id,status:command.account==='original'?'applied':'held'}};}}));
 checkpointFixture(h);let account='original',phase='arm';
 h.setResponse(body=>({id:'trade-'+phase,kind:'inventory_trade',phase,protocol:2,buyer:123,seller:124,checkpoint:0,session:body.session,account}));
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 phase='deliver';
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 account='changed';
 for(let i=0;i<2;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.ok(calls.filter(c=>c.phase==='arm').length>=2);assert.ok(calls.filter(c=>c.phase==='deliver').length>=3);
 assert.equal(calls.at(-1).account,'changed');assert.equal(h.requests.at(-1).ack.status,'held');
});

test('consume retains receipt cache while trade exceptions remain controller-owned',async()=>{
 let consumed=0,traded=0;let kind='inventory_consume';
 const h=harness(false,null,null,null,()=>mockTradeController({consume(command){consumed++;return {done:true,ack:{id:command.id,status:'applied'}};},
 step(command){traded++;if(traded===1)throw Error('rejected first payload');return {done:true,ack:{id:command.id,status:'armed'}};}}));
 checkpointFixture(h);h.setResponse(body=>({id:'same-id',kind,actor:123,buyer:123,seller:124,checkpoint:0,session:body.session}));
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.equal(consumed,1);kind='inventory_trade';
 for(let i=0;i<4;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.ok(traded>=2);assert.equal(h.requests.at(-1).ack.status,'armed');
});

test('only the exact saved trade contract admits an initial arm against its own reservation',async()=>{
 for(const changed of [false,true]){
  let calls=0;
  const h=harness(false,null,null,null,()=>mockTradeController({step(command){calls++;return {done:true,ack:{id:command.id,status:'armed'}};}}));checkpointFixture(h);
  const original={id:'opening-arm',kind:'inventory_trade',protocol:2,phase:'arm',buyer:123,seller:124,before:{buyer:{gold:10},seller:{gold:10}},after:{buyer:{gold:8},seller:{gold:12}}};
  h.setPresentation({society:{checkpoint:0,unsettled_effect:{status:'pending',command:original}}});
  h.setResponse(body=>({...original,checkpoint:0,session:body.session,...(changed?{after:{buyer:{gold:0},seller:{gold:20}}}:{})}));
  for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
  if(changed){assert.equal(calls,0);assert.match(h.requests.at(-1).ack.error,/exact saved\/native contract/);}
  else assert.ok(calls>=2);
 }
});

test('retained native trade permits exact continuation but rejects another contract',async()=>{
 let calls=0;let allow=true;
 const h=harness(false,null,null,null,()=>mockTradeController({reservedActors:()=>[123,124],permitsCommand:command=>command.permit==='live',
  step(command){calls++;return {done:true,ack:{id:command.id,status:'applied'}};}}));checkpointFixture(h);
 h.setResponse(body=>({id:'trade-deliver',kind:'inventory_trade',phase:'deliver',buyer:123,seller:124,checkpoint:0,session:body.session,permit:allow?'live':'other'}));
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 const prior=calls;allow=false;
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.equal(calls,prior+1);assert.match(h.requests.at(-1).ack.error,/Unsettled trade/);
});

test('held trade reserves both purses through reset and blocks unrelated consumption',async()=>{
 const blocked=[],yielded=[];
 const control=()=>({reset(){},yieldActors(ids){yielded.push([...ids]);},status:()=>({}),renew(){},tick(_s,_r,_f,ids){blocked.push([...ids]);}});
 const h=harness(false,null,control,null,()=>mockTradeController());checkpointFixture(h);
 h.handlers.get('preLoadGame')();h.handlers.get('postLoadGame')();
 h.setPresentation({society:{checkpoint:0,unsettled_effect:{status:'held',command:{kind:'inventory_trade',buyer:123,seller:124}}}});
 h.setResponse(body=>({id:'eat',kind:'inventory_consume',actor:124,checkpoint:0,session:body.session}));
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.ok(blocked.at(-1).includes(123)&&blocked.at(-1).includes(124));
 assert.ok(yielded.some(ids=>ids.includes(123)&&ids.includes(124)));
 assert.match(h.requests.at(-1).ack.error,/Unsettled trade reserves/);
});

test('unknown trade participant conservatively reserves managed and observed residents',async()=>{
 for(const nativeUnknown of [false,true]){
  const blocked=[];const control=()=>({reset(){},yieldActors(){},status:()=>({}),renew(){},tick(_s,_r,_f,ids){blocked.push([...ids]);}});
  const h=harness(false,null,control,null,()=>mockTradeController(nativeUnknown?{status:()=>({protocol:2,reserved_actors:'unknown'})}:{}));checkpointFixture(h);
  h.setPresentation({society:{checkpoint:0,people:{'125':{}},town:{residents:{'126':{}}},
   ...(nativeUnknown?{}:{unsettled_effect:{status:'held',command:{kind:'inventory_trade',buyer:124,seller:null}}})}});
  for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
  for(const actor of [123,125,126,...(nativeUnknown?[]:[124])])assert.ok(blocked.at(-1).includes(actor));
 }
});


test('real trade controller publishes reviewed policy identity and revokes its epoch on load',async()=>{
 const policy=require('../config/market-policy.json'),{marketPolicyHash}=require('../bridge/market-policy.js');
 const h=harness();assert.equal(h.nativeReads.length,0);
 h.handlers.get('update')();await settle();const before=h.requests[0].trade_execution;
 assert.equal(before.protocol,2);assert.equal(before.available,true);
 assert.equal(before.catalog_hash,policy.catalog_hash);assert.equal(before.market_policy_hash,marketPolicyHash(policy));
 assert.deepEqual(before.reserved_actors,[]);
 h.advance();h.handlers.get('preLoadGame')();h.handlers.get('postLoadGame')();h.handlers.get('update')();await settle();
 assert.notEqual(h.requests.at(-1).trade_execution.epoch,before.epoch);
 assert.equal(h.requests.at(-1).trade_execution.market_policy_hash,before.market_policy_hash);
});


test('cold held trade cannot authorize a fresh arm even when projected identity matches',async()=>{
 let calls=0;
 const h=harness(false,null,null,null,()=>mockTradeController({step(command){calls++;return {done:true,ack:{id:command.id,status:'armed'}};}}));checkpointFixture(h);
 const saved={id:'held-arm',kind:'inventory_trade',phase:'arm',protocol:2,buyer:123,seller:124,before:{buyer:{gold:10},seller:{gold:10}},after:{buyer:{gold:8},seller:{gold:12}}};
 h.setPresentation({society:{checkpoint:0,unsettled_effect:{status:'held',command:saved}}});
 h.setResponse(body=>({...saved,checkpoint:0,session:body.session}));
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.equal(calls,0);assert.match(h.requests.at(-1).ack.error,/exact saved\/native contract/);
});

test('held trade blocks authored stock preparation without explicit command actor fields',async()=>{
 const h=harness(false,null,null,null,()=>mockTradeController({reservedActors:()=>[108149,123]}));checkpointFixture(h);
 h.setResponse(body=>({id:'legacy-stock',kind:'prepare_market',session:body.session}));
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.match(h.requests.at(-1).ack.error,/Unsettled trade reserves/);
});

test('legacy paid command cannot reuse an unrelated applied cache entry',async()=>{
 const h=harness();let kind='notify';
 h.setResponse(body=>({id:'same-id',kind,session:body.session,worker:123,employer:124}));
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 assert.equal(h.requests.at(-1).ack.status,'applied');
 kind='inventory_produce';
 for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
 const receipt=h.requests.at(-1).ack;
 assert.equal(receipt.status,'held');assert.equal(receipt.reason,'legacy_paid_execution_unqualified');
 assert.equal(receipt.effects_issued,null);assert.equal(receipt.no_effects_issued,false);
 assert.equal(h.requests.at(-1).paid_employment.available,false);
});

test('journey identity checks cannot be bypassed with a cached applied ID',async()=>{
 for(const journeyKind of ['parallel_routines','background_routines']){
  const h=harness();checkpointFixture(h);let kind='notify';
  h.setResponse(body=>({id:'cached-journey',kind,session:body.session,origin_session:body.session,checkpoint:0,
   jobs:[{id:'unpinned',actor:123,target:456,slot:0}]}));
  for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
  assert.equal(h.requests.at(-1).ack.status,'applied');kind=journeyKind;
  for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
  assert.equal(h.requests.at(-1).ack.status,'held');
  assert.ok(h.requests.at(-1).ack.error);
 }
});

test('paid protocol commands cannot reuse an unrelated applied cache entry',async()=>{
 for(const paidKind of ['paid_work_start','inventory_paid_work_commit','paid_work_ack_receipt']){
  const h=harness();checkpointFixture(h);let kind='notify';
  h.setResponse(body=>({id:'cached-paid',kind,session:body.session,checkpoint:0,worker:123,employer:124}));
  for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
  assert.equal(h.requests.at(-1).ack.status,'applied');kind=paidKind;
  for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
  assert.equal(h.requests.at(-1).ack.status,'held');
  assert.ok(h.requests.at(-1).ack.error);
 }
});

test('saved paid employment reserves both participants before native admission',async()=>{
 for(const participant of [123,124]){
  const h=harness();checkpointFixture(h);
  h.setPresentation({society:{checkpoint:0,paid_employment:{jobs:[{worker:123,employer:124,phase:'prepared'}]}}});
  h.setResponse(body=>({id:'conflicting-travel',kind:'walk_to',actor:participant,target:456,session:body.session,checkpoint:0}));
  for(let i=0;i<3;i++){h.handlers.get('update')();await settle();h.advance();}
  assert.equal(h.requests.at(-1).ack.status,'failed');
  assert.match(h.requests.at(-1).ack.error,/Paid employment reserves/);
 }
});
