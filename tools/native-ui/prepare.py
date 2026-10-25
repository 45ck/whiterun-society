"""Prepare pinned build inputs. No compiler, bootstrapper or native code is run."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent


def sha256(path):
    with Path(path).open('rb') as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
        return digest.hexdigest()


def source_list_sha256(path):
    # Git checkout line endings must not change the identity of the reviewed list.
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def validate_manifest(manifest):
    if manifest.get('schema_version') != 1 or manifest.get('variant') != 'upstream-unchanged' or manifest.get('reviewed_patches') != []:
        raise ValueError('Only the unchanged upstream build is reviewed')
    for key, repo, prefix in [('upstream', 'kkEngine/NirnLabUIPlatform', 'NirnLabUIPlatform'), ('vcpkg', 'microsoft/vcpkg', 'vcpkg')]:
        item = manifest[key]
        if not re.fullmatch('[0-9a-f]{40}', item['commit']):
            raise ValueError('An exact source commit is required')
        if not re.fullmatch('[0-9a-f]{64}', item['archive_sha256']):
            raise ValueError('An exact archive checksum is required')
        if item['archive_url'] != f"https://codeload.github.com/{repo}/zip/{item['commit']}" or item['archive_root'] != f"{prefix}-{item['commit']}":
            raise ValueError('Source URL/root does not match its reviewed repository and commit')
    vcpkg = manifest['vcpkg']
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', vcpkg['tool_release']):
        raise ValueError('An exact tool release is required')
    if vcpkg['tool_url'] != f"https://github.com/microsoft/vcpkg-tool/releases/download/{vcpkg['tool_release']}/vcpkg.exe":
        raise ValueError('Unexpected tool URL')
    if not isinstance(vcpkg.get('tool_sha256'), str) or not re.fullmatch('[0-9a-f]{64}', vcpkg['tool_sha256']):
        raise ValueError('Unresolved vcpkg executable checksum')
    if vcpkg['triplet'] != 'x64-windows-static':
        raise ValueError('Unreviewed triplet')


def download(url, destination, expected):
    destination = Path(destination)
    with urllib.request.urlopen(url, timeout=120) as response, destination.open('xb') as out:
        shutil.copyfileobj(response, out)
    actual = sha256(destination)
    if actual != expected:
        raise ValueError(f'Checksum mismatch for {destination.name}; do not execute or extract')
    return {'url': url, 'sha256': actual, 'bytes': destination.stat().st_size}


def extract(archive, destination, root):
    """Reject traversal, links, duplicates and excessive expansion before writing."""
    destination = Path(destination)
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if sum(info.file_size for info in members) > 512 * 1024 * 1024 or len(members) > 100000:
            raise ValueError('Unexpected archive size')
        seen = set()
        for info in members:
            path = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (not path.parts or path.parts[0] != root or path.is_absolute()
                    or '..' in path.parts or '\\' in info.filename or ':' in info.filename
                    or stat.S_ISLNK(mode) or info.filename.casefold() in seen):
                raise ValueError('Unsafe archive member')
            seen.add(info.filename.casefold())
        destination.mkdir()
        for info in members:
            relative = PurePosixPath(info.filename).parts[1:]
            if not relative:
                continue
            target = destination.joinpath(*relative)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(info) as src, target.open('xb') as out:
                    shutil.copyfileobj(src, out)


def verify_source(source, proof):
    rows = []
    for relative, expected in proof['files'].items():
        path = PurePosixPath(relative)
        if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative:
            raise ValueError('Unsafe source manifest path')
        data = Path(source).joinpath(*path.parts).read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if actual != expected:
            raise ValueError(f'Upstream source changed: {relative}')
        rows.append({'path': relative, 'git_blob_sha1': actual, 'sha256': hashlib.sha256(data).hexdigest()})
    return rows


def prepare(output):
    output = Path(output).resolve()
    output.mkdir(exist_ok=True)
    evidence = output / 'evidence'
    evidence.mkdir(exist_ok=True)
    manifest = json.loads((HERE / 'manifest.json').read_text())
    validate_manifest(manifest)
    if source_list_sha256(HERE / 'upstream-files.json') != manifest['upstream']['files_manifest_sha256']:
        raise ValueError('Source-file manifest checksum mismatch')
    proof = json.loads((HERE / 'upstream-files.json').read_text())
    if proof['commit'] != manifest['upstream']['commit']:
        raise ValueError('Source-file manifest commit mismatch')
    receipts = []
    for key in ['upstream', 'vcpkg']:
        spec = manifest[key]
        archive = output / f'{key}.zip'
        receipts.append(download(spec['archive_url'], archive, spec['archive_sha256']))
        extract(archive, output / key, spec['archive_root'])
    rows = verify_source(output / 'upstream', proof)
    metadata = (output / 'vcpkg/scripts/vcpkg-tool-metadata.txt').read_text()
    if f"VCPKG_TOOL_RELEASE_TAG={manifest['vcpkg']['tool_release']}" not in metadata.splitlines():
        raise ValueError('Tool release differs from pinned vcpkg source')
    spec = manifest['vcpkg']
    receipts.append(download(spec['tool_url'], output / 'vcpkg/vcpkg.exe', spec['tool_sha256']))
    (output / 'vcpkg/.vcpkg-root').touch(exist_ok=True)
    shutil.copy2(HERE / 'manifest.json', evidence / 'input-manifest.json')
    shutil.copy2(HERE / 'upstream-files.json', evidence / 'upstream-files.json')
    (evidence / 'prepared-inputs.json').write_text(json.dumps({'downloads': receipts, 'verified_source_files': rows}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    prepare(parser.parse_args().output)
