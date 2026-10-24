import copy
import unittest
import test_daily_life
from test_conversation import AUDIO,CANDIDATES
from social import social_candidates


class SocialTests(unittest.TestCase):
    tearDown=test_daily_life.DailyLifeTests.tearDown
    sync=test_daily_life.DailyLifeTests.sync
    census=test_daily_life.DailyLifeTests.census
    review=test_daily_life.DailyLifeTests.review

    def setUp(self):
        test_daily_life.DailyLifeTests.setUp(self)
        for row in self.obs['residents']:
            row.update(x=200 if row['id']==99 else row.get('x',0),y=0,z=0,isGuard=False)
        self.obs['routing']={'adapter':'papyrus-mailbox-v1','available':True}
        for person in self.world.active['people'].values():person['needs']['social_contact']=.1
        self.world.active['people']['99']['needs'].update(hunger=.2,fatigue=.9,social_contact=.9)

    def begin(self):
        self.review();self.event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.assertEqual(self.event['kind'],'social_review')
        self.world.start_conversation(self.event['id'],self.obs,99);self.sync()

    def decide(self,action):
        claim=self.world.claim_conversation(self.event['id'],self.obs)['claim'];self.sync()
        self.world.finish_conversation_inference(self.event['id'],claim['id'],{'model':'test-jev','decision':{
            'action_id':action,'reason':'Authored test choice','emotion':'calm'}},self.obs);self.sync()
        return claim['context']

    def meet(self):
        self.decide('approach_108149')
        command=self.world.pending(self.obs['session']);self.assertTrue(command['dynamic'])
        self.obs['ack']={'id':command['id'],'status':'applied','movement':{'actor':99,'target':108149,'ownedPackage':True}}
        self.world.observe(self.obs);self.sync()

    def speak(self):
        claim=self.world.claim_conversation(self.event['id'],self.obs)['claim'];self.sync()
        self.world.finish_conversation_inference(self.event['id'],claim['id'],{'model':'test-llm','proposal':{'candidates':CANDIDATES}},self.obs);self.sync()
        self.decide('option_1');self.world.prepare_speech(self.event['id'],AUDIO,self.obs);self.sync()
        command=self.world.pending(self.obs['session'])
        self.obs['speech']={'id':command['id'],'status':'ended','playedSeconds':3,'nearbyThroughout':True}
        self.world.observe(self.obs);self.sync()

    def release(self):
        command=self.world.pending(self.obs['session']);self.assertEqual(command['actor'],99)
        self.obs['ack']={'id':command['id'],'status':'applied','released':True};self.world.observe(self.obs);self.sync()

    def test_scheduled_partner_consent_voice_appraisal_and_need_recovery(self):
        inventory=copy.deepcopy(self.obs['residents']);self.begin();self.meet()
        self.assertEqual(self.world.conversation_status()['phase'],'respond')
        context=self.decide('chat');self.assertNotIn('other_inventory',context);self.assertEqual(context['actor_id'],108149)
        for _ in range(2):self.speak()
        self.assertEqual(self.world.active['people']['99']['relationships'],{})
        self.release();self.decide('felt_supported');self.decide('neutral')
        c=self.world.conversation_status();self.assertEqual(c['outcome'],'social_exchange_completed')
        p=self.world.active['people']['99'];self.assertAlmostEqual(p['needs']['social_contact'],.7)
        self.assertEqual(p['relationships']['108149']['affinity'],.05)
        self.assertEqual(p['relationships']['108149']['heard_turns'],1)
        self.assertEqual(self.world.active['people']['108149']['relationships']['99']['affinity'],0)
        self.assertEqual(inventory,self.obs['residents']);self.assertTrue(self.world.start_conversation(self.event['id'],self.obs,99)['duplicate'])
        before=copy.deepcopy(self.world.active);self.world.observe(self.obs);self.assertEqual(before,self.world.active)
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['id']==self.event['id']);self.assertEqual(event['status'],'complete')

    def test_quiet_choice_makes_no_meeting_memory_or_relationship(self):
        self.begin();self.decide('defer')
        c=self.world.conversation_status();self.assertEqual(c['outcome'],'continued_quietly')
        self.assertIsNone(self.world.pending(self.obs['session']));self.assertEqual(c['turns'],[])
        self.assertEqual(self.world.active['people']['99']['relationships'],{})
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['social_contact'],.9)

    def test_decline_requires_one_delivered_turn_and_does_not_imply_hostility(self):
        self.begin();self.meet();self.decide('decline');self.speak();self.release()
        self.decide('neutral');self.decide('neutral')
        c=self.world.conversation_status();self.assertEqual(len(c['turns']),1);self.assertEqual(c['outcome'],'spoke_brief_refusal')
        self.assertEqual(self.world.active['people']['99']['relationships']['108149']['affinity'],0)
        self.assertEqual(self.world.active['people']['108149']['relationships'],{})
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['social_contact'],.9)

    def test_unavailable_partner_cannot_be_chosen_after_claim(self):
        self.begin();claim=self.world.claim_conversation(self.event['id'],self.obs)['claim'];self.sync()
        self.obs['residents']=[r for r in self.obs['residents'] if r['id']!=108149]
        with self.assertRaisesRegex(ValueError,'not currently allowed'):
            self.world.finish_conversation_inference(self.event['id'],claim['id'],{'model':'test','decision':{'action_id':'approach_108149','reason':'test','emotion':'calm'}},self.obs)
        self.assertEqual(self.world.active['people']['99']['relationships'],{})

    def test_ownership_and_proximity_are_required_before_partner_response(self):
        self.begin();self.decide('approach_108149');command=self.world.pending(self.obs['session'])
        self.obs['ack']={'id':command['id'],'status':'applied'};self.world.observe(self.obs);self.sync();self.release()
        self.assertEqual(self.world.conversation_status()['phase'],'held')
        self.assertEqual(self.world.active['people']['99']['relationships'],{})

    def test_guards_commitments_unknown_classification_and_distance_excluded(self):
        self.assertTrue(social_candidates(self.world.active,self.obs,99))
        self.obs['residents'][2]['isGuard']=True;self.assertFalse(social_candidates(self.world.active,self.obs,99))
        self.obs['residents'][2]['isGuard']=False;self.world.active['people']['99']['commitments']=[{'kind':'job'}]
        self.assertFalse(social_candidates(self.world.active,self.obs,99))
        self.world.active['people']['99']['commitments']=[];self.obs['residents'][2]['isPerson']=None
        self.assertFalse(social_candidates(self.world.active,self.obs,99))

    def test_older_save_removes_future_relationship_and_recovery(self):
        self.begin();old=copy.deepcopy(self.obs);self.meet();self.decide('chat')
        for _ in range(2):self.speak()
        self.release();self.decide('felt_annoyed');self.decide('felt_supported')
        self.world.observe({**old,'session':'old-social-save'})
        self.assertEqual(self.world.active['people']['99']['relationships'],{})
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['social_contact'],.9)
        self.assertNotIn('social_clock',self.world.active['people']['99'])

    def test_private_partner_state_is_not_exposed_to_social_context(self):
        self.begin();context=self.world.claim_conversation(self.event['id'],self.obs)['claim']['context']
        for candidate in context['nearby_candidates']:
            self.assertEqual(set(candidate),{'id','name','name_known','identity_source','distance','my_relationship','source'})
            self.assertFalse(candidate['name_known'])
            self.assertEqual(candidate['name'],'an unfamiliar resident')
        self.sync()
        with self.assertRaisesRegex(ValueError,'conversation'):self.world.begin_plan('intruder',self.obs)

    def test_failed_release_cannot_create_affinity_or_social_recovery(self):
        self.begin();self.meet();self.decide('chat')
        for _ in range(2):self.speak()
        command=self.world.pending(self.obs['session'])
        self.obs['ack']={'id':command['id'],'status':'failed','released':False}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.conversation_status()['phase'],'held')
        self.assertEqual(self.world.active['people']['99']['relationships'],{})
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['social_contact'],.9)
        self.assertTrue(any(m['kind']=='heard_speech' for m in self.world.active['people']['99']['memories']))

    def test_failed_audio_does_not_become_heard_memory(self):
        self.begin();self.meet();self.decide('chat')
        claim=self.world.claim_conversation(self.event['id'],self.obs)['claim'];self.sync()
        self.world.finish_conversation_inference(self.event['id'],claim['id'],{'model':'test','proposal':{'candidates':CANDIDATES}},self.obs);self.sync()
        self.decide('option_1');self.world.prepare_speech(self.event['id'],AUDIO,self.obs);self.sync()
        command=self.world.pending(self.obs['session'])
        self.obs['speech']={'id':command['id'],'status':'failed','error':'interrupted'}
        self.world.observe(self.obs);self.sync();self.release()
        self.assertEqual(self.world.conversation_status()['phase'],'held')
        for actor in ('99','108149'):
            self.assertFalse(any(m['kind']=='heard_speech' for m in self.world.active['people'][actor]['memories']))

    def test_partner_opportunity_settles_and_growth_uses_recovery_clock(self):
        self.world.active['people']['108149']['needs'].update(hunger=.2,fatigue=.9,social_contact=.9)
        self.begin();self.meet();self.decide('chat')
        self.obs['gameDays']+=1/24
        for _ in range(2):self.speak()
        self.release();self.decide('neutral');self.decide('neutral')
        partner_event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==108149)
        self.assertEqual(partner_event['outcome'],'participated_as_partner')
        before=self.world.active['people']['99']['needs']['social_contact']
        rate=.018+.025*self.world.active['people']['99']['profile']['big_five']['extraversion']
        self.review(.5)
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['social_contact'],before+.5*rate,places=5)


if __name__=='__main__':unittest.main()
