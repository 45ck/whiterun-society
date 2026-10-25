/* Save-derived updates for watching the town. No simulated headlines. */
function movieBroadcastFrames(data){
 const society=data?.society||{},metrics=society.metrics||{},economy=metrics.economy||{};
 const population=Object.keys(society.town?.residents||{}).length;
 const active=x=>x&&!['complete','held'].includes(x.phase);
 const plan=society.plan,chat=society.conversation,queue=society.town?.daily?.queue||[];
 const name=id=>society.people?.[String(id)]?.profile?.name||'Resident';
 const count=value=>Number.isFinite(value)?String(value):'—';
 const completed=[...queue].reverse().find(e=>e.status==='complete');
 const frames=[
  {title:'Economy in this save',value:`${count(economy.committed_sales)} sales · ${count(economy.committed_production)} production shifts`,detail:'Verified retained outcomes · no estimate of town-wide profit'},
  {title:'Independent lives',value:`${population} residents · ${queue.filter(e=>e.status==='pending').length} decisions queued`,detail:`${(data.parallel_routines?.activities||[]).filter(a=>['travelling','walking','requesting'].includes(a.phase)).length} independent journeys observed now · queued does not mean thinking`},
  {title:'Current encounter',value:active(chat)?'Conversation in progress':active(plan)?`${name(plan.actor)} · ${(plan.phase||'').replaceAll('_',' ')}`:'Between encounters',detail:active(chat)?(chat.speakers||[]).map(name).join(' & '):data.director?.running?'Society director running':'Scheduling paused · the camera remains available'},
  {title:'Latest completed activity',value:completed?`${name(completed.actor)} · ${(completed.outcome||completed.kind||'activity').replaceAll('_',' ')}`:'No completed queued activity recorded',detail:'Latest retained activity, not a fabricated live event'}
 ];
 return frames;
}
function renderMovieBroadcast(root,data,now=Date.now()){
 if(!root)return;
 const movie=data?.camera?.manual===false||data?.camera?.mode==='story';root.hidden=!movie;
 if(!movie)return;
 const frames=movieBroadcastFrames(data),index=Math.floor(now/12000)%frames.length,frame=frames[index];
 const title=root.querySelector('[data-broadcast-title]'),value=root.querySelector('[data-broadcast-value]'),detail=root.querySelector('[data-broadcast-detail]');
 title.textContent=frame.title;value.textContent=frame.value;
 detail.textContent=frame.detail+` · ${index+1}/${frames.length}`;
}
if(typeof module!=='undefined')module.exports={movieBroadcastFrames,renderMovieBroadcast};
if(typeof window!=='undefined')window.renderMovieBroadcast=renderMovieBroadcast;
