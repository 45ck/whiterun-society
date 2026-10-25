const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const {paidEmploymentLabel,paidEmploymentJobs,renderPaidEmploymentJob,renderPaidEmploymentMetrics,employmentConcurrencyForJob,renderEmploymentConcurrency}=require('../ui/society-dashboard.js');
const read=name=>fs.readFileSync(path.join(__dirname,'../ui',name),'utf8');
const stages=changes=>({offered:true,accepted:true,attendance_qualified:false,output_verified:false,wage_paid:false,completed:false,released:false,held:false,...changes});
const job=changes=>({id:'job-1',worker:7,employer:8,worker_name:'Worker One',employer_name:'Employer Two',recipe_id:'metal_recipe',wage_gold:5,work_minutes:20,phase:'attending',stages:stages(),...changes});
function card(value,concurrency){const dom=new JSDOM('<main></main>'),root=dom.window.document.querySelector('main');renderPaidEmploymentJob(root,value,{commodity_labels:{ore:'Copper ore',ingot:'Copper ingot'}},concurrency);return {dom,root};}
function proof(root,label){return [...root.querySelectorAll('dt')].find(e=>e.textContent===label).nextElementSibling.textContent;}
test('paid employment stages distinguish attendance, output, wages, completion and release',()=>{
 assert.equal(paidEmploymentLabel(job()),'Accepted contract · attendance not yet qualified');
 assert.equal(paidEmploymentLabel(job({stages:stages({attendance_qualified:true})})),'Attendance qualified · settlement not verified');
 assert.equal(paidEmploymentLabel(job({stages:stages({output_verified:true})})),'Output verified · wage transfer not verified');
 assert.equal(paidEmploymentLabel(job({stages:stages({wage_paid:true})})),'Wage transfer verified · output not verified');
 assert.equal(paidEmploymentLabel(job({stages:stages({completed:true})})),'Contract completed · release not verified');
 assert.equal(paidEmploymentLabel(job({stages:stages({completed:true,released:true})})),'Contract completed · release verified');
 assert.match(paidEmploymentLabel(job({stages:stages({output_verified:true,held:true})})),/held · inspect each effect separately/);
});
test('job card keeps frozen exact terms and shows output without asserting an unpaid wage',()=>{
 const {dom,root}=card(job({recipe:{status:'verified',inputs:{ore:2},outputs:{ingot:1}},stages:stages({attendance_qualified:true,output_verified:true,held:true}),held_reason:'Wage credit witness missing'}));try{
 assert.match(root.textContent,/Worker Worker One · employer Employer Two/);assert.match(root.textContent,/Agreed wage 5 septims · 20 game minutes/);assert.match(root.textContent,/2 Copper ore → 1 Copper ingot/);
 assert.equal(proof(root,'Output verified'),'Yes · recorded proof');assert.equal(proof(root,'Wage transfer verified'),'Not verified');assert.equal(proof(root,'Contract completed'),'Not verified');assert.match(root.textContent,/Wage credit witness missing/);assert.equal(root.querySelector('progress'),null);
 }finally{dom.window.close();}
});
test('phase complete, balances, and string booleans cannot manufacture evidence',()=>{
 const {dom,root}=card(job({phase:'complete',stages:{wage_paid:'true'},inventory:{worker:{gold:999}},wage_gold:null,work_minutes:null}));try{
 assert.equal(proof(root,'Wage transfer verified'),'Unknown');assert.equal(proof(root,'Contract completed'),'Unknown');assert.match(root.textContent,/Proposed wage — septims · — game minutes/);assert.doesNotMatch(root.textContent,/999|Yes · recorded proof/);
 }finally{dom.window.close();}
 assert.deepEqual(paidEmploymentJobs({paid_employment:{jobs:[job()]}}),[],'raw saved/native jobs do not substitute for metrics proof');
 assert.deepEqual(paidEmploymentJobs({paid_employment_metrics:{measured:false,jobs:[job()]}}),[]);
});
test('quantitative stage ledger shows assessed and unknown samples without an overall success score',()=>{
 const dom=new JSDOM('<main></main>'),root=dom.window.document.querySelector('main');try{
 renderPaidEmploymentMetrics(root,{measured:true,retained_jobs:3,stages:{offered:{success:3,n:3,unknown:0,percent:100},wage_paid:{success:1,n:2,unknown:1,percent:50}},jobs:[],scope:'Retained evidence only'});
 const tiles=[...root.querySelectorAll('.town-stock')],wage=tiles.find(t=>t.textContent.includes('Wage transfer verified'));assert.equal(wage.querySelector('strong').textContent,'1');assert.match(wage.textContent,/2 assessed · 1 unknown/);assert.match(root.textContent,/3 retained jobs/);assert.doesNotMatch(root.textContent,/50%|100%|realism score/);
 root.replaceChildren();renderPaidEmploymentMetrics(root,{measured:false,retained_jobs:0,stages:{},jobs:[job()]});assert.match(root.textContent,/Unmeasured/);assert.equal(root.querySelectorAll('.town-stock').length,0);assert.equal(root.querySelectorAll('[data-paid-employment-job]').length,0);
 }finally{dom.window.close();}
});
test('held reasons and resident labels render as text',()=>{
 const {dom,root}=card(job({worker_name:'<img src=x>',held_reason:'<script>unsafe</script>'}));try{assert.equal(root.querySelector('img'),null);assert.equal(root.querySelector('script'),null);assert.match(root.textContent,/<img src=x>/);}finally{dom.window.close();}
});
test('current v2 capability is independent of legacy status, missing observations and stale availability',()=>{
 const dom=new JSDOM('<main></main>'),root=dom.window.document.querySelector('main');try{
 for(const [capability,expected] of [[undefined,'unknown'],[{fresh:false,available:true,protocol:2},'unknown'],[{fresh:true,available:true,protocol:1},'unknown'],[{fresh:true,available:true,protocol:2},'available'],[{fresh:true,available:false,protocol:2},'unavailable']]){root.replaceChildren();renderPaidEmploymentMetrics(root,{measured:false,capability});assert.equal(root.querySelector('[data-paid-executor]').dataset.paidExecutor,expected);assert.match(root.textContent,/Unmeasured/);}
 }finally{dom.window.close();}
});
test('partial wage legs, unsatisfied journal settlement and missing timing samples stay explicit',()=>{
 const dom=new JSDOM('<main></main>'),root=dom.window.document.querySelector('main');try{
 renderPaidEmploymentMetrics(root,{measured:true,retained_jobs:2,stages:{},jobs:[],partial_effects:{output_verified_without_commit:1,wage_debit_without_verified_credit:1,wages_verified_without_commit:0,observed_output_goods:{ingot:2}},legacy_rows_excluded:3,latency:{output_to_wages_game_minutes:{n:1,eligible:2,unknown:1,median:4,p95:4},output_to_wages_wall_seconds:{n:0,eligible:2,unknown:2,median:null,p95:null}},eligibility:{n:null,scope:'No opportunity snapshots'}},{commodity_labels:{ingot:'Copper ingot'}});
 assert.match(root.textContent,/Wage debited without verified worker credit: 1/);assert.match(root.textContent,/Unsettled witnessed output: 2 Copper ingot/);assert.match(root.textContent,/3 legacy records excluded/);assert.match(root.textContent,/4 median \/ 4 p95 game minutes · 1 timed \/ 2 eligible · 1 missing/);assert.match(root.textContent,/— median \/ — p95 wall seconds · 0 timed \/ 2 eligible · 2 missing/);assert.match(root.textContent,/Opportunity coverage unmeasured/);
 }finally{dom.window.close();}
});
function native(){const dom=new JSDOM(read('index.html'),{runScripts:'outside-only',url:'https://local.invalid/'}),w=dom.window;w.setInterval=()=>1;w.skyrimPlatform={sendMessage(){}};for(const script of w.document.scripts)vm.runInContext(script.src?read(path.basename(script.src)):script.textContent,dom.getInternalVMContext());return {dom,w};}
const concurrencyJob=()=>({id:'job-1',identity_digest:'a'.repeat(64),reservations:{worker_activity:true,worker_inventory:true,employer_activity:false,employer_inventory:true},employer_non_economic_eligible:true,employer_activity:{state:'observed_loaded'}});
test('inventory locks are separate from activity locks without claiming the employer is universally free',()=>{
 const {dom,root}=card(job(),concurrencyJob());try{
 const rows=root.querySelectorAll('.paid-reservation-table tbody tr');assert.equal(rows.length,2);
 assert.deepEqual([...rows[0].querySelectorAll('td')].map(e=>e.dataset.reservation),['reserved','reserved']);
 assert.deepEqual([...rows[1].querySelectorAll('td')].map(e=>e.dataset.reservation),['reserved','not_reserved']);
 assert.match(rows[1].textContent,/Not currently reserved/);assert.match(root.textContent,/other guards may still block activity/);assert.match(root.textContent,/current admission checks pass/);assert.doesNotMatch(root.textContent,/employer is free|overlap verified|overlap [1-9]/i);
 assert.equal(proof(root,'Wage transfer verified'),'Not verified');
 }finally{dom.window.close();}
});
test('reservation joins require the exact job identity and current projection; unknown never becomes unlocked',()=>{
 const paid=job({identity_digest:'a'.repeat(64)}),row=concurrencyJob(),valid={fresh:true,jobs:[row]};assert.equal(employmentConcurrencyForJob(valid,paid),row);
 for(const report of [undefined,{...valid,fresh:false},{fresh:true,jobs:[{...row,identity_digest:'b'.repeat(64)}]},{fresh:true,jobs:[row,row]}])assert.equal(employmentConcurrencyForJob(report,paid),null);
 assert.equal(employmentConcurrencyForJob(valid,{...paid,identity_digest:undefined}),null);assert.equal(employmentConcurrencyForJob(valid,{...paid,lineage_conflict:true}),null);
 const {dom,root}=card(paid);try{assert.equal(root.querySelectorAll('[data-reservation=unknown]').length,4);assert.match(root.textContent,/eligibility is unmeasured/);assert.match(root.textContent,/Employer activity: Unmeasured/);assert.doesNotMatch(root.textContent,/Not currently reserved/);}finally{dom.window.close();}
});
test('employer observed activity is explicit and a snapshot is not an overlap measurement',()=>{
 for(const [activity,label] of [[{state:'conversation_attending',conversation_id:'chat-2'},'Observed conversation attendance · encounter chat-2'],[{state:'native_scene'},'Observed native scene'],[{state:'observed_loaded'},'Observed loaded; current activity unclassified'],[{state:'invented_idle'},'Unmeasured']]){
 const {dom,root}=card(job(),{...concurrencyJob(),employer_activity:activity});try{assert.match(root.textContent,new RegExp('Employer activity: '+label));assert.match(root.textContent,/single observation do not prove overlapping work or conversation/);assert.equal(root.querySelector('svg'),null);assert.equal(root.querySelector('progress'),null);}finally{dom.window.close();}
 }
});
test('a reservation snapshot never invents overlap intervals, while a measured zero remains zero',()=>{
 const dom=new JSDOM('<main></main>'),root=dom.window.document.querySelector('main');try{
 renderEmploymentConcurrency(root,{fresh:true,counts:{paid_account_participants:2,paid_activity_reserved_participants:1,observed_attending_workers:1,employers_non_economic_eligible:1}});
 assert.equal((root.textContent.match(/Unmeasured · no qualified paired intervals/g)||[]).length,2);assert.doesNotMatch(root.textContent,/0 sampled job-seconds/);assert.equal(root.querySelector('svg'),null);
 root.replaceChildren();renderEmploymentConcurrency(root,{fresh:true,counts:{},overlap:{employer_movement:{n:4,positive_intervals:0,unknown_intervals:2,sampled_overlap_seconds:0,sampled_overlap_game_minutes:0}}});
 assert.match(root.textContent,/0 positive \/ 4 assessed intervals · 2 unknown/);assert.match(root.textContent,/0 sampled job-seconds · 0 accrued game minutes/);assert.match(root.textContent,/Displacement does not mean continuous motion/);
 }finally{dom.window.close();}
});
test('stale employer telemetry cannot retain current reservation counts or turn measured windows into live activity',()=>{
 const dom=new JSDOM('<main></main>'),root=dom.window.document.querySelector('main');try{
 renderEmploymentConcurrency(root,{fresh:false,counts:{paid_account_participants:2,paid_activity_reserved_participants:1},overlap:{employer_conversation:{n:3,positive_intervals:2,unknown_intervals:1,sampled_overlap_seconds:10,sampled_overlap_game_minutes:2}},coverage:{qualified_attendance_intervals:4,candidate_job_intervals:7,excluded:{gap:3}}});
 assert.deepEqual([...root.querySelectorAll('.town-flow strong')].map(e=>e.textContent),['—','—','—','—']);assert.match(root.textContent,/Retained window measurements below do not describe current activity/);assert.match(root.textContent,/2 positive \/ 3 assessed intervals/);assert.match(root.textContent,/4 qualified attendance \/ 7 candidate job intervals · excluded: gap: 3/);
 }finally{dom.window.close();}
});
test('native inspector shows the selected worker or employer evidence independent of foreground plan',()=>{
 const {dom,w}=native();try{const person={profile:{name:'Worker One',big_five:{}},needs:{hunger:.2},memories:[]},paid=job({identity_digest:'a'.repeat(64),stages:stages({output_verified:true,held:true}),held_reason:'Missing wage debit witness'});
 w.whiterunRender({residents:[{id:7,name:'Worker One',isPerson:true,inventory:{gold:999}}],trades:[],society:{people:{7:person},town:{residents:{7:{name:'Worker One'}}},plan:{id:'unrelated',actor:9,phase:'travelling'}},dashboard:{control:{},stock:{},needs:{hunger:{known:0,high:0},fatigue:{known:0,high:0},social_contact:{known:0,high:0}},economy:{},paid_employment_metrics:{measured:true,jobs:[paid],stages:{},retained_jobs:1},employment_concurrency_metrics:{fresh:true,jobs:[concurrencyJob()],counts:{}}}});w.whiterunInspectKey(2);
 const panel=w.document.getElementById('resident-inspector');assert.match(panel.textContent,/Missing wage debit witness/);assert.equal(proof(panel,'Output verified'),'Yes · recorded proof');assert.equal(proof(panel,'Wage transfer verified'),'Not verified');
 assert.match(panel.textContent,/Not currently reserved/);assert.match(panel.textContent,/Employer activity: Observed loaded; current activity unclassified/);
 }finally{dom.window.close();}
});
test('legacy completed outcome never certifies modern wages or invented recipe output',()=>{
 const {dom,w}=native();try{const person={profile:{name:'Worker One',big_five:{}},needs:{hunger:.2},memories:[]},plan={id:'legacy',actor:7,target:8,kind:'work_shift',phase:'complete',outcome:'paid_work_completed',work_terms:{policy:{wage_gold:3,work_minutes:30}}};
 w.whiterunRender({residents:[{id:7,name:'Worker One',isPerson:true,inventory:{gold:8}}],trades:[],society:{people:{7:person},town:{residents:{7:{name:'Worker One'}}},plan}});assert.match(w.document.getElementById('trade').textContent,/legacy execution unqualified/);assert.doesNotMatch(w.document.getElementById('work-stage').textContent,/wage received/);w.whiterunInspectKey(2);assert.match(w.document.getElementById('resident-inspector').textContent,/no wage or output is certified from this outcome label/);assert.doesNotMatch(w.document.getElementById('resident-inspector').textContent,/Native output and conserved wage verified/);
 }finally{dom.window.close();}
});
