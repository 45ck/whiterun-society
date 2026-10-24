import unittest
import test_extended_conversation as fixtures

class ConversationInterruptTests(unittest.TestCase):
    setUp=fixtures.ExtendedConversationTests.setUp
    tearDown=fixtures.ExtendedConversationTests.tearDown
    sync=fixtures.ExtendedConversationTests.sync
    census=fixtures.ExtendedConversationTests.census
    review=fixtures.ExtendedConversationTests.review
    decide=fixtures.ExtendedConversationTests.decide
    meet=fixtures.ExtendedConversationTests.meet
    release=fixtures.ExtendedConversationTests.release
    begin=fixtures.ExtendedConversationTests.begin

    def test_interrupt_releases_participants_without_inventing_heard_turns(self):
        self.begin();self.world.interrupt_conversation(self.event['id'],self.obs);self.sync()
        c=self.world.conversation_status();self.assertEqual(c['phase'],'releasing');self.assertEqual(c['interruption']['stage'],'propose')
        self.assertTrue(self.world.hold_conversation(self.event['id'],'late model result rejected',self.obs)['duplicate'])
        self.release();c=self.world.conversation_status()
        self.assertEqual(c['phase'],'held');self.assertEqual(c['outcome'],'observer_interrupted');self.assertEqual(c['turns'],[])
        self.assertEqual(c['error'],'Observer interrupted conversation')
