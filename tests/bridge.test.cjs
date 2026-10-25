const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../bridge/whiterun-society.js'),'utf8')
  .replace('__SCENE_HANDOFF_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/scene-handoffs.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__CONVERSATION_ATTENDANCE_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/conversation-attendance.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__OBSERVER_CAMERA_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/observer-camera.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__TRANSFER_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/inventory-transfers.js'),'utf8').split('\nif (typeof module')[0])
  .replace('__ENDOWMENT_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/endowments.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__PRODUCTION_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/production.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__MOVEMENT_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/movement.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__PAPYRUS_ROUTER_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/papyrus-router.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__PLACE_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/places.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__PARALLEL_ROUTINES_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/parallel-routines.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__REST_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/rest.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__ROUTINE_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/agent-routines.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__SPEECH_FACTORY__',fs.readFileSync(path.join(__dirname,'../bridge/speech.js'),'utf8').split('\nif(typeof module')[0])
  .replace('__BRIDGE_CONFIG__',JSON.stringify({port:17841,token:'test-only'}));

function harness(nativeGlobal=false) {
  const handlers = new Map(), notifications=[], requests=[], looks=[];
  let respond=()=>null,clock=10000,presentation=null;
  const actor={getFormID:()=>123,getDisplayName:()=> 'Test NPC',is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,
    getPositionX:()=>1,getPositionY:()=>2,getPositionZ:()=>3,setLookAt:(...args)=>looks.push(args)};
  const cell={getName:()=> 'Test cell',getFormID:()=>107135,getNumRefs:filter=>{assert.equal(filter,43);return 1;},getNthRef:()=>actor};
  const player={getFormID:()=>20,getParentCell:()=>cell,is3DLoaded:()=>true,setGhost:()=>{},getPositionX:()=>0,getPositionY:()=>0,getPositionZ:()=>0};
  const sp={storage:{},on:(event,fn)=>{handlers.set(event,fn);return event;},once:(event,fn)=>{handlers.set(event,fn);return event;},
    unsubscribe:key=>handlers.delete(key), Actor:{from:value=>value},Game:{getPlayer:()=>player,getFormEx:id=>id===123?actor:null},
    enableFreeCamera:()=>{},setFreeCameraPosition:()=>{},
    Debug:{notification:text=>notifications.push(text)},getPlatformVersion:()=> 'mock',printConsole:()=>{},writeLogs:()=>{},
    HttpClient:class { post(route,options) { const body=JSON.parse(options.body);requests.push(body);return Promise.resolve({status:200,body:JSON.stringify({command:respond(body),presentation})}); } }};
  const context=vm.createContext({...nativeGlobal?{skyrimPlatform:sp}:{require:()=>sp},Date:{now:()=>clock}});
  vm.runInContext(source,context);
  return {handlers,notifications,requests,looks,player,actor,sp,cell,advance:()=>{clock+=2100;},setResponse:fn=>{respond=fn;},setPresentation:value=>{presentation=value;},reload:()=>vm.runInContext(source,context)};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));

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
