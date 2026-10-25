// Skyrim Platform development probe. The deployer substitutes local credentials.
// Game methods run only inside the update callback or native event handlers.
(() => {
// The installed Node-backed build exposes native exports as a global.
let sp = typeof skyrimPlatform !== 'undefined' ? skyrimPlatform : require('skyrimPlatform');
let session = Date.now() + '-' + Math.random();
__ECONOMY_CATALOG_FACTORY__
const economyCatalog=createEconomyCatalogController(()=>sp,__ECONOMY_CATALOG_MANIFEST__);
__MARKET_POLICY_FACTORY__
__TRANSFER_FACTORY__
const transfers=createInventoryTransfers(()=>sp,Date.now,{catalog:economyCatalog,marketPolicy:__MARKET_POLICY__,session:()=>session});
__RESOURCE_MANIFEST_FACTORY__
__ENDOWMENT_FACTORY__
const endowments=createEndowmentController(()=>sp,Date.now,{catalog:economyCatalog,manifest:__RESOURCE_MANIFEST__,session:()=>session});
__PRODUCTION_FACTORY__
const production=createProductionController(()=>sp,Date.now,{catalog:economyCatalog});
__MOVEMENT_FACTORY__
const movement=createMovementController(()=>sp);
__PAPYRUS_ROUTER_FACTORY__
__RESIDENT_CONTROL_FACTORY__
const residentControl=createResidentControl(()=>sp);
__SCENE_HANDOFF_FACTORY__
const sceneHandoffs=createSceneHandoffController(()=>sp);
__PLACE_FACTORY__
__REST_FACTORY__
const rest=createRestController(()=>sp);
__ACTIVITY_JOBS_FACTORY__
const activityJobs=createActivityJobsController(()=>sp);
__OWNER_WORK_JOBS_FACTORY__
const ownerWorkJobs=createOwnerWorkJobsController(()=>sp,Date.now,{catalog:economyCatalog});
__ROUTINE_FACTORY__
const routines=createAgentRoutineController(()=>sp);
__PARALLEL_ROUTINES_FACTORY__
const parallelRoutines=createParallelRoutineController(()=>sp);
__CONVERSATION_ATTENDANCE_FACTORY__
const conversationAttendance=createConversationAttendance(()=>sp,Date.now,{releasePrior:()=>routines.release()});
__SPEECH_FACTORY__
const speech=createSpeechController(()=>sp);
__OBSERVER_CAMERA_FACTORY__
const observerCamera=createObserverCamera();
let remoteCamera=null,lastPresentationAt=0;
let movementSource=null;
let routineRecoveryNeeded=true;
function conversationQuarantineActors(society,observed){
  const chat=society?.conversation;
  if(chat?.phase!=='held'||!(chat.release_required===true||chat.cleanup_review_required===true))return [];
  const valid=id=>Number.isInteger(id)&&id>0&&id<=0xffffffff;
  const ids=[chat.initiator,chat.partner,chat.meeting_route?.actor,chat.meeting_route?.target,
    ...(Array.isArray(chat.speakers)?chat.speakers:[]),...(Array.isArray(chat.scenario?.participants)?chat.scenario.participants:[])].filter(valid);
  const pairs=[];
  if('meeting_route' in chat)pairs.push([chat.meeting_route?.actor,chat.meeting_route?.target]);
  if('initiator' in chat||'partner' in chat)pairs.push([chat.initiator,chat.partner]);
  if('speakers' in chat)pairs.push(chat.speakers);
  if('scenario' in chat)pairs.push(chat.scenario?.participants);
  const complete=pair=>Array.isArray(pair)&&pair.length===2&&pair.every(valid)&&pair[0]!==pair[1];
  if(new Set(ids).size>=2&&pairs.every(complete))return [...new Set(ids)];
  const managed=Object.values(society?.town?.resident_control?.assignments||{}).map(row=>row?.actor);
  const people=[...Object.keys(society?.people||{}),...Object.keys(society?.town?.residents||{})].filter(key=>/^[1-9][0-9]{0,9}$/.test(key)).map(Number);
  return [...new Set([...ids,...managed,...people,...(observed||[]).map(row=>row?.id)].filter(valid))];
}
const config = __BRIDGE_CONFIG__;
const client = new sp.HttpClient('http://127.0.0.1:' + config.port);
let selected = 0;
let pending = null;
let ack = null;
let busy = false;
let lastSent = 0;
let lastAckSent=null;
let announced = false;
let observerReady = false;
let loading = false;
let bindingsReady = false;
let refreshBindings = false;
let lastBindingAttempt = 0;
let bindingAttempts = 0;
let residents = [];
let hud = null;
let cameraMode='story',cameraActor=0,cameraDirty=true,cursor=true,movieShot=null,cameraFraming=null;
let directorControl=null,playerControlRequest=null,audioOutput=null;
let presentation={trades:[],committedCount:0};
let lastProjection=0,projectionSample=[],mapProjection=null;
let observerKey=null,uiHealth=null;
let browserFocusReady=false;
let nativeButtonEvents=0,lastNativeControlKey=null;
const observerPressed={};
const oldHud=globalThis.whiterunSocietyHud;
if (typeof oldHud==='number') { try { sp.destroyText(oldHud); } catch (_) {} }
const completed = new Map();
// Hot reload must replace subscriptions instead of adding a second controller.
const registrationKey = 'whiterunSocietyHandlers';
const previous = sp.storage[registrationKey];
if (Array.isArray(previous)) previous.forEach(handle => sp.unsubscribe(handle));
const registrations = [];
sp.storage[registrationKey] = registrations;
function on(event, callback) { registrations.push(sp.on(event, callback)); }

function resourceReservedActors(inventoryObserved=[]) {
  const valid=id=>Number.isInteger(id)&&id>0&&id<=0xffffffff;
  const ids=new Set();let unknown=false;
  const include=values=>{if(!Array.isArray(values)){unknown=true;return;}
    for(const id of values){if(valid(id))ids.add(id);else unknown=true;}};
  include(endowments.reservedActors());
  const native=endowments.status();
  if(native&&Object.prototype.hasOwnProperty.call(native,'reserved_actors'))include(native.reserved_actors);
  if(pending?.kind==='inventory_endowment'&&pending.session===session)include([pending.actor]);
  const society=presentation.society;
  for(const record of [society?.pending,society?.resource_delivery]){
    const command=record?.command;
    if(command?.kind!=='inventory_endowment'||['committed','complete'].includes(record.status))continue;
    const actors=[command.actor];
    if(Object.prototype.hasOwnProperty.call(record,'actor'))actors.push(record.actor);
    if(Object.prototype.hasOwnProperty.call(record,'recipient'))actors.push(record.recipient?.actor);
    include(actors);
  }
  if(unknown){
    for(const people of [society?.people,society?.town?.residents])
      for(const key of Object.keys(people||{}))if(/^[1-9][0-9]{0,9}$/.test(key)&&valid(Number(key)))ids.add(Number(key));
    for(const row of Object.values(society?.town?.resident_control?.assignments||{}))if(valid(row?.actor))ids.add(row.actor);
    for(const row of [...residents,...inventoryObserved])if(valid(row?.id))ids.add(row.id);
  }
  return [...ids];
}
function savedTradeReservations() {
  const society=presentation.society;
  return [society?.pending,society?.unsettled_effect].filter(record=>record?.command?.kind==='inventory_trade'&&!['committed','complete'].includes(record.status));
}
function tradeReservedActors(inventoryObserved=[]) {
  const valid=id=>Number.isInteger(id)&&id>0&&id<=0xffffffff;
  const ids=new Set();let unknown=false;
  const include=values=>{if(!Array.isArray(values)){unknown=true;return;}
    for(const id of values){if(valid(id))ids.add(id);else unknown=true;}};
  include(transfers.reservedActors());
  const native=transfers.status();
  if(native&&Object.prototype.hasOwnProperty.call(native,'reserved_actors'))include(native.reserved_actors);
  if(pending?.kind==='inventory_trade'&&pending.session===session)include([pending.buyer,pending.seller]);
  for(const record of savedTradeReservations()){
    const identities=[record.command.buyer,record.command.seller];
    for(const field of ['buyer','seller'])if(Object.prototype.hasOwnProperty.call(record,field))identities.push(record[field]);
    include(identities);
  }
  if(unknown){
    const society=presentation.society;
    for(const people of [society?.people,society?.town?.residents])
      for(const key of Object.keys(people||{}))if(/^[1-9][0-9]{0,9}$/.test(key)&&valid(Number(key)))ids.add(Number(key));
    for(const row of Object.values(society?.town?.resident_control?.assignments||{}))if(valid(row?.actor))ids.add(row.actor);
    for(const row of [...residents,...inventoryObserved])if(valid(row?.id))ids.add(row.id);
  }
  return [...ids];
}
function tradeReservationAllows(command) {
  const valid=id=>Number.isInteger(id)&&id>0&&id<=0xffffffff;
  const actors=[command.buyer,command.seller];
  const native=transfers.reservedActors();
  if(!Array.isArray(native)||native.some(id=>!valid(id)))return false;
  if(native.some(id=>actors.includes(id))&&!transfers.permitsCommand(command))return false;
  const reported=transfers.status();
  if(reported&&Object.prototype.hasOwnProperty.call(reported,'reserved_actors')){
    const held=reported.reserved_actors;
    if(!Array.isArray(held)||held.some(id=>!valid(id)))return false;
    if(held.some(id=>actors.includes(id))&&!transfers.permitsCommand(command))return false;
  }
  // Only transport binding fields differ between the saved journal command and
  // its emitted envelope. Every contractual field and both full accounts match.
  const contract=value=>Object.fromEntries(Object.entries(value).filter(([key])=>!['session','checkpoint'].includes(key)));
  for(const record of savedTradeReservations()){
    const ids=[record.command.buyer,record.command.seller];
    for(const field of ['buyer','seller'])if(Object.prototype.hasOwnProperty.call(record,field))ids.push(record[field]);
    if(ids.some(id=>!valid(id)))return false;
    if(!ids.some(id=>actors.includes(id)))continue;
    try{if(canonicalJson(contract(command))!==canonicalJson(contract(record.command)))return false;}catch(_){return false;}
    if(record.status==='held'&&!transfers.permitsCommand(command))return false;
  }
  return true;
}
function reset() {
  browserFocusReady=false;uiHealth=null;nativeButtonEvents=0;lastNativeControlKey=null;
  directorControl=null;playerControlRequest=null;audioOutput=null;
  lastAckSent=null;
  sceneHandoffs.reset();residentControl.reset();lastPresentationAt=0;
  observerCamera.reset();remoteCamera=null;movieShot=null;cameraFraming=null;
  endowments.reset();
  speech.reset();conversationAttendance.reset();
  session = Date.now() + '-' + Math.random();
  selected = 0; pending = null; ack = null; completed.clear(); announced = false;
  observerReady = false; residents = [];
  cameraDirty=true;
  transfers.reset();
  activityJobs.reset();ownerWorkJobs.reset();production.reset();rest.reset();parallelRoutines.reset();
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
  if(message?.type==='society-ui-focus'&&message.focused===false&&sp.browser){cursor=false;sp.browser.setFocused(false);return;}
  if(message?.type==='society-director'&&['play','pause'].includes(message.action)){
    directorControl={id:'control-'+Date.now()+'-'+Math.random().toString(16).slice(2,10),action:message.action};return;
  }
  if(message?.type==='society-audio-output'){audioOutput={label:String(message.label||'Windows default').slice(0,160),error:message.error?String(message.error).slice(0,200):null,supported:message.supported===true,status:message.status||'ready',test:message.test||null,selection:message.selection||null};return;}
  if(message?.type==='society-ui-health'){uiHealth={rts:message.rts===true,mode:String(message.mode||'').slice(0,20),last_input:String(message.last_input||'').slice(0,30),pointer:message.pointer||null,click:message.click||null,diagnostics:message.diagnostics||null};return;}
  if(message?.type==='society-camera-release'){observerCamera.reset();cameraMode='story';cameraActor=0;cameraDirty=true;return;}
  if(message && message.type==='society-speech'){speech.message(message);return;}
  if (!message || message.type!=='society-camera') return;
  if(message.automatic===true){
    if(observerCamera.status().manual)return;
    if(!['market','trade','street','focus'].includes(message.mode))return;
    if(message.mode==='focus'&&!residents.some(r=>r.id===message.id&&r.isPerson===true))return;
    cameraMode=message.mode;cameraActor=message.id||0;cameraDirty=true;return;
  }
  if(!observerCamera.accept(message,residents,presentation.society?.town?.residents||{}))return;
  cameraMode=message.mode;cameraActor=message.id||0;cameraDirty=true;
});
on('buttonEvent',event=>{
  nativeButtonEvents++;
  if([2,3,4,17,30,31,32,16,18,15,64,65,66].includes(event.code))lastNativeControlKey={code:event.code,down:event.isDown===true};
  if(event.isDown&&[2,3,4,64,65].includes(event.code))observerKey=event.code;
  if (event.code===66 && event.isDown && sp.browser) {cursor=!cursor;sp.browser.setFocused(cursor);}
});
function updateCamera(player) {
  if (typeof sp.setFreeCameraRotation!=='function') return;
  const control=observerCamera.status();
  let target=[24500,-7100,-3320],offset=[-650,-850,450];
  if(cameraMode==='street'){target=[20950,-7500,-3540];offset=[-1250,-100,300];}
  if(cameraMode==='trade'&&control.manual){
    const pair=tradeCameraActors(presentation.society,residents);
    const a=pair[0]?sp.Actor.from(sp.Game.getFormEx(pair[0])):null,b=pair[1]?sp.Actor.from(sp.Game.getFormEx(pair[1])):null;
    if(a&&b&&a.is3DLoaded()&&b.is3DLoaded()) target=[(a.getPositionX()+b.getPositionX())/2,(a.getPositionY()+b.getPositionY())/2,(a.getPositionZ()+b.getPositionZ())/2+60];
    offset=[-400,-500,280];
  }
  if(cameraMode==='focus'&&control.manual){
    const actor=sp.Actor.from(sp.Game.getFormEx(cameraActor));
    if(!actor||!actor.is3DLoaded())return;
    target=[actor.getPositionX(),actor.getPositionY(),actor.getPositionZ()+80];
    const heading=actor.getAngleZ()*Math.PI/180;
    offset=[Math.sin(heading)*140,Math.cos(heading)*140,35];
  }
  if(control.manual){
    movieShot=null;cameraFraming=null;
    if(cameraMode==='free')target=[control.panX,control.panY,-3320];
    const yaw=control.yaw*Math.PI/180;
    offset=[Math.sin(yaw)*control.distance,Math.cos(yaw)*control.distance,control.elevation];
  }
  if(!control.manual&&control.mode==='story'){
    let ids=movieSubjects(presentation.society,residents);
    const lead=storyActor(presentation.society,residents);
    if(lead&&ids.includes(lead))ids=[lead,...ids.filter(id=>id!==lead)];
    const rows=[];
    for(const id of ids){const a=sp.Actor.from(sp.Game.getFormEx(id));if(a&&a.is3DLoaded())rows.push({id,x:a.getPositionX(),y:a.getPositionY(),z:a.getPositionZ(),heading:a.getAngleZ()});}
    const shot=rows.length===ids.length?movieFrame(rows,movieShot,typeof sp.getFreeCameraPosition==='function'?sp.getFreeCameraPosition():null):null;
    if(shot){if(shot.key!==movieShot?.key||shot.profile!==movieShot?.profile)cameraDirty=true;movieShot=shot;}
    if(!movieShot){cameraFraming={status:'waiting_for_activity',collision:'unverified'};cameraMode='story';cameraActor=0;}
    // Freeze the last composition when the encounter ends; do not chase a
    // departed speaker or start an unsolicited tour while the director is idle.
    if(movieShot){target=movieShot.target;offset=movieShot.offset;
    cameraMode=movieShot.kind==='pair'?'trade':'focus';cameraActor=lead||movieShot.ids[0];
    cameraFraming={profile:movieShot.profile,kind:movieShot.kind,subjects:movieShot.ids,
      status:shot?'following_activity':'holding_last_shot',distance:Math.hypot(offset[0],offset[1]),
      elevation:offset[2],target,collision:movieShot.collision,geometry_query:movieShot.geometry_query,
      occlusion_strategy:movieShot.occlusion_strategy};}
  }
  if(cameraMode==='atlas'){target=[control.panX,control.panY,-3320];offset=[0,0,18000];}
  if(cameraMode==='portrait'){
    const actor=sp.Actor.from(sp.Game.getFormEx(cameraActor));if(!actor||!actor.is3DLoaded())return;
    target=[actor.getPositionX(),actor.getPositionY(),actor.getPositionZ()+125];
    const heading=actor.getAngleZ()*Math.PI/180;offset=[Math.sin(heading)*140,Math.cos(heading)*140,10];
  }
  const desired=target.map((v,i)=>v+offset[i]);
  const rotation=[Math.atan2(offset[2],Math.hypot(offset[0],offset[1])),cameraMode==='atlas'?0:Math.atan2(-offset[0],-offset[1]),0];
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
    if (actor)selected = actor.getFormID();
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
  if(routineRecoveryNeeded){routines.release();rest.release();parallelRoutines.release();routineRecoveryNeeded=false;}
  parallelRoutines.tickBackground();
  parallelRoutines.sampleSocialOverlap(conversationAttendance.status(),speech.status()?.status==='playing');
  if (!announced) {
    if (sp.browser) {
      sp.browser.loadUrl('file:///Data/Platform/UI/index.html?rev='+Date.now());
      sp.browser.setVisible(true);sp.browser.setFocused(true);
    }
    // The overlay presents connection status without overlapping native notifications.
    announced = true;
  }
  // NirnLab can cache focus before page load, then skip applying it because
  // its cached flag already equals the requested value. Wait for the actual
  // page heartbeat and cross two update frames to open its native cursor.
  if(uiHealth&&sp.browser&&browserFocusReady!==true){
    if(browserFocusReady===false){sp.browser.setFocused(false);browserFocusReady='pending';}
    else {sp.browser.setFocused(cursor);browserFocusReady=true;}
  }
  if(remoteCamera){
    if(observerCamera.acceptRemote(remoteCamera,residents,presentation.society?.town?.residents||{}))cameraDirty=true;
    remoteCamera=null;
  }
  const view=observerCamera.status();
  if(view.manual){cameraMode=view.mode;cameraActor=view.id;}
  if(observerReady) updateCamera(player);
  if(observerReady&&sp.Input&&typeof sp.Input.isKeyPressed==='function'){
    for(const code of [2,3,4,64,65]){const down=sp.Input.isKeyPressed(code);if(down&&!observerPressed[code])observerKey=code;observerPressed[code]=down;}
  }
  if(observerKey&&sp.browser){const key=observerKey;observerKey=null;
    sp.browser.executeJavaScript('window.whiterunInspectKey && window.whiterunInspectKey('+key+');');}
  if(observerReady&&sp.browser&&typeof sp.worldPointToScreenPoint==='function'&&Date.now()-lastProjection>100){
    lastProjection=Date.now();projectionSample=[];
    for(const id of residents.filter(r=>r.isPerson===true).map(r=>r.id)){
      const resident=sp.Actor.from(sp.Game.getFormEx(id));if(!resident||!resident.is3DLoaded())continue;
      try{const x=resident.getPositionX(),y=resident.getPositionY(),z=resident.getPositionZ();
        const points=sp.worldPointToScreenPoint([x,y,z+125],[x,y,z+5]);
        if(Array.isArray(points)&&points.length===2)projectionSample.push({id,head:points[0],foot:points[1]});
      }catch(_){}
    }
    sp.browser.executeJavaScript('window.whiterunProject && window.whiterunProject('+JSON.stringify(projectionSample)+');');
    if(cameraMode==='atlas'){
      const corners=[[17000,-15000,-3320],[30000,-15000,-3320],[17000,1000,-3320]];
      try{mapProjection={world:corners,screen:sp.worldPointToScreenPoint(...corners),camera:sp.getFreeCameraPosition()};}catch(_){mapProjection=null;}
    }else mapProjection=null;
  }
  speech.tick();
  // Long furniture attendance progresses even while a disjoint voice, meal,
  // model decision or checkpoint occupies the foreground command channel.
  residentControl.yieldActors([...activityJobs.reservedActors(),...resourceReservedActors(),...tradeReservedActors()]);
  activityJobs.tick(presentation.society?.activity_jobs,session,Date.now()-lastPresentationAt<10000&&!presentation.society?.error);
  ownerWorkJobs.tick(presentation.society?.owner_work_jobs,session,Date.now()-lastPresentationAt<10000&&!presentation.society?.error,residentControl.status());
  residentControl.yieldActors(ownerWorkJobs.releasingActors());
  if (pending) {
    const command = pending; pending = null;
    // Grants and trades validate complete identity on every arm/deliver replay.
    // The generic ID-only cache must never bypass that controller's checks.
    const resourceCommand=command.kind==='inventory_endowment',tradeCommand=command.kind==='inventory_trade';
    const controllerReceipt=resourceCommand||tradeCommand;
    if(!controllerReceipt&&command.session===session&&completed.has(command.id)&&completed.get(command.id))ack=completed.get(command.id);
    if (command.session === session && (controllerReceipt||!completed.has(command.id))) {
      try {
        if(tradeCommand){
          if(!Number.isInteger(command.checkpoint)||checkpointValue()!==command.checkpoint)throw new Error('Trade checkpoint mismatch');
          if(!tradeReservationAllows(command))throw new Error('Unsettled trade reserves the accounts; exact saved/native contract required');
        }else{
          const reserved=tradeReservedActors();
          const actors=[command.kind==='look_at_player'?selected:undefined,command.kind==='prepare_market'?108149:undefined,command.actor,command.target,command.worker,command.employer,command.buyer,command.seller,...(command.participants||[]),...(command.members||[]).flatMap(m=>[m.actor,m.target])];
          if(actors.some(id=>reserved.includes(id)))throw new Error('Unsettled trade reserves a command participant');
        }
        if(!resourceCommand){
          const reserved=resourceReservedActors();
          const actors=[command.actor,command.target,command.worker,command.employer,command.buyer,command.seller,...(command.participants||[]),...(command.members||[]).flatMap(m=>[m.actor,m.target])];
          if(actors.some(id=>reserved.includes(id)))throw new Error('Pending resource grant reserves a command participant');
        }
        if(!['activity_start_rest','activity_ack_receipt'].includes(command.kind)){
          const actors=[command.actor,command.target,command.worker,command.employer,command.buyer,command.seller,...(command.participants||[]),...(command.members||[]).map(m=>m.actor)];
          if(actors.some(id=>activityJobs.ownsActor(id))||activityJobs.ownsTarget(command.target))throw new Error('Background activity owns a command participant or furniture');
        }
        if(!['owner_work_start','owner_work_ack_receipt'].includes(command.kind)){
          const actors=[command.actor,command.target,command.worker,command.employer,command.buyer,command.seller,...(command.participants||[]),...(command.members||[]).map(m=>m.actor)];
          if(actors.some(id=>ownerWorkJobs.ownsActor(id))&&!ownerWorkJobs.permitsCommand(command))throw new Error('Independent owner work reserves a command participant');
        }
        if(['walk_to','parallel_routines','background_routines','rest_at_bench','activity_start_rest','owner_work_start','conversation_attend','scene_handoff'].includes(command.kind)){
          const quarantined=conversationQuarantineActors(presentation.society,residents);
          const actors=[command.actor,command.target,...(command.participants||[]),...(command.members||[]).flatMap(member=>[member.actor,member.target])];
          if(actors.some(id=>quarantined.includes(id)))throw new Error('Unverified conversation cleanup reserves a command participant');
        }
        if(['activity_start_rest','activity_ack_receipt','owner_work_start','owner_work_ack_receipt'].includes(command.kind)){
          if(checkpointValue()!==command.checkpoint)throw new Error('Activity checkpoint mismatch');
          const blocked=[];
          if(command.kind==='activity_start_rest'||command.kind==='owner_work_start'){
            const attendance=conversationAttendance.status(),foregroundRest=rest.status(),work=production.status(),travel=movementSource?.status();
            for(const participant of attendance?.participants||[])if(!participant.released)blocked.push(participant.actor);
            if(foregroundRest&&(!['applied','held'].includes(foregroundRest.phase)||!foregroundRest.release_verified))blocked.push(foregroundRest.actor);
            if(work&&!['complete','held'].includes(work.phase))blocked.push(work.actor);
            if(travel&&!['applied','held','released'].includes(travel.phase))blocked.push(travel.actor,travel.target);
            if(['starting','playing'].includes(speech.status()?.status))for(const participant of speech.status()?.facing||[])blocked.push(participant.actor);
            if(parallelRoutines.ownsActor(command.actor))blocked.push(command.actor);
            blocked.push(...activityJobs.reservedActors(),...ownerWorkJobs.reservedActors(),...resourceReservedActors(),...tradeReservedActors());
          }
          const result=command.kind==='activity_start_rest'?activityJobs.start(command,blocked):
            command.kind==='activity_ack_receipt'?activityJobs.acknowledge(command):
            command.kind==='owner_work_start'?ownerWorkJobs.start(command,blocked):ownerWorkJobs.acknowledge(command);
          ack=result.ack;completed.set(command.id,JSON.parse(JSON.stringify(ack)));
          residentControl.yieldActors(activityJobs.reservedActors());
        }
        else if (command.kind === 'inventory_trade' || command.kind === 'inventory_consume') {
          if (!Number.isInteger(command.checkpoint) || checkpointValue()!==command.checkpoint) throw new Error('Trade checkpoint mismatch');
          const result=command.kind==='inventory_consume'?transfers.consume(command):transfers.step(command);
          if (!result.done) pending=command;
          else {ack=result.ack;if(!tradeCommand)completed.set(command.id,ack?.id===command.id?JSON.parse(JSON.stringify(ack)):null);}
        }
        else if (['inventory_produce','inventory_self_produce','inventory_self_produce_commit','inventory_supply'].includes(command.kind)) {
          if(checkpointValue()!==command.checkpoint)throw new Error('Production checkpoint mismatch');
          const result=command.kind==='inventory_self_produce_commit'?production.commitOwnerRecipe(command,ownerWorkJobs):production.step(command);
          if(!result.done)pending=command;
          else {ack=result.ack;completed.set(command.id,ack?.id===command.id?JSON.parse(JSON.stringify(ack)):null);}
        }
        else if(command.kind==='rest_at_bench'){
          if(checkpointValue()!==command.checkpoint)throw new Error('Rest checkpoint mismatch');
          const result=rest.step(command);
          if(!result.done)pending=command;else {ack=result.ack;completed.set(command.id,ack?.id===command.id?JSON.parse(JSON.stringify(ack)):null);}
        }
        else if(command.kind==='scene_handoff'){
          if(checkpointValue()!==command.checkpoint)throw new Error('Scene handoff checkpoint mismatch');
          const result=sceneHandoffs.step(command);
          if(!result.done)pending=command;else {ack=result.ack;completed.set(command.id,ack?.id===command.id?JSON.parse(JSON.stringify(ack)):null);}
        }
        else if(command.kind==='speak'){
          if(checkpointValue()!==command.checkpoint)throw new Error('Speech checkpoint mismatch');
          speech.start(command);
          completed.set(command.id,ack?.id===command.id?JSON.parse(JSON.stringify(ack)):null);
        }
        else if(command.kind==='conversation_attend'){
          if(checkpointValue()!==command.checkpoint)throw new Error('Attendance checkpoint mismatch');
          if(command.participants?.some(id=>parallelRoutines.ownsActor(id)))throw new Error('Background journey owns an attendance participant');
          const result=conversationAttendance.meet(command);
          if(!result.done)pending=command;else{ack=result.ack;completed.set(command.id,ack?.id===command.id?JSON.parse(JSON.stringify(ack)):null);}
        }
        else if(command.kind==='inventory_endowment'){
          if(checkpointValue()!==command.checkpoint)throw new Error('Endowment checkpoint mismatch');
          const result=endowments.step(command);
          if(!result.done)pending=command;
          else ack=result.ack;
        }
        else if(command.kind==='parallel_routines'||command.kind==='background_routines'){
          if(checkpointValue()!==command.checkpoint||command.origin_session!==session)throw new Error('Independent routine checkpoint or session mismatch');
          const result=command.kind==='background_routines'?parallelRoutines.startBackground(command):parallelRoutines.step(command);
          if(!result.done)pending=command;else{ack=result.ack;completed.set(command.id,ack?.id===command.id?JSON.parse(JSON.stringify(ack)):null);}
        }
        else if (command.kind === 'walk_to') {
          if(parallelRoutines.ownsActor(command.actor)||parallelRoutines.ownsActor(command.target))throw new Error('Background journey owns a meeting participant');
          if(command.checkpoint!==undefined&&checkpointValue()!==command.checkpoint)throw new Error('Travel checkpoint mismatch');
          movementSource=command.method==='package'?routines:movement;
          const result=movementSource.step(command);
          if(!result.done)pending=command;
          else {ack=result.ack;completed.set(command.id,ack?.id===command.id?JSON.parse(JSON.stringify(ack)):null);}
        }
        else if(command.kind==='release_routine'){
          if(checkpointValue()!==command.checkpoint)throw new Error('Release checkpoint mismatch');
          const stopped=command.stop_speech_id?speech.interrupt(command.stop_speech_id):null;
          const original=routines.finish(command);
          const paired=command.participants?conversationAttendance.finish(command):null;
          const result=paired?(!original.done||!paired.done?{done:false}:original.ack.released?paired:original):original;
          if(!result.done)pending=command;
          else {ack={...result.ack,...(command.stop_speech_id?{speechStop:{id:command.stop_speech_id,acknowledged:stopped,status:speech.status()?.status}}:{})};completed.set(command.id,ack?.id===command.id?JSON.parse(JSON.stringify(ack)):null);}
        }
        else if (command.kind === 'bind_checkpoint') {
          if (!Number.isInteger(command.next)||command.next<1||command.next>16777215) throw new Error('Invalid checkpoint');
          const global=checkpointGlobal();
          if (!global || global.getValue()!==command.expected) throw new Error('Checkpoint changed before binding');
          global.setValue(command.next);
          if (global.getValue()!==command.next) throw new Error('Checkpoint write not observed');
        }
        else if (command.kind === 'test_voice_output') {if(!sp.browser)throw Error('Overlay unavailable');sp.browser.executeJavaScript('window.whiterunTestVoice && window.whiterunTestVoice('+JSON.stringify(command.id)+');');}
        else if (command.kind === 'select_voice_output') {if(!sp.browser)throw Error('Overlay unavailable');sp.browser.executeJavaScript('window.whiterunSelectVoiceOutput && window.whiterunSelectVoiceOutput('+JSON.stringify(command.id)+','+JSON.stringify(command.output)+');');}
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
        if (!['activity_start_rest','activity_ack_receipt','owner_work_start','owner_work_ack_receipt','scene_handoff','speak','conversation_attend','inventory_trade','inventory_consume','inventory_produce','inventory_self_produce','inventory_self_produce_commit','inventory_supply','inventory_endowment','rest_at_bench','parallel_routines','background_routines','walk_to','release_routine'].includes(command.kind)) {ack = {id:command.id,status:'applied',actor:selected};completed.set(command.id,ack?.id===command.id?JSON.parse(JSON.stringify(ack)):null);}
      } catch (error) { ack = {id:command.id,status:'failed',error:String(error)};if(!controllerReceipt)completed.set(command.id,ack?.id===command.id?JSON.parse(JSON.stringify(ack)):null); }
    }
  }
  const activeConversation=presentation.society?.conversation;
  const activeDelivery=presentation.society?.resource_delivery?.status==='pending';
  const activePlan=presentation.society?.plan;
  const residentActive=activePlan&&(!['complete','held'].includes(activePlan.phase)||activePlan.release_required);
  const ackKey=ack?ack.id+':'+ack.status:null;
  const protocolProgress=ackKey!==lastAckSent||presentation.society?.transition&&!presentation.society?.error;
  // Consent and thinking are part of the encounter too. A bound checkpoint
  // or finished native command must not wait behind the idle town cadence.
  const cadence=protocolProgress?100:activeDelivery?250:(residentActive||activeConversation&&!['complete','held'].includes(activeConversation.phase)?350:2000);
  if (busy || Date.now()-lastSent<cadence) return;
  const currentSession = session;
  residents = [];
  const seen=new Set();
  function observe(resident) {
    if (resident && resident.getFormID()!==0x14 && !seen.has(resident.getFormID()) && resident.is3DLoaded() && !resident.isDead() && !resident.isChild()) {
      seen.add(resident.getFormID());
      const inventory=economyCatalog.readInventory(resident);
      let isPerson=null,isGuard=null,outdoors=null,voiceSex=null,race=null,space=null,baseId=null;
      try{if(typeof resident.getRace==='function'){const nativeRace=resident.getRace();if(nativeRace){const label=typeof nativeRace.getName==='function'?nativeRace.getName():null;race={id:nativeRace.getFormID(),name:typeof label==='string'&&label?label.slice(0,80):null,source:'native Skyrim race; descriptive game metadata only'};}}}catch(_){}
      try{const raw=resident.getActorBase?.()||resident.getBaseObject?.();const base=raw&&sp.ActorBase?.from(raw);baseId=raw?raw.getFormID():null;if(base&&typeof base.getSex==='function')voiceSex=base.getSex();}catch(_){}
      try{if(sp.Keyword&&typeof resident.hasKeyword==='function'){
        const keyword=sp.Keyword.from(sp.Game.getFormEx(0x13794));if(keyword)isPerson=resident.hasKeyword(keyword);
      }}catch(_){}
      try{if(typeof resident.isGuard==='function')isGuard=resident.isGuard();}catch(_){}
      try{const ownCell=resident.getParentCell();if(ownCell&&typeof ownCell.isInterior==='function'){
        const interior=ownCell.isInterior(),world=resident.getWorldSpace?.();outdoors=!interior;
        space={cell:ownCell.getFormID(),interior,world:world?world.getFormID():null};
      }}catch(_){}
      residents.push({id:resident.getFormID(),name:resident.getDisplayName(),inventory,isPerson,isGuard,outdoors,voiceSex,race,space,baseId,
        activity:observeNativeActivity(resident),
        classificationSource:isPerson===null?'unavailable':'native ActorTypeNPC keyword; child/dead filters applied',
        x:resident.getPositionX(),y:resident.getPositionY(),z:resident.getPositionZ()});
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
  // Accounting observations are not perception or evidence of physical action.
  // Persistent actor inventories can be inspected even when 3D is unloaded.
  const inventoryObservations=[];
  for(const key of Object.keys(presentation.society?.town?.residents||{}).slice(0,128)){
    const id=Number(key);if(!Number.isInteger(id)||id<=0)continue;
    try{
      const owner=sp.Actor.from(sp.Game.getFormEx(id));
      if(!owner||owner.isDead()||owner.isChild()||typeof owner.getItemCount!=='function')continue;
      const keyword=sp.Keyword?.from(sp.Game.getFormEx(0x13794));
      if(!keyword||!owner.hasKeyword(keyword))continue;
      const inventory=economyCatalog.readInventory(owner);
      const base=owner.getActorBase?.()||owner.getBaseObject?.();
      inventoryObservations.push({id,isPerson:true,loaded:owner.is3DLoaded(),baseId:base?base.getFormID():null,inventory});
    }catch(_){} // Missing references are not assigned fictitious empty purses.
  }
  const perception={};
  // Diagnose the current observed population, not a named demonstration cast.
  // This sensor remains unqualified and cannot teach residents hidden facts.
  for(const {id} of residents.filter(row=>row.isPerson===true)){
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
    try{
      if(typeof sp.Game.disablePlayerControls==='function'){
        sp.Game.disablePlayerControls(true,true,true,true,true,false,true,true,0);
        playerControlRequest='requested';
      }else playerControlRequest='api_unavailable';
    }catch(_){playerControlRequest='request_failed';}
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
  let gameDays=null,weather=null;
  try{if(sp.Utility&&typeof sp.Utility.getCurrentGameTime==='function')gameDays=sp.Utility.getCurrentGameTime();}catch(_){}
  try{if(sp.Weather&&typeof sp.Weather.getCurrentWeather==='function'){
    const current=sp.Weather.getCurrentWeather();if(current){const classification=current.getClassification();
      weather={id:current.getFormID(),classification,label:({0:'pleasant',1:'cloudy',2:'rainy',3:'snow'})[classification]||'unknown',
        source:'native current-weather classification; not a forecast'};
    }
  }}catch(_){}
  try {if(sp.Utility&&typeof sp.Utility.getINIBool==='function')audioEnabled=sp.Utility.getINIBool('bEnableAudio:Audio');} catch(_) {}
  function controlEnabled(name){try{return typeof sp.Game[name]==='function'?sp.Game[name]():null;}catch(_){return null;}}
  const societyState=presentation.society,foreground=new Set([...resourceReservedActors(inventoryObservations),...tradeReservedActors(inventoryObservations)]);
  const plan=societyState?.plan,chat=societyState?.conversation,batch=societyState?.routine_batch;
  if(plan&&(!['complete','held','delegated'].includes(plan.phase)||plan.release_required)){for(const id of [plan.actor,plan.target,...(plan.economic_pair||[])])if(id)foreground.add(id);}
  if(chat&&(!['complete','held'].includes(chat.phase)||chat.release_required||chat.cleanup_review_required)){
    for(const id of [chat.initiator,chat.partner,...(Array.isArray(chat.speakers)?chat.speakers:[]),...conversationQuarantineActors(societyState,residents)])
      if(Number.isInteger(id)&&id>0)foreground.add(id);
  }
  if(batch&&!['complete','held'].includes(batch.phase))for(const m of batch.members||[])foreground.add(m.actor);
  const controlFresh=Date.now()-lastPresentationAt<10000&&!societyState?.error;
  const activityReserved=[...activityJobs.reservedActors(),...ownerWorkJobs.releasingActors()],savedControl=societyState?.town?.resident_control;
  const effectiveControl=savedControl?{...savedControl,assignments:Object.fromEntries(Object.entries(savedControl.assignments||{}).filter(([,row])=>!activityReserved.includes(row.actor)))}:savedControl;
  const publicPlaces=routines.places(residents),restObservation=rest.sense(residents);
  // A checkpoint transition pauses new bindings; it must not release every
  // standing task while a disjoint conversation commits a memory.
  if(!controlFresh||(!societyState?.transition&&societyState?.checkpoint===checkpointValue()))
    residentControl.tick(effectiveControl,residents,controlFresh,[...foreground,...activityReserved],[...publicPlaces.filter(p=>p.available),...(restObservation.sites||[]).filter(p=>p.loaded)],[...ownerWorkJobs.holds(),...(plan?[plan]:[])]);
  else residentControl.renew(residents,controlFresh);
  const observation = {
    economy_catalog:economyCatalog.status(),
    resource_import:endowments.status(),
    trade_execution:transfers.status(),
    director_control:directorControl,
    player_controls:{request:playerControlRequest,
      movement:controlEnabled('isMovementControlsEnabled'),
      fighting:controlEnabled('isFightingControlsEnabled'),
      activate:controlEnabled('isActivateControlsEnabled')},
    transport:{cadence_ms:cadence,previous_request_interval_ms:lastSent?Date.now()-lastSent:null},
    resident_control:residentControl.status(),
    activity_jobs:activityJobs.status(),
    owner_work_jobs:ownerWorkJobs.status(),
    ui_health:uiHealth?{...uiHealth,native:{button_events:nativeButtonEvents,last_control_key:lastNativeControlKey,focus_ready:browserFocusReady===true,focus_requested:cursor,browser_wanted_focus:typeof sp.browser?.isFocused==='function'?sp.browser.isFocused():null}}:null,audio_output:audioOutput,
    camera:{...observerCamera.status(),mode:cameraMode,id:cameraActor,framing:cameraFraming,position:typeof sp.getFreeCameraPosition==='function'?sp.getFreeCameraPosition():null},
    session, checkpoint:checkpointValue(), movement:movementSource?movementSource.status():null, routing:routines.capabilities(),parallel_routines:parallelRoutines.status(),platform:sp.getPlatformVersion(),
    ready:observerReady,mode:'observer',residents,places:publicPlaces,inventory_observations:inventoryObservations,inventory_checkpoint:presentation.society?.checkpoint??null,perception,gameDays,weather,rest:restObservation,productionWork:production.status(),speech:speech.status(),conversationAttendance:conversationAttendance.status(),projection:projectionSample,audioDiagnostic:config.audioDiagnostic===true,audioEnabled,
    player:{id:player.getFormID(),cell:cell.getName(),cellId:cell.getFormID(),x:player.getPositionX(),y:player.getPositionY(),z:player.getPositionZ()},
    map_projection:mapProjection,selected:actor ? {id:selected,name:actor.getDisplayName()} : null, ack
  };
  if (sp.browser) {
    sp.setTextsVisibility('off');
    sp.browser.executeJavaScript('window.whiterunRender && window.whiterunRender('+JSON.stringify({...observation,...presentation})+');');
  }
  busy=true; lastSent=Date.now();lastAckSent=ackKey;
  client.post('/heartbeat',{body:JSON.stringify(observation),contentType:'application/json',headers:{Authorization:'Bearer '+config.token}})
    .then(response => {
      if (session===currentSession && response.status===200) {
        const result=JSON.parse(response.body);pending=result.command;
        if(directorControl&&result.director_control_receipt?.id===directorControl.id)directorControl=null;
        if(result.presentation){presentation=result.presentation;lastPresentationAt=Date.now();}
        if(result.observer_camera&&result.observer_camera.request_id!==observerCamera.status().request_id)remoteCamera=result.observer_camera;
      }
    }).catch(error => sp.writeLogs('whiterun-society',String(error))).finally(()=>{busy=false;});
});
})();
