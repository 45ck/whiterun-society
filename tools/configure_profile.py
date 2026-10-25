"""Normalize only the isolated MO2 profile after its first-run setup."""
import argparse
import configparser
import json
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--audio-diagnostic',action='store_true',help='Disable audio for an explicitly labelled diagnostic run')
parser.add_argument('--experimental-rest',action='store_true',help='Opt into the unqualified seated-rest plugin; a cold launch has hung')
parser.add_argument('--experimental-routines',action='store_true',help='Enable the experimental eight-slot routing plugin')
parser.add_argument('--experimental-resident-control',action='store_true',help='Enable additive resident continuity control')
args=parser.parse_args()
root=args.root.resolve()
if args.experimental_rest and not (root/'game/Data/WhiterunRest.esp').is_file():
    raise ValueError('Build and stage WhiterunRest.esp before opting into the rest experiment')
if args.experimental_routines and not (root/'game/Data/WhiterunLanes.esp').is_file():
    raise ValueError('Build and stage WhiterunLanes.esp before enabling independent routing')
if args.experimental_resident_control and not (root/'game/Data/WhiterunCitizens.esp').is_file():
    raise ValueError('Stage WhiterunCitizens.esp before enabling resident control')
profile=root/'mod-organizer'/'profiles'/'Default'
settings=configparser.ConfigParser()
settings.read(profile/'settings.ini')
if not settings.getboolean('General','LocalSaves') or not settings.getboolean('General','LocalSettings'):
    raise SystemExit('Enable profile-specific saves and INIs first')
ini=configparser.ConfigParser(interpolation=None)
ini.optionxform=str
ini.read(root/'game'/'Skyrim_Default.ini')
ini['General']['SLocalSavePath']='Saves\\'
ini['General']['bAlwaysActive']='1'
if args.audio_diagnostic:
    if 'Audio' not in ini:ini['Audio']={}
    ini['Audio']['bEnableAudio']='0'
# The source multiplayer installation disables native navigation.
if 'Actor' in ini: ini['Actor'].pop('bUseNavMeshForMovement',None)
if 'Archive' in ini:
    ini['Archive']['bInvalidateOlderFiles']='1'
    ini['Archive']['sResourceDataDirsFinal']=''
with (profile/'skyrim.ini').open('w') as f: ini.write(f,space_around_delimiters=False)
(profile/'skyrimcustom.ini').write_text('[General]\nsStartingCell=WhiterunOrigin\nbAlwaysActive=1\n',encoding='utf-8')
prefs=configparser.ConfigParser(interpolation=None)
prefs.optionxform=str
prefs.read(profile/'skyrimprefs.ini')
for key,value in {'iSize W':'1280','iSize H':'720','bFull Screen':'0','bBorderless':'0','iShadowMapResolution':'1024'}.items():
    prefs['Display'][key]=value
with (profile/'skyrimprefs.ini').open('w') as f: prefs.write(f,space_around_delimiters=False)
print('Observer profile: automatic Whiterun start; local saves and INIs; 1280x720 window; native navigation')
(root/'runtime'/'audio-mode.json').write_text(json.dumps({'disabled':args.audio_diagnostic,
    'scope':'Explicit diagnostic only; not a fix or voice-ready demonstration'}))

plugins=profile/'plugins.txt'
lines=plugins.read_text(encoding='utf-8-sig').splitlines() if plugins.exists() else []
for name in ('WhiterunSociety.esp','WhiterunAgents.esp','WhiterunRouter.esp','WhiterunRest.esp','WhiterunLanes.esp','WhiterunCitizens.esp'):
    if name=='WhiterunCitizens.esp' and not args.experimental_resident_control:
        lines=[line.lstrip('*') if line.lstrip('*').lower()==name.lower() else line for line in lines]
        continue
    if name=='WhiterunLanes.esp' and not args.experimental_routines:
        lines=[line.lstrip('*') if line.lstrip('*').lower()==name.lower() else line for line in lines]
        continue
    if name=='WhiterunRest.esp' and not args.experimental_rest:
        lines=[line.lstrip('*') if line.lstrip('*').lower()==name.lower() else line for line in lines]
        continue
    if name!='WhiterunSociety.esp' and not (root/'game/Data'/name).exists():continue
    # Enable in place. Reordering existing plugins would change saved form IDs.
    matches=[i for i,line in enumerate(lines) if line.lstrip('*').lower()==name.lower()]
    if len(matches)>1:raise ValueError('Duplicate society plugin entry')
    if matches:lines[matches[0]]='*'+name
    else:lines.append('*'+name)
plugins.write_text('\n'.join(lines)+'\n',encoding='utf-8')
