import copy
import unittest
from agency_metrics import agency_metrics,economic_network,drama_metrics
from quality_goals import quality_goals,validate_catalog
from metrics import simulation_metrics


class AgencyMetricTests(unittest.TestCase):
    def test_empty_metrics_have_unknown_rates_and_costs(self):
        result=agency_metrics({})
        for key in ('current_goal_coverage','decision_acceptance','journey_arrival','cost_coverage'):
            self.assertEqual(result[key],{'success':0,'n':0,'percent':None})
        self.assertIsNone(result['known_cost_usd']);self.assertIsNone(result['choice_entropy_bits'])
        self.assertIsNone(economic_network({})['seller_transaction_hhi'])

    def test_results_normalize_destinations_exclude_fixtures_and_keep_missing_costs(self):
        result=lambda action,**extra:{'model':'live','attempted':True,'accepted':True,'decision':{'action_id':action},**extra}
        rows=[result('visit_10',elapsed_seconds=2,usage={'cost':0},chosen_family='visit_public_place'),result('visit_11',elapsed_seconds=4,chosen_family='visit_bench_area'),
              result('quiet',model='test-jev'),{'model':'live','attempted':True,'accepted':False,'failure':'inference_failed','elapsed_seconds':float('nan')}]
        state={'town':{'goal_waves':[{'phase':'complete','results':rows}]}}
        before=copy.deepcopy(state);m=agency_metrics(state)
        self.assertEqual(m['decision_acceptance'],{'success':2,'n':3,'percent':66.67})
        self.assertEqual(m['inference_failures']['percent'],33.33)
        self.assertEqual(m['choice_classes'],{'visit_destination':2});self.assertEqual(m['distinct_chosen_destinations'],2)
        self.assertEqual(m['destination_kind_choices'],{'visit_public_place':1,'visit_bench_area':1})
        self.assertEqual(m['excluded_fixture_results'],1);self.assertEqual(m['known_cost_usd'],0)
        self.assertEqual(m['cost_coverage'],{'success':1,'n':3,'percent':33.33})
        self.assertEqual(m['inference_seconds'],{'n':2,'mean':3,'median':3,'p95':4})
        self.assertEqual(state,before)

    def test_skips_cannot_improve_latency_or_count_as_failed_model_calls(self):
        rows=[{'model':'live','attempted':False,'accepted':False,'failure':'inference_failed','elapsed_seconds':0},
              {'model':'live','attempted':True,'accepted':True,'elapsed_seconds':4,'usage':{'cost':.1},'decision':{'action_id':'quiet'}},
              {'model':'legacy','accepted':False,'failure':'inference_failed','elapsed_seconds':6,'usage':{'cost':.2}}]
        m=agency_metrics({'town':{'goal_waves':[{'phase':'complete','results':rows}]}})
        self.assertEqual(m['recorded_attempted_calls'],1);self.assertEqual(m['skipped_before_inference'],1)
        self.assertEqual(m['attempt_status_unknown'],1);self.assertEqual(m['attempt_status_coverage']['percent'],66.67)
        self.assertEqual(m['inference_failures'],{'success':0,'n':1,'percent':0})
        self.assertEqual(m['cost_coverage'],{'success':1,'n':1,'percent':100})
        self.assertEqual(m['inference_seconds']['median'],5);self.assertEqual(m['known_cost_usd'],.3)
        self.assertEqual(m['decision_acceptance']['n'],3)

    def test_outcomes_deduplicate_actor_event_without_counting_inflight_as_failure(self):
        arrival={'event_id':'a','kind':'standing_goal_arrival','travel_game_minutes':4,'elapsed_seconds':12,'provenance':'model_decision'}
        failure={'event_id':'b','kind':'standing_goal_failed'}
        fixture={**arrival,'event_id':'test','provenance':'test_fixture'}
        state={'town':{'residents':{'1':{},'2':{},'3':{},'4':{}}},'people':{
            '1':{'standing_goal':{'phase':'travelling'},'memories':[arrival,arrival,failure,fixture]},
            '2':{'standing_goal':{'phase':'quiet'}},'3':{'standing_goal':{'phase':'held'}}}}
        m=agency_metrics(state)
        self.assertEqual(m['current_goal_coverage'],{'success':2,'n':4,'percent':50})
        self.assertEqual(m['journey_arrival'],{'success':1,'n':2,'percent':50})
        self.assertEqual(m['journey_outcomes_with_unknown_provenance'],1)
        self.assertEqual(m['journey_game_minutes']['n'],1);self.assertEqual(m['decision_to_settlement_seconds']['median'],12)
        self.assertEqual(m['excluded_fixture_journey_outcomes'],1)

    def test_network_uses_committed_complete_parties_and_observed_labels_only(self):
        trade=lambda a,b,**kw:{'status':'committed','command':{'buyer':a,'seller':b,**kw}}
        state={'trades':[trade(1,2,cost=3,commodity='bread'),trade(3,2,cost=4,commodity='grain'),
                         trade(2,3,cost=0,commodity='grain'),trade(True,2),
                         {'status':'held','command':{'buyer':4,'seller':5,'cost':999,'commodity':'iron'}}]}
        m=economic_network(state)
        self.assertEqual(m['distinct_participants'],3);self.assertEqual(m['directed_trade_links'],3)
        self.assertEqual(m['party_identity_coverage'],{'success':3,'n':4,'percent':75})
        self.assertEqual(m['goods_receipts'],{'bread':1,'grain':2});self.assertEqual(m['known_turnover_septims'],7)
        self.assertEqual(m['seller_transaction_hhi'],.5556);self.assertEqual(m['trade_link_density'],.5)
        self.assertIn('controlled',m['scope'])

    def test_negative_affinity_is_not_a_qualified_drama_chain(self):
        m=drama_metrics({'people':{'1':{'relationships':{'1':{'heard_turns':99},'2':{'affinity':-.5,'heard_turns':2},'3':{'affinity':.5,'background':{'seeded':True}}}}}})
        self.assertEqual(m['recorded_directed_edges'],2);self.assertEqual(m['heard_history_coverage']['percent'],50)
        self.assertEqual(m['negative_affinity_edges'],1);self.assertIsNone(m['qualified_conflict_resolution_chains'])


