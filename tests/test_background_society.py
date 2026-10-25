import copy
import unittest
import test_parallel_routines
from population import person_seed
from social import social_candidates
from activity_leases import routine_actors
from places import MARKET
from test_conversation import candidates_for,AUDIO


class BackgroundSocietyTests(unittest.TestCase):
    setUp=test_parallel_routines.ParallelRoutineTests.setUp
    tearDown=test_parallel_routines.ParallelRoutineTests.tearDown
    sync=test_parallel_routines.ParallelRoutineTests.sync
    census=test_parallel_routines.ParallelRoutineTests.census
    review=test_parallel_routines.ParallelRoutineTests.review
    choose=test_parallel_routines.ParallelRoutineTests.choose

    def background(self):
        self.obs['parallel_routines']['background_capacity']=6
        self.batch=self.world.begin_routines('cohort',self.events,self.obs,background=True)['batch'];self.sync()
        self.choose();command=self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'],'background_routines');self.jobs=command['jobs']
        self.obs['parallel_routines'].update(id='cohort',background=True)
        self.obs['ack']={'id':'cohort','status':'started'};self.world.observe(self.obs);self.sync()
        self.assertIsNone(self.world.active['pending']);self.assertTrue(self.world.routines_busy())

    def add_free_pair(self):
        self.obs['routing'].update(adapter='papyrus-mailbox-v1')
        row={'id':501,'name':'Other resident','isPerson':True,'isGuard':False,'x':200,'y':0,'z':0,
             'inventory':{'gold':9,'bread':1,'grain':0}}
        self.obs['residents'].append(row)
        self.world.active['people']['501']=person_seed(row,'test',self.obs['gameDays'])
        self.world.active['town']['residents']['501']={'id':501}

    def finish_background(self,verified=True):
        receipts=[{'id':j['id'],'slot':j['slot'],'status':'applied','release_verified':verified,'seller_nearby':False,
            'movement':{'actor':j['actor'],'target':MARKET,'target_kind':'place','distance':200,'aliasesConfirmed':True,
                        'hasOwnedPackage':True,'adapter':'papyrus-mailbox'}} for j in self.jobs]
        self.obs['parallel_routines']['result']={'id':'cohort','status':'applied','routines':receipts}
        self.world.observe(self.obs);self.sync()

    def test_background_reserves_actors_but_disjoint_social_choice_can_finish(self):
        self.add_free_pair();self.background();inventory=copy.deepcopy(self.obs['residents'])
        self.assertEqual(routine_actors(self.world.active),set(self.ids))
        self.assertEqual(social_candidates(self.world.active,self.obs,99),[])
        self.assertEqual([p['id'] for p in social_candidates(self.world.active,self.obs,108149)],[501])
        self.world.start_conversation('free-pair',self.obs);self.sync()
        claim=self.world.claim_conversation('free-pair',self.obs)['claim'];self.sync()
        self.assertNotIn(claim['context']['actor_id'],self.ids)
        self.world.finish_conversation_inference('free-pair',claim['id'],{'model':'test',
            'decision':{'action_id':'defer','reason':'Quiet choice','emotion':'calm'}},self.obs);self.sync()
        self.assertEqual(self.world.conversation_status()['phase'],'complete')
        self.assertEqual(self.world.routine_batch()['phase'],'travelling')
        self.finish_background();self.assertFalse(self.world.routines_busy())
        self.assertEqual(inventory,self.obs['residents'])

    def test_background_receipt_can_settle_during_a_foreground_claim(self):
        self.add_free_pair();self.background();self.world.start_conversation('free-pair',self.obs);self.sync()
        claim=self.world.claim_conversation('free-pair',self.obs)['claim'];self.sync()
        self.finish_background()
        self.assertEqual(self.world.conversation_status()['claim']['id'],claim['id'])
        self.world.finish_conversation_inference('free-pair',claim['id'],{'model':'test',
            'decision':{'action_id':'defer','reason':'Quiet choice','emotion':'calm'}},self.obs);self.sync()
        self.assertEqual(self.world.conversation_status()['phase'],'complete')

    def test_speech_delivery_survives_background_arrival_checkpoint(self):
        self.add_free_pair();self.background();self.world.start_conversation('free-pair',self.obs,max_turns=2);self.sync()
        def decide(action):
            claim=self.world.claim_conversation('free-pair',self.obs)['claim'];self.sync()
            self.world.finish_conversation_inference('free-pair',claim['id'],{'model':'test',
                'decision':{'action_id':action,'reason':'Test choice','emotion':'calm'}},self.obs);self.sync()
        initiator=self.world.conversation_status()['initiator'];partner=108149 if initiator==501 else 501
        decide('approach_'+str(partner))
        meet=self.world.pending(self.obs['session'])
        self.obs['ack']={'id':meet['id'],'status':'applied','movement':{'actor':initiator,'target':partner,'ownedPackage':True,
            'id':meet['id'],'aliasesConfirmed':True,'adapter':'papyrus-mailbox'}}
        self.world.observe(self.obs);self.sync();decide('chat')
        attend=self.world.pending(self.obs['session'])
        self.obs['conversationAttendance']={'id':attend['id'],'phase':'attending','participants':[
            {'actor':a,'slot':i+6,'loaded':True,'ownedPackage':True} for i,a in enumerate(attend['participants'])]}
        self.obs['ack']={'id':attend['id'],'status':'applied'};self.world.observe(self.obs);self.sync()
        claim=self.world.claim_conversation('free-pair',self.obs)['claim'];self.sync()
        self.world.finish_conversation_inference('free-pair',claim['id'],{'model':'test','proposal':{'candidates':candidates_for(claim['context'])}},self.obs);self.sync()
        decide('option_1');self.world.prepare_speech('free-pair',AUDIO,self.obs);self.sync()
        speech=self.world.pending(self.obs['session']);self.finish_background()
        self.assertEqual(self.world.pending(self.obs['session'])['id'],speech['id'])
        self.obs['speech']={'id':speech['id'],'status':'ended','playedSeconds':3,'nearbyThroughout':True}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(len(self.world.conversation_status()['turns']),1)
        self.assertEqual(self.world.routine_batch()['phase'],'complete')

    def test_uncertain_background_release_does_not_deadlock_existing_social_cleanup(self):
        self.add_free_pair();self.background();self.world.start_conversation('free-pair',self.obs);self.sync()
        claim=self.world.claim_conversation('free-pair',self.obs)['claim'];self.sync()
        self.finish_background(verified=False)
        self.assertTrue(self.world.routines_busy());self.assertEqual(routine_actors(self.world.active),set(self.ids))
        self.world.finish_conversation_inference('free-pair',claim['id'],{'model':'test',
            'decision':{'action_id':'defer','reason':'Quiet choice','emotion':'calm'}},self.obs);self.sync()
        self.assertEqual(self.world.conversation_status()['phase'],'complete')
        with self.assertRaises(ValueError):self.world.start_conversation('another',self.obs)
        with self.assertRaises(ValueError):self.world.begin_plan('meal',self.obs, 108186)

    def test_background_mode_requires_capability_and_reserves_two_slots(self):
        with self.assertRaisesRegex(ValueError,'protocol'):self.world.begin_routines('bad',self.events,self.obs,background=True)
        self.obs['parallel_routines']['background_capacity']=6
        with self.assertRaises(ValueError):self.world.begin_routines('bad',[str(i) for i in range(7)],self.obs,background=True)
        with self.assertRaises(ValueError):self.world.begin_routines('bad',self.events,self.obs,background='yes')

    def test_reload_of_background_and_social_claim_holds_without_replay(self):
        self.add_free_pair();self.background();self.world.start_conversation('free-pair',self.obs);self.sync()
        self.world.claim_conversation('free-pair',self.obs);self.sync()
        self.obs['session']='reloaded';self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.routine_batch()['phase'],'held')
        self.assertNotIn((self.world.pending('reloaded') or {}).get('kind'),('background_routines','conversation_speak'))
