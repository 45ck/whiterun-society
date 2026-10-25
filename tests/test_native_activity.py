import copy
import unittest
import test_background_society as fixture
from routing import activity_blocker,route_available
from places import market_opportunity
from social import social_candidates,capture_social_notice
from parallel_routines import select_routine_events
from tools.run_daily_life import event_available

FREE={'scene_id':0,'in_combat':False,'sleep_state':0,'package_id':42}


class NativeActivityTests(unittest.TestCase):
    setUp=fixture.BackgroundSocietyTests.setUp
    tearDown=fixture.BackgroundSocietyTests.tearDown
    sync=fixture.BackgroundSocietyTests.sync
    census=fixture.BackgroundSocietyTests.census
    review=fixture.BackgroundSocietyTests.review
    add_free_pair=fixture.BackgroundSocietyTests.add_free_pair
    choose=fixture.BackgroundSocietyTests.choose

    def test_scene_occupancy_skips_inference_then_reopens_same_pending_opportunity(self):
        actor=self.ids[1];row=next(r for r in self.obs['residents'] if r['id']==actor)
        row['activity']={**FREE,'scene_id':888}
        queue=self.world.active['town']['daily']['queue']
        event=next(e for e in queue if e['actor']==actor)
        before=copy.deepcopy(self.world.active)
        self.assertIsNone(market_opportunity(self.world.active,self.obs,actor))
        self.assertNotIn(event,select_routine_events(self.world.active,self.obs,queue))
        self.assertFalse(event_available({'society':self.world.status(),'bridge':{'observation':self.obs}},event))
        with self.assertRaisesRegex(ValueError,'occupied'):
            self.world.begin_plan(event['id'],self.obs,actor=actor,kind='need_review')
        self.assertEqual(self.world.active,before)
        row['activity']=FREE.copy()
        self.assertIsNotNone(market_opportunity(self.world.active,self.obs,actor))
        self.assertIn(event,select_routine_events(self.world.active,self.obs,queue))
        self.assertTrue(event_available({'society':self.world.status(),'bridge':{'observation':self.obs}},event))

    def test_unavailable_native_activity_is_unknown_not_free(self):
        self.assertIsNone(activity_blocker({'activity':FREE}))
        for activity in (None,{}, {**FREE,'scene_id':None},{**FREE,'sleep_state':-1},{**FREE,'in_combat':0}):
            self.assertEqual(activity_blocker({'activity':activity}),'activity_unknown')
        self.assertEqual(activity_blocker({'activity':{**FREE,'in_combat':True}}),'combat')
        self.assertEqual(activity_blocker({'activity':{**FREE,'sleep_state':3}}),'sleep_transition')

    def test_transient_social_opportunity_can_share_the_director_queue_with_travel(self):
        queue=self.world.active['town']['daily']['queue']
        expected=select_routine_events(self.world.active,self.obs,queue)
        self.assertTrue(expected)
        mixed=[{'id':'encounter-1','kind':'social_opportunity','actor':None},*queue]
        self.assertEqual(select_routine_events(self.world.active,self.obs,mixed),expected)

    def test_scene_started_during_inference_cancels_trip_and_retains_held_outcome(self):
        self.batch=self.world.begin_routines('cohort',self.events,self.obs)['batch'];self.sync()
        row=next(r for r in self.obs['residents'] if r['id']==self.ids[0]);row['activity']={**FREE,'scene_id':888}
        self.choose(('check_market','defer'))
        batch=self.world.routine_batch()
        self.assertEqual(batch['phase'],'held');self.assertTrue(batch['release_verified'])
        self.assertTrue(batch['settled']);self.assertIsNone(self.world.active['pending'])
        self.assertEqual([m['phase'] for m in batch['members']],['held','complete'])
        self.assertEqual(batch['members'][0]['outcome'],'changed_before_departure')

    def test_busy_social_partner_is_excluded_even_with_a_recent_notice(self):
        self.add_free_pair();self.obs['routing']['adapter']='papyrus-mailbox-v1'
        actor=next(r for r in self.obs['residents'] if r['id']==501)
        self.assertTrue(route_available(self.obs,108149,501))
        notice=capture_social_notice(self.world.active,self.obs)
        actor['activity']={**FREE,'scene_id':888}
        self.assertFalse(route_available(self.obs,108149,501))
        self.assertNotIn(501,[r['id'] for r in social_candidates(self.world.active,self.obs,108149,notice)])
        actor['activity']=FREE.copy()
        self.assertIn(501,[r['id'] for r in social_candidates(self.world.active,self.obs,108149)])


if __name__=='__main__':unittest.main()
