let inspectedResident=null,lastEncounterPhase=null,phaseBegan=Date.now();
const markerNodes=new Map();
window.whiterunInspectKey=code=>{
 if(code===65){window.whiterunEnterRts?.();return;}
 const id=[2,3,4].includes(code)?(state?.residents||[]).filter(r=>state?.society?.town?.residents?.[String(r.id)])[code-2]?.id:null;
 if(id){inspectedResident=id;choose('focus',id);window.drawEncounter();}
 if(code===64){inspectedResident=null;choose('story');window.drawEncounter();}
};
document.addEventListener('keydown',event=>{const code={'1':2,'2':3,'3':4,'F6':64}[event.key];if(code){event.preventDefault();window.whiterunInspectKey(code);}});
window.whiterunProject=points=>{
 const c=state?.society?.conversation,active=c&&!['complete','held'].includes(c.phase);
 const cohort=state?.society?.routine_batch,cohortIds=cohort?.phase==='travelling'?cohort.members.filter(m=>m.phase==='travelling').map(m=>m.actor):[];
 const rts=window.whiterunRtsActive?.()===true;
 const economicPair=state?.society?.plan?.economic_speech?state.society.plan.economic_pair:null;
 const ids=rts?(state?.residents||[]).filter(r=>state?.society?.town?.residents?.[String(r.id)]).map(r=>r.id):cohortIds.length?cohortIds:inspectedResident?[inspectedResident]:economicPair|| (active?c.speakers:focusId?[focusId]:[]);
 for(const node of markerNodes.values())node.hidden=true;
 for(const point of points){if(!ids.includes(point.id))continue;
  const [x,y,z]=point.head,[fx,fy]=point.foot;
  if(![x,y,z,fx,fy].every(Number.isFinite)||z<=0||x<0||x>1||y<0||y>1)continue;
  let node=markerNodes.get(point.id);
  if(!node){node=document.createElement('div');node.className='resident-marker';const label=document.createElement('span');node.append(label);document.getElementById('resident-markers').append(node);markerNodes.set(point.id,node);}
  const height=Math.max(45,Math.min(innerHeight*.85,Math.abs(fy-y)*innerHeight)),width=Math.max(45,height*.4);
  const talking=state?.speech?.status==='playing'&&(state?.society?.plan?.economic_speech?.actor||c?.current?.speaker)===point.id;
  node.classList.toggle('talking',talking);node.classList.toggle('rts-pick',rts);node.classList.toggle('selected',point.id===inspectedResident);node.onclick=rts?()=>{inspectedResident=point.id;window.drawEncounter();}:null;node.hidden=false;
  node.style.left=(x*innerWidth-width/2)+'px';node.style.top=((1-y)*innerHeight)+'px';
  node.style.width=width+'px';node.style.height=height+'px';
  node.firstChild.textContent=(names[point.id]||'Resident')+(talking?' · speaking':point.id===inspectedResident?' · selected':rts?' · inspect':active?' · encounter':'');
 }
};
function inspectorText(parent,value,cls='small'){const el=document.createElement('div');el.className=cls;el.textContent=value;parent.append(el);return el;}
window.drawEncounter=()=>{
 const c=state?.society?.conversation,key=c?c.id+':'+c.turn+':'+c.phase:'idle';
 if(key!==lastEncounterPhase){lastEncounterPhase=key;phaseBegan=Date.now();}
 const timing=document.getElementById('encounter-timing');
 const economic=state?.society?.plan;
 timing.textContent='';
 if(economic?.economic_pair&&!['complete','held'].includes(economic.phase)){
  const d=economic.decisions?.at(-1),t=economic.economic_speech||economic.economic_turns?.at(-1);
  const fixture=economic.decisions?.some(row=>String(row.model).includes('fixture'));
  text('encounter-pipeline',fixture?'Controlled protocol test → spoken terms → game rules':economic.natural_trade?'Resident decision → language + Jev → spoken terms':'Resident decisions → spoken terms → game rules');
  timing.textContent=[Number.isFinite(d?.elapsed_seconds)?'Decision '+d.elapsed_seconds.toFixed(2)+'s':null,t?.wording_results?.length?'Wording '+t.wording_results.length+' calls':null,t?.wording_fallback?'Original terms fallback':null,t?.audio?'Voice '+t.audio.seconds.toFixed(1)+'s':null].filter(Boolean).join(' · ');
 }else if(c){text('encounter-pipeline','Language → resident decision → game rules');const t=c.current||c.turns?.at(-1),language=t?.language?.elapsed_seconds,decision=t?.decision?.elapsed_seconds;
  timing.textContent=[language!==undefined?'Language '+language.toFixed(2)+'s':null,decision!==undefined?'Decision '+decision.toFixed(2)+'s':null,t?.audio?'Voice '+t.audio.seconds.toFixed(1)+'s':null].filter(Boolean).join(' · ');}
 if(state?.society?.routine_batch?.phase==='travelling')text('notice','Independent lives · '+(state.parallel_routines?.peak_owned||0)+' peak simultaneous journeys observed');
 const displayResident=inspectedResident||((!c||['complete','held'].includes(c.phase))&&!state?.society?.plan?.economic_speech&&camera==='focus'?focusId:null);
 const panel=document.getElementById('resident-inspector');panel.hidden=!displayResident;
 if(!displayResident)return;
 document.getElementById('focus-card').hidden=true;
 document.getElementById('conversation-card').hidden=true;document.getElementById('day-card').hidden=true;document.getElementById('work-card').hidden=true;
 const person=state?.society?.people?.[String(displayResident)];if(!person)return;
 panel.replaceChildren();panel.append(window.residentMedia.portrait(state.residents?.find(r=>r.id===displayResident)||{id:displayResident,name:person.profile.name},84));inspectorText(panel,'INSPECT A RESIDENT','eyebrow');inspectorText(panel,person.profile.name,'section-title');
 const batch=state?.society?.routine_batch,member=batch?.members.find(m=>m.actor===displayResident);
 if(member){const native=state?.parallel_routines?.activities.find(a=>a.actor===displayResident);inspectorText(panel,'Independent journey · slot '+(member.slot+1),'label');inspectorText(panel,(member.outcome||native?.phase||native?.status||member.phase).replaceAll('_',' '));if(native)inspectorText(panel,Math.round(native.distance??native.movement?.distance??0)+' units from the public market');inspectorText(panel,(state.parallel_routines?.peak_owned||batch.concurrency?.peak_owned||0)+' peak simultaneous native journeys observed');if(member.result)inspectorText(panel,'Own choice · '+member.result.decision.action_id.replaceAll('_',' '));}
 const plan=state?.society?.plan;
 const goal=person.standing_goal;
 if(goal){
  const native=state.resident_control?.activities?.find(a=>a.actor===displayResident);
  inspectorText(panel,'Personal standing goal','label');
  const focus=typeof goal.focus==='string'?goal.focus.replaceAll('_',' '):null;
  const review=focus?focus.charAt(0).toUpperCase()+focus.slice(1)+' review':null;
  const label=goal.target?.name||review||(goal.phase==='quiet'?'Quiet interval':'Personal goal');
  inspectorText(panel,label+' · '+String(goal.phase||'unknown').replaceAll('_',' '));
  if(review&&goal.target)inspectorText(panel,review+' after arrival · no completed action implied');
  const follow=goal.follow_through;
  if(follow){
   const event=(state.society?.town?.daily?.queue||[]).find(e=>e.id===follow.event_id);
   const status=event?.status||follow.status||'unknown',outcome=event?.outcome||follow.outcome;
   inspectorText(panel,'Follow-through · '+String(status).replaceAll('_',' '),'label');
   if(follow.event_id)inspectorText(panel,'Recorded event · '+follow.event_id);
   if(outcome)inspectorText(panel,'Recorded outcome · '+String(outcome).replaceAll('_',' '));
   else if(status==='pending')inspectorText(panel,'Waiting for review · not currently thinking or completing work');
   else if(status==='started')inspectorText(panel,'Review started · outcome not yet recorded');
   if(follow.reason)inspectorText(panel,follow.reason);
  }
  if(Number.isFinite(native?.distance)&&native.goal_id===goal.id)inspectorText(panel,Math.round(native.distance)+' units to chosen destination');
  if(Number.isFinite(state.gameDays)&&Number.isFinite(goal.decided_day))inspectorText(panel,Math.max(0,Math.round((state.gameDays-goal.decided_day)*1440))+' game minutes since this decision');
  inspectorText(panel,'Movement does not imply trade, work or rest recovery.');
 }
 if(plan?.actor===displayResident&&plan.enterprise_change){
  inspectorText(panel,plan.decisions?.some(d=>String(d.model).includes('fixture'))?'Business integration test':'Own business decision','label');
  inspectorText(panel,(plan.outcome||plan.phase).replaceAll('_',' '));
  inspectorText(panel,'Services updated · goods and money stay in the resident’s inventory');
 }
 if(plan?.actor===displayResident&&(plan.kind==='work_shift'||plan.work_terms||plan.own_work_terms)){
  const owner=!!plan.own_work_terms,terms=plan.own_work_terms?.policy||plan.work_terms?.policy||{wage_gold:2,work_minutes:30};
  inspectorText(panel,plan.decisions?.some(d=>d.rationale_kind==='test_fixture')?'Employment integration test':owner?'Owner production':'Employment decisions','label');
  inspectorText(panel,(plan.outcome||plan.phase).replaceAll('_',' '));
  inspectorText(panel,(owner?'Own stock · no wage transfer · ':terms.wage_gold+' gold for ')+terms.work_minutes+' game minutes · 1 grain → 2 bread');
  if(plan.phase==='working'){
   const work=state.productionWork;
   inspectorText(panel,Number(work?.workedMinutes||0).toFixed(1)+' / '+terms.work_minutes+' nearby attendance minutes');
   if(work?.phase==='approaching_work')inspectorText(panel,'Catching up to employer · travel earns no work credit');
  }
  if(['work_interrupted','owner_work_interrupted'].includes(plan.outcome))inspectorText(panel,'Interrupted before inventory effects · no wage or output');
  if(plan.outcome==='paid_work_completed')inspectorText(panel,'Native output and conserved wage verified');
  if(plan.outcome==='owner_work_completed')inspectorText(panel,'Owned output verified · gold unchanged');
 }
 if(plan?.actor===displayResident&&plan.destination){
  text('notice',plan.phase==='travelling'?'Resident-chosen journey · '+plan.destination.name:'Market visit · '+(plan.outcome||plan.phase).replaceAll('_',' '));
  inspectorText(panel,'Known destination · '+plan.destination.name,'label');
  inspectorText(panel,'Plan · '+(plan.outcome||plan.phase).replaceAll('_',' '));
  if(plan.phase==='travelling'&&state.movement?.actor===displayResident)inspectorText(panel,Math.round(state.movement.distance)+' units remaining · '+state.movement.phase);
  if(plan.market_visit)inspectorText(panel,plan.market_visit.seller_nearby?'Seller observed nearby. Sale requires consent.':'Seller not observed nearby. No food or money changed.');
 }
 const rest=state?.rest?.activity;
 if(rest?.actor===displayResident&&rest.id==='rest-'+state?.society?.plan?.id){
  text('notice',rest.phase==='applied'?'Seated break verified':'Resident-chosen rest · '+rest.phase.replaceAll('_',' '));
  inspectorText(panel,'Seated break · '+rest.phase.replaceAll('_',' '),'label');
  inspectorText(panel,Number(rest.rested_minutes||0).toFixed(1)+' / 30 game minutes observed');
  const progress=document.createElement('progress');progress.max=30;progress.value=rest.rested_minutes||0;progress.style.width='100%';panel.append(progress);
  inspectorText(panel,rest.phase==='applied'?'Attendance and release verified.':'Recovery waits for completed attendance and release.');
 }
 inspectorText(panel,person.profile.role);inspectorText(panel,'Skyrim race · '+(state?.residents?.find(r=>r.id===displayResident)?.race?.name||'unobserved')+' · descriptive game metadata');const hunger=inspectorText(panel,'Simulated hunger · '+Math.round(person.needs.hunger*100)+'%');hunger.style.marginTop='12px';
 const hungerBar=document.createElement('progress');hungerBar.max=1;hungerBar.value=person.needs.hunger;hungerBar.style.width='100%';panel.append(hungerBar);
 const traits=inspectorText(panel,'Authored Big Five traits','label');traits.style.marginTop='14px';
 for(const [name,value] of Object.entries(person.profile.big_five)){const row=document.createElement('div');row.className='trait-row';const label=document.createElement('span');label.textContent=name;const bar=document.createElement('meter');bar.min=0;bar.max=1;bar.value=value;row.append(label,bar);panel.append(row);}
 let current=c?.current?.speaker===displayResident?c.current:[...(c?.turns||[])].reverse().find(t=>t.speaker===displayResident);
 if(current?.selected){const title=inspectorText(panel,c&&!['complete','held'].includes(c.phase)?'Current speech intention · generated':'Previous speech intention · generated','label');title.style.marginTop='14px';inspectorText(panel,current.selected.intention);inspectorText(panel,'Tone: '+current.selected.tone);}
 const memories=inspectorText(panel,'Recent memories','label');memories.style.marginTop='14px';
 for(const m of person.memories.slice(-2)){const item=inspectorText(panel,m.quote?'“'+m.quote+'”':m.kind.replaceAll('_',' '));item.style.marginTop='9px';if(m.quote)inspectorText(panel,'Remembered claim · truth unverified');}
 for(const [need,value] of Object.entries(person.needs)){if(need==='hunger')continue;inspectorText(panel,need.replaceAll('_',' ')+' · '+Math.round(value*100)+'%');const bar=document.createElement('progress');bar.max=1;bar.value=value;bar.style.width='100%';panel.append(bar);}
 inspectorText(panel,'Resident state · '+(person.agency?.state||'unknown').replaceAll('_',' '));
 inspectorText(panel,person.agency?.reason||'No current reason recorded');
 inspectorText(panel,'Personal knowledge','label');
 const known=Object.values(person.known_people||{});if(!known.length)inspectorText(panel,'No names learned through introductions yet.');
 for(const k of known.slice(-6))inspectorText(panel,(k.name||'Familiar unnamed resident')+' · '+(k.name_source?'self-reported name':'name unknown'));
 inspectorText(panel,'Relationships','label');
 const relations=Object.entries(person.relationships||{});if(!relations.length)inspectorText(panel,'No relationship history recorded yet.');
 for(const [id,value] of relations){const edge=state?.society?.metrics?.relationships?.edges.find(e=>e.actor===displayResident&&e.other===Number(id));inspectorText(panel,(names[id]||id)+' · '+(edge?.level||'unclassified').replaceAll('_',' ')+' · familiarity '+Math.round((value.familiarity||0)*100)+'% · affinity '+Number(value.affinity||0).toFixed(2)+' · '+(value.heard_turns||0)+' heard turns');}
 inspectorText(panel,'Traits are authored gameplay tendencies, not psychological measurements.').style.marginTop='14px';
};
setInterval(()=>{const c=state?.society?.conversation;if(c&&!['complete','held'].includes(c.phase)){
 const seconds=Math.floor((Date.now()-phaseBegan)/1000);document.getElementById('phase-clock').textContent=seconds+'s in this stage';
}else {const p=state?.society?.plan;document.getElementById('phase-clock').textContent=p&&!['complete','held'].includes(p.phase)?'Resident activity · '+p.phase.replaceAll('_',' '):'Last encounter';}},500);
