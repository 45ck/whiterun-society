"""Fetch pinned, checksum-verified local inference files into the development lab."""
import argparse,hashlib,json,time,urllib.request,zipfile
from pathlib import Path

ASSETS=[
 ('vendor/llama-b11849-bin-win-cpu-x64.zip','https://github.com/ggml-org/llama.cpp/releases/download/b11849/llama-b11849-bin-win-cpu-x64.zip','d06c1e2f3b9d80b948fd95b1de1e02221db30f6a9fe147ec16106a73ad101a85'),
 ('models/Qwen3.5-2B-Q4_K_M.gguf','https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/f6d5376be1edb4d416d56da11e5397a961aca8ae/Qwen3.5-2B-Q4_K_M.gguf','aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223')]

def digest(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args();root=args.root.resolve()
 if not (root/'runtime-manifest.json').exists():raise SystemExit('Use the prepared lab directory')
 for relative,url,expected in ASSETS:
  dest=root/relative;dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists() and digest(dest)==expected:print('Verified existing',dest.name,flush=True);continue
  partial=dest.with_suffix(dest.suffix+'.partial');last=time.monotonic();total=0
  with urllib.request.urlopen(url,timeout=60) as response, partial.open('wb') as output:
   while chunk:=response.read(1024*1024):
    output.write(chunk);total+=len(chunk)
    if time.monotonic()-last>10:print(f'{dest.name}: {total/1024**2:.0f} MiB',flush=True);last=time.monotonic()
  if digest(partial)!=expected:raise SystemExit('Checksum mismatch: '+dest.name)
  partial.replace(dest);print('Downloaded and verified',dest.name,flush=True)
 target=root/'vendor/llama-b11849';target.mkdir(exist_ok=True)
 with zipfile.ZipFile(root/ASSETS[0][0]) as archive:
  for member in archive.infolist():
   if not (target/member.filename).resolve().is_relative_to(target):raise SystemExit('Unsafe archive path')
  archive.extractall(target)
 (root/'runtime/model-manifest.json').write_text(json.dumps({'model':'Qwen3.5-2B-Q4_K_M','engine':'llama.cpp b11849','files':[{'path':p,'url':u,'sha256':h} for p,u,h in ASSETS]},indent=2))
 print('Local model prepared; no inference server started',flush=True)

if __name__=='__main__':main()
