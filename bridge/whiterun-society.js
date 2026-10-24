// Skyrim Platform development probe. The deployer substitutes local credentials.
// Game methods run only inside the update callback or native event handlers.
(() => {
// The installed Node-backed build exposes native exports as a global.
let sp = typeof skyrimPlatform !== 'undefined' ? skyrimPlatform : require('skyrimPlatform');
__TRANSFER_FACTORY__
const transfers=createInventoryTransfers(()=>sp);
__PRODUCTION_FACTORY__
const production=createProductionController(()=>sp);
__MOVEMENT_FACTORY__
const movement=createMovementController(()=>sp);
__ROUTINE_FACTORY__
const routines=createAgentRoutineController(()=>sp);
let movementSource=null;
let routineRecoveryNeeded=true;
const config = __BRIDGE_CONFIG__;
const economyForms={gold:0xf,bread:0x65c97,grain:0x4b0ba};
const client = new sp.HttpClient('http://127.0.0.1:' + config.port);
let session = Date.now() + '-' + Math.random();
let selected = 0;
let pending = null;
let ack = null;
let busy = false;
let lastSent = 0;
let announced = false;
let observerReady = false;
let loading = false;
let bindingsReady = false;
let refreshBindings = false;
let lastBindingAttempt = 0;
let bindingAttempts = 0;
let residents = [];
let hud = null;
let cameraMode='market',cameraActor=0,cameraDirty=true,cursor=true;
let presentation={trades:[],committedCount:0};
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
  cameraDirty=true;
  transfers.reset();
  production.reset();
  movement.reset();
  routines.reset();movementSource=null;routineRecoveryNeeded=true;
}
on('preLoadGame', () => {reset();loading=true;sp.printConsole('[Society] preLoadGame');});
// The engine loadGame event can arrive before SKSE preLoadGame. Pair the
// SKSE lifecycle events instead, so an early engine event cannot leave us paused.
on('postLoadGame', () => {loading=false;sp.printConsole('[Society] postLoadGame complete');});
on('newGame', () => {reset();loading=false;});
function checkpointGlobal() {
  if (!sp.GlobalVariable || typeof sp.Game.getFormFromFile!=='function') return null;
  return sp.GlobalVariable.from(sp.Game.getFormFromFile(0x800,'WhiterunSociety.esp'));
}
function checkpointValue() {
  const global=checkpointGlobal();
  return global ? global.getValue() : null;
}
on('browserMessage',event=>{
  const message=event.arguments && event.arguments[0];
  if (!message || message.type!=='society-camera') return;
  if (!['market','trade','street','focus'].includes(message.mode)) return;
  if (message.mode==='focus' && ![108149,108186,108156].includes(message.id)) return;
  cameraMode=message.mode;cameraActor=message.id||0;cameraDirty=true;
});
on('buttonEvent',event=>{
  if (event.code===66 && event.isDown && sp.browser) {cursor=!cursor;sp.browser.setFocused(cursor);}
});
function updateCamera(player) {
  if (typeof sp.setFreeCameraRotation!=='function') return;
  let target=[24500,-7100,-3320],offset=[-650,-850,450];
  if(cameraMode==='street'){target=[20950,-7500,-3540];offset=[-1250,-100,300];}
  if(cameraMode==='trade'){
    const a=sp.Actor.from(sp.Game.getFormEx(108149)),b=sp.Actor.from(sp.Game.getFormEx(108186));
    if(a&&b&&a.is3DLoaded()&&b.is3DLoaded()) target=[(a.getPositionX()+b.getPositionX())/2,(a.getPositionY()+b.getPositionY())/2,(a.getPositionZ()+b.getPositionZ())/2+60];
    offset=[-400,-500,280];
  }
  if(cameraMode==='focus'){
    const actor=sp.Actor.from(sp.Game.getFormEx(cameraActor));
    if(!actor||!actor.is3DLoaded())return;
    target=[actor.getPositionX(),actor.getPositionY(),actor.getPositionZ()+80];
    const heading=actor.getAngleZ()*Math.PI/180;
    offset=[Math.sin(heading)*140,Math.cos(heading)*140,35];
  }
  const desired=target.map((v,i)=>v+offset[i]);
  const rotation=[Math.atan2(offset[2],Math.hypot(offset[0],offset[1])),Math.atan2(-offset[0],-offset[1]),0];
  if(cameraDirty||typeof sp.getFreeCameraPosition!=='function') {
    sp.setFreeCameraPosition(desired);sp.setFreeCameraRotation(rotation);cameraDirty=false;
  } else {
    const current=sp.getFreeCameraPosition(),r=sp.getFreeCameraRotation();
    sp.setFreeCameraPosition(current.map((v,i)=>v+(desired[i]-v)*0.08));
    const delta=Math.atan2(Math.sin(rotation[1]-r[1]),Math.cos(rotation[1]-r[1]));
    sp.setFreeCameraRotation([r[0]+(rotation[0]-r[0])*0.08,r[1]+delta*0.08,0]);
  }
}
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
  if (loading) return;
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
  if(routineRecoveryNeeded){routines.release();routineRecoveryNeeded=false;}
  if (!announced) {
    if (sp.browser) {
      sp.browser.loadUrl('file:///Data/Platform/UI/index.html?rev='+Date.now());
      sp.browser.setVisible(true);sp.browser.setFocused(true);
    }
    // The overlay presents connection status without overlapping native notifications.
    announced = true;
  }
  if(observerReady) updateCamera(player);
  if (pending) {
    const command = pending; pending = null;
    if (command.session === session && !completed.has(command.id)) {
      try {
        if (command.kind === 'inventory_trade' || command.kind === 'inventory_consume') {
          if (!Number.isInteger(command.checkpoint) || checkpointValue()!==command.checkpoint) throw new Error('Trade checkpoint mismatch');
          const result=command.kind==='inventory_consume'?transfers.consume(command):transfers.step(command);
          if (!result.done) pending=command;
          else {ack=result.ack;completed.add(command.id);}
        }
        else if (command.kind === 'inventory_produce' || command.kind === 'inventory_supply') {
          if(checkpointValue()!==command.checkpoint)throw new Error('Production checkpoint mismatch');
          const result=production.step(command);
          if(!result.done)pending=command;
          else {ack=result.ack;completed.add(command.id);}
        }
        else if (command.kind === 'walk_to') {
          if(command.checkpoint!==undefined&&checkpointValue()!==command.checkpoint)throw new Error('Travel checkpoint mismatch');
          cameraMode='focus';cameraActor=command.actor;cameraDirty=true;
          movementSource=command.method==='package'?routines:movement;
          const result=movementSource.step(command);
          if(!result.done)pending=command;
          else {ack=result.ack;completed.add(command.id);}
        }
        else if(command.kind==='release_routine'){
          if(checkpointValue()!==command.checkpoint)throw new Error('Release checkpoint mismatch');
          const result=routines.finish(command);
          if(!result.done)pending=command;
          else {ack=result.ack;completed.add(command.id);}
        }
        else if (command.kind === 'bind_checkpoint') {
          if (!Number.isInteger(command.next)||command.next<1||command.next>16777215) throw new Error('Invalid checkpoint');
          const global=checkpointGlobal();
          if (!global || global.getValue()!==command.expected) throw new Error('Checkpoint changed before binding');
          global.setValue(command.next);
          if (global.getValue()!==command.next) throw new Error('Checkpoint write not observed');
        }
        else if (command.kind === 'notify') sp.Debug.notification('Whiterun Society: command received from local service');
        else if (command.kind === 'prepare_market') {
          if (checkpointValue()!==0) throw new Error('Demo setup requires a new-world marker');
          const seller=sp.Actor.from(sp.Game.getFormEx(108149)),bread=sp.Game.getFormEx(0x65c97);
          if (!seller||!seller.is3DLoaded()||!bread) throw new Error('Demo seller is unavailable');
          const missing=Math.max(0,3-seller.getItemCount(bread));
          if (missing) seller.addItem(bread,missing,true);
        }
        else if (command.kind === 'save_game' || command.kind === 'load_game') {
          if (!/^WS-[A-Za-z0-9_-]{1,48}$/.test(command.name)) throw new Error('Invalid lab save name');
          if (command.kind==='save_game') {
            sp.Game.setInChargen(false,false,false);
            sp.Game.saveGame(command.name);
          } else sp.Game.loadGame(command.name);
        }
        else if (command.kind === 'look_at_player') {
          const actor = sp.Actor.from(sp.Game.getFormEx(selected));
          if (!actor || !actor.is3DLoaded()) throw new Error('Interact with a loaded NPC first');
          actor.setLookAt(player, false);
        } else throw new Error('Unknown command');
        if (!['inventory_trade','inventory_consume','inventory_produce','inventory_supply','walk_to','release_routine'].includes(command.kind)) {ack = {id:command.id,status:'applied',actor:selected};completed.add(command.id);}
      } catch (error) { ack = {id:command.id,status:'failed',error:String(error)};completed.add(command.id); }
    }
  }
  if (busy || Date.now()-lastSent<2000) return;
  const currentSession = session;
  residents = [];
  const seen=new Set();
  function observe(resident) {
    if (resident && resident.getFormID()!==0x14 && !seen.has(resident.getFormID()) && resident.is3DLoaded() && !resident.isDead() && !resident.isChild()) {
      seen.add(resident.getFormID());
      const inventory={};
      if (typeof resident.getItemCount==='function') {
        for (const [item,id] of Object.entries(economyForms)) inventory[item]=resident.getItemCount(sp.Game.getFormEx(id));
      }
      residents.push({id:resident.getFormID(),name:resident.getDisplayName(),inventory,x:resident.getPositionX(),y:resident.getPositionY(),z:resident.getPositionZ()});
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
  const perception={};
  for(const id of [108149,108186,108156]){
    const eye=sp.Actor.from(sp.Game.getFormEx(id));
    const record={available:false,visible:[],source:'experimental engine line of sight; not yet qualified as resident perception'};
    perception[id]=record;
    if(!eye||!eye.is3DLoaded()||typeof eye.hasLOS!=='function'||typeof eye.getAngleZ!=='function')continue;
    try{
      const heading=eye.getAngleZ()*Math.PI/180;
      record.diagnostics={headingDegrees:eye.getAngleZ(),nearby:0,inCone:0,nativeVisible:0};
      for(const seen of residents){
        if(seen.id===id)continue;
        const dx=seen.x-eye.getPositionX(),dy=seen.y-eye.getPositionY(),dz=seen.z-eye.getPositionZ();
        const range=Math.hypot(dx,dy,dz),bearing=Math.atan2(dx,dy)-heading;
        if(range>2000)continue;
        record.diagnostics.nearby++;
        if(Math.abs(Math.atan2(Math.sin(bearing),Math.cos(bearing)))>Math.PI*.45)continue;
        record.diagnostics.inCone++;
        const other=sp.Actor.from(sp.Game.getFormEx(seen.id));
        if(other&&eye.hasLOS(other))record.visible.push({id:seen.id,name:seen.name,distance:Math.round(range)});
      }
      record.visible.sort((a,b)=>a.distance-b.distance);record.visible=record.visible.slice(0,8);
      record.diagnostics.nativeVisible=record.visible.length;
      // Keep experimental native output out of resident knowledge until live
      // positive/occlusion controls qualify the sensor.
      record.visible=[];
    }catch(_){record.visible=[];}
  }
  if (!residents.some(resident=>resident.id===selected)) selected=residents.length?residents[0].id:0;
  if (!observerReady && residents.length) {
    player.setGhost(true);
    sp.enableFreeCamera(true);
    sp.setFreeCameraPosition([player.getPositionX(),player.getPositionY(),player.getPositionZ()+240]);
    observerReady=true;
    // Observer readiness is shown by the live overlay.
  }
  if (!sp.browser && hud===null && typeof sp.createText==='function') {
    sp.setTextsVisibility('on');
    hud=sp.createText(640,110,'WHITERUN SOCIETY | Observer',[1,1,1,1],'DIN-Pro-bold');
    sp.setTextOrigin(hud,[0,0]);
    sp.setTextSize(hud,0.6);
    globalThis.whiterunSocietyHud=hud;
  }
  if (hud!==null) sp.setTextString(hud,'WHITERUN SOCIETY | Observer | '+residents.length+' actors loaded');
  const actor = selected ? sp.Actor.from(sp.Game.getFormEx(selected)) : null;
  let audioEnabled=null;
  try {if(sp.Utility&&typeof sp.Utility.getINIBool==='function')audioEnabled=sp.Utility.getINIBool('bEnableAudio:Audio');} catch(_) {}
  const observation = {
    session, checkpoint:checkpointValue(), movement:movementSource?movementSource.status():null, platform:sp.getPlatformVersion(),
    ready:observerReady,mode:'observer',residents,perception,productionWork:production.status(),audioDiagnostic:config.audioDiagnostic===true,audioEnabled,
    player:{id:player.getFormID(),cell:cell.getName(),cellId:cell.getFormID(),x:player.getPositionX(),y:player.getPositionY(),z:player.getPositionZ()},
    selected:actor ? {id:selected,name:actor.getDisplayName()} : null, ack
  };
  if (sp.browser) {
    sp.setTextsVisibility('off');
    sp.browser.executeJavaScript('window.whiterunRender && window.whiterunRender('+JSON.stringify({...observation,...presentation})+');');
  }
  busy=true; lastSent=Date.now();
  client.post('/heartbeat',{body:JSON.stringify(observation),contentType:'application/json',headers:{Authorization:'Bearer '+config.token}})
    .then(response => {
      if (session===currentSession && response.status===200) {
        const result=JSON.parse(response.body);pending=result.command;
        if(result.presentation) presentation=result.presentation;
      }
    }).catch(error => sp.writeLogs('whiterun-society',String(error))).finally(()=>{busy=false;});
});
})();
