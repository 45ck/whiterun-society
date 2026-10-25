const test=require('node:test'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const {movieBroadcastFrames,renderMovieBroadcast,personalGoalBudget,dispatchStatus}=require('../ui/movie-broadcast.js');

test('dispatch exposes queue starvation with game-time units and preserves unknowns',()=>{
 assert.equal(dispatchStatus({}),'Activity dispatch unavailable');
 assert.match(dispatchStatus({dispatch:{}}),/— pending · — overdue · longest wait — game min/);
 assert.match(dispatchStatus({dispatch:{pending_count:0,overdue_count:0,maximum_wait_game_minutes:0}}),/0 pending · 0 overdue · longest wait 0 game min/);
 const director={running:true,dispatch:{pending_count:9,overdue_count:3,maximum_wait_game_minutes:42.25}};
 const frame=movieBroadcastFrames({director})[2];
 assert.match(frame.detail,/9 pending · 3 overdue · longest wait 42.3 game min/);
 assert.doesNotMatch(frame.detail,/thinking|productive/);
 assert.match(dispatchStatus({dispatch:{pending_count:-1,overdue_count:null,maximum_wait_game_minutes:NaN}}),/— pending · — overdue · longest wait — game min/);
});

test('movie separates delegated background work from foreground and retained verified completion',()=>{
 const data={society:{plan:{id:'delegated',actor:7,phase:'delegated'}},dashboard:{activity_jobs:{fresh:true,background_active:2,foreground_active:0,states:{travelling:1,resting:1,releasing:0},verified_completions:0}}};
 let frames=movieBroadcastFrames(data),frame=frames.find(f=>f.title==='Concurrent activities');
 assert.equal(frames[2].value,'Between encounters');
 assert.match(frame.value,/2 observed background active · — unmeasured · 0 foreground assignments/);assert.match(frame.detail,/1 travelling · 1 resting · 0 releasing · 0 verified rests/);
 assert.match(frame.detail,/admission is not completion/);
 data.dashboard.activity_jobs.fresh=false;data.dashboard.activity_jobs.background_active=null;
 frame=movieBroadcastFrames(data).find(f=>f.title.includes('telemetry unavailable'));
 assert.match(frame.value,/— observed background active/);assert.match(frame.detail,/— travelling · — resting · — releasing/);
});

test('movie explicitly identifies unmeasured leases when only part of background activity is observed',()=>{
 const frame=movieBroadcastFrames({dashboard:{activity_jobs:{fresh:true,leased_jobs:2,native_matched_jobs:1,background_active:1,foreground_active:1,states:{travelling:0,resting:1,releasing:0,unmeasured:1},verified_completions:0}}}).find(f=>f.title==='Concurrent activities');
 assert.equal(frame.value,'1 observed background active · 1 unmeasured · 1 foreground assignments');
 assert.match(frame.detail,/1 resting/);
});

test('owner work movie frame keeps attendance, uncovered leases and journal production separate',()=>{
 const work={fresh:true,configured_capacity:4,leased_jobs:2,observed_working:1,unmeasured_jobs:1,awaiting_commit:0,committed_jobs:0};
 let frame=movieBroadcastFrames({dashboard:{owner_work:work}}).find(f=>f.title==='Owner work · measured stages');
 assert.equal(frame.value,'1 observed working · 1 unmeasured · 0 awaiting commit');
 assert.match(frame.detail,/2\/4 work slots reserved · 0 linked verified production records/);
 assert.match(frame.detail,/admission and attendance are not output/);
 work.fresh=false;work.observed_working=null;
 frame=movieBroadcastFrames({dashboard:{owner_work:work}}).find(f=>f.title==='Owner work · native telemetry unavailable');
 assert.match(frame.value,/— observed working/);
});
test('movie updates distinguish unknown economics, queued work and observed activity',()=>{
 const data={society:{town:{residents:{7:{},8:{}},daily:{queue:[{actor:7,status:'pending'},{actor:8,status:'complete',outcome:'ate_bread'}]}},people:{8:{profile:{name:'Resident B'}}}},parallel_routines:{activities:[{phase:'travelling'},{phase:'complete'}]}};
 const frames=movieBroadcastFrames(data);
 assert.match(frames[0].value,/— sales/);assert.match(frames[1].value,/2 residents · 1 decisions queued/);
 assert.match(frames[1].detail,/1 independent journeys observed/);assert.match(frames[3].value,/Resident B · ate bread/);
 assert.match(frames[2].detail,/Scheduling paused/);
});
test('movie statistics cycle every twelve seconds and disappear during manual control',()=>{
 const dom=new JSDOM('<aside><div data-broadcast-title></div><div data-broadcast-value></div><div data-broadcast-detail></div></aside>');
 try{const root=dom.window.document.querySelector('aside'),data={camera:{manual:false},society:{metrics:{economy:{committed_sales:2,committed_production:1}}}};
 renderMovieBroadcast(root,data,0);assert.equal(root.hidden,false);assert.match(root.textContent,/2 sales · 1 production shifts/);
 renderMovieBroadcast(root,data,12000);assert.match(root.textContent,/Independent lives/);
 renderMovieBroadcast(root,{camera:{mode:'free',manual:true}},24000);assert.equal(root.hidden,true);
 }finally{dom.window.close();}
});

test('movie movement and trade cards distinguish stale measurements and controlled economic receipts',()=>{
 const data={dashboard:{spatial:{fresh:false,current:{observed_moving:3,observed_stationary:2,travel_intentions:8},samples:5,coverage:{usable_percent:40}},economic_network:{distinct_participants:4,directed_trade_links:2,distinct_goods:1,known_turnover_septims:null}}};
 const frames=movieBroadcastFrames(data),movement=frames.find(f=>f.title.startsWith('Movement')),trade=frames.find(f=>f.title==='Recorded trade network');
 assert.match(movement.value,/3 moving · 8 intending/);assert.match(movement.detail,/no present activity inferred/);
 assert.match(trade.detail,/— septims turnover/);assert.match(trade.detail,/includes controlled trials; not profit/);
});

test('initial paused and excluded position samples do not fabricate measured zero movement',()=>{
 for(const current of [{observed_moving:0,observed_stationary:0},{observed_moving:0},{observed_stationary:2},{}]){
  const frame=movieBroadcastFrames({dashboard:{spatial:{fresh:true,current:{...current,travel_intentions:5},samples:1,coverage:{usable_percent:0}}}}).find(f=>f.title==='Observed movement');
  assert.match(frame.value,/— moving · 5 intending/);
 }
 const frame=movieBroadcastFrames({dashboard:{spatial:{fresh:true,current:{observed_moving:0,observed_stationary:3,travel_intentions:5},samples:2,coverage:{usable_percent:100}}}}).find(f=>f.title==='Observed movement');
 assert.match(frame.value,/0 moving · 5 intending/);
});

test('personal budget counts keep pending reservations distinct from reported calls and unknowns',()=>{
 assert.equal(personalGoalBudget({}), 'Personal decision budget unavailable');
 assert.match(personalGoalBudget({running:true,goal_scheduler:{status:'idle',budget:64}}),/—\/64 calls reported/);
 const text=personalGoalBudget({running:true,goal_model_calls:26,goal_scheduler:{status:'running',budget:64,budget_committed:40}});
 assert.match(text,/26\/64 calls reported · 14 reserved or pending/);assert.match(text,/Choosing personal goals/);
});

test('personal cap and held notices never replace independently observed journey counts',()=>{
 for(const [status,phrase] of [['held',/goals held; no new personal decisions/],['budget_exhausted',/cap reached; no new personal decisions this session/]]){
  const frame=movieBroadcastFrames({director:{running:true,goal_model_calls:64,goal_scheduler:{status,budget:64,budget_committed:64,error:status==='held'?'Claim receipt missing':undefined}},dashboard:{autonomy:{with_goal:20,loaded_population:29,walking_now:7,claimed_decisions:0,awaiting_first_goal:0,held_goals:1}}})[1];
  assert.match(frame.value,/20\/29 personal goals · 7 walking/);assert.match(frame.detail,phrase);assert.match(frame.detail,/64\/64 calls reported/);
  assert.doesNotMatch(frame.detail,/all models|all activity|all journeys/);
 }
});
