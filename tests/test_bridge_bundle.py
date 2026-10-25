"""Build the distributable bridge in a disposable fixture, never the game lab."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from economy_catalog import canonical_json, load_catalog

REPO = Path(__file__).resolve().parents[1]


class BridgeBundleTests(unittest.TestCase):
    def test_deployer_embeds_catalog_and_every_factory_in_parseable_bundle(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required to validate the distributable bridge')
        with tempfile.TemporaryDirectory(prefix='whiterun-bundle-test-') as folder:
            root = Path(folder)
            (root / 'runtime').mkdir()
            (root / 'runtime-manifest.json').write_text(json.dumps({
                'game': str(root / 'game'), 'source': str(root / 'source-fixture')
            }), encoding='utf-8')
            (root / 'runtime' / 'bridge-config.json').write_text(json.dumps({
                'port': 1, 'token': 'test-only-not-a-credential'
            }), encoding='utf-8')
            subprocess.run([sys.executable, str(REPO / 'tools/deploy_bridge.py'), '--root', str(root)],
                           cwd=REPO, check=True, capture_output=True, text=True, timeout=30)
            target = root / 'game/Data/Platform/PluginsDev/whiterun-society.js'
            source = target.read_text(encoding='utf-8')
            self.assertEqual(re.findall(r'__[A-Z_]+__', source), [])
            self.assertIn(canonical_json(load_catalog()), source)
            self.assertIn('economy_catalog:economyCatalog.status()', source)
            self.assertNotIn('const economyForms=', source)
            subprocess.run([node, '--check', str(target)], check=True,
                           capture_output=True, text=True, timeout=15)


if __name__ == '__main__':
    unittest.main()
