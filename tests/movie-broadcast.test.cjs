const test=require('node:test'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const {movieBroadcastFrames,renderMovieBroadcast}=require('../ui/movie-broadcast.js');
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
