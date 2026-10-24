let inspectedResident=null,lastEncounterPhase=null,phaseBegan=Date.now();
const markerNodes=new Map();
window.whiterunInspectKey=code=>{
 const id={2:108149,3:108186,4:108156}[code];
 if(id){inspectedResident=id;choose('focus',id);window.drawEncounter();}
 if(code===64){inspectedResident=null;tour=true;window.drawEncounter();}
};
document.addEventListener('keydown',event=>{const code={'1':2,'2':3,'3':4,'F6':64}[event.key];if(code){event.preventDefault();window.whiterunInspectKey(code);}});
window.whiterunProject=points=>{
 const c=state?.society?.conversation,active=c&&!['complete','held'].includes(c.phase);
 const cohort=state?.society?.routine_batch,cohortIds=cohort?.phase==='travelling'?cohort.members.filter(m=>m.phase==='travelling').map(m=>m.actor):[];
 const ids=cohortIds.length?cohortIds:inspectedResident?[inspectedResident]:active?c.speakers:focusId?[focusId]:[];
 for(const node of markerNodes.values())node.hidden=true;
 for(const point of points){if(!ids.includes(point.id))continue;
  const [x,y,z]=point.head,[fx,fy]=point.foot;
  if(![x,y,z,fx,fy].every(Number.isFinite)||z<=0||x<0||x>1||y<0||y>1)continue;
  let node=markerNodes.get(point.id);
  if(!node){node=document.createElement('div');node.className='resident-marker';const label=document.createElement('span');node.append(label);document.getElementById('resident-markers').append(node);markerNodes.set(point.id,node);}
  const height=Math.max(45,Math.min(innerHeight*.85,Math.abs(fy-y)*innerHeight)),width=Math.max(45,height*.4);
  const talking=state?.speech?.status==='playing'&&c?.current?.speaker===point.id;
  node.classList.toggle('talking',talking);node.hidden=false;
  node.style.left=(x*innerWidth-width/2)+'px';node.style.top=((1-y)*innerHeight)+'px';
  node.style.width=width+'px';node.style.height=height+'px';
  node.firstChild.textContent=names[point.id]+(talking?' · speaking':active?' · encounter':' · selected');
 }
};
function inspectorText(parent,value,cls='small'){const el=document.createElement('div');el.className=cls;el.textContent=value;parent.append(el);return el;}
window.drawEncounter=()=>{
 const c=state?.society?.conversation,key=c?c.id+':'+c.turn+':'+c.phase:'idle';
 if(key!==lastEncounterPhase){lastEncounterPhase=key;phaseBegan=Date.now();}
 const timing=document.getElementById('encounter-timing');
 if(c){const t=c.current||c.turns?.at(-1),language=t?.language?.elapsed_seconds,decision=t?.decision?.elapsed_seconds;
  timing.textContent=[language!==undefined?'Language '+language.toFixed(2)+'s':null,decision!==undefined?'Decision '+decision.toFixed(2)+'s':null,t?.audio?'Voice '+t.audio.seconds.toFixed(1)+'s':null].filter(Boolean).join(' · ');}
 if(state?.society?.routine_batch?.phase==='travelling')text('notice','Independent lives · '+(state.parallel_routines?.peak_owned||0)+' peak simultaneous journeys observed');
 const displayResident=inspectedResident||((!c||['complete','held'].includes(c.phase))&&camera==='focus'?focusId:null);
 const panel=document.getElementById('resident-inspector');panel.hidden=!displayResident;
 if(!displayResident)return;
 document.getElementById('focus-card').hidden=true;
 document.getElementById('conversation-card').hidden=true;document.getElementById('day-card').hidden=true;document.getElementById('work-card').hidden=true;
 const person=state?.society?.people?.[String(displayResident)];if(!person)return;
 panel.replaceChildren();inspectorText(panel,'INSPECT A RESIDENT','eyebrow');inspectorText(panel,person.profile.name,'section-title');
 const batch=state?.society?.routine_batch,member=batch?.members.find(m=>m.actor===displayResident);
 if(member){const native=state?.parallel_routines?.activities.find(a=>a.actor===displayResident);inspectorText(panel,'Independent journey · slot '+(member.slot+1),'label');inspectorText(panel,(member.outcome||native?.phase||native?.status||member.phase).replaceAll('_',' '));if(native)inspectorText(panel,Math.round(native.distance??native.movement?.distance??0)+' units from the public market');inspectorText(panel,(state.parallel_routines?.peak_owned||batch.concurrency?.peak_owned||0)+' peak simultaneous native journeys observed');if(member.result)inspectorText(panel,'Own choice · '+member.result.decision.action_id.replaceAll('_',' '));}
 const plan=state?.society?.plan;
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
 inspectorText(panel,person.profile.role);const hunger=inspectorText(panel,'Simulated hunger · '+Math.round(person.needs.hunger*100)+'%');hunger.style.marginTop='12px';
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
 inspectorText(panel,'Relationships','label');
 const relations=Object.entries(person.relationships||{});if(!relations.length)inspectorText(panel,'No relationship history recorded yet.');
 for(const [id,value] of relations)inspectorText(panel,(names[id]||id)+' · familiarity '+Math.round((value.familiarity||0)*100)+'% · affinity '+Number(value.affinity||0).toFixed(2)+' · '+(value.heard_turns||0)+' heard turns');
 inspectorText(panel,'Traits are authored gameplay tendencies, not psychological measurements.').style.marginTop='14px';
};
setInterval(()=>{const c=state?.society?.conversation;if(c&&!['complete','held'].includes(c.phase)){
 const seconds=Math.floor((Date.now()-phaseBegan)/1000);document.getElementById('phase-clock').textContent=seconds+'s in this stage';
}else document.getElementById('phase-clock').textContent='No model running';},500);
