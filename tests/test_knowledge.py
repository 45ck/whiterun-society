import copy
import json
import unittest

from knowledge import person_view, record_heard_identity
import test_conversation as conversation_fixtures
from test_conversation import CANDIDATES, AUDIO
import test_social as social_fixtures
from population import person_seed


class IdentityKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.state = {'people': {'7': {'profile': {'name': 'Nara'}}, '8': {'profile': {'name': 'Tovin'}}}}
        self.turn = {'speaker': 7, 'listener': 8, 'delivery_id': 'heard-1', 'delivered': True,
                     'selected': {'line': 'My name is Nara. How are you today?'}}

    def test_global_name_and_renaming_do_not_change_personal_knowledge(self):
        self.assertFalse(person_view(self.state, 8, 7)['name_known'])
        record_heard_identity(self.state, self.turn)
        self.state['people']['7']['profile']['name'] = 'New global name'
        view = person_view(self.state, 8, 7)
        self.assertEqual(view['name'], 'Nara')
        self.assertEqual(view['identity_source']['kind'], 'heard_self_introduction')
        self.assertFalse(person_view(self.state, 7, 8)['name_known'])

    def test_undelivered_or_quoted_introduction_teaches_no_name(self):
        record_heard_identity(self.state, {**self.turn, 'delivered': False})
        self.assertNotIn('known_people', self.state['people']['8'])
        for line in ['Someone said, My name is Nara.', 'Is your name Nara?', 'My name is Tovin.']:
            with self.subTest(line=line):
                record_heard_identity(self.state, {**self.turn, 'delivery_id': line, 'selected': {'line': line}})
                self.assertFalse(person_view(self.state, 8, 7)['name_known'])
        self.assertEqual(person_view(self.state, 8, 7)['name'], 'a familiar resident')

    def test_repeat_delivery_is_idempotent_and_projection_is_detached(self):
        record_heard_identity(self.state, self.turn)
        before = copy.deepcopy(self.state)
        record_heard_identity(self.state, self.turn)
        self.assertEqual(before, self.state)
        person_view(self.state, 8, 7)['identity_source']['event_id'] = 'tampered'
        self.assertEqual(before, self.state)


class DeliveredIdentityTests(unittest.TestCase):
    setUp = conversation_fixtures.ConversationTests.setUp
    tearDown = conversation_fixtures.ConversationTests.tearDown
    sync = conversation_fixtures.ConversationTests.sync
    start = conversation_fixtures.ConversationTests.start
    release = conversation_fixtures.ConversationTests.release
    delivered = conversation_fixtures.ConversationTests.delivered

    def prepare_introduction(self):
        self.start()
        claim = self.world.claim_conversation('chat', self.obs)['claim']; self.sync()
        self.assertFalse(claim['context']['listener']['name_known'])
        candidates = copy.deepcopy(CANDIDATES)
        candidates[0]['line'] = 'My name is Ysolda. It is good to meet you.'
        self.world.finish_conversation_inference('chat', claim['id'], {'model': 'fixture', 'proposal': {'candidates': candidates}}, self.obs); self.sync()
        claim = self.world.claim_conversation('chat', self.obs)['claim']; self.sync()
        self.world.finish_conversation_inference('chat', claim['id'], {'model': 'fixture', 'decision':
            {'action_id': 'option_1', 'reason': 'Introduce myself', 'emotion': 'calm'}}, self.obs); self.sync()
        self.world.prepare_speech('chat', AUDIO, self.obs); self.sync()
        return self.world.pending(self.obs['session'])

    def test_name_is_learned_after_hearing_and_removed_by_old_save(self):
        command = self.prepare_introduction()
        before_delivery = copy.deepcopy(self.obs)
        self.assertFalse(person_view(self.world.active, 108149, 108186)['name_known'])
        self.delivered(command)
        self.assertEqual(person_view(self.world.active, 108149, 108186)['name'], 'Ysolda')
        context = self.world.claim_conversation('chat', self.obs)['claim']['context']; self.sync()
        self.assertEqual(context['listener']['name'], 'Ysolda')
        self.world.observe({**before_delivery, 'session': 'before-introduction'})
        self.assertFalse(person_view(self.world.active, 108149, 108186)['name_known'])

    def test_failed_audio_cannot_teach_name(self):
        command = self.prepare_introduction()
        self.obs['speech'] = {'id': command['id'], 'status': 'failed', 'error': 'interrupted'}
        self.world.observe(self.obs); self.sync()
        self.assertFalse(person_view(self.world.active, 108149, 108186)['name_known'])


