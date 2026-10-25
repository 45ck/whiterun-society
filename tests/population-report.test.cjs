const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {JSDOM}=require('jsdom');

function report(program){
 const template=fs.readFileSync(path.join(__dirname,'../tools/render_population.py'),'utf8').match(/HTML = '''([\s\S]*?)'''/)[1];
 const residents=[true,false,null,null].map((support,index)=>({id:index+1,name:['Available','Unavailable','Unmeasured','Missing observation'][index],household:'fixture',native_route_supported:support,loaded:true,latest_inventory:{gold:0,bread:0,grain:0},person:{profile:{role:'Resident',big_five:{}},needs:{hunger:.2},agency:{state:'awaiting_review'},relationships:{},commitments:[],memories:[]}}));
 const data={resource_program:program,checkpoint:7,counts:{residents:4,households:4,businesses:0,native_route_supported:1,native_route_unavailable:1,native_route_unknown:2},residents,businesses:[],events:[]};
 const dom=new JSDOM(template.replace('__SNAPSHOT__',JSON.stringify(data)),{runScripts:'outside-only'});
 for(const script of dom.window.document.scripts)if(script.type!=='application/json')vm.runInContext(script.textContent,dom.getInternalVMContext());
 return dom;
}

test('recorded population capability labels and counts distinguish unmeasured from unavailable',()=>{
 const dom=report();try{const doc=dom.window.document;
  assert.equal(doc.querySelectorAll('[data-route-state="supported"]').length,1);
  assert.equal(doc.querySelectorAll('[data-route-state="unavailable"]').length,1);
  assert.equal(doc.querySelectorAll('[data-route-state="unknown"]').length,2);
  assert.match(doc.getElementById('metrics').textContent,/1Route capability reported available1Route capability reported unavailable2Route capability unmeasured/);
  assert.doesNotMatch(doc.getElementById('residents').textContent,/Native routine extension needed|Prototype route available/);
  assert.match(doc.body.textContent,/Available capability does not prove movement or completed work/);
 }finally{dom.window.close();}
});

test('population filters preserve separate available unavailable and unknown categories',()=>{
 const dom=report();try{const w=dom.window,doc=w.document,filter=doc.getElementById('filter'),search=doc.getElementById('search');
  for(const [category,count] of [['supported',1],['unavailable',1],['unknown',2],['all',4]]){
   filter.value=category;filter.dispatchEvent(new w.Event('input'));
   assert.equal(doc.querySelectorAll('.resident').length,count);
   assert.equal(doc.getElementById('result-count').textContent,`${count} of 4 residents shown`);
   if(category!=='all')assert.equal(doc.querySelectorAll(`[data-route-state="${category}"]`).length,count);
  }
  filter.value='unknown';search.value='Missing';search.dispatchEvent(new w.Event('input'));
  assert.equal(doc.querySelectorAll('.resident').length,1);
  assert.match(doc.getElementById('residents').textContent,/Missing observation/);
 }finally{dom.window.close();}
});


test('population snapshot labels legacy imports without reconstructing verified deliveries',()=>{
 const dom=report({capacity:{gold:100},remaining:{gold:3},grants:{}});try{
  const text=dom.window.document.getElementById('resources').textContent;
  assert.match(text,/Historical external grants · legacy provenance/);
  assert.doesNotMatch(text,/97|verified settled imports/);
 }finally{dom.window.close();}
});

test('population snapshot displays generic reserved and verified import buckets separately',()=>{
 const dom=report({protocol:2,id:'example',manifest_hash:'b'.repeat(64),manifest:{id:'example',version:'v2',provenance:'Authored test',capacity:{ore:10}},capacity:{ore:10},available:{ore:4},reserved:{ore:6},delivered:{ore:0},grants:{}});try{
  assert.match(dom.window.document.getElementById('resources').textContent,/partial or uncertain native effects may already be present/);
  assert.match(dom.window.document.getElementById('resources').textContent,/ore: 4 available · 6 reserved · 0 verified settled imports · 10 source capacity/);
 }finally{dom.window.close();}
});
