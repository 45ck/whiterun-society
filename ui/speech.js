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
 audio.play().catch(error=>report('failed',{error:error.name+': '+error.message}));
};
window.drawConversation=()=>{
 const c=state?.society?.conversation,card=document.getElementById('conversation-card');card.hidden=!c;
 if(!c)return;
 document.getElementById('day-card').hidden=true;document.getElementById('work-card').hidden=true;
 const speaking=c.phase==='speaking';
 if(speaking){camera='focus';focusId=c.current.speaker;document.getElementById('focus-card').hidden=true;text('camera-label',names[focusId]+' · speaking');}
 document.getElementById('conversation-stage').textContent=c.phase==='complete'?'Both residents heard and remember':c.phase==='held'?'Conversation paused':c.phase==='meeting'?'Walking over to talk':c.phase==='releasing'?'Returning to the day':c.phase.includes('propose')?'Language model: forming intentions':c.phase.includes('select')?'Jev: choosing an intention':c.phase==='synthesize'?'Creating a local voice':'Speaking · listening';
 const transcript=document.getElementById('conversation-transcript');transcript.replaceChildren();
 for(const turn of c.turns){const row=document.createElement('div');row.style.marginTop='12px';const name=document.createElement('strong');name.textContent=names[turn.speaker];name.style.color='var(--gold)';const quote=document.createElement('div');quote.textContent=turn.selected.line;row.append(name,quote);transcript.append(row);}
 text('notice',c.phase==='complete'?'A conversation becomes a memory':c.phase==='held'?c.error:'Living conversation · two residents, different priorities');
 if(c.phase==='complete'||c.phase==='held')document.getElementById('speech-caption').hidden=true;
 if(c.phase==='held'||c.final_phase==='held')window.whiterunStopSpeech();
};
