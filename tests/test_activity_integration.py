"""SQLite/checkpoint integration; authored receipts are not native-game proof."""
import copy
import unittest

import test_rest
from test_conversation import AUDIO, candidates_for
from activity_leases import reserved_activity_actors
from lineage import TimelineEconomy
from places import registered_venues


class ActivityIntegrationTests(unittest.TestCase):
    tearDown = test_rest.RestTests.tearDown
    sync = test_rest.RestTests.sync
    census = test_rest.RestTests.census
    review = test_rest.RestTests.review
    decide = test_rest.RestTests.decide

    def setUp(self):
        test_rest.RestTests.setUp(self)
        self.obs['activity_jobs'] = {'available': True, 'capacity': 2, 'receipts': []}
        self.obs['routing'] = {'adapter': 'papyrus-mailbox-v1', 'available': True}
        self.obs['rest']['sites'] = [
            {'id': seat, 'position': [200, 0, 0], 'loaded': True,
             'occupancy_known': True, 'occupied': False}
            for seat in list(registered_venues('rest_bench'))[:2]]
        for actor in (99, 108186, 108149):
            self.world.active['people'][str(actor)]['needs'].update(
                hunger=.2, fatigue=.9, social_contact=.1)
            self.obs['rest']['sensors'][str(actor)] = {
                'sit_available': True, 'furniture_reference_available': True,
                'sit_state': 0, 'furniture': 0}
        self.review()

    def delegate(self, actor=99):
        event = next(e for e in self.world.active['town']['daily']['queue']
                     if e['actor'] == actor and e['status'] == 'pending')
        self.world.begin_plan(event['id'], self.obs, actor, 'need_review'); self.sync()
        self.decide('rest_at_bench', event['id'])
        plan = self.world.agency_plan()
        self.assertEqual(plan['phase'], 'delegated')
        return copy.deepcopy(self.world.active['activity_jobs'][plan['activity_job']])

    def identity(self, job):
        return {'job_id': job['id'], **{key: job[key] for key in
                ('actor', 'target', 'slot', 'session', 'epoch')}}

    def accept(self, job):
        command = self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'], 'activity_start_rest')
        self.obs['ack'] = {**self.identity(job), 'id': command['id'],
                           'status': 'applied', 'accepted': True}
        self.world.observe(self.obs); self.sync()
        self.assertEqual(self.world.active['activity_jobs'][job['id']]['phase'], 'running')
        self.obs.pop('ack', None)

    def offer_receipt(self, job):
        self.obs['gameDays'] = max(self.obs['gameDays'], job['created_day'] + 30 / 1440)
        self.obs['activity_jobs']['receipts'] = [{**self.identity(job), 'status': 'applied',
            'rest': {'actor': job['actor'], 'target': job['target'], 'rested_minutes': 30,
                     'seated_samples': 8, 'exact_furniture_verified': True, 'release_verified': True}}]

    def begin_other(self, actor=108186):
        self.world.begin_plan('foreground', self.obs, actor, 'meal_time'); self.sync()

    def assert_receipt_deferred(self, job, kind):
        self.offer_receipt(job)
        before = self.world.marker
        command = self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'], kind)
        self.world.observe(self.obs)
        self.assertIsNone(self.world.transition)
        self.assertEqual(self.world.marker, before)
        self.assertEqual(self.world.pending(self.obs['session']), command)
        self.assertEqual(self.world.active['activity_jobs'][job['id']]['phase'], 'running')
        self.assertEqual(self.world.active['people']['99']['needs']['fatigue'], .9)

    def test_two_delegated_jobs_release_foreground_and_admit_disjoint_economic_plan(self):
        first = self.delegate(); self.accept(first)
        self.assertFalse(self.world.agency_busy())
        second = self.delegate(108186); self.accept(second)
        self.assertEqual({first['slot'], second['slot']}, {0, 1})
        self.assertFalse(self.world.agency_busy())
        self.assertEqual(reserved_activity_actors(self.world.active,include_identity=False), {99, 108186})
        self.begin_other(108149)
        self.assertTrue(self.world.agency_busy())
        self.decide('eat_bread', 'foreground')
        self.assertEqual(self.world.pending(self.obs['session'])['kind'], 'inventory_consume')
        self.assertEqual([j['phase'] for j in self.world.active['activity_jobs'].values()], ['running', 'running'])

    def test_lease_blocks_same_actor_but_original_event_is_idempotent(self):
        job = self.delegate(); self.accept(job)
        self.assertTrue(self.world.begin_plan(job['source_plan'], self.obs, 99, 'need_review')['duplicate'])
        with self.assertRaisesRegex(ValueError, 'activity lease'):
            self.world.begin_plan('overlap', self.obs, 99, 'meal_time')

    def test_receipt_settles_source_plan_once_preserving_newer_plan_and_survives_reopen(self):
        job = self.delegate(); self.accept(job); self.begin_other()
        foreground = copy.deepcopy(self.world.agency_plan())
        self.offer_receipt(job); self.world.observe(self.obs); self.sync()
        self.assertEqual(self.world.agency_plan(), foreground)
        source = next(p for p in self.world.active['plans'] if p['id'] == job['source_plan'])
        self.assertEqual(source['phase'], 'complete')
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['fatigue'], .5625)
        self.assertEqual(len(self.world.active['rests']), 1)
        state = copy.deepcopy(self.world.active)
        self.world.db.close()
        self.world = TimelineEconomy(self.temp.name + '/timeline.sqlite')
        self.world.observe(self.obs)
        self.assertEqual(self.world.active, state)
        self.world.observe(self.obs)
        self.assertIsNone(self.world.transition)
        self.assertEqual(len(self.world.active['rests']), 1)

    def test_receipt_does_not_preempt_pending_inventory_transaction(self):
        job = self.delegate(); self.accept(job); self.begin_other()
        self.decide('eat_bread', 'foreground')
        self.assert_receipt_deferred(job, 'inventory_consume')

    def test_rollback_quarantines_future_receipt_without_importing_rest_or_replaying_job(self):
        old = copy.deepcopy(self.obs)
        job = self.delegate(); self.accept(job); self.offer_receipt(job)
        receipt = copy.deepcopy(self.obs['activity_jobs']['receipts'])
        self.obs = {**old, 'session': 'loaded-older-save', 'activity_jobs': {
            'available': True, 'capacity': 2, 'receipts': receipt}}
        self.world.observe(self.obs); self.sync()
        self.assertEqual(self.world.active['people']['99']['needs']['fatigue'], .9)
        self.assertEqual(self.world.active.get('rests', []), [])
        self.assertFalse(any(p['id'] == job['source_plan'] for p in self.world.active.get('plans', [])))
        self.assertIn(99, reserved_activity_actors(self.world.active,include_identity=False))
        command = self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'], 'activity_ack_receipt')
        self.assertEqual(command['session'], 'loaded-older-save')
        self.assertEqual(command['job_session'], job['session'])
        self.obs['ack'] = {**self.identity(job), 'id': command['id'],
                           'status': 'applied', 'acknowledged': True}
        self.world.observe(self.obs); self.sync()
        # Saved execution lease is cleared; stale native receipts and absent
        # identity observations are separate admission exclusions.
        self.assertNotIn(99, reserved_activity_actors(self.world.active,include_identity=False))
        self.assertEqual(self.world.active.get('rests', []), [])
        self.assertIsNone(self.world.pending(self.obs['session']))

    def test_receipt_does_not_preempt_owned_travel(self):
        job = self.delegate(); self.accept(job)
        self.obs['residents'][0]['inventory']['bread'] = 0
        self.begin_other()
        self.decide('seek_bread', 'foreground')
        self.assert_receipt_deferred(job, 'walk_to')

    def conversation_choice(self, action):
        claim = self.world.claim_conversation('chat', self.obs)['claim']; self.sync()
        self.world.finish_conversation_inference('chat', claim['id'], {'model': 'authored-test',
            'decision': {'action_id': action, 'reason': 'Authored integration fixture', 'emotion': 'calm'}}, self.obs)
        self.sync()

    def start_disjoint_conversation(self):
        self.world.start_conversation('chat', self.obs, max_turns=2); self.sync()
        actor = self.world.conversation_status()['initiator']
        partner = 108149 if actor == 108186 else 108186
        self.conversation_choice('approach_' + str(partner))
        command = self.world.pending(self.obs['session'])
        self.obs['ack'] = {'id': command['id'], 'status': 'applied',
            'movement': {'id': command['id'], 'adapter': 'papyrus-mailbox', 'aliasesConfirmed': True,
                         'actor': actor, 'target': partner, 'ownedPackage': True}}
        self.world.observe(self.obs); self.sync(); self.obs.pop('ack', None)
        self.conversation_choice('chat')
        return [actor, partner]

    def test_receipt_does_not_preempt_conversation_attendance(self):
        job = self.delegate(); self.accept(job)
        actors = self.start_disjoint_conversation()
        self.assertNotIn(job['actor'], actors)
        self.assert_receipt_deferred(job, 'conversation_attend')

    def test_receipt_does_not_preempt_speech_playback(self):
        job = self.delegate(); self.accept(job); actors = self.start_disjoint_conversation()
        attendance = {'id': 'attend-chat', 'phase': 'attending', 'participants': [
            {'actor': actor, 'loaded': True, 'ownedPackage': True} for actor in actors]}
        self.obs['conversationAttendance'] = attendance
        self.obs['ack'] = {'id': 'attend-chat', 'status': 'applied', 'attendance': attendance}
        self.world.observe(self.obs); self.sync(); self.obs.pop('ack', None)
        claim = self.world.claim_conversation('chat', self.obs)['claim']; self.sync()
        self.world.finish_conversation_inference('chat', claim['id'], {'model': 'authored-test',
            'proposal': {'candidates': candidates_for(claim['context'])}}, self.obs); self.sync()
        self.conversation_choice('option_1')
        self.world.prepare_speech('chat', AUDIO, self.obs); self.sync()
        self.assert_receipt_deferred(job, 'speak')


if __name__ == '__main__':
    unittest.main()
