"""Additive migration tests, plus optional real staged-plugin binary readback.

Set WHITERUN_ACTIVITIES_STAGE to the builder output directory to validate the
actual generated artifact. This suite never reads or changes a live game.
"""
from collections import Counter
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.verify_plan_save import plugin_manifest, plugins_compatible

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))
import install_router
sys.path.pop(0)


class ActivitiesMigrationTests(unittest.TestCase):
    def test_only_explicit_appended_activity_plugin_can_extend_saved_identity(self):
        old = [{'name': 'Skyrim.esm'}, {'name': 'WhiterunRest.esp', 'sha256': 'existing'}]
        extra = {'name': 'WhiterunActivities.esp', 'sha256': 'new'}
        actual = old + [extra]
        self.assertFalse(plugins_compatible(old, actual))
        self.assertTrue(plugins_compatible(old, actual, 'WhiterunActivities.esp'))
        self.assertFalse(plugins_compatible(old, [old[1], old[0], extra], 'WhiterunActivities.esp'))
        self.assertFalse(plugins_compatible(old, [old[0], {**old[1], 'sha256': 'changed'}, extra], 'WhiterunActivities.esp'))
        self.assertFalse(plugins_compatible(old, old + [{**extra, 'sha256': ''}], 'WhiterunActivities.esp'))
        self.assertFalse(plugins_compatible(actual, actual + [extra], 'WhiterunActivities.esp'))

    def test_activity_plugin_bytes_are_in_the_save_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); profile = root / 'mod-organizer/profiles/Default'; profile.mkdir(parents=True)
            data = root / 'game/Data'; data.mkdir(parents=True)
            artifact = data / 'WhiterunActivities.esp'; artifact.write_bytes(b'first')
            (profile / 'plugins.txt').write_text('*Skyrim.esm\n*WhiterunActivities.esp\n')
            before = plugin_manifest(root)
            self.assertEqual(before[-1]['sha256'], hashlib.sha256(b'first').hexdigest())
            artifact.write_bytes(b'changed')
            self.assertFalse(plugins_compatible(before, plugin_manifest(root), 'WhiterunActivities.esp'))

    def test_profile_appends_activities_without_reordering_existing_enabled_plugins(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); game = root / 'game'; data = game / 'Data'; data.mkdir(parents=True)
            (root / 'runtime').mkdir(); profile = root / 'mod-organizer/profiles/Default'; profile.mkdir(parents=True)
            (game / 'Skyrim_Default.ini').write_text('[General]\nsLanguage=ENGLISH\n')
            (profile / 'settings.ini').write_text('[General]\nLocalSaves=true\nLocalSettings=true\n')
            (profile / 'skyrimprefs.ini').write_text('[Display]\niSize W=1280\n')
            old = ['*Skyrim.esm', '*Unrelated.esp', '*WhiterunSociety.esp', '*WhiterunRouter.esp',
                   '*WhiterunRest.esp', '*WhiterunLanes.esp', '*WhiterunCitizens.esp']
            for name in [line[1:] for line in old[2:]] + ['WhiterunActivities.esp']:
                (data / name).write_bytes(name.encode())
            before = {p.name: p.read_bytes() for p in data.iterdir()}
            (profile / 'plugins.txt').write_text('\n'.join(old) + '\n')
            command = [sys.executable, str(REPO / 'tools/configure_profile.py'), '--root', str(root),
                       '--experimental-rest', '--experimental-routines', '--experimental-resident-control', '--experimental-activities']
            for _ in range(2):
                subprocess.run(command, capture_output=True, text=True, check=True)
                self.assertEqual((profile / 'plugins.txt').read_text().splitlines(), old + ['*WhiterunActivities.esp'])
                self.assertEqual({p.name: p.read_bytes() for p in data.iterdir()}, before)

    def fixture(self, folder):
        base = Path(folder); root = base / 'lab'; game = root / 'game'; stage = base / 'stage'
        (game / 'Data/Scripts').mkdir(parents=True); (root / 'runtime').mkdir(); stage.mkdir()
        (root / 'runtime-manifest.json').write_text(json.dumps({'game': str(game), 'source': str(base / 'original')}))
        plugin = b'TES4' + bytes(200); script = bytes.fromhex('fa57c0de') + bytes(200)
        (stage / 'WhiterunActivities.esp').write_bytes(plugin); (stage / 'WSSocietyRouter.pex').write_bytes(script)
        (game / 'Data/Scripts/WSSocietyRouter.pex').write_bytes(script)
        (game / 'Data/WhiterunRest.esp').write_bytes(b'existing-rest-records')
        return root, game, stage

    def run_install(self, root, stage):
        with patch.object(sys, 'argv', ['install_router', '--root', str(root), '--stage', str(stage), '--activities']), \
             patch.object(install_router, 'game_paths', return_value=[]), contextlib.redirect_stdout(io.StringIO()) as out:
            install_router.main()
        return json.loads(out.getvalue())

    def test_install_preserves_shared_script_and_existing_plugin_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root, game, stage = self.fixture(folder)
            before = {str(p.relative_to(game)): p.read_bytes() for p in game.rglob('*') if p.is_file()}
            receipt = self.run_install(root, stage)
            self.assertTrue(receipt['shared_script_unchanged'])
            self.assertEqual(set(receipt['files']), {'WhiterunActivities.esp'})
            for name, data in before.items(): self.assertEqual((game / name).read_bytes(), data)

    def test_install_rejects_shared_script_change_or_replacing_existing_activity_plugin(self):
        for change in ('script', 'plugin'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                root, game, stage = self.fixture(folder)
                if change == 'script': (stage / 'WSSocietyRouter.pex').write_bytes(bytes.fromhex('fa57c0de') + b'changed' * 30)
                else: (game / 'Data/WhiterunActivities.esp').write_bytes(b'previous activity records')
                with self.assertRaises(ValueError): self.run_install(root, stage)
                self.assertEqual(list((root / 'runtime').iterdir()), [])


@unittest.skipUnless(os.environ.get('WHITERUN_ACTIVITIES_STAGE'), 'Set WHITERUN_ACTIVITIES_STAGE for real generated plugin readback')
class ActivitiesArtifactTests(unittest.TestCase):
    def test_generated_binary_has_two_disjoint_furniture_mailboxes_and_matching_readback(self):
        stage = Path(os.environ['WHITERUN_ACTIVITIES_STAGE']); path = stage / 'WhiterunActivities.esp'; raw = path.read_bytes()
        def records(start, end):
            while start < end:
                tag, size = struct.unpack_from('<4sI', raw, start)
                if tag == b'GRUP':
                    yield from records(start + 24, start + size); start += size
                else:
                    _, _, flags, form, *_ = struct.unpack_from('<4sIIIIHH', raw, start)
                    self.assertEqual(flags & 0x40000, 0)  # No compressed fixture hiding another layout.
                    yield tag, form, raw[start + 24:start + 24 + size]; start += 24 + size
            self.assertEqual(start, end)
        def subrecords(data):
            offset = 0; result = []
            while offset < len(data):
                tag, size = struct.unpack_from('<4sH', data, offset)
                result.append((tag, data[offset + 6:offset + 6 + size])); offset += 6 + size
            self.assertEqual(offset, len(data)); return result
        parsed = list(records(0, len(raw)))
        self.assertEqual(Counter(tag for tag, _, _ in parsed), {b'TES4': 1, b'QUST': 2, b'PACK': 2, b'FLST': 4, b'GLOB': 6})
        by_id = {form & 0xffffff: (tag, subrecords(data)) for tag, form, data in parsed if tag != b'TES4'}
        self.assertEqual(set(by_id), {first + i for first in (0x800, 0x900) for i in range(7)})
        self.assertTrue(all(form >> 24 == 1 for tag, form, _ in parsed if tag != b'TES4'))
        for first in (0x800, 0x900):
            self.assertEqual([by_id[first + i][0] for i in range(7)], [b'QUST', b'PACK', b'FLST', b'FLST', b'GLOB', b'GLOB', b'GLOB'])
            quest, package = dict(by_id[first][1]), dict(by_id[first + 1][1])
            self.assertEqual(quest[b'DNAM'][:3], bytes([0, 0, 95]))
            self.assertEqual(struct.unpack('<I', quest[b'ALPC'])[0] & 0xffffff, first + 1)
            self.assertIn(b'WSSocietyRouter', quest[b'VMAD'])
            self.assertEqual(struct.unpack('<III', package[b'PKCU']), (3, 0xA9277, 2))
            self.assertEqual(struct.unpack('<III', package[b'PTDA']), (4, 1, 0))
            self.assertEqual(struct.unpack('<I', package[b'QNAM'])[0] & 0xffffff, first)
        proof = json.loads(Path(str(path) + '.verification.json').read_text())
        self.assertEqual(proof['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual([s['offset'] for s in proof['slots']], [0, 0x100])
        for slot in proof['slots']:
            first = slot['quest']
            self.assertEqual(slot['properties'], dict(zip(['ResidentReference', 'DestinationReference', 'RequestSerial', 'AcknowledgedSerial', 'RouteStatus'], range(first + 2, first + 7))))


if __name__ == '__main__': unittest.main()
