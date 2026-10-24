"""Render measured native travel samples as a portable, offline review page."""
import argparse
import html
import json
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--input',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();evidence=json.loads(args.input.read_text())
movement=evidence['ack']['movement'];samples=evidence['samples']
values=[movement['startDistance']]+[s['distance'] for s in samples]
maximum=max(values)*1.08
points=' '.join(f'{70+i*820/max(1,len(values)-1):.1f},{320-v/maximum*250:.1f}' for i,v in enumerate(values))
names={a['id']:a['name'] for a in evidence['before']['residents']}
actor=html.escape(names.get(movement['actor'],str(movement['actor'])))
target=html.escape(names.get(movement['target'],str(movement['target'])))
duration=(movement['releaseAt']-movement['at'])/1000
threshold=320-250/maximum*250
page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Whiterun resident travel evidence</title><style>
body{{background:#10161c;color:#e7edf2;font:17px/1.55 system-ui;margin:auto;padding:44px 24px;max-width:1050px}}
h1{{font-size:38px;line-height:1.15}}.label{{color:#9dc6e0;text-transform:uppercase;letter-spacing:2px;font-size:13px}}
.cards{{display:flex;flex-wrap:wrap;gap:14px}}.card{{background:#1d2933;border:1px solid #354a5c;border-radius:12px;padding:20px;flex:1;min-width:180px}}
.value{{display:block;font-size:30px;color:#9cdbbb}}svg{{width:100%;background:#19232d;border-radius:12px;margin-top:24px}}a{{color:#a6d6ff}}.note{{color:#acbbc8}}
</style><body><p class="label">Whiterun Society · Native game evidence</p>
<h1>{actor} walks to {target}</h1>
<p>Papyrus bound both residents, Skyrim applied our travel package, and the resident returned to a vanilla package after arrival.</p>
<div class="cards"><div class="card">Starting separation<span class="value">{movement['startDistance']:,.0f}</span>Skyrim units</div>
<div class="card">Arrival separation<span class="value">{movement['distance']:,.0f}</span>inside the 250-unit threshold</div>
<div class="card">Route duration<span class="value">{duration:.1f}s</span>including assignment and release request</div></div>
<svg viewBox="0 0 940 385" role="img" aria-label="Observed separation decreases from {movement['startDistance']:.0f} to {movement['distance']:.0f} units">
<text x="70" y="35" fill="#e7edf2">Distance to destination</text>
<line x1="70" x2="890" y1="320" y2="320" stroke="#526477"/>
<line x1="70" x2="890" y1="{threshold:.1f}" y2="{threshold:.1f}" stroke="#d6b678" stroke-dasharray="6 6"/>
<polyline points="{points}" fill="none" stroke="#9cdbbb" stroke-width="4"/>
<text x="70" y="360" fill="#acbbc8">Observed samples, in order</text><text x="700" y="360" fill="#d6b678">Arrival threshold: 250</text></svg>
<h2>What this demonstrates</h2><p>A resident outside the original three can take an owned travel task and release it. The destination in this probe was selected by the test. Separate model-driven trials selected a nearby visit and a deferral; they do not establish a long autonomous journey.</p>
<p class="note">This is a chart of native observations, not a game recording. Interior routes, simultaneous travel, whole-town resource persistence and the expanded in-game interface remain unqualified.</p>
<p><a href="https://github.com/45ck/whiterun-society/blob/main/docs/papyrus-routing.md">Source and reproduction</a> · <a href="index.html">Population overview</a></p></body></html>'''
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(page,encoding='utf-8')
print(str(args.output))
