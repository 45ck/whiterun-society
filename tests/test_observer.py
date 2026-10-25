import copy
import time
import unittest
from observer import camera_request,observer_state,enterprise_editor_metadata
from unittest.mock import patch
import economy_catalog
import market_policy


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.obs={'residents':[{'id':99,'isPerson':True,'x':1,'y':2,'z':3,'inventory':{'gold':7}}]}
        self.society={'checkpoint':10,'town':{'residents':{'99':{'name':'Resident'},'100':{'name':'Unloaded'}}},'people':{'99':{'memories':[]}}}

    def test_camera_only_accepts_current_loaded_initialized_people(self):
        self.assertEqual(camera_request({'mode':'focus','id':99},self.obs,self.society)['id'],99)
        for actor in (100,True,'99',-1):
            with self.assertRaises(ValueError):camera_request({'mode':'focus','id':actor},self.obs,self.society)
        for distance in (float('inf'),float('nan'),0,4001,True):
            with self.assertRaises(ValueError):camera_request({'mode':'free','distance':distance},self.obs,self.society)

    def test_projection_retains_unloaded_people_and_never_exposes_bridge_command(self):
        before=copy.deepcopy(self.society)
        result=observer_state({'last_seen':time.time(),'observation':self.obs,'command':{'secret':'not for observer'}},self.society)
        self.assertTrue(result['connected']);self.assertEqual(len(result['residents']),2)
        self.assertFalse(result['residents'][1]['loaded']);self.assertIsNone(result['residents'][1]['inventory'])
        self.assertNotIn('command',result);self.assertEqual(before,self.society)
        result=observer_state({'last_seen':0,'observation':self.obs},self.society)
        self.assertFalse(result['connected'])

    def test_current_scene_occupancy_is_visible_without_inventing_an_agent_intention(self):
        self.obs['residents'][0]['activity']={'scene_id':888,'in_combat':False,'sleep_state':0,'package_id':42}
        result=observer_state({'last_seen':time.time(),'observation':self.obs},self.society)
        self.assertEqual(result['residents'][0]['activity_blocker'],'native_scene')
        self.assertEqual(result['residents'][0]['native_activity']['scene_id'],888)
        self.assertIsNone(result['residents'][1]['native_activity'])

    def test_paid_capability_is_unknown_when_disconnected_or_checkpoint_changes(self):
        self.obs.update(ready=True,checkpoint=10,session='paid-observer',paid_employment={
            'available':True,'protocol':2,'epoch':'paid-epoch','session':'paid-observer'})
        bridge={'last_seen':time.time(),'observation':self.obs}
        current=observer_state(bridge,self.society)
        self.assertTrue(current['dashboard']['paid_employment_metrics']['capability']['available'])
        self.assertEqual(current['paid_employment_metrics'],current['dashboard']['paid_employment_metrics'])
        for stale in ({**bridge,'last_seen':0},
                      {**bridge,'observation':{**self.obs,'checkpoint':11}}):
            result=observer_state(stale,self.society)
            self.assertIsNone(result['paid_employment_metrics']['capability']['available'])
            self.assertFalse(result['paid_employment_metrics']['capability']['fresh'])
        self.assertEqual(result['residents'][1]['activity_blocker'],'not_loaded')

    def test_concurrency_projection_keeps_sampled_history_but_clears_stale_reservations(self):
        self.obs.update(ready=True,checkpoint=10,session='concurrency-observer',paid_employment={
            'available':True,'protocol':2,'epoch':'paid-epoch','session':'concurrency-observer'})
        overlap={'employer_movement':{'n':2,'sampled_overlap_seconds':5}}
        bridge={'last_seen':time.time(),'observation':self.obs,
                'employment_concurrency':{'fresh':True,'overlap':overlap,'coverage':{'qualified_attendance_intervals':2}}}
        current=observer_state(bridge,self.society)['employment_concurrency_metrics']
        self.assertTrue(current['fresh']);self.assertEqual(current['overlap'],overlap)
        for stale in ({**bridge,'last_seen':0},{**bridge,'observation':{**self.obs,'checkpoint':11}}):
            result=observer_state(stale,self.society)
            metrics=result['employment_concurrency_metrics']
            self.assertFalse(metrics['fresh'])
            self.assertIsNone(metrics['counts']['paid_account_participants'])
            self.assertEqual(metrics['overlap'],overlap)
            self.assertEqual(metrics,result['dashboard']['employment_concurrency_metrics'])
            self.assertEqual(metrics,result['metrics']['employment_concurrency'])
        held=observer_state(bridge,{**self.society,'error':'Timeline execution held'})
        self.assertFalse(held['employment_concurrency_metrics']['fresh'])
        self.assertIsNone(held['employment_concurrency_metrics']['counts']['paid_account_participants'])
        self.assertEqual(held['employment_concurrency_metrics']['overlap'],overlap)

    def test_independent_review_metrics_reach_inspector_and_expire_with_observation(self):
        self.obs.update(ready=True,checkpoint=10,session='reviews')
        self.society.update(independent_reviews={},independent_plans={},independent_review_waves=[])
        bridge={'last_seen':time.time(),'observation':self.obs}
        result=observer_state(bridge,self.society)
        metric=result['independent_review_metrics']
        self.assertTrue(metric['fresh'])
        self.assertEqual(metric,result['dashboard']['independent_review_metrics'])
        self.assertEqual(metric,result['metrics']['independent_reviews'])
        for changed in ({**bridge,'last_seen':0},{**bridge,'observation':{**self.obs,'checkpoint':11}},
                        {**bridge,'observation':{**self.obs,'paused':True}}):
            self.assertFalse(observer_state(changed,self.society)['independent_review_metrics']['fresh'])

    def test_configured_recipe_editor_is_generic_and_does_not_mutate_catalog(self):
        from test_catalog_enterprises import expanded_catalog
        catalog=expanded_catalog()
        with patch.object(economy_catalog,'ECONOMY_CATALOG',catalog):
            policy=copy.deepcopy(market_policy.MARKET_POLICY);policy['catalog_hash']=economy_catalog.catalog_hash()
            policy['goods'].append({**policy['goods'][0],'commodity':'ore','legacy_retail_capability':None,'reserve_mode':'seller_choice'})
            with patch.object(market_policy,'MARKET_POLICY',policy):
                before=copy.deepcopy((catalog,policy));result=enterprise_editor_metadata()
                recipe=next(r for r in result['recipes'] if r['id']=='metal_recipe')
                self.assertEqual(recipe['inputs'],{'ore':2});self.assertEqual(recipe['outputs'],{'ingot':1})
                fields={f['key']:f for f in recipe['fields']}
                self.assertEqual((fields['work_minutes']['min'],fields['work_minutes']['max']),(12,24))
                self.assertIn('target_output',fields);self.assertNotIn('target_bread',fields)
                self.assertIn({'id':'ore','legacy_capability':None},result['sale_goods'])
                self.assertEqual(before,(catalog,policy))

    def test_startup_identity_requires_fresh_matching_checkpoint_and_outcomes_exclude_priors(self):
        binding={'schema_version':1,'actor':99,'base_id':44,'event_id':'Census1'}
        self.society['town']['residents']['99'].update(id=99,identity_binding=binding)
        self.obs.update(ready=True,session='fixture',checkpoint=10)
        self.obs['residents'][0]['baseId']=44
        self.society['town']['livelihood_backgrounds']=[{'id':'prior','assignments':[{'actor':99}]}]
        self.society['production']=[{'status':'prepared'},{'status':'held'},{'status':'committed'}]
        self.society['trades']=[{'status':'committed'},{'status':'held'}]
        self.society['paid_work_capability']={'available':False,'reason':'legacy_paid_execution_unqualified','detail':'Requires wage witnesses'}
        fresh={'last_seen':time.time(),'observation':self.obs}
        result=observer_state(fresh,self.society)
        self.assertEqual(result['startup']['identity_qualified'],1)
        self.assertEqual(result['startup']['committed_production'],1)
        self.assertEqual(result['startup']['committed_sales'],1)
        self.assertEqual(len(result['startup']['backgrounds']),1)
        self.assertEqual(result['startup']['paid_work_capability'],self.society['paid_work_capability'])
        for bridge in ({**fresh,'last_seen':0},{**fresh,'observation':{**self.obs,'checkpoint':11}}):
            result=observer_state(bridge,self.society)
            self.assertFalse(result['startup']['current']);self.assertEqual(result['startup']['identity_qualified'],0)

    def test_unconfigured_background_manifest_is_reported_without_hiding_observer(self):
        with patch('observer.load_livelihood_manifest',side_effect=ValueError('catalog changed')):
            result=observer_state({'last_seen':time.time(),'observation':self.obs},self.society)
            self.assertFalse(result['startup']['scenario']['available'])
            self.assertEqual(result['startup']['scenario']['reason'],'catalog changed')
