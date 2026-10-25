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
endowments=(Path(__file__).resolve().parents[1]/'bridge'/'endowments.js').read_text().split('\nif(typeof module')[0]
source=source.replace('__ENDOWMENT_FACTORY__',endowments)
production=(Path(__file__).resolve().parents[1]/'bridge'/'production.js').read_text().split('\nif(typeof module')[0]
source=source.replace('__PRODUCTION_FACTORY__',production)
movement=(Path(__file__).resolve().parents[1]/'bridge'/'movement.js').read_text().split('\nif(typeof module')[0]
source=source.replace('__MOVEMENT_FACTORY__',movement)
router=(Path(__file__).resolve().parents[1]/'bridge'/'papyrus-router.js').read_text().split('\nif(typeof module')[0]
source=source.replace('__PAPYRUS_ROUTER_FACTORY__',router)
source=source.replace('__RESIDENT_CONTROL_FACTORY__',(Path(__file__).resolve().parents[1]/'bridge/resident-control.js').read_text(encoding='utf-8-sig').split('\nif(typeof module')[0])
source=source.replace('__SCENE_HANDOFF_FACTORY__',(Path(__file__).resolve().parents[1]/'bridge'/'scene-handoffs.js').read_text().split('\nif(typeof module')[0])
source=source.replace('__PLACE_FACTORY__',(Path(__file__).resolve().parents[1]/'bridge'/'places.js').read_text().split('\nif(typeof module')[0])
rest=(Path(__file__).resolve().parents[1]/'bridge'/'rest.js').read_text().split('\nif(typeof module')[0]
source=source.replace('__REST_FACTORY__',rest)
routines=(Path(__file__).resolve().parents[1]/'bridge'/'agent-routines.js').read_text().split('\nif(typeof module')[0]
source=source.replace('__ROUTINE_FACTORY__',routines)
source=source.replace('__PARALLEL_ROUTINES_FACTORY__',(Path(__file__).resolve().parents[1]/'bridge'/'parallel-routines.js').read_text().split('\nif(typeof module')[0])
source=source.replace('__CONVERSATION_ATTENDANCE_FACTORY__',(Path(__file__).resolve().parents[1]/'bridge'/'conversation-attendance.js').read_text().split('\nif(typeof module')[0])
speech=(Path(__file__).resolve().parents[1]/'bridge'/'speech.js').read_text().split('\nif(typeof module')[0]
source=source.replace('__SPEECH_FACTORY__',speech)
source=source.replace('__OBSERVER_CAMERA_FACTORY__',(Path(__file__).resolve().parents[1]/'bridge'/'observer-camera.js').read_text().split('\nif(typeof module')[0])
target=game/'Data'/'Platform'/'PluginsDev'/'whiterun-society.js'
target.parent.mkdir(parents=True,exist_ok=True)
ui_source=''.join((Path(__file__).resolve().parents[1]/'ui'/name).read_text(encoding='utf-8') for name in ('index.html','speech.js','encounter.js','rts-camera.js','rts-controls.js','movie-broadcast.js','society-dashboard.js','voice-output.js','resident-media-data.js','resident-media.js'))
source+='\n// UI revision: '+hashlib.sha256(ui_source.encode()).hexdigest()+'\n'
target.write_text(source.replace('__BRIDGE_CONFIG__',json.dumps(config)),encoding='utf-8')
ui=game/'Data'/'Platform'/'UI'/'index.html'
ui.parent.mkdir(parents=True,exist_ok=True)
ui.write_text((Path(__file__).resolve().parents[1]/'ui'/'index.html').read_text(encoding='utf-8'),encoding='utf-8')
(ui.parent/'speech.js').write_text((Path(__file__).resolve().parents[1]/'ui'/'speech.js').read_text(encoding='utf-8'),encoding='utf-8')
(ui.parent/'encounter.js').write_text((Path(__file__).resolve().parents[1]/'ui'/'encounter.js').read_text(encoding='utf-8'),encoding='utf-8')
for name in ('rts-camera.js','rts-controls.js','movie-broadcast.js','society-dashboard.js','voice-output.js','resident-media-data.js','resident-media.js'):
    (ui.parent/name).write_text((Path(__file__).resolve().parents[1]/'ui'/name).read_text(encoding='utf-8'),encoding='utf-8')
(ui.parent/'voice-check.wav').write_bytes((Path(__file__).resolve().parents[1]/'docs/audio/scene-handoff-a-1.wav').read_bytes())
print('Deployed custom bridge to isolated game')

media=json.loads((Path(__file__).resolve().parents[1]/'docs/images/resident-media.json').read_text())
(ui.parent/'media').mkdir(exist_ok=True)
for asset in [media['map'],*media['portraits'].values()]:
    name=asset['file']
    if Path(name).name!=name or not name.endswith(('.png','.jpg')):raise ValueError('Invalid captured media path')
    (ui.parent/'media'/name).write_bytes((Path(__file__).resolve().parents[1]/'docs/images'/name).read_bytes())
