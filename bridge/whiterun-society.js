// Skyrim Platform development probe. The deployer substitutes local credentials.
// Game methods run only inside the update callback or native event handlers.
(() => {
// The installed Node-backed build exposes native exports as a global.
let sp = typeof skyrimPlatform !== 'undefined' ? skyrimPlatform : require('skyrimPlatform');
const config = __BRIDGE_CONFIG__;
const client = new sp.HttpClient('http://127.0.0.1:' + config.port);
let session = Date.now() + '-' + Math.random();
let selected = 0;
let pending = null;
let ack = null;
let busy = false;
let lastSent = 0;
let announced = false;
let observerReady = false;
let bindingsReady = false;
let refreshBindings = false;
let lastBindingAttempt = 0;
let bindingAttempts = 0;
let residents = [];
let hud = null;
const oldHud=globalThis.whiterunSocietyHud;
if (typeof oldHud==='number') { try { sp.destroyText(oldHud); } catch (_) {} }
const completed = new Set();
// Hot reload must replace subscriptions instead of adding a second controller.
const registrationKey = 'whiterunSocietyHandlers';
const previous = sp.storage[registrationKey];
if (Array.isArray(previous)) previous.forEach(handle => sp.unsubscribe(handle));
const registrations = [];
sp.storage[registrationKey] = registrations;
function on(event, callback) { registrations.push(sp.on(event, callback)); }

function reset() {
  session = Date.now() + '-' + Math.random();
  selected = 0; pending = null; ack = null; completed.clear(); announced = false;
  observerReady = false; residents = [];
}
on('preLoadGame', reset);
on('newGame', reset);
on('activate', event => {
  if (event.caster && event.caster.getFormID() === 0x14 && event.target) {
    const actor = sp.Actor.from(event.target);
    if (actor) selected = actor.getFormID();
  }
});
registrations.push(sp.once('tick', () => sp.printConsole('[Whiterun Society] custom bridge loaded')));
on('tick',()=>{
  if (refreshBindings && bindingAttempts<3 && Date.now()-lastBindingAttempt>1000) {
    lastBindingAttempt=Date.now();refreshBindings=false;bindingAttempts++;
    // Rebuild on the loader's tick context, outside a Papyrus update stack.
    if (typeof sp.addNativeExports==='function') sp=sp.addNativeExports('skyrimPlatform',{});
  }
});
on('update', () => {
  const player = sp.Game.getPlayer();
  if (!player || !player.is3DLoaded()) return;
  const cell = player.getParentCell();
  if (!cell) return;
  if (!bindingsReady) {
    // Native functions are bound after plugin startup. Rebuild wrappers once the
    // world exists, rather than retaining the incomplete startup class table.
    if (typeof sp.Game.getFormEx!=='function') {refreshBindings=true;return;}
    bindingsReady=true;
  }
  if (!announced) {
    if (sp.browser) { sp.browser.setFocused(false); sp.browser.setVisible(false); }
    sp.Debug.notification('Whiterun Society: local development bridge loaded');
    announced = true;
  }
  if (pending) {
    const command = pending; pending = null;
    if (command.session === session && !completed.has(command.id)) {
      try {
        if (command.kind === 'notify') sp.Debug.notification('Whiterun Society: command received from local service');
        else if (command.kind === 'look_at_player') {
          const actor = sp.Actor.from(sp.Game.getFormEx(selected));
          if (!actor || !actor.is3DLoaded()) throw new Error('Interact with a loaded NPC first');
          actor.setLookAt(player, false);
        } else throw new Error('Unknown command');
        ack = {id:command.id,status:'applied',actor:selected};
      } catch (error) { ack = {id:command.id,status:'failed',error:String(error)}; }
      completed.add(command.id);
    }
  }
  if (busy || Date.now()-lastSent<2000) return;
  const currentSession = session;
  residents = [];
  const seen=new Set();
  function observe(resident) {
    if (resident && resident.getFormID()!==0x14 && !seen.has(resident.getFormID()) && resident.is3DLoaded() && !resident.isDead() && !resident.isChild()) {
      seen.add(resident.getFormID());
      residents.push({id:resident.getFormID(),name:resident.getDisplayName(),x:resident.getPositionX(),y:resident.getPositionY(),z:resident.getPositionZ()});
    }
  }
  // Only numeric IDs cross frame boundaries: native object handles are pooled
  // and expire after the callback. "Loaded" IDs still require a 3D check.
  if (typeof sp.getLoadedActorIds==='function') {
    sp.getLoadedActorIds().slice(0,64).forEach(id=>observe(sp.Actor.from(sp.Game.getFormEx(id))));
  }
  // SKSE filters references by their BASE form type: NPC is 43 (not ACHR 62).
  const count = Math.min(cell.getNumRefs(43),32);
  for (let i=0;i<count;i++) {
    const resident=sp.Actor.from(cell.getNthRef(i,43));
    observe(resident);
  }
  const distance=r=>(r.x-player.getPositionX())**2+(r.y-player.getPositionY())**2+(r.z-player.getPositionZ())**2;
  residents.sort((a,b)=>distance(a)-distance(b));
  residents=residents.slice(0,40);
  if (!residents.some(resident=>resident.id===selected)) selected=residents.length?residents[0].id:0;
  if (!observerReady && residents.length) {
    player.setGhost(true);
    sp.enableFreeCamera(true);
    sp.setFreeCameraPosition([player.getPositionX(),player.getPositionY(),player.getPositionZ()+240]);
    observerReady=true;
    sp.Debug.notification('Whiterun Society: observer ready; actors discovered automatically');
  }
  if (hud===null && typeof sp.createText==='function') {
    sp.setTextsVisibility('on');
    hud=sp.createText(640,110,'WHITERUN SOCIETY | Observer',[1,1,1,1],'DIN-Pro-bold');
    sp.setTextOrigin(hud,[0,0]);
    sp.setTextSize(hud,0.6);
    globalThis.whiterunSocietyHud=hud;
  }
  if (hud!==null) sp.setTextString(hud,'WHITERUN SOCIETY | Observer | '+residents.length+' actors loaded');
  const actor = selected ? sp.Actor.from(sp.Game.getFormEx(selected)) : null;
  const observation = {
    session, platform:sp.getPlatformVersion(),
    ready:observerReady,mode:'observer',residents,
    player:{id:player.getFormID(),cell:cell.getName(),cellId:cell.getFormID(),x:player.getPositionX(),y:player.getPositionY(),z:player.getPositionZ()},
    selected:actor ? {id:selected,name:actor.getDisplayName()} : null, ack
  };
  busy=true; lastSent=Date.now();
  client.post('/heartbeat',{body:JSON.stringify(observation),contentType:'application/json',headers:{Authorization:'Bearer '+config.token}})
    .then(response => {
      if (session===currentSession && response.status===200) pending=JSON.parse(response.body).command;
    }).catch(error => sp.writeLogs('whiterun-society',String(error))).finally(()=>{busy=false;});
});
})();
