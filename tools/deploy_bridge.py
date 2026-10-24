"""Deploy only to an explicitly prepared isolated test installation."""
import argparse
import json
import hashlib
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,required=True)
args=parser.parse_args()
root=args.root.resolve()
manifest=json.loads((root/'runtime-manifest.json').read_text())
game=Path(manifest['game']).resolve()
if game.parent!=root or Path(manifest['source']).resolve()==game:
    raise SystemExit('Refusing unverified runtime directory')
config=json.loads((root/'runtime'/'bridge-config.json').read_text())
audio_mode=root/'runtime'/'audio-mode.json'
config['audioDiagnostic']=json.loads(audio_mode.read_text()).get('disabled',False) if audio_mode.exists() else False
source=(Path(__file__).resolve().parents[1]/'bridge'/'whiterun-society.js').read_text()
factory=(Path(__file__).resolve().parents[1]/'bridge'/'inventory-transfers.js').read_text().split('\nif (typeof module')[0]
source=source.replace('__TRANSFER_FACTORY__',factory)
production=(Path(__file__).resolve().parents[1]/'bridge'/'production.js').read_text().split('\nif(typeof module')[0]
source=source.replace('__PRODUCTION_FACTORY__',production)
movement=(Path(__file__).resolve().parents[1]/'bridge'/'movement.js').read_text().split('\nif(typeof module')[0]
source=source.replace('__MOVEMENT_FACTORY__',movement)
routines=(Path(__file__).resolve().parents[1]/'bridge'/'agent-routines.js').read_text().split('\nif(typeof module')[0]
source=source.replace('__ROUTINE_FACTORY__',routines)
target=game/'Data'/'Platform'/'PluginsDev'/'whiterun-society.js'
target.parent.mkdir(parents=True,exist_ok=True)
ui_source=(Path(__file__).resolve().parents[1]/'ui'/'index.html').read_text(encoding='utf-8')
source+='\n// UI revision: '+hashlib.sha256(ui_source.encode()).hexdigest()+'\n'
target.write_text(source.replace('__BRIDGE_CONFIG__',json.dumps(config)),encoding='utf-8')
ui=game/'Data'/'Platform'/'UI'/'index.html'
ui.parent.mkdir(parents=True,exist_ok=True)
ui.write_text((Path(__file__).resolve().parents[1]/'ui'/'index.html').read_text(encoding='utf-8'),encoding='utf-8')
print('Deployed custom bridge to isolated game')
