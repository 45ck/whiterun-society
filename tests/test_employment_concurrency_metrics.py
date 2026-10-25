"""Authored timestamped observations; no native gameplay qualification."""
import copy
import unittest

from employment_concurrency_metrics import EmploymentConcurrencyTelemetry, snapshot_metrics
from paid_employment import paid_identity
from paid_employment_metrics import paid_employment_metrics
import test_paid_employment_metrics as fixtures


class EmploymentConcurrencyMetricsTests(unittest.TestCase):
    def setUp(self):
        fixtures.PaidEmploymentProofMetricsTests.setUp(self)
        self.job['phase'] = 'working';self.job['effect_unreconciled'] = False
        self.state['paid_work_epoch'] = 'epoch'
        self.state['people'] = {};self.state['town'] = {'residents': {}}
        self.obs.update(checkpoint=5, gameDays=1, conversationAttendance=None,
                        routing={'adapter': 'papyrus-mailbox-v1', 'available': True})
        self.obs['residents'] = []
        for actor in (7, 8, 9):
            binding = {'schema_version': 1, 'actor': actor, 'base_id': actor * 10, 'event_id': 'fixture-census'}
            self.state['people'][str(actor)] = {'identity_binding': copy.deepcopy(binding), 'profile': {'name': 'Test resident'}}
            self.state['town']['residents'][str(actor)] = {'id': actor, 'identity_binding': copy.deepcopy(binding)}
            self.obs['residents'].append({'id': actor, 'baseId': actor * 10, 'isPerson': True,
                'isChild': False, 'isDead': False, 'loaded': True, 'x': actor * 10, 'y': 0, 'z': 0,
                'cell_id': 77, 'activity': {'package_id': 99 if actor == 7 else 123,
                    'in_combat': False, 'scene_id': 0, 'sleep_state': 0}})
        self.native = {**paid_identity(self.job), 'phase': 'working', 'attendance': {
            'slot': 0, 'serial': 1, 'expected_package': 99, 'cell_id': 77, 'anchor': [0, 0, 0],
            'samples': 2, 'worked_minutes': 0}}
        self.obs['paid_employment'].update(session='session', jobs=[self.native], receipts=[],
            reserved_actors=[7, 8], account_reserved_actors=[7, 8], activity_reserved_actors=[7])
        self.obs['resident_control'] = {'activities': [{'actor': 7, 'slot': 0, 'expectedPackage': 99,
            'work_hold_id': 'paid-work-job-1', 'goal_id': 'paid-work-job-1', 'mode': 'await_decision', 'target': 7}]}
        self.telemetry = EmploymentConcurrencyTelemetry()

    def sample(self, at=0):return self.telemetry.observe(self.state, self.obs, now=at)

    def advance(self, seconds=5, game_minutes=.5, move=20):
        self.obs['gameDays'] += game_minutes / 1440
        self.native['attendance']['worked_minutes'] += game_minutes
        self.native['attendance']['samples'] += 1
        self.obs['residents'][1]['x'] += move
        return self.sample(seconds)

    def conversation(self, identifier='chat-attend'):
        self.obs['conversationAttendance'] = {'id': identifier, 'phase': 'attending',
            'participants': [{'actor': actor, 'ownedPackage': True, 'loaded': True} for actor in (8, 9)]}

    def test_account_reservations_do_not_imply_employer_physical_restriction(self):
        result = snapshot_metrics(self.state, self.obs, fresh=True);row = result['jobs'][0]
        self.assertEqual(row['reservations'], {'worker_activity': True, 'worker_inventory': True,
                                             'employer_activity': False, 'employer_inventory': True})
        self.assertTrue(row['employer_non_economic_eligible'])
        self.assertEqual(result['counts']['paid_account_participants'], 2)
        self.assertEqual(result['counts']['paid_activity_reserved_participants'], 1)
        self.assertEqual(row['identity_digest'], paid_employment_metrics(self.state)['jobs'][0]['identity_digest'])

    def test_first_snapshot_is_not_observed_overlap_or_measured_zero(self):
        result = self.sample()
        for channel in result['overlap'].values():
            self.assertEqual(channel['n'], 0);self.assertIsNone(channel['sampled_overlap_seconds'])
        self.assertEqual(result['coverage']['candidate_job_intervals'], 0)
        self.assertEqual(result['coverage']['unpaired_initial_jobs'], 1)

    def test_movement_requires_two_exact_attendance_samples_and_displacement(self):
        self.sample();result = self.advance()
        movement = result['overlap']['employer_movement']
        self.assertEqual(movement['n'], 1);self.assertEqual(movement['positive_intervals'], 1)
        self.assertEqual(movement['sampled_overlap_seconds'], 5)
        self.assertEqual(movement['sampled_overlap_game_minutes'], .5)
        self.assertEqual(result['overlap']['employer_conversation']['sampled_overlap_seconds'], 0)

    def test_stationary_employer_is_measured_zero_movement_not_unknown(self):
        self.sample();result = self.advance(move=0)
        self.assertEqual(result['overlap']['employer_movement']['n'], 1)
        self.assertEqual(result['overlap']['employer_movement']['sampled_overlap_seconds'], 0)

    def test_owned_conversation_attendance_requires_same_identity_at_both_endpoints(self):
        self.conversation();self.sample();result = self.advance(move=0)
        channel = result['overlap']['employer_conversation']
        self.assertEqual(channel['n'], 1);self.assertEqual(channel['sampled_overlap_seconds'], 5)
        self.assertFalse(result['jobs'][0]['employer_non_economic_eligible'])
        self.assertEqual(result['jobs'][0]['employer_activity']['state'], 'conversation_attending')

    def test_different_conversations_do_not_fabricate_continuous_overlap(self):
        self.conversation();self.sample();self.conversation('another-chat')
        result = self.advance()
        self.assertIsNone(result['overlap']['employer_conversation']['sampled_overlap_seconds'])
        self.assertEqual(result['overlap']['employer_conversation']['unknown_intervals'], 1)

    def test_missing_conversation_telemetry_is_not_zero_conversation(self):
        self.obs.pop('conversationAttendance');self.sample();result = self.advance()
        self.assertEqual(result['overlap']['employer_conversation']['n'], 0)
        self.assertEqual(result['overlap']['employer_movement']['n'], 1)

    def test_changed_lease_serial_excludes_interval(self):
        self.sample();self.native['attendance']['serial'] += 1;result = self.advance()
        self.assertEqual(result['coverage']['excluded']['worker_lease_changed'], 1)
        self.assertEqual(result['coverage']['qualified_attendance_intervals'], 0)

    def test_no_attendance_progress_is_not_measured_simultaneous_activity(self):
        self.sample();result = self.advance(game_minutes=0)
        self.assertEqual(result['coverage']['qualified_attendance_intervals'], 0)
        self.assertIsNone(result['overlap']['employer_movement']['sampled_overlap_seconds'])

    def test_gap_and_teleport_are_excluded_instead_of_counted_as_activity(self):
        self.sample();result = self.advance(seconds=31)
        self.assertEqual(result['coverage']['excluded']['observation_gap'], 1)
        self.telemetry = EmploymentConcurrencyTelemetry();self.sample()
        result = self.advance(move=100000)
        self.assertEqual(result['overlap']['employer_movement']['n'], 0)
        self.assertEqual(result['overlap']['employer_movement']['unknown_intervals'], 1)

    def test_same_job_id_with_different_frozen_contract_cannot_pair(self):
        self.sample();self.job['business_revision'] += 1;self.native['business_revision'] += 1
        result = self.advance()
        self.assertEqual(result['coverage']['qualified_attendance_intervals'], 0)
        self.assertEqual(result['coverage']['excluded']['job_identity_not_paired'], 2)

    def test_replaced_or_unloaded_employer_has_unknown_activity_and_no_movement_credit(self):
        self.sample();self.obs['residents'][1]['baseId'] = 999
        result = self.advance()
        self.assertEqual(result['jobs'][0]['employer_activity']['state'], 'unmeasured')
        self.assertEqual(result['overlap']['employer_movement']['n'], 0)

    def test_worker_native_phase_without_exact_package_does_not_prove_attendance(self):
        self.sample();self.obs['residents'][0]['activity']['package_id'] = 500
        result = self.advance()
        self.assertFalse(result['jobs'][0]['worker_attendance_observed'])
        self.assertEqual(result['coverage']['qualified_attendance_intervals'], 0)

    def test_session_epoch_checkpoint_and_clock_rollback_reset_ephemeral_history(self):
        for change in ('session', 'epoch', 'checkpoint', 'clock'):
            with self.subTest(change=change):
                self.setUp();self.sample();self.advance()
                if change == 'session':self.obs['session'] = 'new-session'
                if change == 'epoch':self.obs['paid_employment']['epoch'] = 'new-epoch'
                if change == 'checkpoint':self.obs['checkpoint'] = 4
                result = self.sample(1 if change == 'clock' else 10)
                self.assertEqual(result['coverage']['qualified_attendance_intervals'], 0)
                self.assertEqual(result['samples'], 1)
                self.assertEqual(result['segment'], 2)

    def test_repeated_sample_cannot_double_count_and_stale_snapshot_masks_current_fields(self):
        self.sample();first = self.advance();second = self.sample(5)
        self.assertEqual(first['overlap'], second['overlap'])
        stale = self.telemetry.status('session', now=50)
        self.assertFalse(stale['fresh']);self.assertIsNone(stale['counts']['paid_account_participants'])
        self.assertIsNone(stale['jobs'][0]['reservations']['employer_inventory'])

    def test_other_activity_reservation_is_not_subtracted_when_employer_is_freed_from_paid_hold(self):
        self.state['activity_jobs'] = {'rest': {'actor': 8, 'target': 90, 'receipt_acknowledged': False}}
        result = snapshot_metrics(self.state, self.obs, fresh=True)
        self.assertTrue(result['jobs'][0]['reservations']['employer_activity'])
        self.assertFalse(result['jobs'][0]['employer_non_economic_eligible'])

    def test_snapshot_and_sampler_do_not_mutate_saved_state_or_expose_private_accounts(self):
        before = copy.deepcopy((self.state, self.obs));result = self.sample()
        self.assertEqual((self.state, self.obs), before)
        self.assertNotIn('before', str(result));self.assertNotIn('PRIVATE-NATIVE-PERMIT', str(result))
        result['jobs'][0]['reservations']['worker_inventory'] = False
        self.assertTrue(self.telemetry.status('session', now=0)['jobs'][0]['reservations']['worker_inventory'])

    def test_invalid_sampling_policy_and_clock_are_rejected(self):
        with self.assertRaises(ValueError):EmploymentConcurrencyTelemetry({'sample_seconds': 0})
        with self.assertRaises(ValueError):self.sample(float('nan'))

    def test_changed_attendance_participants_with_reused_id_are_not_the_same_conversation(self):
        self.conversation();self.sample()
        # Same native identifier alone cannot join a different observed pair.
        self.obs['conversationAttendance']['participants'][1]['actor'] = 7
        result = self.advance()
        self.assertEqual(result['overlap']['employer_conversation']['n'], 0)
        self.assertEqual(result['overlap']['employer_conversation']['unknown_intervals'], 1)

    def test_malformed_native_attendance_and_missing_session_do_not_crash_or_create_overlap(self):
        self.sample();self.native['attendance'] = 'unknown'
        self.obs['gameDays'] += .5 / 1440
        result = self.sample(5)
        self.assertEqual(result['coverage']['qualified_attendance_intervals'], 0)
        self.obs['paid_employment'].pop('session')
        result = self.sample(10)
        self.assertFalse(result['fresh'])
        self.assertIsNone(result['jobs'][0]['reservations']['employer_activity'])

    def test_rolloff_removes_old_intervals_without_pretending_lifetime_counts(self):
        self.sample();self.advance()
        status = self.telemetry.status('session', now=1000)
        self.assertEqual(status['samples'], 0)
        self.assertEqual(status['coverage']['qualified_attendance_intervals'], 0)
        self.assertIsNone(status['overlap']['employer_movement']['sampled_overlap_seconds'])

    def test_held_timeline_cannot_report_current_eligibility_or_sample_overlap(self):
        self.sample();self.state['error'] = 'Timeline execution held'
        snapshot = snapshot_metrics(self.state, self.obs, fresh=True)
        self.assertFalse(snapshot['fresh'])
        self.assertIsNone(snapshot['jobs'][0]['employer_non_economic_eligible'])
        self.assertEqual(snapshot['jobs'][0]['employer_activity']['state'], 'unmeasured')
        self.assertIsNone(snapshot['counts']['employers_non_economic_eligible'])
        result = self.advance()
        self.assertFalse(result['fresh'])
        self.assertEqual(result['coverage']['qualified_attendance_intervals'], 0)
        self.assertIsNone(result['overlap']['employer_movement']['sampled_overlap_seconds'])
