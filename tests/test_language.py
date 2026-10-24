import io
import json
import unittest
from unittest.mock import patch

from language import LanguageOutputError, propose


class LanguageTests(unittest.TestCase):
    config = {'provider': 'openrouter_chat', 'model': 'ibm-granite/granite-4.2-8b',
              'reasoning_effort': 'none', 'openrouter_provider': 'coreweave'}

    def response(self, content, finish='stop', usage=None):
        return io.BytesIO(json.dumps({'choices': [{'finish_reason': finish,
            'message': {'content': content}}], 'usage': usage or {}}).encode())

    def test_explicit_non_thinking_and_provider_reach_request(self):
        candidates = {'candidates': [
            {'id': 'option_1', 'intention': 'Greet', 'line': 'Good morning to you.', 'tone': 'calm'},
            {'id': 'option_2', 'intention': 'Ask', 'line': 'How are you today?', 'tone': 'hopeful'}]}
        with patch('language.urllib.request.urlopen', return_value=self.response(json.dumps(candidates))) as http:
            result = propose({}, self.config, 'test-placeholder')
        payload = json.loads(http.call_args.args[0].data)
        self.assertEqual(http.call_count, 1)
        self.assertEqual(payload['reasoning'], {'effort': 'none'})
        self.assertEqual(payload['provider'], {'only': ['coreweave'], 'allow_fallbacks': False, 'require_parameters': True})
        self.assertNotIn('chat_template_kwargs', payload)
        self.assertEqual(result['proposal'], candidates)

    def test_truncated_reasoning_retains_cost_without_repeating_request(self):
        usage = {'cost': .001, 'completion_tokens': 500,
                 'completion_tokens_details': {'reasoning_tokens': 499}, 'untrusted': 'do not log'}
        with patch('language.urllib.request.urlopen', return_value=self.response('', 'length', usage)) as http:
            with self.assertRaises(LanguageOutputError) as error:
                propose({}, self.config, 'test-placeholder')
        self.assertEqual(http.call_count, 1)
        self.assertEqual(error.exception.receipt['usage']['cost'], .001)
        self.assertEqual(error.exception.receipt['usage']['completion_tokens_details']['reasoning_tokens'], 499)
        self.assertNotIn('untrusted', error.exception.receipt['usage'])
        self.assertEqual(error.exception.receipt['finish_reason'], 'length')

    def test_invalid_candidates_are_not_exposed_or_accepted(self):
        for content in ('private raw invalid output', '{"candidates": []}'):
            with self.subTest(content=content), patch('language.urllib.request.urlopen',
                    return_value=self.response(content, usage={'cost': .002})):
                with self.assertRaises(LanguageOutputError) as error:
                    propose({}, self.config, 'test-placeholder')
            self.assertEqual(str(error.exception), 'Invalid language candidates')
            self.assertEqual(error.exception.receipt['usage']['cost'], .002)
            self.assertNotIn(content, json.dumps(error.exception.receipt))

    def test_invalid_controls_fail_before_paid_request(self):
        for update in ({'reasoning_effort': 'infinite'}, {'openrouter_provider': ''},
                       {'provider': 'local'}, {'openrouter_provider': ['coreweave']}):
            with self.subTest(update=update), patch('language.urllib.request.urlopen') as http:
                with self.assertRaises(ValueError):propose({}, {**self.config, **update}, 'test-placeholder')
                http.assert_not_called()
