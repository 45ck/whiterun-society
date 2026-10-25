import copy
import unittest
import test_population
from scene_handoffs import scene_candidates

FREE={'scene_id':0,'in_combat':False,'sleep_state':0,'package_id':42}


class SceneHandoffTests(unittest.TestCase):
    tearDown=test_population.PopulationTests.tearDown
    sync=test_population.PopulationTests.sync
    census=test_population.PopulationTests.census

    def setUp(self):
        test_population.PopulationTests.setUp(self);self.census()
        self.world.initialize_population('census','handoff-test',self.obs);self.sync()
        self.row=next(r for r in self.obs['residents'] if r['id']==99)
        self.row['activity']={**FREE,'scene_id':888}

    def begin(self):
        self.world.request_scene_handoff('handoff',99,888,self.obs)
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'bind_checkpoint')
        self.sync()
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'scene_handoff')

    def release(self,**ack):
        self.row['activity']=FREE.copy()
        self.obs['ack']={'id':'handoff','status':'applied','actor':99,'scene_id':888,'release_observed':True,**ack}
        self.world.observe(self.obs);self.sync()

    def test_verified_release_changes_availability_not_inventory_memories_or_relationships(self):
        before=copy.deepcopy(self.world.active['people']);inventory=copy.deepcopy(self.row['inventory'])
        self.begin();self.release()
        self.assertIsNone(self.world.active['pending'])
        self.assertEqual(self.world.status()['scene_handoffs'][-1]['status'],'released')
        self.assertEqual(self.world.status()['metrics']['scene_handoffs']['verified_release'],{'success':1,'n':1,'percent':100})
        self.assertEqual(inventory,self.row['inventory'])
        for key,p in before.items():
            for field in ('needs','memories','trust'):
                self.assertEqual(p[field],self.world.active['people'][key][field])
        self.assertEqual(self.world.active['people']['99']['agency']['next_review_day'],self.obs['gameDays'])
        self.assertTrue(self.world.request_scene_handoff('handoff',99,888,self.obs)['duplicate'])

    def test_changed_scene_combat_sleep_and_unmanaged_actor_never_dispatch(self):
        for update in ({'scene_id':999},{'in_combat':True},{'sleep_state':3},{'scene_id':None}):
            self.row['activity']={**FREE,'scene_id':888,**update}
            with self.assertRaises(ValueError):self.world.request_scene_handoff('handoff',99,888,self.obs)
        self.row['activity']={**FREE,'scene_id':888};self.row['isPerson']=False
        with self.assertRaises(ValueError):self.world.request_scene_handoff('handoff',99,888,self.obs)
        self.assertIsNone(self.world.transition)

    def test_ack_without_matching_observation_or_identity_cannot_prove_release(self):
        self.begin()
        self.obs['ack']={'id':'handoff','status':'applied','actor':99,'scene_id':888,'release_observed':True}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['scene_handoffs'][-1]['status'],'held')
        self.assertIsNone(self.world.active['pending'])
        self.row['activity']={**FREE,'scene_id':888}
        self.world.request_scene_handoff('explicit-second-attempt',99,888,self.obs);self.sync()
        self.row['activity']=FREE.copy()
        self.obs['ack']={'id':'explicit-second-attempt','status':'applied','actor':100,'scene_id':888,'release_observed':True}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['scene_handoffs'][-1]['status'],'held')

    def test_loading_pending_checkpoint_never_replays_scene_stop(self):
        self.begin();self.obs['session']='reloaded'
        self.world.observe(self.obs);self.sync()
        self.assertIsNone(self.world.pending('reloaded'))
        self.assertEqual(self.world.active['scene_handoffs'][-1]['outcome'],'session_changed')

    def test_older_save_discards_future_handoff_and_repeated_heartbeat_does_not_repeat_it(self):
        old=copy.deepcopy(self.obs);self.begin();self.release()
        marker=self.world.marker;self.world.observe(self.obs);self.assertEqual(self.world.marker,marker)
        self.world.observe({**old,'session':'old-save'})
        self.assertEqual(self.world.status()['scene_handoffs'],[])

    def test_director_skips_attempted_scene_including_its_other_participants(self):
        self.assertEqual([r['id'] for r in scene_candidates(self.world.status(),self.obs)],[99])
        self.begin();self.release(status='held')
        self.row['activity']={**FREE,'scene_id':888}
        self.obs['residents'][0]['activity']={**FREE,'scene_id':888}
        self.assertEqual(scene_candidates(self.world.status(),self.obs),[])

    def test_next_plan_records_handoff_provenance_without_assuming_a_successful_action(self):
        self.begin();self.release()
        self.world.begin_plan('after-scene',self.obs,actor=99);self.sync()
        self.assertEqual(self.world.agency_plan()['scene_handoff'],{'id':'handoff','scene_id':888})
        self.assertEqual(self.world.active['scene_handoffs'][-1]['resumed_by'],'after-scene')
        self.assertEqual(self.world.status()['metrics']['scene_handoffs']['resumed_plan_outcomes'],{'choose':1})


if __name__=='__main__':unittest.main()
