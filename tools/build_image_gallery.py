"""Build the documentation gallery from project images; no remote dependencies."""
from html import escape
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
GENERATED={'npc-four-systems.png','whole-simulation.png','personal-knowledge-loop.png','voiced-trade-loop.png'}

def build():
    images=sorted((ROOT/'docs/images').iterdir(),key=lambda p:(p.name not in GENERATED,p.name))
    records=[];cards=[];markdown=['# Visual documentation','All finished project images are stored in `docs/images`. Generated illustrations explain design; captured interfaces show historical prototype states, not current acceptance of every visible feature. See the linked evidence documents for scope.']
    for image in images:
        if image.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):continue
        title=image.stem.replace('-',' ').capitalize()
        kind='Generated system illustration — not gameplay' if image.name in GENERATED else 'Captured game or observer interface — historical prototype'
        records.append({'file':image.name,'title':title,'kind':kind})
        cards.append(f'<article><a href="images/{escape(image.name)}"><img loading="lazy" src="images/{escape(image.name)}" alt="{escape(title)}"></a><h2>{escape(title)}</h2><p>{escape(kind)}</p><a href="images/{escape(image.name)}">Open full image</a></article>')
        markdown.extend([f'## {title}',kind,f'![{title}](images/{image.name})'])
    (ROOT/'docs/images/catalog.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
    (ROOT/'docs/gallery.md').write_text('\n\n'.join(markdown)+'\n',encoding='utf-8')
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Whiterun Society — visual documentation</title>
<style>body{background:#111c22;color:#eee5d5;font:16px system-ui;margin:0}header,main{max-width:1400px;margin:auto;padding:28px}h1{font:42px Georgia;margin-bottom:12px}p{line-height:1.6;color:#bdc9cb}a{color:#ecc77c}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:24px}article{background:#1d2c33;border:1px solid #40515a;border-radius:12px;padding:16px}img{width:100%;aspect-ratio:1.5;object-fit:contain;background:#10181d;border-radius:5px}h2{font-size:20px}article p{font-size:14px}</style>
<header><p>WHITERUN SOCIETY · OPEN SOURCE</p><h1>Visual documentation</h1><p>System diagrams and captured game/observer views. Illustrations are labelled; screenshots preserve historical milestones and do not prove every current requirement is complete.</p><nav><a href="http://127.0.0.1:17854/">Local control room (requires lab)</a> · <a href="https://github.com/45ck/whiterun-society">README &amp; source</a> · <a href="https://github.com/45ck/whiterun-society/blob/main/docs/quality-metrics.md">Metrics and evidence limits</a></nav></header><main>'''+''.join(cards)+'</main></html>\n'
    (ROOT/'docs/index.html').write_text(html,encoding='utf-8')
    readme=ROOT/'README.md';text=readme.read_text(encoding='utf-8')
    start='<!-- IMAGE_GALLERY_START -->';end='<!-- IMAGE_GALLERY_END -->'
    gallery='\n\n'.join(['<details>',f'<summary>Browse every finished project image ({len(records)})</summary>',
        *[f"### {r['title']}\n\n{r['kind']}\n\n![{r['title']}](docs/images/{r['file']})" for r in records],'</details>'])
    block=start+'\n'+gallery+'\n'+end
    if start in text:text=text[:text.index(start)]+block+text[text.index(end)+len(end):]
    else:text=text.rstrip()+'\n\n'+block+'\n'
    readme.write_text(text,encoding='utf-8')
    print(json.dumps({'finished_images':len(records),'generated':len(GENERATED),'gallery':'docs/index.html'}))

if __name__=='__main__':build()
