"""Source-only packaging tests: never execute deploy_bridge or touch a game."""
import ast
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from economy_catalog import canonical_json
from resource_manifest import load_manifest, manifest_hash

ROOT=Path(__file__).resolve().parents[1]


def packaging_function():
    source=ast.parse((ROOT/'tools/deploy_bridge.py').read_text())
    definition=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='resource_bundle_inputs')
    scope={'load_manifest':load_manifest,'manifest_hash':manifest_hash,'canonical_json':canonical_json,'hashlib':hashlib,'re':re}
    exec(compile(ast.Module(body=[definition],type_ignores=[]),'<isolated resource packager>','exec'),scope)
    return scope


class ResourceBundleWiringTests(unittest.TestCase):
    def test_packaging_function_validates_exact_config_and_canonical_hash(self):
        scope=packaging_function();factory,encoded,digest=scope['resource_bundle_inputs'](ROOT)
        self.assertEqual(encoded,canonical_json(load_manifest()))
        self.assertEqual(digest,manifest_hash())
        self.assertEqual(digest,hashlib.sha256(encoded.encode()).hexdigest())
        self.assertIn('function validateResourceManifest(',factory)
        self.assertNotIn('module.exports',factory)

    def test_bad_manifest_and_mismatched_hash_fail_before_packaging(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'config').mkdir()
            bad=load_manifest();bad['catalog_hash']='0'*64
            (root/'config/resource-manifest.json').write_text(json.dumps(bad))
            with self.assertRaises(ValueError):packaging_function()['resource_bundle_inputs'](root)
            self.assertEqual(sorted(p.name for p in root.iterdir()),['config'])
        scope=packaging_function();scope['manifest_hash']=lambda _: '0'*64
        with self.assertRaisesRegex(ValueError,'canonical hash'):scope['resource_bundle_inputs'](ROOT)

    def test_manifest_factory_precedes_endowments_and_packager_precedes_writes(self):
        bridge=(ROOT/'bridge/whiterun-society.js').read_text()
        self.assertLess(bridge.index('__RESOURCE_MANIFEST_FACTORY__'),bridge.index('__ENDOWMENT_FACTORY__'))
        self.assertLess(bridge.index('let session ='),bridge.index('createEndowmentController('))
        self.assertIn('manifest:__RESOURCE_MANIFEST__,session:()=>session',bridge)
        self.assertIn('resource_import:endowments.status()',bridge)
        deploy=(ROOT/'tools/deploy_bridge.py').read_text()
        self.assertLess(deploy.index('resource_factory,resource_manifest_json,resource_manifest_digest='),deploy.index('target.parent.mkdir'))
        self.assertIn("source.replace('__RESOURCE_MANIFEST__',resource_manifest_json)",deploy)
