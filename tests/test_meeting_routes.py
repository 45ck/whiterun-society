"""New meetings carry saved route identity; old meetings cannot be reinterpreted."""
import copy
import unittest
import test_social
import test_conversation


class MeetingRouteTests(unittest.TestCase):
    setUp=test_social.SocialTests.setUp
    tearDown=test_social.SocialTests.tearDown
    sync=test_social.SocialTests.sync
    census=test_social.SocialTests.census
    review=test_social.SocialTests.review
    begin=test_social.SocialTests.begin
    decide=test_social.SocialTests.decide

    def prepare_meeting(self):
        self.begin();self.decide('approach_108149')
        return self.world.pending(self.obs['session'])

    def test_new_meeting_pins_actor_target_adapter_and_session(self):
        command=self.prepare_meeting()
        self.assertTrue(command['dynamic'])
        self.assertEqual(self.world.conversation_status()['meeting_route'],{
            'adapter':'papyrus-mailbox-v1','actor':99,'target':108149,'session':self.obs['session']})

    def test_legacy_meeting_is_not_dispatched_or_credited_from_cached_ack(self):
        command=self.prepare_meeting()
        self.world.active['conversation'].pop('meeting_route')
        self.assertIsNone(self.world.speech_command(self.obs['session']))
        self.obs['ack']={'id':command['id'],'status':'applied','movement':{
            'id':command['id'],'actor':99,'target':108149,'ownedPackage':True,
            'adapter':'papyrus-mailbox','aliasesConfirmed':True}}
        self.world.observe(self.obs);self.sync()
        conversation=self.world.conversation_status()
        self.assertEqual(conversation['phase'],'releasing')
        self.assertEqual(conversation['final_phase'],'held')
        self.assertNotIn('meeting_evidence',conversation)
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'release_routine')
        self.assertEqual(self.world.active['people']['99']['relationships'],{})

    def test_changed_saved_target_cannot_redirect_meeting(self):
        self.prepare_meeting()
        self.world.active['conversation']['meeting_route']['target']=108156
        self.assertIsNone(self.world.speech_command(self.obs['session']))
        self.world.observe(self.obs);self.sync()
        conversation=self.world.conversation_status()
        self.assertEqual(conversation['phase'],'held')
        self.assertTrue(conversation['cleanup_review_required'])
        self.assertTrue(conversation['release_required'])
        self.assertTrue(self.world.conversation_busy())
        self.assertIsNone(self.world.speech_command(self.obs['session']))
        self.assertNotIn('meeting_evidence',conversation)

    def test_changed_session_does_not_replay_meeting(self):
        self.prepare_meeting()
        self.assertIsNone(self.world.speech_command('new-session'))
        self.obs['session']='new-session'
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.conversation_status()['phase'],'releasing')
        self.assertNotIn('meeting_evidence',self.world.conversation_status())

    def test_wrong_or_missing_alias_witness_cannot_start_response(self):
        command=self.prepare_meeting()
        baseline=copy.deepcopy(self.world.active)
        for changed in ({'aliasesConfirmed':False},{'adapter':'fixed-quest'},
                        {'id':'another-meeting'},{'actor':108156},{'target':108156},
                        {'ownedPackage':False}):
            with self.subTest(changed=changed):
                self.world.active=copy.deepcopy(baseline)
                self.obs['ack']={'id':command['id'],'status':'applied','movement':{
                    'id':command['id'],'adapter':'papyrus-mailbox','aliasesConfirmed':True,
                    'actor':99,'target':108149,'ownedPackage':True,**changed}}
                self.world.observe(self.obs);self.sync()
                self.assertEqual(self.world.conversation_status()['phase'],'releasing')
                self.assertNotIn('meeting_evidence',self.world.conversation_status())
                self.assertEqual(self.world.active['people']['99']['relationships'],{})


class AuthoredMeetingRouteTests(unittest.TestCase):
    setUp=test_conversation.ConversationTests.setUp
    tearDown=test_conversation.ConversationTests.tearDown
    sync=test_conversation.ConversationTests.sync

    def test_authored_meeting_has_no_receipt_bypass(self):
        self.world.start_scenario_conversation('chat',self.obs,test_conversation.authored_pair_scenario(108186,108149));self.sync()
        self.assertTrue(self.world.pending(self.obs['session'])['dynamic'])
        self.obs['ack']={'id':'meet-chat','status':'applied'}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.conversation_status()['phase'],'releasing')
        self.assertNotIn('meeting_evidence',self.world.conversation_status())

    def test_authored_meeting_requires_same_observed_executor(self):
        self.obs['routing']={'adapter':'papyrus-mailbox-v1','available':False}
        before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'mailbox capability'):
            self.world.start_scenario_conversation('chat',self.obs,test_conversation.authored_pair_scenario(108186,108149))
        self.assertEqual(self.world.active,before)


if __name__=='__main__':unittest.main()
