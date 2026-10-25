"""Validate only the isolated market packager function, never deploy to a lab."""
import ast
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from economy_catalog import canonical_json
from market_policy import load_policy, policy_hash

ROOT=Path(__file__).resolve().parents[1]


def packager():
    definition=next(node for node in ast.parse((ROOT/'tools/deploy_bridge.py').read_text()).body
                    if isinstance(node,ast.FunctionDef) and node.name=='market_bundle_inputs')
    scope={'load_policy':load_policy,'policy_hash':policy_hash,'canonical_json':canonical_json,'hashlib':hashlib,'re':re}
    exec(compile(ast.Module(body=[definition],type_ignores=[]),'<isolated market packager>','exec'),scope)
    return scope


class MarketBundleWiringTests(unittest.TestCase):
    def test_reviewed_market_policy_and_hash_are_injected_before_transfer_factory(self):
        factory,encoded,digest=packager()['market_bundle_inputs'](ROOT)
        self.assertEqual(encoded,canonical_json(load_policy()))
        self.assertEqual(digest,policy_hash())
        self.assertEqual(digest,hashlib.sha256(encoded.encode()).hexdigest())
        self.assertIn('function validateMarketPolicy(',factory)
        self.assertNotIn('module.exports',factory)
        bridge=(ROOT/'bridge/whiterun-society.js').read_text()
        self.assertLess(bridge.index('__MARKET_POLICY_FACTORY__'),bridge.index('__TRANSFER_FACTORY__'))
        self.assertIn('marketPolicy:__MARKET_POLICY__,session:()=>session',bridge)
        self.assertIn('trade_execution:transfers.status()',bridge)
        deploy=(ROOT/'tools/deploy_bridge.py').read_text()
        self.assertLess(deploy.index('market_factory,market_policy_json,market_policy_digest='),deploy.index('target.parent.mkdir'))

    def test_invalid_policy_or_changed_hash_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'config').mkdir()
            bad=load_policy();bad['catalog_hash']='0'*64
            (root/'config/market-policy.json').write_text(json.dumps(bad))
            with self.assertRaises(ValueError):packager()['market_bundle_inputs'](root)
            self.assertEqual([p.name for p in root.iterdir()],['config'])
        scope=packager();scope['policy_hash']=lambda _: '0'*64
        with self.assertRaisesRegex(ValueError,'canonical hash'):scope['market_bundle_inputs'](ROOT)
