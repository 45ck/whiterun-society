const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const read=n=>fs.readFileSync(path.join(__dirname,'../ui',n),'utf8');
const metadata=()=>({catalog_hash:'catalog-fixture',market_policy_hash:'market-fixture',commodities:[{id:'gold',label:'Septims'},{id:'bread',label:'Bread'},{id:'grain',label:'Wheat'},{id:'ore',label:'Copper ore'},{id:'ingot',label:'Copper ingot'}],sale_goods:[{id:'bread',legacy_capability:'retail_food'},{id:'grain',legacy_capability:'retail_grain'},{id:'ore',legacy_capability:null}],recipes:[['bread_recipe',{grain:1},{bread:2},'target_bread',5,120,30],['metal_recipe',{ore:2},{ingot:1},'target_output',12,24,15]].map(([id,inputs,outputs,target,min,max,duration])=>({id,inputs,outputs,fields:[{key:'wage_gold',label:'Wage',min:1,max:20,default:2},{key:'work_minutes',label:'Minutes',min,max,default:duration},{key:target,label:'Target',min:2,max:40,default:8}]}))});
async function fixture(){
 const state={connected:true,session:'session-a',checkpoint:7,residents:[{id:91,name:'Artisan',loaded:true,identity:{qualified:true},person:{skills:{craft:.25}}}],places:[],businesses:[],limits:[],director:{running:false},enterprise_editor:metadata(),startup:{current:true,initialized_residents:1,identity_qualified:1,identity_reasons:{},backgrounds:[],charters:0,committed_production:0,committed_sales:0,scenario:{available:true,id:'starting-knowledge',hash:'hash-fixture',provenance:'Authored test scenario'}},dashboard:{inventory_catalog:{verified:true}}};
 const dom=new JSDOM(read('observer.html'),{runScripts:'outside-only',url:'http://127.0.0.1:17854/'}),w=dom.window,requests=[];
 w.setInterval=()=>1;w.renderTownCharts=()=>{};w.renderQualityGoals=()=>{};w.directorLabel=()=> 'Paused';
 w.fetch=async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>url==='/observer/state'?state:url.includes('livelihood-background')?{background:{assignments:[{actor:91,recipe_id:'metal_recipe'}]},checkpoint:8}:{business:{revision:2},checkpoint:8}};};
 for(const script of w.document.scripts)if(!script.src)w.eval(script.textContent);await new Promise(r=>setImmediate(r));
 return {dom,w,state,requests,el:id=>w.document.getElementById(id),posts:()=>requests.filter(r=>r.options?.method==='POST')};
}
test('loading only observes; startup separates backgrounds, imports, charters and settled outcomes',async()=>{const f=await fixture();try{assert.equal(f.posts().length,0);assert.match(f.el('startup-overview').textContent,/0 committed production records · 0 settled sales/);assert.match(f.el('startup-imports').textContent,/No external import program/);assert.equal(f.el('background-apply').disabled,true);}finally{f.dom.window.close();}});
test('catalog-driven editor sends fourth-good recipe terms and checkpoint pins without bread defaults',async()=>{const f=await fixture();try{
 f.w.editEnterprise();f.el('enterprise-name').value='Copper works';f.el('enterprise-goods').querySelector('[value=ore]').checked=true;
 const box=f.el('enterprise-recipes').querySelector('[data-recipe=metal_recipe]');box.querySelector('[data-recipe-choice]').checked=true;box.querySelector('[data-recipe-choice]').onchange();
 assert.match(box.textContent,/2 Copper ore → 1 Copper ingot/);assert.equal(box.querySelector('[data-field=work_minutes]').min,'12');box.querySelector('[data-field=target_output]').value='9';
 await f.el('enterprise-form').onsubmit({preventDefault(){}});const body=JSON.parse(f.posts()[0].options.body);assert.deepEqual(body.enterprise.capabilities,['metal_recipe','retail_goods']);assert.deepEqual(body.enterprise.sale_commodities,['ore']);assert.deepEqual(body.enterprise.recipe_policies,{metal_recipe:{wage_gold:2,work_minutes:15,target_output:9}});assert.equal(body.expected_checkpoint,7);assert.equal(body.expected_session,'session-a');assert.equal(body.enterprise.production_policy,undefined);
}finally{f.dom.window.close();}});
test('legacy combinations preserve their recipes and retail aliases; generic closed listings survive edit',async()=>{const f=await fixture();try{
 const caps=['bread_recipe','retail_food','retail_grain'];for(let mask=1;mask<8;mask++){const expected=caps.filter((_,i)=>mask&(1<<i));f.w.editEnterprise({id:'b',name:'Earlier shop',custodian:91,revision:1,capabilities:expected,active:true});await f.el('enterprise-form').onsubmit({preventDefault(){}});const sent=JSON.parse(f.posts().at(-1).options.body).enterprise;for(const cap of expected)assert.ok(sent.capabilities.includes(cap));assert.equal(sent.expected_revision,1);}
 f.w.editEnterprise({id:'b',name:'Closed ore shop',custodian:91,revision:2,capabilities:['retail_goods'],sale_commodities:['ore'],advertised_goods:[],active:false});assert.equal(f.el('enterprise-goods').querySelector('[value=ore]').checked,true);
}finally{f.dom.window.close();}});
test('stale checkpoint, unqualified custodian and invalid bounds never submit a charter',async()=>{const f=await fixture();try{
 f.w.editEnterprise();f.state.checkpoint=8;await f.el('enterprise-form').onsubmit({preventDefault(){}});assert.equal(f.posts().length,0);assert.match(f.el('enterprise-status').textContent,/Reopen/);
 f.w.editEnterprise();const box=f.el('enterprise-recipes').querySelector('[data-recipe=metal_recipe]'),choice=box.querySelector('[data-recipe-choice]');choice.checked=true;choice.onchange();box.querySelector('[data-field=work_minutes]').value=100;await f.el('enterprise-form').onsubmit({preventDefault(){}});assert.equal(f.posts().length,0);assert.match(f.el('enterprise-status').textContent,/bounds/);
 box.querySelector('[data-field=work_minutes]').value=15;f.state.residents[0].identity.qualified=false;await f.el('enterprise-form').onsubmit({preventDefault(){}});assert.equal(f.posts().length,0);
}finally{f.dom.window.close();}});
test('unknown charter capability cannot be silently removed by the generic editor',async()=>{const f=await fixture();try{
 f.w.editEnterprise();f.w.editEnterprise({id:'future',name:'Future workshop',custodian:91,revision:3,capabilities:['uninstalled_recipe'],active:true});
 assert.equal(f.el('enterprise-form').hidden,true);assert.match(f.el('enterprise-status').textContent,/terms were preserved/);await f.el('enterprise-form').onsubmit({preventDefault(){}});assert.equal(f.posts().length,0);
}finally{f.dom.window.close();}});
test('background application requires explicit preview and sends the exact preview request',async()=>{const f=await fixture();try{
 f.el('background-seed').value='Town1';f.el('background-cohort').querySelector('input').checked=true;await f.w.backgroundRequest(false);assert.equal(f.posts().length,1);assert.match(f.posts()[0].url,/preview$/);assert.equal(f.el('background-apply').disabled,false);assert.match(f.el('background-assignments').textContent,/Artisan · metal recipe · authored prior/);
 await f.w.backgroundRequest(true);assert.equal(f.posts().length,2);assert.equal(f.posts()[0].options.body,f.posts()[1].options.body);assert.match(f.el('background-status').textContent,/No production or resources/);
}finally{f.dom.window.close();}});
test('changed checkpoint or seed and running director invalidate or block applying a preview',async()=>{const f=await fixture();try{
 f.el('background-seed').value='Town1';f.el('background-cohort').querySelector('input').checked=true;await f.w.backgroundRequest(false);f.state.director.running=true;await f.w.backgroundRequest(true);assert.equal(f.posts().length,1);
 f.state.director.running=false;f.state.checkpoint=8;f.w.renderStartup();assert.equal(f.el('background-apply').disabled,true);await f.w.backgroundRequest(true);assert.equal(f.posts().length,1);
 await f.w.backgroundRequest(false);f.el('background-seed').oninput();await f.w.backgroundRequest(true);assert.equal(f.posts().length,2);
}finally{f.dom.window.close();}});
test('a late preview cannot restore an earlier seed or cohort after the user edits the draft',async()=>{const f=await fixture();try{
 const original=f.w.fetch;let release;f.w.fetch=(url,options)=>url.endsWith('/preview')?new Promise(resolve=>{release=()=>original(url,options).then(resolve);}):original(url,options);
 f.el('background-seed').value='Town1';f.el('background-cohort').querySelector('input').checked=true;const pending=f.w.backgroundRequest(false);
 f.el('background-seed').value='ChangedTown';f.el('background-seed').oninput();release();await pending;
 assert.equal(f.el('background-apply').disabled,true);assert.match(f.el('background-status').textContent,/Draft changed/);await f.w.backgroundRequest(true);assert.equal(f.posts().length,1);assert.equal(f.el('background-assignments').textContent,'');
}finally{f.dom.window.close();}});
test('startup warns that paid labour lacks required execution witnesses without obscuring historical records',async()=>{const f=await fixture();try{
 f.state.startup.paid_work_capability={available:false,reason:'legacy_paid_execution_unqualified',detail:'Paid production requires session-bound attendance and issued/observed inventory and wage witnesses.'};f.w.renderStartup();
 assert.match(f.el('startup-overview').textContent,/Paid labour unavailable/);assert.match(f.el('startup-overview').textContent,/inventory and wage witnesses/);assert.match(f.el('startup-overview').textContent,/Historical paid-work records remain readable/);assert.match(f.el('startup-overview').textContent,/owner production is a separate mechanism/);
}finally{f.dom.window.close();}});
test('knowledge inspector distinguishes authored prior, verified learning and legacy records',async()=>{const f=await fixture();try{
 const resident={person:{skills:{craft:.25},authored_recipe_priors:{metal_recipe:{scenario_id:'start',event_id:'prior',provenance:'Scenario craft history'}},known_recipes:{bread_recipe:{source:'verified_native_production',definition:{id:'bread_recipe'},event_id:'work'},legacy_recipe:{source:'old_source'}}},recipe_knowledge:{recipes:{metal_recipe:true,bread_recipe:true},provenance:{metal_recipe:{source:'authored_livelihood_background',valid:true},bread_recipe:{source:'verified_native_production',valid:true}}}};
 f.w.renderRecipeKnowledge(f.el('details'),resident);const text=f.el('details').textContent;assert.match(text,/Authored prior/);assert.match(text,/Learned after verified production/);assert.match(text,/Legacy or unmatched learning record/);assert.match(text,/not measured competence or earned levels/);assert.match(text,/craft: 0.25/);
}finally{f.dom.window.close();}});