class DynamicSocialIdentityTests(unittest.TestCase):
    setUp = social_fixtures.SocialTests.setUp
    tearDown = social_fixtures.SocialTests.tearDown
    sync = social_fixtures.SocialTests.sync
    census = social_fixtures.SocialTests.census
    review = social_fixtures.SocialTests.review
    begin = social_fixtures.SocialTests.begin
    decide = social_fixtures.SocialTests.decide

    def test_recent_failed_attempt_does_not_monopolize_operator_opportunities(self):
        self.review()
        for person in self.world.active['people'].values():
            person['social_clock']=0;person['social_attempt_day']=10
        self.world.active['people']['108149']['social_attempt_day']=1
        self.world.start_conversation('fair-offer',self.obs);self.sync()
        self.assertEqual(self.world.conversation_status()['initiator'],108149)

    def test_operator_offer_uses_current_cast_but_does_not_require_conversation(self):
        before=copy.deepcopy(self.obs['residents'])
        self.world.start_conversation('offered-current-cast',self.obs);self.sync()
        c=self.world.conversation_status()
        self.assertEqual(c['phase'],'choose_partner')
        self.assertEqual(c['speakers'],[])
        self.assertIn('Operator offered',c['source'])
        claim=self.world.claim_conversation(c['id'],self.obs)['claim'];self.sync()
        self.world.finish_conversation_inference(c['id'],claim['id'],{'model':'test-jev',
            'decision':{'action_id':'defer','reason':'Prefer quiet','emotion':'calm'}},self.obs);self.sync()
        self.assertEqual(self.world.conversation_status()['phase'],'complete')
        self.assertEqual(self.world.conversation_status()['turns'],[])
        self.assertEqual(self.obs['residents'],before)
        self.assertTrue(self.world.start_conversation(c['id'],self.obs)['duplicate'])

    def test_new_people_with_no_legacy_cast_can_choose_and_meet(self):
        row = {'id': 501, 'name': 'Tovin the newcomer', 'isPerson': True, 'isGuard': False,
               'x': 250, 'y': 0, 'z': 0, 'inventory': {'gold': 9, 'bread': 1, 'grain': 0}}
        self.world.active['people']['501'] = person_seed(row, 'new-cast', self.obs['gameDays'])
        self.world.active['people'] = {k: v for k, v in self.world.active['people'].items() if k in ('99', '501')}
        town = self.world.active['town']
        town['residents'] = {'99': town['residents']['99'], '501': {'id': 501, 'name': row['name'], 'is_guard': False, 'observed_game_day': self.obs['gameDays']}}
        town['businesses'] = {}
        self.obs['residents'] = [r for r in self.obs['residents'] if r['id'] == 99] + [row]
        self.begin()
        context = self.decide('approach_501')
        self.assertNotIn('Tovin', json.dumps(context))
        self.assertFalse(context['nearby_candidates'][0]['name_known'])
        command = self.world.pending(self.obs['session'])
        self.assertEqual((command['actor'], command['target']), (99, 501))
        self.assertTrue(command['dynamic'])
        self.obs['ack'] = {'id': command['id'], 'status': 'applied',
                           'movement': {'actor': 99, 'target': 501, 'ownedPackage': True}}
        self.world.observe(self.obs); self.sync()
        response = self.decide('chat')
        self.assertEqual(response['actor_id'], 501)
        self.assertFalse(response['other']['name_known'])
        claim = self.world.claim_conversation(self.event['id'], self.obs)['claim']
        self.assertNotIn('Tovin', json.dumps(claim['context']))
