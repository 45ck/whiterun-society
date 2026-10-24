"""Download pinned Kokoro assets to an already prepared isolated lab.

Create voice-venv and install voice-requirements.txt separately. No game assets,
voices from actors, secrets or model weights are distributed by this project.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ASSETS={'kokoro-v1.0.onnx':'beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a',
        'voices-v1.0.bin':'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    root=args.root.resolve();manifest=json.loads((root/'runtime-manifest.json').read_text())
    if Path(manifest['game']).resolve()!=root/'game' or Path(manifest['source']).resolve()==root/'game':
        raise ValueError('An isolated prepared lab is required')
    target=root/'models/kokoro';target.mkdir(parents=True,exist_ok=True);evidence=[]
    for name,digest in ASSETS.items():
        asset=target/name;url='https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'+name
        if not asset.exists():
            tmp=asset.with_suffix(asset.suffix+'.downloading');urllib.request.urlretrieve(url,tmp)
            if hashlib.sha256(tmp.read_bytes()).hexdigest()!=digest:raise ValueError('Downloaded model hash mismatch')
            tmp.replace(asset)
        if hashlib.sha256(asset.read_bytes()).hexdigest()!=digest:raise ValueError('Existing model hash mismatch')
        evidence.append({'name':name,'url':url,'bytes':asset.stat().st_size,'sha256':digest})
    (target/'provenance.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence))


if __name__=='__main__':main()
