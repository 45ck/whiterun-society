// A quest alias supplies the managed resident's package stack. Only scalar IDs
// survive updates; every native handle is reacquired before use.
function createAgentRoutineController(platform,now=Date.now){
 const makeRouter=typeof createPapyrusRouterController==='function'?createPapyrusRouterController:require('./papyrus-router.js').createPapyrusRouterController;
 const makePlaces=typeof createPlaceObserver==='function'?createPlaceObserver:require('./places.js').createPlaceObserver;
 const places=makePlaces(platform);
 const router=makeRouter(platform,now,{placeObserver:places});
 let useRouter=false;
 let releaseStarted=null;
 // Historical plugin offsets are retained only for release, never admission.
 const legacySlots=[0,1,2,3,4,5];
 return {
  reset(){releaseStarted=null;router.reset();useRouter=false;},
  capabilities(){return {adapter:'papyrus-mailbox-v1',available:router.available(),places:true};},
  places(residents){return places.sense(residents);},
  release(){
   const sp=platform();
   if(!sp.Quest)return;
   if(sp.Game.getFormFromFile)router.release();
   for(let i=0;i<legacySlots.length;i++){
    const quest=sp.Quest.from(sp.Game.getFormFromFile(0x800+i*2,'WhiterunAgents.esp'));
    if(quest&&quest.isRunning())quest.stop();
   }
  },
  finish(command){
   const sp=platform();
   if(!releaseStarted||releaseStarted.id!==command.id){releaseStarted={id:command.id,at:now()};this.release();return {done:false};}
   const actor=sp.Actor.from(sp.Game.getFormEx(command.actor));
   if(!actor||!actor.is3DLoaded())return {done:true,ack:{id:command.id,status:'held',released:false,error:'Resident unavailable; package release is unverified'}};
   const current=actor&&actor.getCurrentPackage();
   const routerPackage=sp.Game.getFormFromFile(0x801,'WhiterunRouter.esp');
   const owned=(routerPackage&&current&&routerPackage.getFormID()===current.getFormID())||legacySlots.some(i=>{
    const pkg=sp.Game.getFormFromFile(0x801+i*2,'WhiterunAgents.esp');
    return pkg&&current&&pkg.getFormID()===current.getFormID();
   });
   if(owned&&now()-releaseStarted.at<10000)return {done:false};
   if(useRouter)router.observeRelease(!!owned);
   return {done:true,ack:{id:command.id,status:owned?'held':'applied',released:!owned}};
  },
  status(){return useRouter?router.status():null;},
  step(command){
   // A legacy pending command cannot become a fresh mailbox trip, nor can a
   // running old quest prove which saved command originally acquired it.
   if(command.dynamic!==true)return {done:true,ack:{id:command.id,status:'held',
    released:false,release_required:true,error:'Legacy or unversioned route requires explicit release; new travel requires the mailbox protocol'}};
   useRouter=true;
   return router.step(command);
  }
 };
}
if(typeof module!=='undefined')module.exports={createAgentRoutineController};
