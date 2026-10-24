import unittest
import test_social as social_fixtures


class ExtendedConversationTests(unittest.TestCase):
    setUp=social_fixtures.SocialTests.setUp
    tearDown=social_fixtures.SocialTests.tearDown
    sync=social_fixtures.SocialTests.sync
    census=social_fixtures.SocialTests.census
    review=social_fixtures.SocialTests.review
    decide=social_fixtures.SocialTests.decide
    meet=social_fixtures.SocialTests.meet
    speak=social_fixtures.SocialTests.speak
    release=social_fixtures.SocialTests.release

    def begin(self):
        self.review();self.event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.world.start_conversation(self.event['id'],self.obs,99,max_turns=6);self.sync()
        self.meet();self.decide('chat')

    def test_each_listener_chooses_continuation_and_closing_stops_early(self):
        self.begin();self.speak()
        self.assertEqual(self.world.conversation_status()['phase'],'continue_dialogue')
        context=self.decide('reply');self.assertEqual(context['actor_id'],108149)
        self.assertEqual(len(context['heard']),1);self.assertNotIn('other_inventory',context)
        self.speak();context=self.decide('close_politely');self.assertEqual(context['actor_id'],99)
        c=self.world.conversation_status();self.assertEqual(self.world._speech_context(c,self.obs)['event']['dialogue_stage'],'closing')
        self.speak();self.assertEqual(self.world.conversation_status()['phase'],'releasing')
        self.release();self.decide('neutral');self.decide('neutral')
        c=self.world.conversation_status();self.assertEqual(c['phase'],'complete')
        self.assertEqual(c['end_reason'],'polite_closure');self.assertEqual(len(c['turns']),3)
        self.assertEqual([t['speaker'] for t in c['turns']],[99,108149,99])

    def test_quiet_departure_cannot_create_an_unheard_reply(self):
        self.begin();self.speak();self.decide('leave_quietly')
        c=self.world.conversation_status();self.assertEqual(c['phase'],'releasing')
        self.assertEqual(c['end_reason'],'left_quietly');self.assertEqual(len(c['turns']),1)
        self.assertNotIn('current',c)

    def test_six_turn_limit_is_hard_and_last_line_is_a_closing(self):
        self.begin()
        for index in range(6):
            c=self.world.conversation_status()
            if index==5:self.assertEqual(self.world._speech_context(c,self.obs)['event']['dialogue_stage'],'closing')
            self.speak()
            if index<5:self.decide('reply')
        c=self.world.conversation_status();self.assertEqual(c['phase'],'releasing')
        self.assertEqual(len(c['turns']),6);self.assertEqual(c['max_llm_calls'],6);self.assertEqual(c['max_jev_calls'],15)

    def test_invalid_limits_do_not_start_an_encounter(self):
        for limit in (True,1,7,'6'):
            with self.assertRaises(ValueError):self.world.start_conversation('bad',self.obs,max_turns=limit)
        self.assertIsNone(self.world.conversation_status())
