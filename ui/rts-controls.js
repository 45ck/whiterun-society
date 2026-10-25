const rtsCamera=createRtsCamera();
let rtsDrag=null,lastRtsSend=0,lastRtsInput='loaded',lastUiPointer=null,lastUiClick=null;
const uiInputCounts={pointerdown:0,pointerup:0,click:0,keydown:0,wheel:0};
let lastUiEventAt=null,lastUiControlKey=null;
for(const kind of Object.keys(uiInputCounts))document.addEventListener(kind,event=>{
 uiInputCounts[kind]++;lastUiEventAt=Date.now();
 if(kind==='keydown'&&!event.target.closest?.('input,textarea,select')&&['Tab','F7','F8','w','a','s','d','q','e','+','-'].includes(event.key))lastUiControlKey=event.key;
},true);
window.whiterunObserveRtsCamera=sample=>rtsCamera.observe(sample);
window.whiterunRtsActive=()=>camera==='free';
function rtsMove(action,dx=0,dy=0){
 const view=rtsCamera.step(action,dx,dy);if(!view)return;
 lastRtsInput=action;
 camera='free';focusId=null;
 send({type:'society-camera',...view});
 document.getElementById('rts-controls').hidden=false;
 text('camera-label','RTS overview · wheel zoom · drag to pan');
 window.drawEncounter?.();
}
document.getElementById('rts-mode').onclick=()=>rtsMove('enter');
window.whiterunEnterRts=()=>rtsMove('enter');
for(const button of document.querySelectorAll('[data-rts]'))button.onclick=()=>rtsMove(button.dataset.rts);
document.addEventListener('keydown',event=>{
 if(event.key==='F8'){event.preventDefault();send({type:'society-ui-focus',focused:false});rtsDrag=null;return;}
 if(event.target.closest?.('input,textarea,select'))return;
 if(event.key==='F7'){event.preventDefault();rtsMove('enter');return;}
 if(!window.whiterunRtsActive())return;
 const action={w:'north',s:'south',a:'west',d:'east',q:'left',e:'right','+':'in','-':'out'}[event.key.toLowerCase()];
 if(action){event.preventDefault();rtsMove(action);}
});
document.addEventListener('wheel',event=>{
 if(!window.whiterunRtsActive()||event.target.closest?.('.sidebar,#resident-inspector'))return;
 event.preventDefault();rtsMove(event.deltaY<0?'in':'out');
},{passive:false});
document.addEventListener('click',event=>{lastUiClick={x:event.clientX,y:event.clientY,target:event.target.closest?.('button')?.dataset?.resident||event.target.closest?.('button')?.id||event.target.tagName};},true);
document.addEventListener('pointerdown',event=>{lastUiPointer={x:event.clientX,y:event.clientY,target:event.target.tagName};},true);
document.addEventListener('pointerdown',event=>{
 if(!window.whiterunRtsActive()||event.target.closest?.('button,.panel,.brand,.resident-marker'))return;
 if(event.button!==0&&event.button!==1)return;
 rtsDrag={x:event.clientX,y:event.clientY,id:event.pointerId};
 try{event.target.setPointerCapture?.(event.pointerId);}catch(_){}
});
document.addEventListener('pointermove',event=>{
 if(!rtsDrag||event.pointerId!==rtsDrag.id||!window.whiterunRtsActive())return;
 if((event.buttons&5)===0){rtsDrag=null;return;}
 const now=Date.now();if(now-lastRtsSend<50)return;
 const dx=event.clientX-rtsDrag.x,dy=event.clientY-rtsDrag.y;
 rtsDrag.x=event.clientX;rtsDrag.y=event.clientY;lastRtsSend=now;rtsMove('drag',dx,dy);
});
for(const name of ['pointerup','pointercancel','blur'])window.addEventListener(name,()=>{rtsDrag=null;});
setInterval(()=>{document.getElementById('rts-controls').hidden=!window.whiterunRtsActive()||state?.speech?.status==='playing';},250);
setInterval(()=>send({type:'society-ui-health',rts:true,mode:camera,last_input:lastRtsInput,pointer:lastUiPointer,click:lastUiClick,diagnostics:{counts:{...uiInputCounts},last_event_at:lastUiEventAt,last_control_key:lastUiControlKey,document_focused:document.hasFocus(),visibility:document.visibilityState}}),2000);
