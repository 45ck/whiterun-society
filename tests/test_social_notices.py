import copy
import time
import unittest
from unittest.mock import patch
from social import social_candidates,valid_social_notice,same_social_space
import test_background_society as fixture
from metrics import simulation_metrics


class SocialNoticeTests(unittest.TestCase):
    setUp=fixture.BackgroundSocietyTests.setUp
    tearDown=fixture.BackgroundSocietyTests.tearDown
    sync=fixture.BackgroundSocietyTests.sync
    census=fixture.BackgroundSocietyTests.census
    review=fixture.BackgroundSocietyTests.review
    choose=fixture.BackgroundSocietyTests.choose
    background=fixture.BackgroundSocietyTests.background
    add_free_pair=fixture.BackgroundSocietyTests.add_free_pair

    def started_notice(self):
        self.add_free_pair();self.background()
        return copy.deepcopy(self.world.routine_batch()['social_notice'])

    def test_short_lived_notice_preserves_options_without_freezing_people(self):
        notice=self.started_notice()
        self.assertNotIn(str(self.ids[0]),notice['candidates_by_actor'])
        next(a for a in self.obs['residents'] if a['id']==501)['x']=2200
        self.assertEqual(social_candidates(self.world.active,self.obs,108149),[])
        recent=social_candidates(self.world.active,self.obs,108149,notice)
        self.assertEqual([a['id'] for a in recent],[501]);self.assertIn('recent proximity',recent[0]['source'])
        before=copy.deepcopy(self.obs)
        self.world.start_conversation('noticed',self.obs,opportunity_batch='cohort');self.sync()
        c=self.world.conversation_status();actor=c['initiator'];partner=501 if actor==108149 else 108149
        self.assertEqual(list(c['social_notice']['candidates_by_actor']),[str(actor)])
        claim=self.world.claim_conversation('noticed',self.obs)['claim'];self.sync()
        self.assertIn('approach_'+str(partner),[a['id'] for a in claim['context']['options']])
        self.world.finish_conversation_inference('noticed',claim['id'],{'model':'test','decision':{
            'action_id':'approach_'+str(partner),'reason':'Choose to approach','emotion':'calm'}},self.obs);self.sync()
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'walk_to')
        self.assertEqual(before['residents'],self.obs['residents'])
        self.assertEqual(self.world.routine_batch()['social_notice']['consumed_by'],'noticed')
        self.assertNotIn('attendance_evidence',self.world.conversation_status())

    def test_unloaded_committed_or_out_of_reach_people_are_not_preserved(self):
        notice=self.started_notice();state=self.world.active
        for update in ('unloaded','committed','too_far'):
            o=copy.deepcopy(self.obs);s=copy.deepcopy(state)
            if update=='unloaded':o['residents']=[r for r in o['residents'] if r['id']!=501]
            elif update=='committed':s['people']['501']['commitments']=[{'kind':'shift'}]
            else:next(r for r in o['residents'] if r['id']==501)['x']=4000
            self.assertEqual(social_candidates(s,o,108149,notice),[],update)

    def test_expired_other_session_and_future_notices_do_not_expand_range(self):
        notice=self.started_notice();next(r for r in self.obs['residents'] if r['id']==501)['x']=2200
        for age in (-1,46):
            n={**notice,'captured_at':time.time()-age}
            self.assertFalse(valid_social_notice(n,self.obs))
            self.assertEqual(social_candidates(self.world.active,self.obs,108149,n),[])
        self.assertFalse(valid_social_notice(notice,{**self.obs,'session':'loaded'}))
        with patch('social.time.time',return_value=notice['captured_at']+46):
            with self.assertRaisesRegex(ValueError,'expired'):self.world.start_conversation('old',self.obs,opportunity_batch='cohort')
        self.assertIsNone(self.world.routine_batch()['social_notice'].get('consumed_by'))

    def test_notice_cannot_create_acquaintance_or_force_a_chat_and_is_single_use(self):
        self.started_notice();people=copy.deepcopy(self.world.active['people'])
        with self.assertRaises(ValueError):self.world.start_conversation('wrong',self.obs,opportunity_batch='other')
        self.world.start_conversation('noticed',self.obs,opportunity_batch='cohort');self.sync()
        claim=self.world.claim_conversation('noticed',self.obs)['claim'];self.sync()
        self.world.finish_conversation_inference('noticed',claim['id'],{'model':'test','decision':{
            'action_id':'defer','reason':'Keep walking','emotion':'calm'}},self.obs);self.sync()
        self.assertEqual(self.world.conversation_status()['turns'],[])
        for actor,p in people.items():
            self.assertEqual(p['memories'],self.world.active['people'][actor]['memories'])
            self.assertEqual(p.get('relationships'),self.world.active['people'][actor].get('relationships'))
        with self.assertRaisesRegex(ValueError,'consumed'):self.world.start_conversation('reuse',self.obs,opportunity_batch='cohort')


class NoticeMetricTests(unittest.TestCase):
    def test_coordinates_only_compare_in_a_shared_native_space(self):
        exterior=lambda world,cell:{'space':{'interior':False,'world':world,'cell':cell}}
        inside=lambda cell:{'space':{'interior':True,'world':None,'cell':cell}}
        self.assertTrue(same_social_space(exterior(1,10),exterior(1,11)))
        self.assertTrue(same_social_space(inside(10),inside(10)))
        for a,b in ((exterior(1,10),exterior(2,10)),(inside(10),inside(11)),
                    (inside(10),exterior(1,10)),({'space':None},inside(10)),({},inside(10))):
            self.assertFalse(same_social_space(a,b))

    def test_old_zero_overlap_and_unused_opportunities_remain_in_denominators(self):
        def batch(name,notice=None,frames=0):
            return {'id':name,'background':True,'phase':'complete','members':[],
                    'social_notice':notice,'concurrency':{'speech_overlap_samples':frames}}
        notice={'candidates_by_actor':{'1':[2],'2':[1]}}
        state={'routine_batches':[batch('old'),batch('missed',notice),batch('used',{**notice,'consumed_by':'chat'},45)],
               'conversation':{'id':'chat','mode':'autonomous_social','phase':'complete','social_notice':notice,
                   'notice_to_start_seconds':2.5,'approach_source':'recent proximity notice; currently observed; vision unqualified','turns':[]}}
        m=simulation_metrics(state)['encounter_scheduling']
        self.assertEqual(m['travel_speech_overlap'],{'success':1,'n':3,'percent':33.33})
        self.assertEqual(m['cohorts_without_notice_telemetry'],1)
        self.assertEqual(m['captured_directed_pairs'],4);self.assertEqual(m['notices_consumed'],1)
        self.assertEqual(m['terminal_notices_without_encounter'],1);self.assertEqual(m['recent_notice_approaches'],1)
        self.assertEqual(m['notice_to_start_seconds']['median'],2.5)