class DataDefinedGoalTests(unittest.TestCase):
    def catalog(self):
        return {'version':7,'source':'Test target','items':[{'id':'X','objective':'Test','measure':'Sample',
                'target':90,'unit':'percent','minimum_sample':30,'direction':'gte','scope':'Test evidence',
                'metric_path':'x.percent','sample_path':'x.n'}]}

    def test_threshold_is_data_driven_and_cannot_pass_with_missing_or_small_samples(self):
        c=self.catalog();m={'x':{'percent':91,'n':30}}
        self.assertEqual(quality_goals(m,c)['items'][0]['status'],'met')
        before_hash=quality_goals(m,c)['catalog_sha256']
        c['items'][0]['target']=95;self.assertEqual(quality_goals(m,c)['items'][0]['status'],'below_target')
        self.assertNotEqual(before_hash,quality_goals(m,c)['catalog_sha256'])
        m['x']['n']=True;self.assertEqual(quality_goals(m,c)['items'][0]['status'],'insufficient_sample')
        m['x']['percent']=float('inf');self.assertEqual(quality_goals(m,c)['items'][0]['status'],'unmeasured')

    def test_invalid_catalogs_fail_without_silently_changing_targets(self):
        for mutate in (lambda c:c['items'].append(c['items'][0]),lambda c:c['items'][0].update(target=float('nan')),
                       lambda c:c['items'][0].update(direction='equals'),lambda c:c['items'][0].update(minimum_sample=-1)):
            c=self.catalog();mutate(c)
            with self.assertRaises(ValueError):validate_catalog(c)

    def test_version_two_retains_existing_ids_and_adds_measured_and_unmeasured_agency(self):
        m=simulation_metrics({});goals=m['quality_goals'];ids={g['id']:g for g in goals['items']}
        self.assertEqual(goals['version'],2);self.assertGreaterEqual(len(ids),51)
        for key in ('SOC-01','PHY-04','ECO-06','BEH-04','REL-03','EVO-02','AGT-10','DRA-04','OPS-02'):self.assertIn(key,ids)
        self.assertEqual(ids['AGT-01']['status'],'unmeasured');self.assertEqual(ids['DRA-02']['status'],'unmeasured')
