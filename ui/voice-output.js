// Select a permitted output without requesting microphone access or changing Windows defaults.
let voiceSink='',voiceOutputLabel='Windows default',voiceOutputError=null;
try{voiceSink=localStorage.getItem('whiterun-voice-output')||'';}catch(_){}
function reportVoiceOutput(extra={}){send({type:'society-audio-output',label:voiceOutputLabel,error:voiceOutputError,supported:typeof HTMLMediaElement.prototype.setSinkId==='function',...extra});}
async function refreshVoiceOutputs(){
 const select=document.getElementById('voice-output'),status=document.getElementById('voice-output-status');
 select.replaceChildren();const add=(id,label)=>{const option=document.createElement('option');option.value=id;option.textContent=label;select.append(option);};add('','Windows default');
 const supported=typeof HTMLMediaElement.prototype.setSinkId==='function';select.disabled=!supported;
 try{
  const devices=await navigator.mediaDevices?.enumerateDevices?.()||[];
  for(const device of devices.filter(d=>d.kind==='audiooutput'&&!['default','communications'].includes(d.deviceId)))add(device.deviceId,device.label||'Permitted output '+select.options.length);
  if(!Array.from(select.options).some(o=>o.value===voiceSink)){voiceSink='';try{localStorage.removeItem('whiterun-voice-output');}catch(_){}voiceOutputError='Saved output unavailable; using Windows default';}
  select.value=voiceSink;voiceOutputLabel=select.selectedOptions[0].textContent;
  const defaultDevice=devices.find(d=>d.kind==='audiooutput'&&d.deviceId==='default');
  if(!voiceSink&&defaultDevice?.label)voiceOutputLabel=defaultDevice.label;
  status.textContent=voiceOutputError||voiceOutputLabel+(supported?' · applies to next voice':' · output selection unavailable in this overlay');
 }catch(error){voiceOutputError='Output discovery unavailable: '+error.name;status.textContent=voiceOutputError;}
 reportVoiceOutput();
}
async function applyVoiceOutput(audio){
 if(typeof audio.setSinkId==='function')await audio.setSinkId(voiceSink);
 else if(voiceSink)throw Error('Selected voice output is unsupported');
 reportVoiceOutput({status:'routed'});
}
document.getElementById('voice-output').onchange=event=>{
 voiceSink=event.target.value;voiceOutputError=null;voiceOutputLabel=event.target.selectedOptions[0].textContent;
 try{localStorage.setItem('whiterun-voice-output',voiceSink);}catch(_){}
 document.getElementById('voice-output-status').textContent=voiceOutputLabel+' · applies to next voice';reportVoiceOutput();
};
const chooseOutput=document.getElementById('voice-output-choose');chooseOutput.hidden=typeof navigator.mediaDevices?.selectAudioOutput!=='function';
chooseOutput.onclick=async()=>{try{const device=await navigator.mediaDevices.selectAudioOutput();voiceSink=device.deviceId;voiceOutputError=null;try{localStorage.setItem('whiterun-voice-output',voiceSink);}catch(_){}await refreshVoiceOutputs();}catch(error){voiceOutputError='Output selection: '+error.name;document.getElementById('voice-output-status').textContent=voiceOutputError;reportVoiceOutput();}};
navigator.mediaDevices?.addEventListener?.('devicechange',()=>refreshVoiceOutputs());
refreshVoiceOutputs();
let voiceTestAudio=null;
window.whiterunTestVoice=async(id='manual-'+Date.now())=>{
 const status=document.getElementById('voice-output-status');
 if(voiceTestAudio||speechAudio){status.textContent='Wait for the current voice to finish';return;}
 const audio=new Audio('voice-check.wav');voiceTestAudio=audio;audio.volume=1;audio.muted=false;
 const report=(phase,error=null)=>reportVoiceOutput({test:{id,status:phase,error,playedSeconds:audio.currentTime||0,volume:audio.volume,muted:audio.muted}});
 const finish=(phase,error)=>{voiceTestAudio=null;document.getElementById('voice-output-test').disabled=false;status.textContent=error||'Audio check finished · saved sample, no resident event';report(phase,error);};
 document.getElementById('voice-output-test').disabled=true;status.textContent='Audio check · saved voice sample, no resident event';
 audio.onplaying=()=>report('playing');audio.onended=()=>finish('ended');audio.onerror=()=>finish('failed','Audio check media error');
 try{await applyVoiceOutput(audio);await audio.play();}catch(error){finish('failed',error.name+': '+error.message);}
};
document.getElementById('voice-output-test').onclick=()=>window.whiterunTestVoice();
