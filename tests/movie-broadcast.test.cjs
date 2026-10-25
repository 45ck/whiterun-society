const test=require('node:test'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const {movieBroadcastFrames,renderMovieBroadcast,personalGoalBudget}=require('../ui/movie-broadcast.js');
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
