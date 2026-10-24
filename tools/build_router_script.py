"""Compile only our routing script into a staging folder; never install it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

parser=argparse.ArgumentParser()
parser.add_argument('--compiler',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
compiler=args.compiler.resolve();output=args.output.resolve()
interfaces=repo/'tools/papyrus-interfaces'
output.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='router-build-',dir=output) as temporary:
    subprocess.run([str(compiler),'--game','skyrim','--allow-unknown-events','1',
        '--flags',str(interfaces/'Flags.flg'),'--import',str(interfaces),
        '--output',temporary,'WSSocietyRouter.psc'],cwd=repo/'papyrus',check=True)
    built=Path(temporary)/'WSSocietyRouter.pex'
    data=built.read_bytes()
    if len(data)<100 or not any(int.from_bytes(data[:4],order)==0xfa57c0de for order in ('big','little')):
        raise ValueError('Compiler did not produce a PEX artifact')
    if list(Path(temporary).glob('*.pex'))!=[built]:raise ValueError('Only the original router may be compiled')
    shutil.copy2(built,output/built.name)
print(json.dumps({'file':str(output/built.name),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
    'scope':'Compiled staging artifact; quest attachment and native execution are unverified'}))
