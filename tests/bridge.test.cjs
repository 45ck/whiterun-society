const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../bridge/whiterun-society.js'),'utf8')
  .replace('__BRIDGE_CONFIG__',JSON.stringify({port:17841,token:'test-only'}));

function harness() {
  const handlers = new Map(), notifications=[], requests=[], looks=[];
  let respond=()=>null;
  const player={getFormID:()=>20,getParentCell:()=>({getName:()=> 'Test cell'}),getPositionX:()=>0,getPositionY:()=>0,getPositionZ:()=>0};
  const actor={getFormID:()=>123,getName:()=> 'Test NPC',is3DLoaded:()=>true,setLookAt:(...args)=>looks.push(args)};
  const sp={storage:{},on:(event,fn)=>{handlers.set(event,fn);return event;},once:(event,fn)=>{handlers.set(event,fn);return event;},
    unsubscribe:key=>handlers.delete(key), Actor:{from:value=>value},Game:{getPlayer:()=>player,getFormEx:()=>actor},
    Debug:{notification:text=>notifications.push(text)},getPlatformVersion:()=> 'mock',printConsole:()=>{},writeLogs:()=>{},
    HttpClient:class { post(route,options) { const body=JSON.parse(options.body);requests.push(body);return Promise.resolve({status:200,body:JSON.stringify({command:respond(body)})}); } }};
  vm.runInNewContext(source,{require:()=>sp,Date,Math,Set,JSON,Array});
  return {handlers,notifications,requests,looks,player,actor,sp,setResponse:fn=>{respond=fn;},reload:()=>vm.runInNewContext(source,{require:()=>sp,Date,Math,Set,JSON,Array})};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));

test('heartbeat is built from observed game state',async()=>{
  const h=harness();h.handlers.get('update')();await settle();
  assert.equal(h.requests[0].player.cell,'Test cell');
  assert.equal(h.notifications.length,1);
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
  h.handlers.get('update')();assert.equal(h.notifications.length,2);
  assert.ok(h.notifications.every(message=>!message.includes('command received')));
});
test('hot reload unsubscribes the previous controller',()=>{
  const h=harness();const old=h.handlers.get('update');
  h.reload();assert.notEqual(h.handlers.get('update'),old);assert.equal(h.handlers.size,5);
});
