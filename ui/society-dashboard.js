// Operator charts. No chart value enters a resident's private decision context.
function renderTownCharts(root,data){
 if(!root||!data)return;
 const signature=JSON.stringify(data);if(root.dataset.snapshot===signature)return;root.dataset.snapshot=signature;
 const doc=root.ownerDocument,ns='http://www.w3.org/2000/svg';
 if(!doc.getElementById('town-chart-style')){
  const style=doc.createElement('style');style.id='town-chart-style';style.textContent=`
  .town-charts{display:grid;gap:16px}.town-charts h3{margin:0 0 9px;font-size:14px;font-weight:600;color:#eee5d5}
  .town-chart-note{font-size:10px;line-height:1.4;color:#aab9ba;margin:8px 0 0}.town-control{display:flex;align-items:center;gap:13px}
  .town-control svg{width:100px;height:100px;flex:none}.town-legend{font-size:11px;display:grid;gap:5px;flex:1}.town-legend div{display:flex;gap:6px;align-items:center}.town-legend b{margin-left:auto;font-weight:600}
  .town-swatch{width:7px;height:7px;border-radius:50%;flex:none}.town-stock-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.town-stock{padding:10px 7px;border:1px solid #ffffff15;border-radius:8px;background:#ffffff04}.town-stock strong{display:block;font-size:23px;font-weight:500;color:#e0bd72}.town-stock span{font-size:11px;color:#bac5c5}.town-stock small{display:block;font-size:9px;color:#8e9ea2;margin-top:4px}
  .town-need{margin:8px 0}.town-need-label{display:flex;justify-content:space-between;font-size:11px;margin-bottom:5px}.town-need-track{height:7px;border-radius:4px;background:#ffffff0d;overflow:hidden}.town-need-fill{height:100%;border-radius:4px;background:#dfa56d}.town-flow{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;font-size:11px}.town-flow strong{display:block;color:#9dc9ac;font-size:20px;font-weight:500}.town-tabs{display:flex;gap:5px;margin:5px 0}.town-tabs button{flex:1;background:#ffffff08;border:1px solid #ffffff18;border-radius:6px;padding:7px;color:inherit}
  `;doc.head.append(style);
 }
 root.replaceChildren();root.classList.add('town-charts');
 const add=(parent,tag,text,cls)=>{const e=doc.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;parent.append(e);return e;};
 const section=title=>{const e=add(root,'section');add(e,'h3',title);return e;};
 const control=section('Who controls the residents?'),row=add(control,'div',undefined,'town-control');
 const svg=doc.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 120 120');svg.setAttribute('role','img');row.append(svg);
 const labels=[['agent','Agent task','#9dc9ac'],['standby','Agent standby','#6ab5b6'],['scene','Native scene','#d5967f'],['native','Other native routine','#a39ac3'],['unknown','Unknown','#8296a0'],['unloaded','Not loaded','#45565f']];
 const total=labels.reduce((n,[k])=>n+(data.control[k]||0),0),circ=2*Math.PI*46;let offset=0;
 svg.setAttribute('aria-label','Current control: '+labels.map(([k,t])=>`${t} ${data.control[k]||0}`).join(', '));
 for(const [key,label,color] of labels){const value=data.control[key]||0;if(!value||!total)continue;
  const circle=doc.createElementNS(ns,'circle');for(const [k,v] of Object.entries({cx:60,cy:60,r:46,fill:'none',stroke:color,'stroke-width':12,'stroke-dasharray':`${value/total*circ} ${circ}`,'stroke-dashoffset':-offset,transform:'rotate(-90 60 60)'}))circle.setAttribute(k,String(v));svg.append(circle);offset+=value/total*circ;
 }
 const center=doc.createElementNS(ns,'text');center.setAttribute('x','60');center.setAttribute('y','60');center.setAttribute('text-anchor','middle');center.setAttribute('fill','#f0e8d7');center.setAttribute('font-size','24');center.textContent=String(data.control.agent||0);svg.append(center);
 const sub=doc.createElementNS(ns,'text');sub.setAttribute('x','60');sub.setAttribute('y','76');sub.setAttribute('text-anchor','middle');sub.setAttribute('fill','#aab9ba');sub.setAttribute('font-size','10');sub.textContent='agent tasks';svg.append(sub);
 const legend=add(row,'div',undefined,'town-legend');for(const [key,label,color] of labels){const item=add(legend,'div');add(item,'span',undefined,'town-swatch').style.background=color;add(item,'span',label);add(item,'b',String(data.control[key]||0));}
 add(control,'p',data.control_scope,'town-chart-note');
 const stock=section('Observed resources'),grid=add(stock,'div',undefined,'town-stock-grid');
 for(const [key,label] of [['gold','Gold'],['bread','Loaves'],['grain','Grain']]){const value=data.stock[key],card=add(grid,'div',undefined,'town-stock');add(card,'strong',value.total??'—');add(card,'span',label);add(card,'small',`${value.accounts}/${value.population} accounts`);}
 const needs=section('Residents with unmet needs');
 for(const [key,label] of [['hunger','Hungry'],['fatigue','Tired'],['social_contact','Seeking company']]){const value=data.needs[key],item=add(needs,'div',undefined,'town-need'),line=add(item,'div',undefined,'town-need-label');add(line,'span',label);add(line,'span',value.known?`${value.high} / ${value.known}`:'Unknown');const track=add(item,'div',undefined,'town-need-track');track.setAttribute('role','meter');track.setAttribute('aria-label',label);track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax',String(value.known||1));track.setAttribute('aria-valuenow',String(value.high));add(track,'div',undefined,'town-need-fill').style.width=(value.known?value.high/value.known*100:0)+'%';}
 add(needs,'p',data.needs_scope,'town-chart-note');
 const flow=section('Economy in this save'),tiles=add(flow,'div',undefined,'town-flow');
 for(const [key,label] of [['committed_sales','Completed sales'],['committed_production','Production shifts'],['committed_meals','Meals eaten'],['active_enterprises','Open businesses'],['resident_enterprise_changes','Resident business decisions'],['operator_enterprise_changes','Operator charter edits']]){const tile=add(tiles,'div');add(tile,'strong',data.economy[key]??'—');add(tile,'span',label);}
 add(flow,'p',data.economy_scope,'town-chart-note');
 const negotiation=data.economy.negotiations;
 if(negotiation){
  const trade=section('What happened to trade offers?');
  const outcomes=[['sale','Completed sale','#9dc9ac'],['seller_refused','Seller refused','#e0bd72'],['buyer_left','Buyer left','#6ab5b6'],['active','In progress','#a39ac3'],['technical_failure','Technical failure','#d5967f'],['other','Other / unclassified','#8296a0']];
  for(const [key,label,color] of outcomes){
   const count=negotiation.outcomes[key]||0,item=add(trade,'div',undefined,'town-need'),line=add(item,'div',undefined,'town-need-label');
   add(line,'span',label);add(line,'span',`${count} / ${negotiation.n}`);
   const track=add(item,'div',undefined,'town-need-track');track.setAttribute('role','meter');track.setAttribute('aria-label',label);track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax',String(negotiation.n||1));track.setAttribute('aria-valuenow',String(count));
   const fill=add(track,'div',undefined,'town-need-fill');fill.style.width=(negotiation.n?count/negotiation.n*100:0)+'%';fill.style.background=color;
  }
  add(trade,'p',negotiation.n?negotiation.scope:'No retained voiced trade plans yet.','town-chart-note');
  add(trade,'p',`${data.economy.household_release_sales??'Unknown'} committed sales released one reserved loaf. Remaining household stock stays reserved.`,'town-chart-note');
  const bargaining=data.economy.bargaining;
  if(bargaining?.plans){
   for(const [commodity,seriesGroup] of Object.entries(bargaining.by_commodity||{bread:bargaining})){
     if(!seriesGroup.plans)continue;
     add(trade,'h4',commodity==='grain'?'Grain input market':'Bread market');
     const prices=add(trade,'div',undefined,'town-stock-grid');
   for(const [label,key] of [['Buyer bids','buyer_offers'],['Seller asks','seller_counteroffers'],['Paid prices','paid_prices']]){
    const series=seriesGroup[key],card=add(prices,'div',undefined,'town-stock');
    add(card,'strong',series?.n?String(series.median):'—');
    add(card,'span',`${label} · ${series?.n||0}`);
   }
   add(trade,'p',`Median septims per ${commodity==='grain'?'grain unit':'loaf'}. Bids and asks are proposals; paid prices require verified inventory exchange.`,'town-chart-note');
    }
  }
 }
}
if(typeof module!=='undefined')module.exports={renderTownCharts};
