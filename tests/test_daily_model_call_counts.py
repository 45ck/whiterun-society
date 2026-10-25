"""Director counters describe saved inference receipts, never invented calls."""
import copy
import unittest
from tools.run_daily_life import resident_model_call_counts


class DailyModelCallCountTests(unittest.TestCase):
    def test_decision_and_accepted_rejected_wording_each_count_once(self):
        turn={'wording_results':[
            {'claim_id':'proposal-1','stage':'propose','accepted':True},
            {'claim_id':'selection-1','stage':'select','accepted':False,'validation_failure':'invalid_output'}],
            'wording_fallback':'invalid_output','delivered':True}
        plan={'decisions':[{'claim_id':'decision-1'},{'claim_id':'decision-2'},{'claim_id':'decision-1'}],
              'economic_turns':[turn], 'economic_speech':copy.deepcopy(turn)}
        before=copy.deepcopy(plan);result=resident_model_call_counts(plan)
        self.assertEqual(result['model_calls'],4)
        self.assertEqual(result['model_calls_by_lane'],{'decision':2,'wording':2})
        self.assertEqual(result['model_call_unidentified_results'],{'decision':0,'wording':0})
        self.assertEqual(plan,before)

    def test_unidentified_legacy_results_and_fallbacks_are_not_guessed_calls(self):
        plan={'decisions':[{'model':'legacy'}], 'economic_turns':[
            {'wording_results':[{'model':'legacy','accepted':False}]},
            {'wording_fallback':'provider_error','line':'Deterministic fallback, no retained call receipt.'}],
            'economic_speech':{'claim':{'id':'claimed-but-no-result'},'wording_fallback':'direct_terms'}}
        result=resident_model_call_counts(plan)
        self.assertEqual(result['model_calls'],0)
        self.assertEqual(result['model_call_unidentified_results'],{'decision':1,'wording':1})
        self.assertEqual(result['model_call_count_kind'],'recorded_lower_bound')
        self.assertIn('unrecorded attempts are unknown',result['model_call_count_scope'])

    def test_natural_trade_without_wording_result_does_not_infer_two_calls(self):
        result=resident_model_call_counts({'natural_trade':True,'decisions':[{'claim_id':'decision'}],
            'economic_turns':[{'act':'offer','delivered':True,'selected':{'line':'Please.'}}]})
        self.assertEqual(result['model_calls'],1)
        self.assertEqual(result['model_calls_by_lane']['wording'],0)


if __name__=='__main__':unittest.main()
