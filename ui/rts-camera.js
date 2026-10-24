function createRtsCamera(){
 let view={mode:'free',distance:1800,elevation:2200,yaw:180,panX:24500,panY:-7100};
 const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
 return {
  status(){return {...view};},
  step(action,dx=0,dy=0){
   if(!Number.isFinite(dx)||!Number.isFinite(dy))return null;
   const v={...view},angle=v.yaw*Math.PI/180,step=Math.max(80,v.distance/8);
   let across=0,forward=0;
   if(action==='north')forward=step;
   else if(action==='south')forward=-step;
   else if(action==='east')across=step;
   else if(action==='west')across=-step;
   else if(action==='drag'){across=-clamp(dx,-100,100)*v.distance/500;forward=clamp(dy,-100,100)*v.distance/500;}
   else if(action==='in'||action==='out'){const scale=action==='in'?.85:1/.85;v.distance*=scale;v.elevation*=scale;}
   else if(action==='left')v.yaw-=15;
   else if(action==='right')v.yaw+=15;
   else if(action!=='enter')return null;
   v.panX+=Math.cos(angle)*across-Math.sin(angle)*forward;
   v.panY-=Math.sin(angle)*across+Math.cos(angle)*forward;
   v.panX=clamp(v.panX,17000,30000);v.panY=clamp(v.panY,-15000,1000);
   v.distance=clamp(v.distance,100,4000);v.elevation=clamp(v.elevation,40,2500);
   v.yaw=((v.yaw+540)%360)-180;
   view=v;return {...v};
  }
 };
}
if(typeof module!=='undefined')module.exports={createRtsCamera};
