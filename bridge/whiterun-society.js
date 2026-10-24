// Skyrim Platform development probe. The deployer substitutes local credentials.
// Game methods run only inside the update callback or native event handlers.
const sp = require('skyrimPlatform');
const config = __BRIDGE_CONFIG__;
const client = new sp.HttpClient('http://127.0.0.1:' + config.port);
let session = Date.now() + '-' + Math.random();
let selected = 0;
let pending = null;
let ack = null;
let busy = false;
let lastSent = 0;
let announced = false;
const completed = new Set();

function reset() {
  session = Date.now() + '-' + Math.random();
  selected = 0; pending = null; ack = null; completed.clear(); announced = false;
}
sp.on('preLoadGame', reset);
sp.on('newGame', reset);
sp.on('activate', event => {
  if (event.caster && event.caster.getFormID() === 0x14 && event.target) {
    const actor = sp.Actor.from(event.target);
    if (actor) selected = actor.getFormID();
  }
});
sp.once('tick', () => sp.printConsole('[Whiterun Society] custom bridge loaded'));
sp.on('update', () => {
  const player = sp.Game.getPlayer();
  if (!player) return;
  if (!announced) {
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
  const cell = player.getParentCell();
  const actor = selected ? sp.Actor.from(sp.Game.getFormEx(selected)) : null;
  const observation = {
    session, platform:sp.getPlatformVersion(),
    player:{id:player.getFormID(),cell:cell ? cell.getName() : '',x:player.getPositionX(),y:player.getPositionY(),z:player.getPositionZ()},
    selected:actor ? {id:selected,name:actor.getName()} : null, ack
  };
  busy=true; lastSent=Date.now();
  client.post('/heartbeat',{body:JSON.stringify(observation),contentType:'application/json',headers:{Authorization:'Bearer '+config.token}})
    .then(response => {
      if (session===currentSession && response.status===200) pending=JSON.parse(response.body).command;
    }).catch(error => sp.writeLogs('whiterun-society',String(error))).finally(()=>{busy=false;});
});
