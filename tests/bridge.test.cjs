const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../bridge/whiterun-society.js'),'utf8')
  .replace('__BRIDGE_CONFIG__',JSON.stringify({port:17841,token:'test-only'}));

function harness(nativeGlobal=false) {
  const handlers = new Map(), notifications=[], requests=[], looks=[];
  let respond=()=>null;
  const actor={getFormID:()=>123,getDisplayName:()=> 'Test NPC',is3DLoaded:()=>true,isDead:()=>false,isChild:()=>false,
    getPositionX:()=>1,getPositionY:()=>2,getPositionZ:()=>3,setLookAt:(...args)=>looks.push(args)};
  const cell={getName:()=> 'Test cell',getFormID:()=>107135,getNumRefs:filter=>{assert.equal(filter,43);return 1;},getNthRef:()=>actor};
  const player={getFormID:()=>20,getParentCell:()=>cell,is3DLoaded:()=>true,setGhost:()=>{},getPositionX:()=>0,getPositionY:()=>0,getPositionZ:()=>0};
  const sp={storage:{},on:(event,fn)=>{handlers.set(event,fn);return event;},once:(event,fn)=>{handlers.set(event,fn);return event;},
    unsubscribe:key=>handlers.delete(key), Actor:{from:value=>value},Game:{getPlayer:()=>player,getFormEx:id=>id===123?actor:null},
    enableFreeCamera:()=>{},setFreeCameraPosition:()=>{},
    Debug:{notification:text=>notifications.push(text)},getPlatformVersion:()=> 'mock',printConsole:()=>{},writeLogs:()=>{},
    HttpClient:class { post(route,options) { const body=JSON.parse(options.body);requests.push(body);return Promise.resolve({status:200,body:JSON.stringify({command:respond(body)})}); } }};
  const context=vm.createContext(nativeGlobal?{skyrimPlatform:sp}:{require:()=>sp});
  vm.runInContext(source,context);
  return {handlers,notifications,requests,looks,player,actor,sp,cell,setResponse:fn=>{respond=fn;},reload:()=>vm.runInContext(source,context)};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));

test('heartbeat is built from observed game state',async()=>{
  const h=harness();h.handlers.get('update')();await settle();
  assert.equal(h.requests[0].player.cell,'Test cell');
  assert.equal(h.requests[0].ready,true);
  assert.equal(h.requests[0].residents[0].id,123);
  assert.equal(h.requests[0].selected.id,123);
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
  h.reload();assert.notEqual(h.handlers.get('update'),old);assert.equal(h.handlers.size,5);
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
