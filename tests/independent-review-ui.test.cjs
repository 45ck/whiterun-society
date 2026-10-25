const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const {independentReviewMetrics,independentReviewLabel,renderIndependentReview,renderIndependentReviewMetrics}=require('../ui/society-dashboard.js');
const read=name=>fs.readFileSync(path.join(__dirname,'../ui',name),'utf8');
const review=changes=>({event_id:'review-7',actor:7,actor_base_id:70,actor_name:'Resident Seven',session:'save-session',wave_id:'wave-1',claim_id:'claim-7',action_id:'rest_at_bench',plan_id:'plan-7',job_id:'job-7',job_kind:'rest',status:'delegated',native_required:true,source_linked:true,plan_linked:true,job_linked:true,inference_active:null,stages:{waiting:false,claimed:true,accepted:true,delegated:true,native_attending:false,settled:false,held:false,handoff:false,quiet:false},provenance:'resident_model_choice',...changes});
function card(row,fresh=true){const dom=new JSDOM('<main></main>'),root=dom.window.document.querySelector('main');renderIndependentReview(root,row,fresh);return {dom,root};}
const stage=(root,label)=>[...root.querySelectorAll('dt')].find(node=>node.textContent===label).nextElementSibling.textContent;
test('saved requests are not active inference and delegation is not settlement',()=>{
 assert.equal(independentReviewLabel(review({status:'waiting'}),true),'Waiting in the review queue');
 assert.equal(independentReviewLabel(review({status:'claimed'}),true),'Decision request claimed · worker activity unmeasured');
 assert.equal(independentReviewLabel(review({status:'claimed',inference_active:false}),true),'Decision request claimed · inference not active');
 assert.equal(independentReviewLabel(review({status:'claimed',inference_active:true}),true),'Model inference active');
 assert.equal(independentReviewLabel(review(),true),'Native task delegated · outcome pending');
 const {dom,root}=card(review());try{assert.equal(stage(root,'Decision accepted'),'Recorded');assert.equal(stage(root,'Delegated native task'),'Recorded');assert.equal(stage(root,'Settlement'),'Not recorded');assert.match(root.textContent,/not a completed economic effect/);}finally{dom.window.close();}
});
test('resident trace preserves event, claim, action, plan and job links without exposing private reasoning',()=>{
 const {dom,root}=card(review({private_reason:'PRIVATE_REASONS',context:{secret:'PRIVATE_CONTEXT'}}));try{
 for(const expected of ['review-7','claim-7','rest at bench','plan-7','job-7','wave-1','save-session','Bound actor base: 70'])assert.ok(root.textContent.includes(expected));
 assert.match(root.textContent,/Source event linkage: verified/);assert.match(root.textContent,/Delegated job linkage: verified/);assert.doesNotMatch(root.textContent,/PRIVATE_REASONS|PRIVATE_CONTEXT/);
 }finally{dom.window.close();}
});
test('quiet choices and foreground handoffs remain valid non-native outcomes',()=>{
 for(const status of ['quiet','handoff']){const {dom,root}=card(review({status,native_required:false,action_id:status==='quiet'?'defer':'foreground_review',job_id:null,job_linked:null,stages:{quiet:status==='quiet',handoff:status==='handoff',accepted:true,delegated:false,settled:false}}));try{
 assert.match(root.textContent,/No native task is required by this decision/);assert.match(root.textContent,/not failed work/);assert.equal(stage(root,'Delegated native task'),'Not recorded');assert.equal(stage(root,'Settlement'),'Not recorded');assert.equal(root.querySelector('progress'),null);
 if(status==='handoff')assert.match(root.textContent,/Foreground review owns the next decision/);
 }finally{dom.window.close();}}
});
test('stale native attendance becomes unknown while saved accepted decision evidence remains visible',()=>{
 const {dom,root}=card(review({status:'native_attending',stages:{accepted:true,native_attending:true}}),false);try{
 assert.match(root.textContent,/Native attendance unmeasured · observation stale/);assert.equal(stage(root,'Native attendance'),'Unknown');assert.equal(stage(root,'Decision accepted'),'Recorded');
 }finally{dom.window.close();}
});
test('summary shows state counts and unknowns without human realism or progress scores',()=>{
 const dom=new JSDOM('<main></main>'),root=dom.window.document.querySelector('main');try{
 renderIndependentReviewMetrics(root,{measured:true,fresh:false,counts:{waiting:3,claimed:2,native_attending:8,quiet:1,handoff:1,unmeasured:4},reviews:[]});
 const tile=label=>[...root.querySelectorAll('.town-stock')].find(node=>node.querySelector('span').textContent===label).querySelector('strong').textContent;
 assert.equal(tile('Queued'),'3');assert.equal(tile('Requests claimed'),'2');assert.equal(tile('Native attendance observed'),'—');assert.equal(tile('Linked settlements'),'—');assert.match(root.textContent,/4 reviews with unmeasured status/);assert.doesNotMatch(root.textContent,/\d+%|Model inference active/);
 root.replaceChildren();renderIndependentReviewMetrics(root,{measured:false,counts:{waiting:0},reviews:[review()]});assert.match(root.textContent,/Unmeasured/);assert.equal(root.querySelectorAll('[data-independent-review]').length,0);
 }finally{dom.window.close();}
});
test('unverified links and hostile identifiers stay text and unknown proof stays unknown',()=>{
 const {dom,root}=card(review({actor_name:'<img src=x>',event_id:'<script>event</script>',source_linked:false,plan_linked:null,job_linked:null,stages:{accepted:'true'}}));try{
 assert.equal(stage(root,'Decision accepted'),'Unknown');assert.match(root.textContent,/Source event linkage: not verified/);assert.match(root.textContent,/Accepted plan linkage: unknown/);assert.equal(root.querySelector('img'),null);assert.equal(root.querySelector('script'),null);
 }finally{dom.window.close();}
});
test('link denominators and missing admission clocks remain explicit without converting queue time into model latency',()=>{
 const dom=new JSDOM('<main></main>'),root=dom.window.document.querySelector('main');try{
 renderIndependentReviewMetrics(root,{measured:true,fresh:true,counts:{},reviews:[],coverage:{claims:{success:2,n:3,unknown:1,eligible:4}},latency:{claim_to_result_seconds:{n:2,eligible:3,unknown:1,median:8,p95:9},result_to_native_admission_seconds:{n:0,eligible:2,unknown:2,median:null,p95:null},result_to_native_admission_game_minutes:{n:2,eligible:2,unknown:0,median:1,p95:2}},timing_scope:'Claim-to-result includes queue time; not pure inference latency.'});
 assert.match(root.textContent,/Decision claims: 2 linked \/ 3 assessed · 1 unknown \/ 4 eligible/);assert.match(root.textContent,/Claim to recorded result: 8 median \/ 9 p95 wall seconds · 2 timed \/ 3 eligible · 1 missing/);assert.match(root.textContent,/Result to native admission: — median \/ — p95 wall seconds · 0 timed \/ 2 eligible · 2 missing/);assert.match(root.textContent,/1 median \/ 2 p95 game minutes/);assert.match(root.textContent,/includes queue time/);
 }finally{dom.window.close();}
});
function native(){const dom=new JSDOM(read('index.html'),{runScripts:'outside-only',url:'https://local.invalid/'}),w=dom.window;w.setInterval=()=>1;w.skyrimPlatform={sendMessage(){}};for(const script of w.document.scripts)vm.runInContext(script.src?read(path.basename(script.src)):script.textContent,dom.getInternalVMContext());return {dom,w};}
test('native resident inspector shows only that resident’s independent follow-through without requiring a foreground plan',()=>{
 const {dom,w}=native();try{const person={profile:{name:'Resident Seven',big_five:{}},needs:{hunger:.2},memories:[]};const metric={measured:true,fresh:true,counts:{delegated:1},reviews:[review(),review({actor:8,event_id:'other-private-trace'})]};
 w.whiterunRender({residents:[{id:7,name:'Resident Seven',isPerson:true,inventory:{gold:5}}],trades:[],society:{people:{7:person},town:{residents:{7:{name:'Resident Seven'}}}},independent_review_metrics:metric});
 w.whiterunInspectKey(2);const panel=w.document.getElementById('resident-inspector');assert.match(panel.textContent,/Native task delegated · outcome pending/);assert.match(panel.textContent,/job-7/);assert.doesNotMatch(panel.textContent,/other-private-trace/);assert.equal(stage(panel,'Settlement'),'Not recorded');
 assert.equal(independentReviewMetrics({dashboard:{independent_review_metrics:metric}}),metric);
 }finally{dom.window.close();}
});
