import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_ui_prepare', HERE / 'prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PreparationTests(unittest.TestCase):
    def manifest(self):
        return json.loads((HERE / 'manifest.json').read_text())

    def test_reviewed_manifest_and_proof_match(self):
        manifest = self.manifest()
        prepare.validate_manifest(manifest)
        self.assertEqual(prepare.source_list_sha256(HERE / 'upstream-files.json'), manifest['upstream']['files_manifest_sha256'])
        proof = json.loads((HERE / 'upstream-files.json').read_text())
        self.assertEqual(proof['commit'], manifest['upstream']['commit'])
        self.assertEqual(len(proof['files']), 109)

    def test_source_list_identity_survives_git_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proof.json'
            path.write_bytes(b'{\n  "files": {}\n}\n')
            expected = prepare.source_list_sha256(path)
            path.write_bytes(b'{\r\n  "files": {}\r\n}\r\n')
            self.assertEqual(prepare.source_list_sha256(path), expected)

    def test_floating_unreviewed_and_unresolved_inputs_rejected(self):
        changes = [('upstream', 'commit', 'main'), ('upstream', 'archive_url', 'https://example.com/source.zip'),
                   ('vcpkg', 'tool_sha256', None), ('vcpkg', 'tool_url', 'https://example.com/tool.exe'),
                   ('vcpkg', 'triplet', 'x86-windows')]
        for section, key, value in changes:
            manifest = self.manifest()
            manifest[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                prepare.validate_manifest(manifest)
        manifest = self.manifest()
        manifest['reviewed_patches'] = ['unreviewed.patch']
        with self.assertRaises(ValueError):
            prepare.validate_manifest(manifest)

    def test_download_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'tool.exe'
            with patch.object(prepare.urllib.request, 'urlopen', return_value=io.BytesIO(b'wrong')):
                with self.assertRaises(ValueError):
                    prepare.download('https://example.com', target, '0' * 64)

    def make_zip(self, root, entries):
        archive = root / 'source.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            for name, data in entries:
                output.writestr(name, data)
        return archive

    def test_safe_archive_extracts_inside_expected_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.make_zip(root, [('expected/', ''), ('expected/src/a.cpp', 'hello')])
            prepare.extract(archive, root / 'out', 'expected')
            self.assertEqual((root / 'out/src/a.cpp').read_text(), 'hello')

    def test_archive_traversal_links_and_case_collisions_rejected_before_write(self):
        link = zipfile.ZipInfo('expected/link')
        link.external_attr = 0o120777 << 16
        for entries in [ [('expected/../escape', 'x')], [('other/a', 'x')],
                         [('expected/C:escape', 'x')], [('expected\\..\\escape', 'x')],
                         [('expected/a', 'x'), ('expected/A', 'y')], [(link, 'target')] ]:
            with self.subTest(entries=str(entries)), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = self.make_zip(root, entries)
                with self.assertRaises(ValueError):
                    prepare.extract(archive, root / 'out', 'expected')
                self.assertFalse((root / 'out').exists())

    def test_source_mutation_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'a.cpp').write_bytes(b'original')
            expected = hashlib.sha1(b'blob 8\0original').hexdigest()
            proof = {'files': {'a.cpp': expected}}
            self.assertEqual(len(prepare.verify_source(root, proof)), 1)
            (root / 'a.cpp').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                prepare.verify_source(root, proof)


if __name__ == '__main__':
    unittest.main()
