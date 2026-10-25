"""Deploy only to an explicitly prepared isolated test installation."""
import argparse
import json
import hashlib
import re
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
venue_catalog=json.loads((Path(__file__).resolve().parents[1]/'config/places.json').read_text(encoding='utf-8'))
if (not isinstance(venue_catalog,dict) or not isinstance(venue_catalog.get('version'),str)
        or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',venue_catalog['version'])
        or not isinstance(venue_catalog.get('knowledge'),str) or not venue_catalog['knowledge'].strip() or len(venue_catalog['knowledge'])>500
        or not isinstance(venue_catalog.get('venues'),list) or len(venue_catalog['venues'])>512):
    raise ValueError('Invalid venue catalogue')
venue_ids=set()
for venue in venue_catalog['venues']:
    if (not isinstance(venue,dict) or type(venue.get('id')) is not int or not 0<venue['id']<=0xffffffff or venue['id'] in venue_ids
            or venue.get('kind') not in ('public_place','rest_bench')
            or any(not isinstance(venue.get(k),str) or not venue[k].strip() or len(venue[k])>limit for k,limit in (('name',120),('provenance',500)))
            or venue.get('access')!=('inspected_unowned' if venue['kind']=='rest_bench' else 'public')
            or ('editor_id' in venue and (not isinstance(venue['editor_id'],str) or len(venue['editor_id'])>120))):
        raise ValueError('Invalid venue catalogue entry')
    venue_ids.add(venue['id'])
venue_source='const WHITERUN_VENUE_CATALOG='+json.dumps(venue_catalog)+';\n'
source=source.replace('__PLACE_FACTORY__',venue_source+(Path(__file__).resolve().parents[1]/'bridge'/'places.js').read_text().split('\nif(typeof module')[0])
rest=(Path(__file__).resolve().parents[1]/'bridge'/'rest.js').read_text().split('\nif(typeof module')[0]
source=source.replace('__REST_FACTORY__',rest)
source=source.replace('__ACTIVITY_JOBS_FACTORY__',(Path(__file__).resolve().parents[1]/'bridge'/'activity-jobs.js').read_text(encoding='utf-8').split('\nif(typeof module')[0])
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
