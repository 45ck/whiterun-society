let speechAudio=null,speechId=null;
window.whiterunStopSpeech=()=>{if(speechAudio){speechAudio.onended=null;speechAudio.onerror=null;speechAudio.pause();speechAudio=null;}speechId=null;};
window.whiterunSpeak=command=>{
 if(command.id===speechId)return;
 window.whiterunStopSpeech();speechId=command.id;
 const caption=document.getElementById('speech-caption');caption.hidden=false;
 document.getElementById('speech-speaker').textContent=names[command.actor]+' · '+command.tone;
 document.getElementById('speech-line').textContent=command.line;
 const audio=new Audio('audio/'+command.audio.file);speechAudio=audio;audio.volume=1;audio.muted=false;
 const report=(status,extra={})=>send({type:'society-speech',id:command.id,status,...extra});
 audio.onplaying=()=>report('playing');
 audio.onended=()=>{report('ended',{playedSeconds:audio.currentTime,volume:audio.volume,muted:audio.muted});speechAudio=null;};
 audio.onerror=()=>report('failed',{error:'Media error '+(audio.error?.code||'unknown')});
 Promise.resolve().then(()=>applyVoiceOutput(audio)).then(()=>{if(speechId===command.id&&speechAudio===audio)return audio.play();}).catch(error=>report('failed',{error:error.name+': '+error.message}));
};
window.drawConversation=()=>{
 const c=state?.society?.conversation,card=document.getElementById('conversation-card');card.hidden=!c;
 const plan=state?.society?.plan;
 if(plan?.voiced_trade&&!['complete','held'].includes(plan.phase)&&(plan.economic_speech||plan.economic_turns?.length)){
  card.hidden=false;document.getElementById('day-card').hidden=true;document.getElementById('work-card').hidden=true;
  text('conversation-stage','Trade · '+plan.phase.replaceAll('_',' '));
  text('notice',plan.purchase_completed?'Inventory transfer verified':'Offers and agreement are not yet a completed sale');
  const transcript=document.getElementById('conversation-transcript');transcript.replaceChildren();
  for(const turn of plan.economic_turns||[]){const row=document.createElement('div');row.style.marginTop='12px';row.textContent=(names[turn.actor]||'Resident')+': '+turn.line;transcript.append(row);}
  document.getElementById('speech-caption').hidden=plan.phase!=='economic_speaking';return;
 }
 if(!c)return;
 const activePlan=state?.society?.plan&&!['complete','held'].includes(state.society.plan.phase);
 if(['complete','held'].includes(c.phase)&&activePlan){card.hidden=true;document.getElementById('speech-caption').hidden=true;return;}
 document.getElementById('day-card').hidden=true;document.getElementById('work-card').hidden=true;
 const speaking=c.phase==='speaking';
 if(speaking&&!state.camera?.manual){focusId=c.current.speaker;document.getElementById('focus-card').hidden=true;text('camera-label',names[focusId]+' · speaking');}
 document.getElementById('conversation-stage').textContent=c.phase==='complete'?(c.outcome||'Both residents heard and remember').replaceAll('_',' '):c.phase==='held'?'Conversation paused':c.phase==='meeting'?'Walking over to talk':c.phase==='releasing'?'Returning to the day':c.phase.includes('propose')?'Language model: forming intentions':c.phase.includes('select')?'Jev: choosing an intention':c.phase==='synthesize'?'Creating a local voice':c.phase==='speaking'?'Speaking · listening':c.phase.replaceAll('_',' ');
 const transcript=document.getElementById('conversation-transcript');transcript.replaceChildren();
 for(const turn of c.turns){const row=document.createElement('div');row.style.marginTop='12px';const name=document.createElement('strong');name.textContent=names[turn.speaker];name.style.color='var(--gold)';const quote=document.createElement('div');quote.textContent=turn.selected.line;row.append(name,quote);transcript.append(row);}
 text('notice',c.phase==='complete'?(c.outcome==='continued_quietly'?'Continued quietly · no conversation':'An encounter becomes a memory'):c.phase==='held'?c.error:'Living conversation · two residents, different priorities');
 if(c.phase==='complete'||c.phase==='held')document.getElementById('speech-caption').hidden=true;
 if(c.phase==='held'||c.final_phase==='held')window.whiterunStopSpeech();
};
