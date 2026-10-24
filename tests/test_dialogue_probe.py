import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.probe_dialogue import run


class DialogueProbeTests(unittest.TestCase):
    def plan(self):
        return {'cases': {'scene': {}}, 'configs': [{'provider': 'openrouter_chat',
            'model': 'test-model', 'openrouter_provider': 'test-provider', 'reasoning_effort': 'none'}]}

    def test_existing_receipt_cannot_repeat_paid_calls(self):
        with tempfile.TemporaryDirectory() as directory, patch('tools.probe_dialogue.propose') as propose:
            output = Path(directory) / 'receipt.json'
            output.write_text('retained receipt', encoding='utf-8')
            with self.assertRaises(FileExistsError):run(self.plan(), output, 'test-placeholder')
            propose.assert_not_called()
            self.assertEqual(output.read_text(), 'retained receipt')

    def test_caps_and_unpinned_routes_fail_before_calls(self):
        with tempfile.TemporaryDirectory() as directory, patch('tools.probe_dialogue.propose') as propose:
            plan = self.plan()
            plan['cases'] = {str(i): {} for i in range(13)}
            with self.assertRaises(ValueError):run(plan, Path(directory) / 'receipt.json', 'test-placeholder')
            plan = self.plan()
            plan['configs'][0].pop('openrouter_provider')
            with self.assertRaises(ValueError):run(plan, Path(directory) / 'receipt.json', 'test-placeholder')
            propose.assert_not_called()

    def test_claim_is_durable_before_call_and_failure_is_not_retried(self):
        import json
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'receipt.json'
            def fail(*args):
                receipt = json.loads(output.read_text())
                self.assertEqual(receipt['results'][0]['status'], 'claimed')
                raise HTTPError('https://example.invalid', 429, 'secret raw body', {}, None)
            with patch('tools.probe_dialogue.propose', side_effect=fail) as propose:
                result = run(self.plan(), output, 'test-placeholder')
            self.assertEqual(propose.call_count, 1)
            self.assertEqual(result['results'][0]['http_status'], 429)
            self.assertNotIn('secret raw body', output.read_text())
