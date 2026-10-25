import copy
import unittest

from tools.verify_plan_save import compare_snapshot, require_settled_activities, snapshot


class SaveActivityTests(unittest.TestCase):
    def setUp(self):
        self.state = {'society': {'checkpoint': 1, 'plan': None, 'people': {},
                        'activity_jobs': {'epoch': 'epoch-a', 'capacity': 2, 'jobs': [], 'history': []}},
                      'world': [], 'bridge': {'observation': {'residents': [],
                        'activity_jobs': {'available': True, 'capacity': 2, 'jobs': [], 'receipts': []}}}}

    def test_snapshot_preserves_projection_epoch_and_terminal_history(self):
        job = {'id': 'done', 'phase': 'complete', 'release_verified': True, 'receipt_acknowledged': True,
               'receipt_hash': 'hash', 'epoch': 'epoch-a'}
        self.state['society']['activity_jobs']['history'].append(job)
        require_settled_activities(self.state)
        saved = snapshot(self.state)
        self.assertEqual(saved['activity_jobs'], self.state['society']['activity_jobs'])
        self.state['society']['activity_jobs']['history'][0]['receipt_hash'] = 'changed'
        self.assertEqual(saved['activity_jobs']['history'][0]['receipt_hash'], 'hash')
        self.assertFalse(compare_snapshot(saved, snapshot(self.state))['activity_jobs'])

    def test_owner_work_is_saved_separately_and_requires_cleanup(self):
        projection = {'epoch': 'work-epoch', 'capacity': 4, 'jobs': [], 'history': []}
        self.state['society']['owner_work_jobs'] = projection
        self.state['bridge']['observation']['owner_work_jobs'] = {'jobs': [], 'receipts': []}
        require_settled_activities(self.state)
        saved = snapshot(self.state)
        for phase in ('running', 'attendance_verified', 'recipe_committed', 'held'):
            projection['jobs'] = [{'phase': phase}]
            with self.assertRaisesRegex(ValueError, 'owner-work leases'):
                require_settled_activities(self.state)
        projection['jobs'] = []
        projection['history'] = [{'release_verified': True, 'receipt_acknowledged': False}]
        with self.assertRaisesRegex(ValueError, 'history'):
            require_settled_activities(self.state)
        projection['history'][0]['receipt_acknowledged'] = True
        require_settled_activities(self.state)
        self.assertFalse(compare_snapshot(saved, snapshot(self.state))['owner_work_jobs'])
        self.assertEqual(saved['owner_work_jobs']['history'], [])
        self.state['bridge']['observation']['owner_work_jobs']['receipts'] = [{'status': 'released'}]
        with self.assertRaisesRegex(ValueError, 'receipts'):
            require_settled_activities(self.state)

    def test_active_or_held_unacknowledged_jobs_block_the_probe(self):
        for phase in ('prepared', 'running', 'held', 'complete'):
            for source in ('society', 'native'):
                with self.subTest(phase=phase, source=source):
                    state = copy.deepcopy(self.state)
                    value = state['society']['activity_jobs'] if source == 'society' else state['bridge']['observation']['activity_jobs']
                    value['jobs'] = [{'phase': phase}]
                    with self.assertRaisesRegex(ValueError, 'leases'):
                        require_settled_activities(state)

    def test_native_terminal_receipts_must_also_be_acknowledged(self):
        self.state['bridge']['observation']['activity_jobs']['receipts'] = [{'phase': 'complete', 'release_verified': True}]
        with self.assertRaisesRegex(ValueError, 'receipts'):
            require_settled_activities(self.state)

    def test_history_requires_release_or_explicit_no_effect_proof(self):
        history = self.state['society']['activity_jobs']['history']
        for job in ({'receipt_acknowledged': False, 'release_verified': True},
                    {'receipt_acknowledged': True, 'release_verified': False}, None):
            history[:] = [job]
            with self.assertRaisesRegex(ValueError, 'history'):
                require_settled_activities(self.state)
        history[:] = [{'receipt_acknowledged': True, 'release_verified': False, 'no_effects_issued': True}]
        require_settled_activities(self.state)

    def test_old_proof_compares_only_its_recorded_fields(self):
        actual = snapshot(self.state)
        old = {key: copy.deepcopy(value) for key, value in actual.items() if key != 'activity_jobs'}
        self.assertTrue(all(compare_snapshot(old, actual).values()))
        actual['checkpoint'] += 1
        self.assertFalse(compare_snapshot(old, actual)['checkpoint'])
        self.assertFalse(compare_snapshot({'missing_expected_field': 1}, actual)['missing_expected_field'])

    def test_new_proof_detects_epoch_changes_even_when_no_jobs_are_live(self):
        expected = snapshot(self.state)
        self.state['society']['activity_jobs']['epoch'] = 'epoch-b'
        require_settled_activities(self.state)
        self.assertFalse(compare_snapshot(expected, snapshot(self.state))['activity_jobs'])

    def test_legacy_service_is_supported_but_invalid_projection_is_rejected(self):
        legacy = copy.deepcopy(self.state)
        legacy['society'].pop('activity_jobs'); legacy['bridge']['observation'].pop('activity_jobs')
        require_settled_activities(legacy)
        self.assertIsNone(snapshot(legacy)['activity_jobs'])
        for invalid in ([], {'jobs': {}}, {'jobs': [], 'history': {}}):
            self.state['society']['activity_jobs'] = invalid
            with self.assertRaises(ValueError): require_settled_activities(self.state)


if __name__ == '__main__': unittest.main()
