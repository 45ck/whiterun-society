import copy
import unittest
from metrics import simulation_metrics,distribution


class MetricsTests(unittest.TestCase):
    def test_missing_measurement_is_unknown_not_perfect(self):
        m=simulation_metrics({})
        self.assertIsNone(m['encounters']['accepted_chat_completion']['percent'])
        self.assertIsNone(m['embodiment']['body_orientation']['mean_error_degrees'])
        self.assertIsNone(m['embodiment']['line_of_sight_raycast_accuracy'])
        self.assertIsNone(m['realism']['human_dialogue_rating'])

    def test_failed_attempts_count_but_quiet_choices_are_not_failed_chats(self):
        scenes=[{'id':'done','mode':'autonomous_social','phase':'complete','response':'chat','outcome':'social_exchange_completed','turns':[]},
                {'id':'bad','mode':'autonomous_social','phase':'held','response':'chat','error':'Listener left before delivery'},
                {'id':'quiet','mode':'autonomous_social','phase':'complete','outcome':'continued_quietly'},
                {'id':'fixture','mode':'autonomous_social','phase':'complete','response':'chat','social_decisions':[{'model':'test-jev'}]}]
        state={'conversation_history':scenes,'conversation':scenes[-1]};before=copy.deepcopy(state)
        m=simulation_metrics(state)['encounters']
        self.assertEqual(m['eligible'],3);self.assertEqual(m['excluded_fixtures'],1)
        self.assertEqual(m['accepted_chat_completion'],{'success':1,'n':2,'percent':50})
        self.assertEqual(m['quiet_outcomes'],1);self.assertEqual(m['failures_by_category'],{'attendance':1})
        self.assertEqual(m['end_reasons'],{'legacy_unrecorded':3})
        self.assertEqual(state,before)

    def test_reply_gaps_and_body_geometry_are_separate_from_eye_accuracy(self):
        turn={'delivered':True,'ended_at':10,'language':{'model':'live','elapsed_seconds':2},
              'playback':{'nearbyThroughout':True,'orientation':{'samples':2,'sum_error_degrees':30,'max_error_degrees':20}}}
        second={**turn,'prepared_at':13,'ended_at':17}
        m=simulation_metrics({'conversation':{'id':'c','mode':'autonomous_social','phase':'complete','response':'chat',
            'outcome':'social_exchange_completed','started_at':1,'finished_at':20,'turns':[turn,second]}})
        self.assertEqual(m['encounters']['reply_dispatch_gap_seconds']['median'],3)
        self.assertEqual(m['encounters']['duration_seconds']['median'],19)
        self.assertEqual(m['embodiment']['body_orientation']['mean_error_degrees'],15)
        self.assertIsNone(m['embodiment']['eye_gaze_error_degrees'])
        self.assertEqual(m['models']['results_with_cost'],0)

    def test_conservation_checks_actual_balances_and_ignores_uncommitted_effects(self):
        good={'quantity':1,'cost':3,'before':{'buyer':{'gold':7},'seller':{'gold':2}},'after':{'buyer':{'gold':4},'seller':{'gold':5}}}
        bad=copy.deepcopy(good);bad['after']['buyer']['gold']=7
        state={'trades':[{'status':'committed','command':good},{'status':'committed','command':bad},{'status':'held','command':good}]}
        m=simulation_metrics(state)['economy']
        self.assertEqual(m['gold_conservation']['percent'],50)
        self.assertEqual(m['distinct_observed_sale_prices'],1)
        self.assertEqual(m['supported_production_recipes'],1)

    def test_nonfinite_and_negative_timings_are_not_samples(self):
        self.assertEqual(distribution([None,True,-1,float('nan'),2,4]),{'n':2,'mean':3,'median':3,'p95':4})

    def test_partner_names_do_not_inflate_semantic_diversity_and_plan_failures_remain_visible(self):
        m=simulation_metrics({'conversation':{'id':'c','mode':'autonomous_social','phase':'complete',
            'social_decisions':[{'decision':{'action_id':'approach_7'}},{'decision':{'action_id':'approach_8'}}]},
            'plans':[{'phase':'held','error':'Resident is not observed','decisions':[{'context':{'options':[{},{}]}}]}]})
        self.assertEqual(m['social_complexity']['distinct_social_choices'],1)
        self.assertEqual(m['social_complexity']['choice_entropy_bits'],0)
        self.assertEqual(m['resident_plans']['held'],1)
        self.assertEqual(m['resident_plans']['failures_by_category'],{'availability':1})
        self.assertEqual(m['resident_plans']['feasible_options_per_decision']['mean'],2)


    def test_followthrough_distinguishes_choice_review_and_actual_outcome(self):
        state={'conversation':{'id':'chat','mode':'autonomous_social','phase':'complete',
            'follow_through':[{'event_id':'next','actor':1,'focus':'food'}]},
            'plans':[{'id':'next','phase':'complete','outcome':'deferred','decisions':[]}]}
        m=simulation_metrics(state)['conversation_followthrough']
        self.assertEqual(m['resident_choices'],1)
        self.assertEqual(m['completed_plans'],1)
        self.assertEqual(m['outcomes'],{'deferred':1})
        self.assertNotIn('ate_bread',m['outcomes'])
