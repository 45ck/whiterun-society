"""Install only our staged router into the stopped, isolated Skyrim lab."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
from launch_demo import game_paths


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--stage',type=Path,required=True)
    parser.add_argument('--lanes',action='store_true',help='Install the additive eight-slot plugin instead of replacing the original router')
    args=parser.parse_args()
    root=args.root.resolve();stage=args.stage.resolve()
    manifest=json.loads((root/'runtime-manifest.json').read_text())
    game=Path(manifest['game']).resolve();original=Path(manifest['source']).resolve()
    if game!=root/'game' or game==original or root in original.parents or original in root.parents:
        raise ValueError('Runtime isolation check failed')
    if game_paths():raise ValueError('Close Skyrim before installing native plugins')
    plugin='WhiterunLanes.esp' if args.lanes else 'WhiterunRouter.esp'
    files={plugin:game/'Data'/plugin,
           'WSSocietyRouter.pex':game/'Data/Scripts/WSSocietyRouter.pex'}
    for name in files:
        data=(stage/name).read_bytes()
        expected=(b'TES4',) if name.endswith('.esp') else (bytes.fromhex('fa57c0de'),bytes.fromhex('dec057fa'))
        if len(data)<100 or data[:4] not in expected:raise ValueError('Invalid staged artifact: '+name)
    backup=root/'runtime'/('router-install-'+str(time.time_ns()));backup.mkdir()
    record={'scope':'Original router only; launch and native execution require separate verification','files':{}}
    for name,target in files.items():
        if target.exists():shutil.copy2(target,backup/name)
        target.parent.mkdir(parents=True,exist_ok=True)
        temp=target.with_suffix(target.suffix+'.new');shutil.copyfile(stage/name,temp);temp.replace(target)
        record['files'][name]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size}
    (backup/'installation.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record))


if __name__=='__main__':main()
