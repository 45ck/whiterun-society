"""Accepted independent rest sources; authored receipts are not native proof."""
import copy
import unittest

import test_activity_jobs as fixtures
from activity_plan_sources import activity_plan_hash
from agency import Agency


class IndependentSavedJobs(fixtures.SavedJobs):
    _agency_guard = Agency._agency_guard

    def __init__(self, state):
        super().__init__(state)
        self.marker = 0
        self.cohort_busy = True

    def routines_busy(self):
        return self.cohort_busy


class IndependentRestAdmissionTests(unittest.TestCase):
    identity = fixtures.ActivityJobsTests.identity
    receipt = fixtures.ActivityJobsTests.receipt
    finish = fixtures.ActivityJobsTests.finish

    def setUp(self):
        fixtures.ActivityJobsTests.setUp(self)
        self.world = IndependentSavedJobs(self.world.active)
        self.world.active['plans'] = [
            {'id': 'foreground', 'actor': 2, 'target': 3, 'phase': 'consent', 'kind': 'meal_time'}]
        self.world.active['conversation'] = {
            'id': 'conversation', 'phase': 'speaking', 'initiator': 2, 'partner': 3, 'speakers': [2, 3]}

    def independent(self, actor=1, seat=None, event_id=None):
        event_id = event_id or 'independent-' + str(actor)
        plan = {'id': event_id, 'actor': actor, 'actor_base_id': 100 + actor,
                'session': self.world.session, 'kind': 'independent_review', 'phase': 'ready_to_rest',
                'rest_target': seat or self.seats[actor - 1],
                'independent_review': {'event_id': event_id, 'wave_id': 'wave', 'claim_id': 'claim-' + str(actor)}}
        self.world.active.setdefault('independent_plans', {})[event_id] = plan
        self.world.active.setdefault('independent_reviews', {})[event_id] = {
            'event_id': event_id, 'plan_id': event_id, 'actor': actor, 'actor_base_id': 100 + actor,
            'session': self.world.session, 'phase': 'accepted', 'accepted': True,
            'wave_id': 'wave', 'claim_id': 'claim-' + str(actor), 'plan_hash': activity_plan_hash(plan)}
        self.world.active['town']['daily']['queue'].append({
            'id': event_id, 'actor': actor, 'kind': 'need_review', 'status': 'started', 'independent_review': 'wave',
            'goal_followups': [{'goal_id': 'rest-goal-' + str(actor)}]})
        return plan

    def delegate(self, plan=None):
        result = self.world.delegate_rest(plan or self.independent(), self.obs)
        self.world.bind()
        return self.world.active['activity_jobs'][result['job_id']]

    def assert_rejected_unchanged(self, plan, pattern=None):
        before = copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError, pattern or '.'):
            self.world.delegate_rest(plan, self.obs)
        self.assertEqual(self.world.active, before)
        self.assertIsNone(self.world.transition)

    def test_disjoint_foreground_plan_and_conversation_do_not_serialize_accepted_rest(self):
        plan = self.independent()
        foreground = copy.deepcopy(self.world.active['plans'])
        conversation = copy.deepcopy(self.world.active['conversation'])
        job = self.delegate(plan)
        self.assertEqual(self.world.active['plans'], foreground)
        self.assertEqual(self.world.active['conversation'], conversation)
        self.assertEqual(self.world.active['independent_plans'][plan['id']]['phase'], 'delegated')
        self.assertEqual(job['source_plan'], plan['id'])
        self.assertEqual(job['actor_base_id'], 101)
        self.assertEqual(self.world.active['people']['1']['needs']['fatigue'], .9)

    def test_foreground_actor_target_and_conversation_participants_still_exclude_rest(self):
        for location in ('actor', 'target', 'initiator', 'partner', 'speakers'):
            with self.subTest(location=location):
                self.setUp()
                plan = self.independent()
                if location in ('actor', 'target'):
                    self.world.active['plans'][-1][location] = 1
                elif location == 'speakers':
                    self.world.active['conversation']['speakers'] = [1, 2]
                else:
                    self.world.active['conversation'][location] = 1
                self.assert_rejected_unchanged(plan, 'conflict')

    def test_forged_copied_mutated_or_unaccepted_independent_sources_cannot_delegate(self):
        for change in ('copy', 'target', 'record', 'event', 'duplicate'):
            with self.subTest(change=change):
                self.setUp()
                plan = self.independent()
                if change == 'copy':
                    plan = copy.deepcopy(plan)
                elif change == 'target':
                    plan['rest_target'] = self.seats[1]
                elif change == 'record':
                    self.world.active['independent_reviews'][plan['id']]['accepted'] = False
                elif change == 'event':
                    self.world.active['town']['daily']['queue'][0]['status'] = 'pending'
                else:
                    self.world.active['plans'].append(copy.deepcopy(plan))
                self.assert_rejected_unchanged(plan)

    def test_stale_session_or_base_review_is_not_rebound_to_current_actor(self):
        for key, value in (('session', 'old-session'), ('actor_base_id', 999)):
            with self.subTest(key=key):
                self.setUp()
                plan = self.independent()
                plan[key] = value
                record = self.world.active['independent_reviews'][plan['id']]
                record[key] = value
                record['plan_hash'] = activity_plan_hash(plan)
                self.assert_rejected_unchanged(plan, 'session or resident identity')

    def test_pending_global_effect_wrong_checkpoint_and_disabled_capability_remain_gates(self):
        for kind in ('pending', 'checkpoint', 'capability'):
            with self.subTest(kind=kind):
                self.setUp()
                plan = self.independent()
                if kind == 'pending':
                    self.world.active['pending'] = {'id': 'unsettled'}
                elif kind == 'checkpoint':
                    self.obs['checkpoint'] += 1
                else:
                    self.obs['activity_jobs']['available'] = False
                self.assert_rejected_unchanged(plan)

    def test_native_seat_and_slot_leases_remain_exclusive(self):
        plan = self.independent()
        self.obs['activity_jobs']['jobs'] = [{'actor': 2, 'target': plan['rest_target'], 'slot': 0}]
        self.assert_rejected_unchanged(plan, 'lease')
        self.obs['activity_jobs']['jobs'] = [{'actor': 2, 'target': self.seats[1], 'slot': 0}]
        job = self.delegate(plan)
        self.assertEqual(job['slot'], 1)

    def test_disjoint_accepted_sources_share_capacity_without_reusing_actor_or_slot(self):
        self.world.active['conversation'] = None
        self.world.active['plans'][-1].update(actor=3, target=3)
        first = self.delegate(self.independent(1))
        second = self.delegate(self.independent(2))
        self.assertEqual({first['slot'], second['slot']}, {0, 1})
        self.assertEqual([p['phase'] for p in self.world.active['independent_plans'].values()], ['delegated', 'delegated'])
        self.world.active['plans'][-1]['phase'] = 'complete'
        self.assert_rejected_unchanged(self.independent(3), 'capacity')

    def test_allowing_disjoint_routines_does_not_steal_a_routine_participant(self):
        plan = self.independent()
        self.world.active['routine_batches'] = [{'id': 'journey', 'phase': 'travelling', 'members': [{'actor': 1, 'phase': 'travelling'}]}]
        self.assert_rejected_unchanged(plan, 'conflict')

    def test_success_updates_only_independent_source_and_recovers_once(self):
        job = self.delegate()
        foreground = copy.deepcopy(self.world.active['plans'])
        self.finish(job)
        state = self.world.active
        self.assertEqual(state['independent_plans'][job['source_plan']]['phase'], 'complete')
        self.assertEqual(state['plans'], foreground)
        self.assertEqual(state['conversation']['phase'], 'speaking')
        self.assertAlmostEqual(state['people']['1']['needs']['fatigue'], .5625)
        self.assertEqual(state['town']['daily']['queue'][0]['status'], 'complete')
        self.assertFalse(self.world.observe_activity_jobs(self.obs))
        self.assertEqual(len(state['people']['1']['memories']), 1)

    def test_failed_receipt_holds_original_independent_source_without_recovery(self):
        job = self.delegate()
        foreground = copy.deepcopy(self.world.active['plans'])
        self.finish(job, self.receipt(job, release_verified=False))
        state = self.world.active
        self.assertEqual(state['independent_plans'][job['source_plan']]['phase'], 'held')
        self.assertEqual(state['plans'], foreground)
        self.assertEqual(state['people']['1']['needs']['fatigue'], .9)
        self.assertTrue(state['independent_plans'][job['source_plan']]['activity_release_required'])

    def test_original_foreground_route_keeps_routine_guard(self):
        self.world.active['conversation'] = None
        plan = {'id': 'foreground-rest', 'actor': 1, 'phase': 'ready_to_rest', 'rest_target': self.seats[0]}
        self.world.active['plans'].append(plan)
        self.assert_rejected_unchanged(plan, 'routine cohort')


if __name__ == '__main__':
    unittest.main()
