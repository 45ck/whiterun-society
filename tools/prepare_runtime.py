"""Create an independent local test installation; never change the Steam install."""
from pathlib import Path
import json
import shutil
import urllib.request
import argparse
import subprocess

def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size == source.stat().st_size:
        return
    temporary=target.with_name(target.name+'.copying')
    shutil.copy2(source,temporary)
    temporary.replace(target)

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
    for relative in ['Data/Platform/Distribution','Data/Platform/Fonts','Data/Platform/Images','Data/NirnLabUIPlatform']:
        for source in (SOURCE / relative).rglob('*'):
            if source.is_file():
                copy(source, GAME / source.relative_to(SOURCE))
    for name in ['SkyrimPlatform.dll','NirnLabUIPlugin.dll','CrashLogger.dll','versionlib-1-6-1170-0.bin','versionlib-1-6-1170-0-1.bin']:
        copy(SOURCE / 'Data' / 'SKSE' / 'Plugins' / name, GAME / 'Data' / 'SKSE' / 'Plugins' / name)
    for name in ['Actor','ActorBase','ObjectReference','Form','Game','Utility','Debug','SKSE','UI','Input','Cell',
                 'ColorForm','Enchantment','HeadPart','Potion','Race','TESModPlatform']:
        source = SOURCE / 'Data' / 'Scripts' / (name + '.pex')
        if source.exists():
            copy(source, GAME / 'Data' / 'Scripts' / source.name)
    # Extended scripts reference one another. A hand-selected subset can make
    # native functions disappear depending on script load order.
    skse_archive=ROOT/'skse64_2_02_06.7z'
    if not skse_archive.exists():
        urllib.request.urlretrieve('https://skse.silverlock.org/beta/skse64_2_02_06.7z',skse_archive)
    vendor=ROOT/'vendor'
    vendor.mkdir(exist_ok=True)
    subprocess.run(['tar','-xf',str(skse_archive),'-C',str(vendor)],check=True)
    for source in (vendor/'skse64_2_02_06'/'Data'/'Scripts').glob('*.pex'):
        shutil.copy2(source,GAME/'Data'/'Scripts'/source.name)
    ini = GAME / 'Data' / 'SKSE' / 'Plugins' / 'SkyrimPlatform.ini'
    if not ini.exists():
        ini.write_text('[Debug]\nLogLevel=2\nCmd=true\nChromiumEnabled=true\n[Main]\nPluginFolders=Data/Platform/PluginsDev\n[Browser]\nBackendName=nirnlab\n', encoding='utf-8')
    ui=GAME/'Data'/'Platform'/'UI'/'index.html'
    ui.parent.mkdir(parents=True,exist_ok=True)
    if not ui.exists(): ui.write_text('<!doctype html><title>Whiterun Society</title>',encoding='utf-8')
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
