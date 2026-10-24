"""Normalize only the isolated MO2 profile after its first-run setup."""
import argparse
import configparser
import json
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--audio-diagnostic',action='store_true',help='Disable audio for an explicitly labelled diagnostic run')
args=parser.parse_args()
root=args.root.resolve()
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
for name in ('WhiterunSociety.esp','WhiterunAgents.esp','WhiterunRouter.esp'):
    if name!='WhiterunSociety.esp' and not (root/'game/Data'/name).exists():continue
    # Enable in place. Reordering existing plugins would change saved form IDs.
    matches=[i for i,line in enumerate(lines) if line.lstrip('*').lower()==name.lower()]
    if len(matches)>1:raise ValueError('Duplicate society plugin entry')
    if matches:lines[matches[0]]='*'+name
    else:lines.append('*'+name)
plugins.write_text('\n'.join(lines)+'\n',encoding='utf-8')
