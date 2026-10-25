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
    parser.add_argument('--resident-control',action='store_true',help='Install the additive standing resident control plugin and its own script')
    parser.add_argument('--activities',action='store_true',help='Install two additive independent furniture slots; preserve the existing shared router script')
    args=parser.parse_args()
    root=args.root.resolve();stage=args.stage.resolve()
    manifest=json.loads((root/'runtime-manifest.json').read_text())
    game=Path(manifest['game']).resolve();original=Path(manifest['source']).resolve()
    if game!=root/'game' or game==original or root in original.parents or original in root.parents:
        raise ValueError('Runtime isolation check failed')
    if game_paths():raise ValueError('Close Skyrim before installing native plugins')
    if sum((args.lanes,args.resident_control,args.activities))>1:raise ValueError('Choose one plugin installation')
    plugin='WhiterunActivities.esp' if args.activities else 'WhiterunCitizens.esp' if args.resident_control else 'WhiterunLanes.esp' if args.lanes else 'WhiterunRouter.esp'
    script='WSSocietyResident.pex' if args.resident_control else 'WSSocietyRouter.pex'
    files={plugin:game/'Data'/plugin,
           script:game/'Data/Scripts'/script}
    for name in files:
        data=(stage/name).read_bytes()
        expected=(b'TES4',) if name.endswith('.esp') else (bytes.fromhex('fa57c0de'),bytes.fromhex('dec057fa'))
        if len(data)<100 or data[:4] not in expected:raise ValueError('Invalid staged artifact: '+name)
    shared_script_unchanged=False
    if args.activities and files[plugin].exists() and files[plugin].read_bytes()!=(stage/plugin).read_bytes():
        raise ValueError('Activities installation is additive; an existing plugin cannot be replaced with different bytes')
    if args.activities and files[script].exists():
        if files[script].read_bytes()!=(stage/script).read_bytes():
            raise ValueError('Activities must reuse the existing router script byte-for-byte')
        shared_script_unchanged=True
        del files[script]
    backup=root/'runtime'/('router-install-'+str(time.time_ns()));backup.mkdir()
    record={'scope':plugin+' only; launch and native execution require separate verification','shared_script_unchanged':shared_script_unchanged,'files':{}}
    for name,target in files.items():
        if target.exists():shutil.copy2(target,backup/name)
        target.parent.mkdir(parents=True,exist_ok=True)
        temp=target.with_suffix(target.suffix+'.new');shutil.copyfile(stage/name,temp);temp.replace(target)
        record['files'][name]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size}
    (backup/'installation.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record))


if __name__=='__main__':main()
