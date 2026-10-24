"""Build our original, minimal Skyrim SE save-lineage plugin.

No Bethesda records or assets are copied. The single non-constant float global
is a save-persistent checkpoint ID; IDs must stay within exact float32 integers.
"""
import argparse
from pathlib import Path
import struct

PLUGIN='WhiterunSociety.esp'
LOCAL_FORM_ID=0x800

def subrecord(kind,data):
    return struct.pack('<4sH',kind,len(data))+data

def record(kind,form_id,data):
    return struct.pack('<4sIIIIHH',kind,len(data),0,form_id,0,44,0)+data

def build():
    header=subrecord(b'HEDR',struct.pack('<fII',1.7,2,LOCAL_FORM_ID+1))
    header+=subrecord(b'CNAM',b'Whiterun Society contributors\0')
    header+=subrecord(b'SNAM',b'Original save-lineage marker for the society service.\0')
    header+=subrecord(b'MAST',b'Skyrim.esm\0')+subrecord(b'DATA',bytes(8))
    data=subrecord(b'EDID',b'WSSocietyCheckpoint\0')
    data+=subrecord(b'FNAM',b'f')+subrecord(b'FLTV',struct.pack('<f',0))
    # One master: the plugin-local namespace is 01 in the file, resolved at load.
    glob=record(b'GLOB',0x01000000|LOCAL_FORM_ID,data)
    group=struct.pack('<4sI4sIHHHH',b'GRUP',24+len(glob),b'GLOB',0,0,0,0,0)+glob
    return record(b'TES4',0,header)+group

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(build())
    print(f'Built original lineage plugin: {args.output} ({args.output.stat().st_size} bytes)')
