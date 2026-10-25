// Slots 6 and 7 hold consenting participants; background journeys use 0..5.
function createConversationAttendance(platform,now=Date.now,options={}){
 const makeRouter=options.routerFactory||(typeof createPapyrusRouterController==='function'?createPapyrusRouterController:require('./papyrus-router.js').createPapyrusRouterController);
 const lanes=[6,7].map(slot=>makeRouter(platform,now,{file:'WhiterunLanes.esp',offset:slot*0x10}));
 let active=null;
 function inspect(actor,slot){
  slot+=6;
  const sp=platform(),a=sp.Actor.from(sp.Game.getFormEx(actor));
  const pkg=sp.Game.getFormFromFile(0x801+slot*0x10,'WhiterunLanes.esp'),quest=sp.Quest.from(sp.Game.getFormFromFile(0x800+slot*0x10,'WhiterunLanes.esp'));
  if(!a?.is3DLoaded()||!pkg||!quest)return {actor,slot,loaded:false,ownedPackage:null,released:false};
  const current=a.getCurrentPackage(),owned=!!current&&current.getFormID()===pkg.getFormID();
  return {actor,slot,loaded:true,expectedPackage:pkg.getFormID(),ownedPackage:owned,released:!owned&&!quest.isRunning()};
 }
 return {
  reset(){active=null;for(const lane of lanes)lane.reset();},
  status(){return active?{id:active.id,phase:active.phase,participants:active.actors.map(inspect)}:null;},
  meet(command){
   const actors=command.participants;
   if(!Array.isArray(actors)||actors.length!==2||actors.some(a=>!Number.isInteger(a)||a<=0)||actors[0]===actors[1])
    return {done:true,ack:{id:command.id,status:'held',error:'Two distinct participants required'}};
   if(!active||active.id!==command.id){
    if(active&&!['released','held'].includes(active.phase))throw Error('Another encounter owns attendance lanes');
    options.releasePrior?.();
    active={id:command.id,actors:[...actors],phase:'approaching',receipts:{}};
   }
   if(JSON.stringify(active.actors)!==JSON.stringify(actors))throw Error('Attendance participants changed');
   for(let slot=0;slot<2;slot++){
    if(active.receipts[slot])continue;
    const result=lanes[slot].step({id:command.id+'-'+slot,actor:actors[slot],target:actors[1-slot],dynamic:true,retain:true,origin:'consenting_conversation'});
    if(result.done){
     if(result.ack.status!=='applied'){for(const lane of lanes)lane.release();active.phase='held';return {done:true,ack:{id:command.id,status:'held',error:result.ack.error||'Attendance route failed'}};}
     active.receipts[slot]=result.ack;
    }
   }
   if(Object.keys(active.receipts).length!==2)return {done:false};
   const attendance=this.status();
   if(!attendance.participants.every(p=>p.ownedPackage===true)){
    for(const lane of lanes)lane.release();active.phase='held';return {done:true,ack:{id:command.id,status:'held',error:'Attendance package ownership lost'}};
   }
   active.phase='attending';return {done:true,ack:{id:command.id,status:'applied',attendance:this.status()}};
  },
  finish(command){
   if(!active||active.releaseId!==command.id){
    const actors=command.participants;
    if(!Array.isArray(actors)||actors.length!==2)return {done:true,ack:{id:command.id,status:'held',released:false}};
    active={...(active||{}),id:active?.id||command.id,actors:[...actors],phase:'releasing',releaseId:command.id,releaseAt:now()};
    for(const lane of lanes)lane.release();return {done:false};
   }
   const attendance=this.status(),released=attendance.participants.every(p=>p.released);
   if(!released&&now()-active.releaseAt<10000)return {done:false};
   active.phase=released?'released':'held';
   return {done:true,ack:{id:command.id,status:released?'applied':'held',released,attendance:this.status()}};
  }
 };
}
if(typeof module!=='undefined')module.exports={createConversationAttendance};
