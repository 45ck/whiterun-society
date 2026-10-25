import copy
import time
import unittest
from activity_metrics import activity_metrics
from observer import observer_state


def job(identifier='job-1', actor=7, slot=0, **extra):
    return dict(id=identifier, actor=actor, target=100 + actor, slot=slot,
                session='session', epoch='epoch', rest_minutes=30,
                phase='running', accepted_day=1, **extra)


class ActivityMetricsTests(unittest.TestCase):
    def setUp(self):
        self.saved = job()
        self.native = {**self.saved, 'job_id': 'job-1', 'phase': 'resting',
                       'rest': {'id': 'job-1', 'actor': 7, 'target': 107,
                                'rested_minutes': 10, 'seated_samples': 4}}
        self.society = {'activity_jobs': {'epoch': 'epoch', 'jobs': [self.saved], 'history': []},
                        'plan': {'id': 'foreground', 'actor': 9, 'phase': 'travelling'},
                        'people': {'7': {'profile': {'name': 'Resident'}}}}
        self.observation = {'session': 'session', 'activity_jobs': {'session': 'session',
            'epoch': 'epoch', 'available': True, 'capacity': 2, 'jobs': [self.native]}}

    def test_native_attendance_and_admission_are_not_completion(self):
        before = copy.deepcopy((self.society, self.observation))
        result = activity_metrics(self.society, self.observation)
        self.assertEqual((result['background_active'], result['foreground_active']), (1, 1))
        self.assertEqual(result['states']['resting'], 1)
        self.assertEqual(result['recorded_admissions'], 1)
        self.assertEqual(result['verified_completions'], 0)
        self.assertEqual(result['jobs'][0]['rested_minutes'], 10)
        self.native['phase'] = 'applied'
        self.assertEqual(activity_metrics(self.society, self.observation)['verified_completions'], 0)
        self.native['phase'] = 'resting'
        self.assertEqual(before, (self.society, self.observation))

    def test_saved_verified_completion_survives_missing_admission_ack_and_history_deduplicates(self):
        self.saved.update(phase='complete', accepted_day=None, outcome='rested_at_bench', release_verified=True)
        self.society['activity_jobs']['history'] = [copy.deepcopy(self.saved)]
        result = activity_metrics(self.society, self.observation)
        self.assertEqual((result['retained_jobs'], result['verified_completions']), (1, 1))
        self.assertEqual((result['recorded_admissions'], result['admission_unknown']), (0, 1))
        self.saved['release_verified'] = False
        self.assertEqual(activity_metrics(self.society, self.observation)['verified_completions'], 0)

    def test_session_epoch_identity_and_duplicate_rows_cannot_borrow_progress(self):
        for field, value in [('actor', 8), ('target', 108), ('slot', 1), ('session', 'old'), ('epoch', 'old'), ('job_id', 'old')]:
            with self.subTest(field=field):
                observation = copy.deepcopy(self.observation)
                observation['activity_jobs']['jobs'][0][field] = value
                result = activity_metrics(self.society, observation)
                self.assertEqual(result['native_matched_jobs'], 0)
                self.assertIsNone(result['background_active'])
                self.assertIsNone(result['jobs'][0]['rested_minutes'])
                self.assertEqual(result['states']['unmeasured'], 1)
        self.observation['activity_jobs']['jobs'].append(copy.deepcopy(self.native))
        self.assertEqual(activity_metrics(self.society, self.observation)['native_matched_jobs'], 0)

    def test_stale_and_missing_protocol_keep_unknowns(self):
        result = activity_metrics(self.society, self.observation, fresh=False)
        self.assertFalse(result['fresh']);self.assertIsNone(result['background_active'])
        self.assertIsNone(result['jobs'][0]['rested_minutes'])
        result = activity_metrics({}, {})
        self.assertIsNone(result['recorded_admissions']);self.assertIsNone(result['verified_completions'])
        self.assertIsNone(result['capacity'])

    def test_partial_coverage_retains_unmeasured_leases_beside_observed_activity(self):
        self.society['activity_jobs']['jobs'].append(job('job-2', actor=8, slot=1))
        result = activity_metrics(self.society, self.observation)
        self.assertEqual((result['background_active'], result['states']['unmeasured']), (1, 1))
        self.assertEqual((result['native_matched_jobs'], result['leased_jobs']), (1, 2))

    def test_orphan_quarantine_never_imports_admission_or_recovery_from_native_history(self):
        self.saved.update(orphan=True, phase='held', outcome='orphan_activity_held',
                          release_verified=True, recovery_applied=False)
        result = activity_metrics(self.society, self.observation)
        self.assertEqual((result['recorded_admissions'], result['admission_unknown'], result['verified_completions']), (0, 0, 0))
        self.assertEqual(result['retained_orphans'], 1);self.assertTrue(result['jobs'][0]['orphan'])
        self.saved.update(phase='complete', outcome='rested_at_bench')
        self.society['activity_jobs']['history'] = [self.saved]
        self.society['activity_jobs']['jobs'] = []
        self.assertEqual(activity_metrics(self.society, self.observation)['verified_completions'], 0)

    def test_releasing_held_and_rejected_admissions_stay_distinct(self):
        self.native['phase'] = 'releasing';self.saved.update(phase='held', error='Interrupted')
        self.society['plan']['phase'] = 'delegated'
        result = activity_metrics(self.society, self.observation)
        self.assertEqual(result['states']['releasing'], 1)
        self.assertEqual(result['retained_held'], 1)
        self.assertEqual(result['foreground_active'], 0)
        self.saved.update(accepted_day=None, no_effects_issued=True)
        result = activity_metrics(self.society, self.observation)
        self.assertEqual((result['recorded_admissions'], result['admission_unknown']), (0, 0))

    def test_progress_requires_matching_inner_rest_and_finite_nonboolean_minutes(self):
        for change in ({'id': 'other'}, {'actor': True}, {'target': 999}, {'rested_minutes': float('nan')}, {'rested_minutes': True}):
            observation = copy.deepcopy(self.observation)
            observation['activity_jobs']['jobs'][0]['rest'].update(change)
            self.assertIsNone(activity_metrics(self.society, observation)['jobs'][0]['rested_minutes'])

    def test_observer_marks_stale_native_jobs_and_projects_resident_without_internal_receipts(self):
        self.society['town'] = {'residents': {'7': {'name': 'Resident'}}}
        self.observation['residents'] = [{'id': 7, 'isPerson': True}]
        self.native['private_internal_receipt'] = {'secret': 'must not project'}
        result = observer_state({'last_seen': time.time(), 'observation': self.observation}, self.society)
        self.assertEqual(result['residents'][0]['activity_job']['native_phase'], 'resting')
        self.assertNotIn('private_internal_receipt', str(result['activity_jobs']))
        result = observer_state({'last_seen': 0, 'observation': self.observation}, self.society)
        self.assertFalse(result['dashboard']['activity_jobs']['fresh'])
        self.assertIsNone(result['dashboard']['activity_jobs']['background_active'])


if __name__ == '__main__':
    unittest.main()
