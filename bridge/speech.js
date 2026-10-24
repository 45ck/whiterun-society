// Audio travels through the in-game overlay, independently of Skyrim's mixer.
// No lip-sync claim: head look and speaker captions are presentation only.
function createSpeechController(getSp, now=()=>Date.now()) {
  let active=null,report=null,started=0,pendingMessage=null;
  function stop(){const sp=getSp(),previous=active;active=null;
    if(sp.browser)sp.browser.executeJavaScript('window.whiterunStopSpeech && window.whiterunStopSpeech();');
    if(previous){for(const id of [previous.actor,previous.target]){try{const a=sp.Actor.from(sp.Game.getFormEx(id));if(a&&a.is3DLoaded()&&a.clearLookAt)a.clearLookAt();}catch(_){if(report)report.lookCleanupUnverified=true;}}}}
  function nearby(c){const sp=getSp(),a=sp.Actor.from(sp.Game.getFormEx(c.actor)),b=sp.Actor.from(sp.Game.getFormEx(c.target));
    if(!a||!b||!a.is3DLoaded()||!b.is3DLoaded()||a.isDead()||b.isDead())return false;
    return Math.hypot(a.getPositionX()-b.getPositionX(),a.getPositionY()-b.getPositionY(),a.getPositionZ()-b.getPositionZ())<=500;}
  function fail(error){report={...report,status:'failed',error:String(error).slice(0,180)};stop();}
  function sampleOrientation(){
    if(!active)return;
    const sp=getSp(),a=sp.Actor.from(sp.Game.getFormEx(active.actor)),b=sp.Actor.from(sp.Game.getFormEx(active.target));
    for(const [first,second] of [[a,b],[b,a]]){
      try{
        if(!first?.is3DLoaded()||!second?.is3DLoaded()||typeof first.getAngleZ!=='function')continue;
        const dx=second.getPositionX()-first.getPositionX(),dy=second.getPositionY()-first.getPositionY(),yaw=first.getAngleZ();
        if(!Number.isFinite(yaw)||!Number.isFinite(dx)||!Number.isFinite(dy)||Math.hypot(dx,dy)<1)continue;
        const bearing=Math.atan2(dx,dy)*180/Math.PI,error=Math.abs(((yaw-bearing)%360+540)%360-180);
        const o=report.orientation;o.samples++;o.sum_error_degrees+=error;o.max_error_degrees=Math.max(o.max_error_degrees,error);
      }catch(_){} // Missing geometry is unknown, never perfect accuracy.
    }
  }
  return {
    start(c){
      if(report?.id===c.id)return; // Retransmitted command is never a replay.
      if(active)throw new Error('Another voice is active');
      if(!/^speech-[a-f0-9]{24}$/.test(c.id)||!/^([a-f0-9]{64})\.wav$/.test(c.audio?.file)||c.audio.file!==c.audio.sha256+'.wav')throw new Error('Invalid audio identity');
      const sp=getSp();report={id:c.id,status:'starting',nearbyThroughout:nearby(c),playedSeconds:0,
        orientation:{samples:0,sum_error_degrees:0,max_error_degrees:0,measurement:'body yaw towards partner, not head/eye gaze or raycast'}};
      if(!report.nearbyThroughout||!sp.browser)return fail('No nearby listener or overlay');
      active=c;started=now();
      const a=sp.Actor.from(sp.Game.getFormEx(c.actor)),b=sp.Actor.from(sp.Game.getFormEx(c.target));
      a.setLookAt(b,false);b.setLookAt(a,false);
      report.facing=[];
      for(const [first,second,id] of [[a,b,c.actor],[b,a,c.target]]){
        let rotated=false;
        try{if(first.getSitState&&first.getSitState()===0&&first.setAngle){
          first.setAngle(0,0,(Math.atan2(second.getPositionX()-first.getPositionX(),second.getPositionY()-first.getPositionY())*180/Math.PI+360)%360);rotated=true;
        }}catch(_){}
        report.facing.push({actor:id,headLookRequested:true,bodyTurnRequested:rotated});
      }
      sp.browser.executeJavaScript('window.whiterunSpeak && window.whiterunSpeak('+JSON.stringify({id:c.id,actor:c.actor,line:c.line,tone:c.tone,audio:c.audio})+');');
    },
    message(m){if(active&&m.id===active.id)pendingMessage=m;},
    applyMessage(m){
      if(!active||m.id!==active.id||!['playing','ended','failed'].includes(m.status))return;
      if(m.status==='failed')return fail(m.error||'Overlay audio failed');
      if(m.status==='playing'){report.status='playing';return;}
      const elapsed=(now()-started)/1000;
      if(!Number.isFinite(m.playedSeconds)||m.playedSeconds<active.audio.seconds-.3||elapsed<active.audio.seconds-.5)return fail('Premature audio completion');
      report={...report,status:'ended',playedSeconds:m.playedSeconds,elapsedSeconds:elapsed,
        channel:'CEF overlay audio',muted:m.muted===true,volume:m.volume};
      if(report.muted||m.volume!==1)return fail('Playback was muted or attenuated');
      stop();
    },
    tick(){sampleOrientation();if(pendingMessage){const m=pendingMessage;pendingMessage=null;this.applyMessage(m);}if(!active)return;if(!nearby(active)){report.nearbyThroughout=false;return fail('Listener left hearing range');}
      if(now()-started>(active.audio.seconds+15)*1000)fail('Overlay playback timed out');},
    reset(){stop();report=null;pendingMessage=null;}, status(){return report?{...report}:null;},
    actor(){return active?.actor||null;}
  };
}
if(typeof module!=='undefined')module.exports={createSpeechController};
