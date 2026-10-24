"""Create an independent local test installation; never change the Steam install."""
from pathlib import Path
import json
import shutil
import urllib.request
import argparse

def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(source, target)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    SOURCE, ROOT = args.source.resolve(), args.root.resolve()
    GAME = ROOT / 'game'
    if ROOT == SOURCE or SOURCE in ROOT.parents or ROOT in SOURCE.parents:
        raise SystemExit('Runtime and original game must be separate directories')
    if not (SOURCE / 'SkyrimSE.exe').exists():
        raise SystemExit('Owned game installation missing')
    ROOT.mkdir(exist_ok=True)
    for name in ['SkyrimSE.exe', 'SkyrimSELauncher.exe', 'bink2w64.dll',
                 'steam_api64.dll', 'steam_appid.txt', 'Skyrim_Default.ini',
                 'skse64_loader.exe', 'skse64_1_6_1170.dll', 'Low.ini', 'Medium.ini']:
        copy(SOURCE / name, GAME / name)
    for source in (SOURCE / 'Data').iterdir():
        if source.name.startswith('Skyrim - ') and source.suffix == '.bsa' or source.name in [
            'Skyrim.esm', 'Update.esm', 'Dawnguard.esm', 'HearthFires.esm', 'Dragonborn.esm']:
            print('Copy', source.name, flush=True)
            copy(source, GAME / 'Data' / source.name)
    for source in (SOURCE / 'Data' / 'Platform' / 'Distribution').rglob('*'):
        if source.is_file():
            copy(source, GAME / source.relative_to(SOURCE))
    for name in ['SkyrimPlatform.dll', 'versionlib-1-6-1170-0.bin', 'versionlib-1-6-1170-0-1.bin']:
        copy(SOURCE / 'Data' / 'SKSE' / 'Plugins' / name, GAME / 'Data' / 'SKSE' / 'Plugins' / name)
    for name in ['Actor', 'ObjectReference', 'Form', 'Game', 'Utility', 'Debug', 'SKSE', 'UI', 'Input', 'Cell']:
        source = SOURCE / 'Data' / 'Scripts' / (name + '.pex')
        if source.exists():
            copy(source, GAME / 'Data' / 'Scripts' / source.name)
    ini = GAME / 'Data' / 'SKSE' / 'Plugins' / 'SkyrimPlatform.ini'
    if not ini.exists():
        ini.write_text('[Debug]\nLogLevel=0\nCmd=false\nChromiumEnabled=false\n[Main]\nPluginFolders=Data/Platform/PluginsDev\n', encoding='utf-8')
    (GAME / 'Data' / 'Platform' / 'PluginsDev').mkdir(parents=True, exist_ok=True)
    archive = ROOT / 'Mod.Organizer-2.5.2.7z'
    if not archive.exists():
        print('Download official Mod Organizer portable archive', flush=True)
        urllib.request.urlretrieve('https://github.com/ModOrganizer2/modorganizer/releases/download/v2.5.2/Mod.Organizer-2.5.2.7z', archive)
    (ROOT / 'runtime-manifest.json').write_text(json.dumps({
        'source': str(SOURCE), 'game': str(GAME), 'game_version': '1.6.1170.0',
        'skse_version': '2.2.6', 'source_modified': False,
        'excluded': ['multiplayer plugins', 'Vortex deployment', 'existing saves', 'modded ESPs'],
        'launch_ready': False, 'pending': 'Configure isolated MO2 profile and verify plugin load'
    }, indent=2))
    print('Runtime staged; not yet launched', flush=True)

if __name__ == '__main__':
    main()
