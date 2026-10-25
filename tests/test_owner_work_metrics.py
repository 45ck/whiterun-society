import copy
import time
import unittest

from owner_work_metrics import owner_work_metrics
from observer import observer_state


def identity():
    return dict(job_id='work-1', actor=7, actor_base_id=70, slot=0, session='session',
                epoch='epoch', business_id='business', business_revision=1,
                recipe_id='bread_recipe', policy_version='policy-v1', work_minutes=30)


class OwnerWorkMetricsTests(unittest.TestCase):
    def setUp(self):
        self.job = dict(identity(), id='work-1', phase='running', accepted_day=1)
        self.native = dict(identity(), phase='working', worked_minutes=10, samples=4)
        self.society = {'owner_work_jobs': {'epoch': 'epoch', 'capacity': 4, 'jobs': [self.job], 'history': []},
                        'people': {'7': {'profile': {'name': 'Resident'}}}}
        self.observation = {'session': 'session', 'owner_work_jobs': {'epoch': 'epoch',
            'available': True, 'capacity': 4, 'jobs': [self.native]}}

    def qualified(self):
        self.job.update(phase='attendance_verified', attendance_verified_day=1.1,
                        attendance_receipt_hash='receipt-digest', attendance={'token': 'private-capability',
                        'worked_minutes': 30, 'samples': 8})

    def committed(self):
        self.qualified()
        before = {'owner': {'gold': 11, 'grain': 4, 'bread': 0}}
        after = {'owner': {'gold': 11, 'grain': 3, 'bread': 2}}
        command = dict(identity(), id='commit-1', kind='inventory_self_produce_commit',
                       before=before, after=after, attendance_token='private-capability')
        ack = dict(identity(), id='commit-1', commit_id='commit-1', status='applied',
                   inventory=copy.deepcopy(after), effects_issued=True, committed_inventory_verified=True,
                   mechanism='native_owner_recipe', attendance_token='private-capability')
        record = {'id': 'commit-1', 'status': 'committed', 'command': command,
                  'evidence': {'session': 'session', 'actual': copy.deepcopy(after), 'ack': ack}}
        self.job.update(phase='recipe_committed', settlement={'phase': 'committed', 'commit_id': 'commit-1',
                        'production_record_id': 'commit-1', 'committed_inventory_verified': True})
        self.society['production'] = [record]
        return record

    def test_admission_and_attendance_are_not_goods(self):
        result = owner_work_metrics(self.society, self.observation)
        self.assertEqual((result['recorded_admissions'], result['observed_working']), (1, 1))
        self.assertEqual(result['configured_capacity'], 4)
        self.assertEqual((result['committed_jobs'], result['produced_goods']), (0, {}))
        self.assertEqual(result['jobs'][0]['worked_minutes'], 10)
        self.qualified()
        result = owner_work_metrics(self.society, self.observation)
        self.assertEqual((result['qualified_attendance'], result['awaiting_commit']), (1, 1))
        self.assertEqual(result['produced_goods'], {})
        self.assertNotIn('private-capability', str(result))

    def test_native_effects_without_committed_journal_do_not_count_goods(self):
        self.native.update(phase='recipe_committed', committed_inventory_verified=True)
        result = owner_work_metrics(self.society, self.observation)
        self.assertEqual(result['jobs'][0]['settlement_state'], 'effects_observed')
        self.assertEqual(result['committed_jobs'], 0)

    def test_release_request_is_not_verified_cleanup(self):
        self.committed()
        self.native.update(phase='recipe_committed', release_requested=True, release_verified=False)
        result = owner_work_metrics(self.society, self.observation)
        self.assertEqual(result['jobs'][0]['cleanup_state'], 'releasing')
        self.assertEqual((result['committed_jobs'], result['released_jobs']), (1, 0))

    def test_verified_output_is_independent_of_cleanup_and_deduplicated(self):
        record = self.committed()
        self.job.update(phase='held', error='Native release still pending')
        self.society['production'].append(copy.deepcopy(record))
        result = owner_work_metrics(self.society, self.observation)
        self.assertEqual(result['committed_jobs'], 1)
        self.assertEqual(result['produced_goods'], {'bread': 2})
        self.assertEqual(result['consumed_goods'], {'grain': 1})
        self.assertEqual(result['jobs'][0]['cleanup_state'], 'held')
        self.assertEqual(result['released_jobs'], 0)
        self.job.update(release_verified=True, receipt_acknowledged=True)
        self.society['owner_work_jobs'].update(jobs=[], history=[self.job])
        result = owner_work_metrics(self.society, self.observation, fresh=False)
        self.assertEqual((result['committed_jobs'], result['released_jobs']), (1, 1))
        self.assertEqual(result['jobs'], [])

    def test_identity_inventory_token_and_ledger_mismatches_cannot_credit_output(self):
        self.committed()
        mutations = [lambda s: s['production'][0].update(status='pending'),
            lambda s: s['production'][0]['command'].update(actor=8),
            lambda s: s['production'][0]['evidence']['ack'].update(attendance_token='other'),
            lambda s: s['production'][0]['evidence']['ack'].update(business_revision=2),
            lambda s: s['production'][0]['evidence']['actual']['owner'].update(bread=1),
            lambda s: s['production'][0]['command']['before']['owner'].update(gold=12),
            lambda s: s['production'][0]['evidence']['ack'].update(mechanism='simulated'),
            lambda s: s['production'][0]['evidence'].update(session='old'),
            lambda s: s['owner_work_jobs']['jobs'][0]['settlement'].update(production_record_id='other')]
        for mutate in mutations:
            society = copy.deepcopy(self.society);mutate(society)
            result = owner_work_metrics(society, self.observation)
            self.assertEqual((result['committed_jobs'], result['produced_goods']), (0, {}))
            self.assertEqual(result['invalid_commit_claims'], 1)
        conflict = copy.deepcopy(self.society['production'][0]);conflict['status'] = 'held'
        self.society['production'].append(conflict)
        self.assertEqual(owner_work_metrics(self.society, self.observation)['committed_jobs'], 0)

    def test_current_progress_requires_unique_full_native_identity_and_capacity(self):
        for key, value in [('actor', 8), ('actor_base_id', 71), ('slot', 1), ('job_id', 'old'),
                           ('session', 'old'), ('epoch', 'old'), ('business_id', 'other'),
                           ('business_revision', 2), ('recipe_id', 'other'), ('policy_version', 'other'),
                           ('work_minutes', 31)]:
            with self.subTest(key=key):
                observation = copy.deepcopy(self.observation)
                observation['owner_work_jobs']['jobs'][0][key] = value
                result = owner_work_metrics(self.society, observation)
                self.assertEqual(result['native_matched_jobs'], 0)
                self.assertIsNone(result['observed_working'])
                self.assertIsNone(result['jobs'][0]['worked_minutes'])
        self.observation['owner_work_jobs']['capacity'] = 2
        self.assertFalse(owner_work_metrics(self.society, self.observation)['fresh'])
        self.observation['owner_work_jobs']['capacity'] = 4
        self.observation['owner_work_jobs']['jobs'].append(copy.deepcopy(self.native))
        self.assertEqual(owner_work_metrics(self.society, self.observation)['native_matched_jobs'], 0)

    def test_partial_coverage_and_invalid_progress_are_explicit(self):
        self.society['owner_work_jobs']['jobs'].append(dict(self.job, id='work-2', job_id='work-2', actor=8, slot=1))
        result = owner_work_metrics(self.society, self.observation)
        self.assertEqual((result['observed_working'], result['unmeasured_jobs']), (1, 1))
        for value in (True, float('nan'), -1):
            self.native['worked_minutes'] = value
            self.assertIsNone(owner_work_metrics(self.society, self.observation)['jobs'][0]['worked_minutes'])

    def test_orphans_never_import_admission_attendance_or_goods(self):
        self.committed();self.job.update(orphan=True, phase='held', release_verified=True)
        result = owner_work_metrics(self.society, self.observation)
        self.assertEqual((result['recorded_admissions'], result['qualified_attendance'], result['committed_jobs']), (0, 0, 0))
        self.assertEqual(result['observed_working'], 0)
        self.assertTrue(result['jobs'][0]['orphan'])

    def test_missing_and_stale_protocol_and_observer_projection(self):
        self.assertIsNone(owner_work_metrics({}, {}))
        result = owner_work_metrics(self.society, self.observation, fresh=False)
        self.assertIsNone(result['observed_working'])
        self.assertIsNone(result['jobs'][0]['worked_minutes'])
        self.society['town'] = {'residents': {'7': {'name': 'Resident'}}}
        self.observation['residents'] = [{'id': 7, 'isPerson': True}]
        result = observer_state({'last_seen': time.time(), 'observation': self.observation}, self.society)
        self.assertEqual(result['residents'][0]['owner_work_job']['attendance_state'], 'working')
        result = observer_state({'last_seen': 0, 'observation': self.observation}, self.society)
        self.assertFalse(result['dashboard']['owner_work']['fresh'])
        self.assertIsNone(result['metrics']['owner_work']['observed_working'])


if __name__ == '__main__':unittest.main()
