function createObserverCamera(){
 let lastRemoteRequest=null;
 let state={mode:'free',id:0,distance:1200,yaw:225,elevation:900,panX:24500,panY:-7100,manual:true,request_id:null};
 return {
  status(){return {...state};},
  reset(){state.manual=true;state.mode='free';state.capture=false;state.request_id=null;},
  acceptRemote(message,residents,managed){
   if(!message?.request_id||message.request_id===lastRemoteRequest)return false;
   lastRemoteRequest=message.request_id;
   return this.accept(message,residents,managed);
  },
  accept(message,residents,managed){
   if(!message||!['market','street','trade','focus','free','story','atlas','portrait'].includes(message.mode))return false;
   if(['focus','portrait'].includes(message.mode)&&(!Number.isInteger(message.id)||!managed[String(message.id)]||!residents.some(r=>r.id===message.id&&r.isPerson===true)))return false;
   if(message.capture!==undefined&&(typeof message.capture!=='boolean'||message.capture&&!['atlas','portrait'].includes(message.mode)))return false;
   const next={...state,mode:message.mode,id:message.id||0,manual:message.mode!=='story',capture:message.capture===true,request_id:message.request_id||null};
   for(const [key,low,high] of [['distance',100,4000],['yaw',-360,360],['elevation',40,2500],['panX',17000,30000],['panY',-15000,1000]]){
    if(message[key]===undefined)continue;
    if(!Number.isFinite(message[key])||message[key]<low||message[key]>high)return false;
    next[key]=message[key];
   }
   state=next;return true;
  }
 };
}
function storyActor(society,residents){
 const c=society?.conversation,p=society?.plan;
 const active=x=>x&&!['held','complete'].includes(x.phase);
 const candidate=active(c)?(c.current?.speaker||c.initiator):active(p)?(p.economic_speech?.actor||p.actor):null;
 return residents.some(r=>r.id===candidate&&r.isPerson===true)?candidate:null;
}
if(typeof module!=='undefined')module.exports={createObserverCamera,storyActor};
