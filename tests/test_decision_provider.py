import io
import json
import unittest
from unittest.mock import patch
from decision_provider import infer_jev


class TypedDecisionTests(unittest.TestCase):
    def setUp(self):
        self.context={'options':[{'id':'wait','effect':'Wait here.'},{'id':'go','effect':'Visit the market.'}]}
        self.config={'url':'https://openrouter.ai/api/alpha/decisions','model':'typesafe/jev-1.14'}

    def call(self, answer):
        response=io.BytesIO(json.dumps({'answers':{'action':answer}}).encode())
        with patch('decision_provider.urllib.request.urlopen',return_value=response) as http:
            result=infer_jev(self.context,self.config,'test-placeholder')
            self.assertEqual(http.call_count,1)
            return result

    def test_typed_choice_is_not_presented_as_generated_dialogue(self):
        result=self.call({'choice':'go','probabilities':{'wait':.2,'go':.8}})
        self.assertEqual(result['rationale_kind'],'authored_action_label_not_dialogue')
        self.assertEqual(result['decision']['emotion'],'unspecified')

    def test_unknown_actions_and_invalid_probabilities_fail(self):
        for answer in [{'choice':'attack','probabilities':{'wait':.2,'go':.8}},
                       {'choice':'go','probabilities':{'wait':.8,'go':.8}},
                       {'choice':'go','probabilities':{'go':float('nan'),'wait':0}}]:
            with self.subTest(answer=answer),self.assertRaises(ValueError):self.call(answer)

    def test_context_limit_is_checked_before_any_paid_call(self):
        self.context['unbounded']='x'*17000
        with patch('decision_provider.urllib.request.urlopen') as http,self.assertRaises(ValueError):
            infer_jev(self.context,self.config,'test-placeholder')
        http.assert_not_called()
