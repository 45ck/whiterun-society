"""Normalize only the isolated MO2 profile after its first-run setup."""
import argparse
import configparser
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,required=True)
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
