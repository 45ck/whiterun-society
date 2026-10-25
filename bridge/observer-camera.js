function createObserverCamera(){
 let lastRemoteRequest=null;
 let state={mode:'story',id:0,distance:1200,yaw:225,elevation:900,panX:24500,panY:-7100,manual:false,request_id:null};
 return {
  status(){return {...state};},
  reset(){state.manual=false;state.mode='story';state.capture=false;state.request_id=null;},
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
 const loaded=id=>residents.some(r=>r.id===id&&r.isPerson===true);
 if(loaded(candidate))return candidate;
 const batch=society?.routine_batch;
 const traveller=active(batch)?batch.members?.find(m=>m.phase==='travelling'&&loaded(m.actor))?.actor:null;
 if(traveller)return traveller;
 const goalActor=Object.entries(society?.people||{}).find(([id,p])=>p.standing_goal?.phase==='travelling'&&loaded(Number(id)));
 return goalActor?Number(goalActor[0]):null;
}
function tradeCameraActors(society,residents){
 const pair=society?.plan?.economic_pair;
 const valid=ids=>Array.isArray(ids)&&ids.length===2&&ids[0]!==ids[1]&&ids.every(id=>residents.some(r=>r.id===id&&r.isPerson===true));
 if(valid(pair))return pair;
 const conversation=society?.conversation;
 if(conversation&&!['complete','held'].includes(conversation.phase)&&valid(conversation.speakers))return conversation.speakers;
 return [];
}
function movieSubjects(society,residents){
 const active=x=>x&&!['held','complete'].includes(x.phase),p=society?.plan,c=society?.conversation;
 const valid=ids=>Array.isArray(ids)&&ids.length===2&&ids[0]!==ids[1]&&ids.every(id=>residents.some(r=>r.id===id&&r.isPerson===true));
 if(active(p)&&valid(p.economic_pair))return [...p.economic_pair].sort((a,b)=>a-b);
 if(active(c)&&valid(c.speakers))return [...c.speakers].sort((a,b)=>a-b);
 const actor=storyActor(society,residents);return actor?[actor]:[];
}
function movieFrame(rows,previous=null,cameraPosition=null){
 // Without a qualified native obstruction query, prefer a steep elevated
 // composition over a blind shoulder-height close-up behind nearby walls.
 // This is a fallback, not proof of clear geometry (roofs may still occlude).
 if(!rows.length||rows.some(r=>!['x','y','z','heading'].every(k=>Number.isFinite(r[k]))))return null;
 let actors=[...rows].sort((a,b)=>a.id-b.id),target,offset,side=1,kind='resident';
 const gap=actors.length===2?Math.hypot(actors[1].x-actors[0].x,actors[1].y-actors[0].y):0;
 if(actors.length===2&&gap>1&&gap<=650){
  kind='pair';target=['x','y','z'].map(k=>(actors[0][k]+actors[1][k])/2);target[2]+=80;
  const perpendicular=[-(actors[1].y-actors[0].y)/gap,(actors[1].x-actors[0].x)/gap];
  const key=actors.map(a=>a.id).join(':');
  if(previous?.key===key)side=previous.side;
  else if(Array.isArray(cameraPosition)&&cameraPosition.length===3&&cameraPosition.every(Number.isFinite)){
   side=(cameraPosition[0]-target[0])*perpendicular[0]+(cameraPosition[1]-target[1])*perpendicular[1]<0?-1:1;
  }
  const distance=Math.max(150,Math.min(350,gap*.6));
  offset=[perpendicular[0]*side*distance,perpendicular[1]*side*distance,Math.max(520,gap*.9)];
 }else{
  // Before attendance, follow the selected resident rather than framing a
  // distant pair through multiple buildings. The caller orders that actor first.
  actors=[rows[0]];const a=actors[0],heading=a.heading*Math.PI/180;
  // Keep the established bearing when a resident turns in place. Body heading
  // is animation/attention evidence, not a request to orbit the camera through
  // nearby architecture. New subjects and manual/reset transitions recompose.
  const stable=previous?.kind==='resident'&&previous.key===String(a.id)&&
    Array.isArray(previous.offset)&&previous.offset.length===3&&previous.offset.every(Number.isFinite)&&
    Math.hypot(previous.offset[0],previous.offset[1])>0;
  const bearing=stable?Math.atan2(previous.offset[0],previous.offset[1]):heading;
  target=[a.x,a.y,a.z+90];offset=[Math.sin(bearing)*180,Math.cos(bearing)*180,520];
 }
 return {key:actors.map(a=>a.id).join(':'),ids:actors.map(a=>a.id),kind,side,target,offset,
  position:target.map((v,i)=>v+offset[i]),collision:'unverified',geometry_query:'unavailable',
  occlusion_strategy:'elevated_fallback',profile:'subject-relative-elevated-v3'};
}
if(typeof module!=='undefined')module.exports={createObserverCamera,storyActor,tradeCameraActors,movieSubjects,movieFrame};
