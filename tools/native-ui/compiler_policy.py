"""Select existing v143 tools and audit effective dependency CMake caches; never compile."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def version_checked(version):
    if not re.fullmatch(r'14\.(3[2-9]|4[0-9])\.\d+', version):
        raise ValueError('Existing MSVC 14.32+ v143 compiler required')
    return version


def write_triplets(root, version):
    root = Path(root).resolve()
    version_checked(version)
    destination = root / 'upstream/overlay_triplets'
    if destination.exists():
        raise ValueError('Refusing to overwrite upstream triplet configuration')
    destination.mkdir()
    receipts = []
    for name in ['x64-windows-static', 'x64-windows']:
        baseline = root / f'vcpkg/triplets/{name}.cmake'
        if not baseline.is_file():
            raise ValueError('Pinned registry triplet missing')
        basepath = baseline.as_posix()
        if any(value in basepath for value in ['"', '\n', '\r', ';']):
            raise ValueError('Invalid CMake include path')
        text = (f'include("{basepath}")\nset(VCPKG_PLATFORM_TOOLSET "v143")\n'
                f'set(VCPKG_PLATFORM_TOOLSET_VERSION "{version}")\n')
        output = destination / f'{name}.cmake'
        output.write_bytes(text.encode('utf-8'))
        receipts.append({'triplet': name, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                         'contents': text, 'baseline_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest()})
    return receipts


def cache_values(text):
    result = {}
    for line in text.splitlines():
        match = re.match(r'^([A-Z_]+):[^=]*=(.*)$', line)
        if match:
            result[match[1]] = match[2]
    return result


def compiler_path_matches(actual, expected, version):
    actual = actual.replace('\\', '/').casefold()
    expected = expected.replace('\\', '/').casefold()
    return (actual == expected and f'/msvc/{version}/bin/hostx64/x64/cl.exe' in actual)


def audit(root, compiler, version, require_complete=True):
    version_checked(version)
    root = Path(root)
    rows, errors = [], []
    for cache in sorted((root / 'vcpkg/buildtrees').rglob('CMakeCache.txt')):
        data = cache_values(cache.read_text(encoding='utf-8', errors='replace'))
        actual = data.get('CMAKE_CXX_COMPILER')
        if not actual:
            continue
        row = {'cache': cache.relative_to(root).as_posix(), 'compiler': actual,
               'toolset': data.get('VCPKG_PLATFORM_TOOLSET'),
               'toolset_version': data.get('VCPKG_PLATFORM_TOOLSET_VERSION'),
               'matches_expected': compiler_path_matches(actual, compiler, version)}
        if (not row['matches_expected'] or row['toolset'] not in (None, 'v143')
                or row['toolset_version'] not in (None, version)):
            errors.append(row['cache'])
        rows.append(row)
    # Both host and target compiler selection must be observed, not merely requested.
    required = ['detect_compiler/x64-windows-static-rel/CMakeCache.txt', 'detect_compiler/x64-windows-rel/CMakeCache.txt']
    missing = [part for part in required if not any(part in row['cache'] for row in rows)]
    expected_file = Path(compiler)
    if not expected_file.is_file():
        errors.append('selected compiler executable is missing')
    return {'expected_toolset': 'v143', 'expected_msvc_version': version, 'expected_compiler': compiler,
            'expected_compiler_sha256': hashlib.sha256(expected_file.read_bytes()).hexdigest() if expected_file.is_file() else None,
            'observed_caches': rows, 'mismatches': errors, 'missing_detection': missing,
            'verified': bool(rows) and not errors and not missing,
            'accepted': not errors and (not require_complete or bool(rows) and not missing),
            'application_source_modified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--msvc-version', required=True)
    parser.add_argument('--compiler')
    parser.add_argument('--create-triplets', action='store_true')
    parser.add_argument('--allow-incomplete', action='store_true')
    args = parser.parse_args()
    if args.create_triplets:
        result = write_triplets(args.root, args.msvc_version)
        (args.root / 'evidence/compiler-triplets.json').write_text(json.dumps(result, indent=2) + '\n')
    else:
        if not args.compiler:
            parser.error('--compiler is required for audit')
        result = audit(args.root, args.compiler, args.msvc_version, not args.allow_incomplete)
        (args.root / 'evidence/effective-dependency-compiler.json').write_text(json.dumps(result, indent=2) + '\n')
        if not result['accepted']:
            raise SystemExit('Effective dependency compiler does not match the selected hosted v143 compiler')
