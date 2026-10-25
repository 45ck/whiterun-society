const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const {paidEmploymentLabel,paidEmploymentJobs,renderPaidEmploymentJob,renderPaidEmploymentMetrics}=require('../ui/society-dashboard.js');
const read=name=>fs.readFileSync(path.join(__dirname,'../ui',name),'utf8');
const stages=changes=>({offered:true,accepted:true,attendance_qualified:false,output_verified:false,wage_paid:false,completed:false,released:false,held:false,...changes});
const job=changes=>({id:'job-1',worker:7,employer:8,worker_name:'Worker One',employer_name:'Employer Two',recipe_id:'metal_recipe',wage_gold:5,work_minutes:20,phase:'attending',stages:stages(),...changes});
function card(value){const dom=new JSDOM('<main></main>'),root=dom.window.document.querySelector('main');renderPaidEmploymentJob(root,value,{commodity_labels:{ore:'Copper ore',ingot:'Copper ingot'}});return {dom,root};}
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
test('native inspector shows the selected worker or employer evidence independent of foreground plan',()=>{
 const {dom,w}=native();try{const person={profile:{name:'Worker One',big_five:{}},needs:{hunger:.2},memories:[]},paid=job({stages:stages({output_verified:true,held:true}),held_reason:'Missing wage debit witness'});
 w.whiterunRender({residents:[{id:7,name:'Worker One',isPerson:true,inventory:{gold:999}}],trades:[],society:{people:{7:person},town:{residents:{7:{name:'Worker One'}}},plan:{id:'unrelated',actor:9,phase:'travelling'}},dashboard:{control:{},stock:{},needs:{hunger:{known:0,high:0},fatigue:{known:0,high:0},social_contact:{known:0,high:0}},economy:{},paid_employment_metrics:{measured:true,jobs:[paid],stages:{},retained_jobs:1}}});w.whiterunInspectKey(2);
 const panel=w.document.getElementById('resident-inspector');assert.match(panel.textContent,/Missing wage debit witness/);assert.equal(proof(panel,'Output verified'),'Yes · recorded proof');assert.equal(proof(panel,'Wage transfer verified'),'Not verified');
 }finally{dom.window.close();}
});
test('legacy completed outcome never certifies modern wages or invented recipe output',()=>{
 const {dom,w}=native();try{const person={profile:{name:'Worker One',big_five:{}},needs:{hunger:.2},memories:[]},plan={id:'legacy',actor:7,target:8,kind:'work_shift',phase:'complete',outcome:'paid_work_completed',work_terms:{policy:{wage_gold:3,work_minutes:30}}};
 w.whiterunRender({residents:[{id:7,name:'Worker One',isPerson:true,inventory:{gold:8}}],trades:[],society:{people:{7:person},town:{residents:{7:{name:'Worker One'}}},plan}});assert.match(w.document.getElementById('trade').textContent,/legacy execution unqualified/);assert.doesNotMatch(w.document.getElementById('work-stage').textContent,/wage received/);w.whiterunInspectKey(2);assert.match(w.document.getElementById('resident-inspector').textContent,/no wage or output is certified from this outcome label/);assert.doesNotMatch(w.document.getElementById('resident-inspector').textContent,/Native output and conserved wage verified/);
 }finally{dom.window.close();}
});
