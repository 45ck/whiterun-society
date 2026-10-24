"""Apply a narrowly verified local compatibility fix to NirnLab's menu flags.

The installed upstream constructor omits CommonLib's kAllowSaving (1 << 11).
This prevents Skyrim saves while the always-open overlay menu is present.
Only the exact inspected binary is supported. Keep the original for rollback.
No third-party binary is distributed by this project.
"""
import argparse
import hashlib
from pathlib import Path

ORIGINAL_SHA256='b2f564afc796ed7c07c3a2993d229fa13aa20b1fc9ba23767229adc1519d13cf'
OFFSET=0x3d7e7
ORIGINAL=bytes.fromhex('81 4f 1c 02 80 01 00')
PATCHED=bytes.fromhex('81 4f 1c 02 88 01 00')

def patched(data):
    if hashlib.sha256(data).hexdigest()!=ORIGINAL_SHA256 or data[OFFSET:OFFSET+7]!=ORIGINAL:
        raise ValueError('Unsupported binary: refusing to patch')
    result=bytearray(data);result[OFFSET:OFFSET+7]=PATCHED
    return bytes(result)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    import json
    manifest=json.loads((root/'runtime-manifest.json').read_text())
    if Path(manifest['game']).resolve()!=root/'game' or Path(manifest['source']).resolve()==root/'game':
        raise SystemExit('Unverified isolated game')
    target=root/'game/Data/NirnLabUIPlatform/NirnLabUIPlatform.dll'
    backup=target.with_suffix('.dll.original')
    data=target.read_bytes()
    if backup.exists() and data==patched(backup.read_bytes()):
        print('Save compatibility fix already applied')
    else:
        fixed=patched(data)
        if backup.exists() and backup.read_bytes()!=data: raise SystemExit('Conflicting backup')
        if not backup.exists(): backup.write_bytes(data)
        target.write_bytes(fixed)
        print('Applied kAllowSaving to the verified lab overlay; original retained')
