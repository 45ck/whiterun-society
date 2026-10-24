"""Deploy only to an explicitly prepared isolated test installation."""
import argparse
import json
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
source=(Path(__file__).resolve().parents[1]/'bridge'/'whiterun-society.js').read_text()
target=game/'Data'/'Platform'/'PluginsDev'/'whiterun-society.js'
target.parent.mkdir(parents=True,exist_ok=True)
target.write_text(source.replace('__BRIDGE_CONFIG__',json.dumps(config)),encoding='utf-8')
print('Deployed custom bridge to isolated game')
