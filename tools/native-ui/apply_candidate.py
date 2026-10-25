"""Apply only the reviewed opt-in input candidate to verified build sources; no execution."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent / 'input-candidate'
EDITS = {
    'src/UIPlatform/Menus/MultiLayerMenu.cpp', 'src/UIPlatform/Menus/CEFMenu.cpp',
    'src/UIPlatform/Hooks/WinProcHook.h', 'src/UIPlatform/Hooks/WinProcHook.cpp',
    'src/UIPlatform/CEF/DefaultBrowser.h', 'src/UIPlatform/CEF/DefaultBrowser.cpp',
}
ADDITIONS = {f'src/UIPlatform/Hooks/{name}': name for name in ['InputPolicy.h', 'WhiterunMouseRoute.h', 'WhiterunMouseRoute.cpp']}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply_edit(original, spec):
    if digest(original) != spec['original_sha256']:
        raise ValueError('Candidate original source checksum mismatch')
    result = original
    for replacement in spec['replacements']:
        old, new = replacement['old'].encode(), replacement['new'].encode()
        if not old or result.count(old) != 1:
            raise ValueError('Candidate requires one exact source match')
        result = result.replace(old, new, 1)
    if digest(result) != spec['result_sha256']:
        raise ValueError('Candidate result checksum mismatch')
    return result


def validate(manifest):
    if manifest.get('schema_version') != 1 or manifest.get('id') != 'save-and-opt-in-mouse-v1':
        raise ValueError('Unreviewed source candidate')
    if manifest.get('upstream_commit') != 'c9514ac16434e2edc2bbfb348be2fcdc47e1d6e2' or manifest.get('default_mode') != 'native' or manifest.get('qualified') is not False:
        raise ValueError('Unreviewed candidate base/default/qualification')
    if len(manifest['edits']) != len(EDITS) or {row['path'] for row in manifest['edits']} != EDITS:
        raise ValueError('Unexpected source edit scope')
    if len(manifest['additions']) != len(ADDITIONS) or {row['path']: row['source'] for row in manifest['additions']} != ADDITIONS:
        raise ValueError('Unexpected source addition scope')
    for row in manifest['additions']:
        if digest((HERE / row['source']).read_bytes().replace(b'\r\n', b'\n')) != row['sha256']:
            raise ValueError('Candidate template checksum mismatch')
    if digest((HERE / 'changes.patch').read_bytes().replace(b'\r\n', b'\n')) != manifest['patch_sha256']:
        raise ValueError('Reviewed source diff checksum mismatch')


def apply(root):
    root = Path(root).resolve()
    manifest = json.loads((HERE / 'candidate.json').read_text())
    validate(manifest)
    prepared, diff = [], []
    for row in manifest['edits']:
        target = root / row['path']
        original = target.read_bytes()
        result = apply_edit(original, row)
        prepared.append((target, result))
        diff.extend(difflib.unified_diff(original.decode().splitlines(keepends=True), result.decode().splitlines(keepends=True),
                                         fromfile='a/' + row['path'], tofile='b/' + row['path']))
    for row in manifest['additions']:
        target = root / row['path']
        if target.exists():
            raise ValueError('Refusing to replace an existing added source file')
        data = (HERE / row['source']).read_bytes().replace(b'\r\n', b'\n')
        prepared.append((target, data))
        diff.extend(difflib.unified_diff([], data.decode().splitlines(keepends=True), fromfile='/dev/null', tofile='b/' + row['path']))
    if digest(''.join(diff).encode()) != manifest['patch_sha256']:
        raise ValueError('Generated source changes differ from reviewed diff')
    # All paths, original bytes, new bytes and review-diff identity checked before writes.
    for target, data in prepared:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return {'id': manifest['id'], 'patch_sha256': manifest['patch_sha256'], 'default_mode': 'native',
            'runtime_qualified': False, 'source_files': [{'path': p.relative_to(root).as_posix(), 'sha256': digest(data)} for p, data in prepared]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    result = apply(args.root)
    args.receipt.write_text(json.dumps(result, indent=2) + '\n')
