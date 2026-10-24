"""Render a portable, offline town overview from recorded population evidence."""
import argparse
import json
from pathlib import Path


def render(evidence):
    state = evidence['after']
    town = state['society']['town']
    people = state['society']['people']
    view = {'checkpoint': state['society']['checkpoint'], 'counts': town['counts'],
            'weather': state['bridge']['observation'].get('weather'),
            'residents': [{**r, 'person': people[key]} for key, r in town['residents'].items()],
            'businesses': list(town['businesses'].values())}
    data = json.dumps(view, ensure_ascii=True).replace('<', '\\u003c')
    return HTML.replace('__SNAPSHOT__', data)


HTML = '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Whiterun Society · Population overview</title>
<style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;color:#ecede6;background:#101b1b}
*{box-sizing:border-box}body{margin:0}main{max-width:1440px;margin:auto;padding:36px}
.eyebrow{color:#d5b880;font-size:12px;letter-spacing:2px;text-transform:uppercase}h1{font-size:clamp(30px,4vw,54px);margin:8px 0 12px;font-weight:550;letter-spacing:-1px}
p{color:#aebfba;line-height:1.6;max-width:850px}.meta{color:#d5b880}header{border-bottom:1px solid #314341;padding-bottom:24px}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:24px 0}.metric{padding:20px;background:#1c2b29;border:1px solid #354640;border-radius:12px}.number{display:block;font-size:34px;color:#f2d39b}
.controls{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}input,select{background:#1c2b29;color:#eef1e9;border:1px solid #637a6d;padding:12px;border-radius:7px;font:inherit}input{min-width:240px}label{display:grid;gap:6px;color:#c3d0ca;font-size:13px}
.residents{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}.resident{background:#172523;border:1px solid #354640;border-radius:12px;padding:20px}h2{font-weight:500}h3{margin:0 0 8px;font-size:20px}.role{font-size:13px;color:#aec1b8;min-height:34px}.stock{display:flex;gap:14px;background:#20332d;padding:12px;margin:12px 0;border-radius:6px;font-size:14px}.need{display:grid;grid-template-columns:110px 1fr 36px;gap:8px;align-items:center;font-size:12px;margin:8px 0}.need progress{width:100%;height:8px;accent-color:#e4bb75}.muted{color:#9cafaa;font-size:12px;line-height:1.6}.badge{display:inline-block;padding:5px 8px;background:#253d36;color:#ccddce;border-radius:5px;font-size:11px;margin:8px 0}.waiting{color:#dfc6a0;background:#3b3528}details{border-top:1px solid #33423e;margin-top:16px;padding-top:12px}summary{cursor:pointer;color:#d5b880;font-size:13px}.businesses{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:30px}.business{padding:20px;border:1px solid #597060;border-radius:12px;background:#223329}.business p{font-size:14px}.empty{padding:32px;color:#cad4cd}footer{margin:30px 0;color:#b5c4bd;font-size:13px}a{color:#e8c486}:focus-visible{outline:3px solid #f4c777;outline-offset:3px}@media(max-width:600px){main{padding:20px}.residents{grid-template-columns:1fr}}
</style>
<main><header><div class="eyebrow">Calvin Kennedy · Whiterun Society</div><h1>A town with a starting state</h1>
<p>Inspect the residents initialized from Skyrim's actual loaded population. Needs and personalities are authored simulation inputs; inventories come from the game. This is a recorded snapshot, not a live feed or proof that every routine is controlled.</p><div class="meta" id="meta"></div></header>
<section class="metrics" id="metrics" aria-label="Population measures"></section>
<h2>Businesses and production</h2><section class="businesses" id="businesses"></section>
<h2>Residents</h2><p>Expand a resident for personality, remembered events and execution status. Households currently use single-adult placeholders; family ties and occupations need deliberate modelling.</p>
<div class="controls"><label>Find a resident<input id="search" type="search" placeholder="Name or form ID"></label><label>Sort<select id="sort"><option value="name">Name</option><option value="hunger">Highest hunger</option><option value="gold">Most carried gold</option></select></label><label>Routine support<select id="filter"><option value="all">All initialized residents</option><option value="supported">Prototype routes available</option><option value="waiting">Native routes still needed</option></select></label></div>
<div id="result-count" class="muted" aria-live="polite"></div><section class="residents" id="residents"></section>
<footer>Source: saved population evidence, checkpoint <span id="checkpoint"></span>. Initialization added no money or goods. <a href="https://github.com/45ck/whiterun-society">Source code and experiments</a></footer></main>
<script type="application/json" id="snapshot">__SNAPSHOT__</script>
<script>
const data=JSON.parse(document.getElementById('snapshot').textContent),byId=id=>document.getElementById(id);
function add(parent,tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;parent.append(e);return e;}
const total=key=>data.residents.reduce((s,r)=>s+r.initial_observed_inventory[key],0);
byId('meta').textContent=`Recorded checkpoint ${data.checkpoint} · Weather observed: ${data.weather?.label||'unavailable'}`;byId('checkpoint').textContent=data.checkpoint;
for(const [value,label] of [[data.counts.residents,'Initialized residents'],[data.counts.households,'Household placeholders'],[data.counts.businesses,'Business charters'],[total('gold'),'Observed carried gold'],[total('bread'),'Observed carried bread']]){const m=add(byId('metrics'),'div',undefined,'metric');add(m,'strong',value,'number');add(m,'span',label);}
for(const b of data.businesses){const c=add(byId('businesses'),'article',undefined,'business');add(c,'h3',b.name);add(c,'p',b.costs.bread_recipe?'Bread recipe: 1 grain + 30 game minutes of paid labour → 2 bread. Wage: 2 gold. The existing prototype has demonstrated this recipe.':'Metalworking is planned. No smithing production or new materials are claimed.');add(c,'div',`Resources held by actor ${b.custodian}; no duplicate business wallet.`,'muted');add(c,'div',`${b.workers.length} assigned workers · ${b.contracts.length} active charter contracts`,'muted');}
function draw(){const q=byId('search').value.toLowerCase(),filter=byId('filter').value,sort=byId('sort').value;let rows=data.residents.filter(r=>(r.name+' '+r.id).toLowerCase().includes(q)&&(filter==='all'||(filter==='supported')===r.native_route_supported));rows.sort((a,b)=>sort==='hunger'?b.person.needs.hunger-a.person.needs.hunger:sort==='gold'?b.initial_observed_inventory.gold-a.initial_observed_inventory.gold:a.name.localeCompare(b.name));byId('residents').replaceChildren();byId('result-count').textContent=`${rows.length} of ${data.residents.length} residents shown`;
for(const r of rows){const p=r.person,c=add(byId('residents'),'article',undefined,'resident');add(c,'h3',r.name);add(c,'div',p.profile.role,'role');add(c,'div',`Form ${r.id} · ${r.household}`,'muted');const stock=add(c,'div',undefined,'stock');for(const k of ['gold','bread','grain'])add(stock,'span',`${r.initial_observed_inventory[k]} ${k}`);for(const [need,value] of Object.entries(p.needs)){const row=add(c,'div',undefined,'need');add(row,'span',need.replaceAll('_',' '));const bar=add(row,'progress');bar.max=1;bar.value=value;bar.setAttribute('aria-label',need);add(row,'span',Math.round(value*100)+'%');}add(c,'span',r.native_route_supported?'Prototype route available':'Native routine extension needed','badge'+(r.native_route_supported?'':' waiting'));const d=add(c,'details');add(d,'summary','Personality, memory and next step');for(const [trait,value] of Object.entries(p.profile.big_five))add(d,'div',`${trait}: ${Math.round(value*100)}%`,'muted');add(d,'p','Traits are authored tendencies, not psychological measurements.','muted');add(d,'div',`State: ${p.agency.state.replaceAll('_',' ')}. ${p.agency.reason||'Awaiting the first scheduled review.'}`,'muted');add(d,'div',`${Object.keys(p.relationships).length} initialized relationship records · ${p.commitments.length} commitments`,'muted');for(const m of p.memories.slice(-3))add(d,'p',m.quote?'Remembered claim: “'+m.quote+'”':m.kind.replaceAll('_',' '),'muted');if(!p.memories.length)add(d,'p','No synthetic past events were added.','muted');}}
for(const id of ['search','sort','filter'])byId(id).addEventListener('input',draw);draw();
</script></html>'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(json.loads(args.input.read_text(encoding='utf-8'))), encoding='utf-8')
    print(args.output)
