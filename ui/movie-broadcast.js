/* Save-derived updates for watching the town. No simulated headlines. */
function personalGoalBudget(director){
 const scheduler=director?.goal_scheduler;
 if(!scheduler)return 'Personal decision budget unavailable';
 const count=value=>Number.isInteger(value)&&value>=0?value:null;
 const used=count(director.goal_model_calls),budget=count(scheduler.budget),committed=count(scheduler.budget_committed);
 const pending=used!==null&&committed!==null?Math.max(0,committed-used):null;
 const tally=`Personal decisions: ${used??'—'}/${budget??'—'} calls reported${pending?` · ${pending} reserved or pending`:''}`;
 const reason=scheduler.status==='held'?`Personal goals held; no new personal decisions${scheduler.error?' · '+String(scheduler.error).slice(0,160):' · awaiting fault review'}`:
  scheduler.status==='budget_exhausted'?'Personal decision cap reached; no new personal decisions this session':
  scheduler.status==='running'?'Choosing personal goals':
  scheduler.status==='idle'?(director.running?'Waiting for due personal goals':'Personal scheduling paused'):'Personal scheduling status unavailable';
 return tally+' · '+reason;
}
function dispatchStatus(director){
 const dispatch=director?.dispatch;
 if(!dispatch)return 'Activity dispatch unavailable';
 const count=value=>Number.isInteger(value)&&value>=0?value:'—';
 const wait=Number.isFinite(dispatch.maximum_wait_game_minutes)&&dispatch.maximum_wait_game_minutes>=0?Math.round(dispatch.maximum_wait_game_minutes*10)/10:'—';
 return `Activity dispatch: ${count(dispatch.pending_count)} pending · ${count(dispatch.overdue_count)} overdue · longest wait ${wait} game min`;
}
function movieBroadcastFrames(data){
 const society=data?.society||{},metrics=society.metrics||{},economy=metrics.economy||{};
 const population=Object.keys(society.town?.residents||{}).length;
 const active=x=>x&&!['complete','held','delegated'].includes(x.phase);
 const plan=society.plan,chat=society.conversation,queue=society.town?.daily?.queue||[];
 const name=id=>society.people?.[String(id)]?.profile?.name||'Resident';
 const count=value=>Number.isFinite(value)?String(value):'—';
 const completed=[...queue].reverse().find(e=>e.status==='complete');
 const autonomy=data.dashboard?.autonomy;
 const frames=[
  {title:'Economy in this save',value:`${count(economy.committed_sales)} sales · ${count(economy.committed_production)} production shifts`,detail:'Verified retained outcomes · no estimate of town-wide profit'},
  {title:'Independent lives',value:autonomy?`${autonomy.with_goal}/${autonomy.loaded_population} personal goals · ${autonomy.walking_now} walking`:`${population} residents · ${queue.filter(e=>e.status==='pending').length} decisions queued`,detail:autonomy?`${autonomy.claimed_decisions} decisions claimed · ${autonomy.awaiting_first_goal} awaiting a first goal · ${autonomy.held_goals} held`:`${(data.parallel_routines?.activities||[]).filter(a=>['travelling','walking','requesting'].includes(a.phase)).length} independent journeys observed now · queued does not mean thinking`},
  {title:'Current encounter',value:active(chat)?'Conversation in progress':active(plan)?`${name(plan.actor)} · ${(plan.phase||'').replaceAll('_',' ')}`:'Between encounters',detail:active(chat)?(chat.speakers||[]).map(name).join(' & '):data.director?.running?'Society director running':'Scheduling paused · the camera remains available'},
  {title:'Latest completed activity',value:completed?`${name(completed.actor)} · ${(completed.outcome||completed.kind||'activity').replaceAll('_',' ')}`:'No completed queued activity recorded',detail:'Latest retained activity, not a fabricated live event'}
 ];
 if(data.director?.goal_scheduler)frames[1].detail+=' · '+personalGoalBudget(data.director);
 if(data.director?.dispatch)frames[2].detail+=' · '+dispatchStatus(data.director);
 const spatial=data.dashboard?.spatial;
 const motion=spatial?.current;
 const motionMeasured=Number.isFinite(motion?.observed_moving)&&motion.observed_moving>=0&&Number.isFinite(motion?.observed_stationary)&&motion.observed_stationary>=0&&motion.observed_moving+motion.observed_stationary>0;
 if(spatial)frames.push({title:spatial.fresh?'Observed movement':'Movement · last observation',
  value:`${motionMeasured?count(motion.observed_moving):'—'} moving · ${count(spatial.current?.travel_intentions)} intending to travel`,
  detail:spatial.fresh?`${count(spatial.coverage?.usable_percent)}% usable position coverage · ${count(spatial.samples)} samples · standing can be work, talk or rest`:'Telemetry stale · no present activity inferred'});
 const network=data.dashboard?.economic_network;
 const work=data.dashboard?.owner_work;
 if(work)frames.push({title:work.fresh?'Owner work · measured stages':'Owner work · native telemetry unavailable',
  value:`${count(work.observed_working)} observed working · ${count(work.unmeasured_jobs)} unmeasured · ${count(work.awaiting_commit)} awaiting commit`,
  detail:`${count(work.leased_jobs)}/${count(work.configured_capacity)} work slots reserved · ${count(work.committed_jobs)} linked verified production records; admission and attendance are not output`});
 const activities=data.dashboard?.activity_jobs;
 if(activities){const phases=activities.states||{};
  frames.push({title:activities.fresh?'Concurrent activities':'Concurrent activities · telemetry unavailable',
   value:`${count(activities.background_active)} observed background active · ${count(phases.unmeasured)} unmeasured · ${count(activities.foreground_active)} foreground assignments`,
   detail:`${activities.fresh?count(phases.travelling):'—'} travelling · ${activities.fresh?count(phases.resting):'—'} resting · ${activities.fresh?count(phases.releasing):'—'} releasing · ${count(activities.verified_completions)} verified rests in retained history; admission is not completion`});
 }
 if(network)frames.push({title:'Recorded trade network',value:`${count(network.distinct_participants)} people · ${count(network.directed_trade_links)} trading links`,
  detail:`${count(network.distinct_goods)} labelled goods · ${count(network.known_turnover_septims)} septims turnover · includes controlled trials; not profit`});
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
if(typeof module!=='undefined')module.exports={movieBroadcastFrames,renderMovieBroadcast,personalGoalBudget,dispatchStatus};
if(typeof window!=='undefined'){window.renderMovieBroadcast=renderMovieBroadcast;window.personalGoalBudget=personalGoalBudget;window.dispatchStatus=dispatchStatus;}
