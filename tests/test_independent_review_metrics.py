"""Read-only metrics over real saved review transitions; native rows are fixtures."""
import copy
import json
import unittest

import test_independent_reviews as core
import test_owner_work_metrics as owner
from activity_plan_sources import activity_plan_hash
from independent_review_metrics import independent_review_metrics


class IndependentReviewMetricsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = core.IndependentReviewTests();self.fixture.setUp()
        self.world = self.fixture.world;self.obs = self.fixture.obs
        self.world.active['independent_reviews'] = {}

    def report(self, fresh=True):
        state = {**self.world.active, 'checkpoint': self.obs['checkpoint'], 'session': self.obs['session']}
        return independent_review_metrics(state, self.obs, fresh)

    def row(self):return next(row for row in self.report()['reviews'] if row['event_id'] == 'source-1')

    def accepted(self):
        wave = self.fixture.claim(1)
        self.fixture.finish(wave, {1: 'rest_' + str(self.fixture.seats[0])})
        return self.world.active['independent_reviews']['source-1']

    def delegated(self):
        self.accepted()
        self.assertTrue(self.world.prepare_independent_review_jobs(self.obs));self.world.bind(self.obs)
        self.assertTrue(self.world.observe_independent_reviews(self.obs));self.world.bind(self.obs)
        return next(iter(self.world.active['activity_jobs'].values()))

    def attending(self):
        job = self.delegated()
        row = {key: job[key] for key in ('actor', 'actor_base_id', 'target', 'slot', 'session', 'epoch')}
        row.update(job_id=job['id'], id=job['id'], phase='resting', rest={
            'id': job['id'], 'actor': job['actor'], 'target': job['target'],
            'exact_furniture_verified': True, 'seated_samples': 2, 'rested_minutes': 1})
        self.obs['activity_jobs'].update(session=job['session'], epoch=job['epoch'], jobs=[row])
        return job

    def completed(self):
        job = self.attending()
        receipt = {key: job[key] for key in ('actor', 'actor_base_id', 'target', 'slot', 'session', 'epoch')}
        receipt.update(job_id=job['id'], status='applied', rest={
            'actor': job['actor'], 'target': job['target'], 'rested_minutes': 30,
            'seated_samples': 8, 'release_verified': True, 'exact_furniture_verified': True})
        self.obs['activity_jobs'].update(receipts=[receipt], jobs=[])
        self.obs['gameDays'] += 30 / 1440
        self.assertTrue(self.world.observe_activity_jobs(self.obs));self.world.bind(self.obs)
        self.assertTrue(self.world.observe_independent_reviews(self.obs));self.world.bind(self.obs)
        return self.world.active['activity_jobs'][job['id']]

    def test_pending_is_waiting_not_a_claim_or_eligibility_count(self):
        result = self.report()
        self.assertEqual(result['counts']['waiting'], 2)
        row = result['reviews'][0]
        self.assertEqual(row['actor_name'], 'resident 1')
        self.assertIsNone(row['actor_base_id']);self.assertIsNone(row['inference_active'])
        self.assertEqual(result['coverage']['claims']['eligible'], 0)

    def test_missing_schema_is_unmeasured_not_zero_activity(self):
        result = independent_review_metrics({})
        self.assertFalse(result['measured']);self.assertTrue(all(v is None for v in result['counts'].values()))
        self.assertIsNone(result['coverage']['claims']['n'])
        self.assertIsNone(result['latency']['claim_to_result_seconds']['eligible'])

    def test_saved_claim_does_not_assert_a_running_model(self):
        self.fixture.claim(1)
        row = self.row()
        self.assertEqual(row['status'], 'claimed');self.assertIsNone(row['inference_active'])
        self.assertIsNone(row['stages']['accepted']);self.assertTrue(row['source_linked'])

    def test_accepted_and_delegated_are_not_native_attendance(self):
        self.accepted();self.assertEqual(self.row()['status'], 'accepted')
        self.world.prepare_independent_review_jobs(self.obs);self.world.bind(self.obs)
        self.world.observe_independent_reviews(self.obs);self.world.bind(self.obs)
        row = self.row()
        self.assertEqual(row['status'], 'delegated');self.assertTrue(row['stages']['accepted'])
        self.assertIsNone(row['stages']['native_attending']);self.assertFalse(row['stages']['settled'])

    def test_quiet_and_handoff_are_intentional_non_native_outcomes(self):
        wave = self.fixture.claim();self.fixture.finish(wave, {1: 'foreground_review'})
        rows = self.report()['reviews']
        self.assertEqual([r['status'] for r in rows], ['handoff', 'quiet'])
        self.assertTrue(all(r['native_required'] is False for r in rows))
        self.assertEqual(self.report()['counts']['held'], 0)

    def test_rejected_result_is_held_with_measured_result_clock(self):
        wave = self.fixture.claim(1)
        self.world.finish_independent_reviews(wave['id'], wave['claim_id'], [{'actor': 1, 'result': None}], self.obs)
        self.world.bind(self.obs)
        self.assertEqual(self.row()['status'], 'held');self.assertFalse(self.row()['stages']['accepted'])
        self.assertEqual(self.report()['latency']['claim_to_result_seconds']['n'], 1)

    def test_exact_native_rest_attendance_has_current_proof_only(self):
        self.attending()
        self.assertEqual(self.row()['status'], 'native_attending')
        self.assertFalse(self.row()['stages']['settled'])
        self.assertEqual(self.report(False)['counts']['native_attending'], 0)

    def test_paused_error_transition_or_stale_observation_hides_current_native_proof(self):
        self.attending()
        for field, value in [('paused', True), ('ready', False)]:
            with self.subTest(field=field):
                obs = {**self.obs, field: value}
                result = independent_review_metrics(self.world.active, obs, True)
                self.assertFalse(result['fresh']);self.assertIsNone(result['reviews'][0]['stages']['native_attending'])
        for field, value in [('error', 'held'), ('transition', {'next': 8}), ('session', 'other'), ('checkpoint', 999)]:
            with self.subTest(field=field):
                self.assertFalse(independent_review_metrics({**self.world.active, field: value}, self.obs, True)['fresh'])

    def test_replaced_base_wrong_epoch_and_duplicate_native_rows_are_unknown(self):
        self.attending()
        for change in ('base', 'epoch', 'duplicate', 'unqualified', 'session'):
            obs = copy.deepcopy(self.obs)
            if change == 'base':obs['residents'][0]['baseId'] = 999
            elif change == 'epoch':obs['activity_jobs']['epoch'] = 'other'
            elif change == 'duplicate':obs['activity_jobs']['jobs'] *= 2
            elif change == 'session':obs['session'] = 'loaded-session'
            else:obs['activity_jobs']['jobs'][0]['rest']['exact_furniture_verified'] = False
            result = independent_review_metrics(self.world.active, obs, True)
            self.assertIsNone(result['reviews'][0]['stages']['native_attending'], change)

    def test_real_rest_settlement_requires_committed_receipt_not_phase(self):
        job = self.completed()
        self.assertEqual(self.row()['status'], 'settled')
        self.assertEqual(self.report(False)['counts']['settled'], 1)
        self.world.active['rests'][0]['status'] = 'pending'
        self.assertIsNone(self.row()['stages']['settled'])
        self.assertEqual(job['phase'], 'complete')

    def test_receipt_tampering_or_missing_base_cannot_claim_settlement(self):
        self.completed()
        for change in ('amount', 'hash', 'base', 'release'):
            state = copy.deepcopy(self.world.active);record = state['rests'][0]
            if change == 'amount':record['evidence']['rest']['rested_minutes'] = 999
            elif change == 'hash':record['receipt_hash'] = 'other'
            elif change == 'base':record['evidence'].pop('actor_base_id')
            else:record['evidence']['rest']['release_verified'] = False
            self.assertIsNone(independent_review_metrics(state)['reviews'][0]['stages']['settled'], change)

    def test_public_projection_and_identical_replay_preserve_single_count(self):
        self.completed();expected = self.report(False)
        state = {**self.world.active, 'activity_jobs': self.world.activity_status()}
        state['activity_jobs']['history'] += copy.deepcopy(state['activity_jobs']['jobs'])
        state['rests'] += copy.deepcopy(state['rests'])
        self.assertEqual(independent_review_metrics(state)['counts'], expected['counts'])

    def test_conflicting_or_transplanted_source_plan_claim_or_job_is_not_credit(self):
        self.attending()
        for change in ('event', 'plan', 'claim', 'job', 'job_target', 'duplicate_member'):
            state = copy.deepcopy(self.world.active)
            if change == 'event':state['town']['daily']['queue'][0]['actor'] = 2
            elif change == 'plan':state['independent_plans']['source-1']['rest_target'] += 1
            elif change == 'claim':state['independent_review_waves'][0]['claim_id'] = 'other'
            elif change == 'job':next(iter(state['activity_jobs'].values()))['source_plan'] = 'other'
            elif change == 'job_target':next(iter(state['activity_jobs'].values()))['target'] += 1
            else:state['independent_review_waves'][0]['members'].append({'actor': 2, 'source_event': 'source-1'})
            row = independent_review_metrics(state, self.obs, True)['reviews'][0]
            self.assertNotIn(row['status'], ('native_attending', 'settled', 'delegated'), change)

    def test_latencies_have_explicit_missing_samples_and_reject_nonfinite_or_reverse_clocks(self):
        job = self.delegated();record = self.world.active['independent_reviews']['source-1']
        record.update(claimed_at=100, result_recorded_at=103, decided_at=103, decided_day=3)
        job.update(accepted_day=3 + 2 / 1440)
        latency = self.report()['latency']
        self.assertEqual(latency['claim_to_result_seconds']['mean'], 3)
        self.assertEqual(latency['result_to_native_admission_game_minutes']['mean'], 2)
        self.assertEqual(latency['result_to_native_admission_seconds']['unknown'], 1)
        for value in (float('nan'), float('inf'), -1, 99, True):
            record['result_recorded_at'] = value
            self.assertIsNone(self.report()['latency']['claim_to_result_seconds']['mean'])

    def test_missing_history_is_unknown_and_invalid_records_are_counted(self):
        self.accepted();self.world.active['independent_review_waves'] = []
        self.world.active['independent_reviews']['bad'] = {'secret': 'hidden'}
        result = self.report()
        self.assertEqual(result['invalid_records'], 1)
        self.assertEqual(result['coverage']['claims'], {'success': 0, 'n': 0, 'unknown': 1, 'eligible': 1})
        self.assertEqual(result['reviews'][0]['status'], 'unmeasured')

    def test_output_is_pure_and_never_exposes_private_decisions_or_capabilities(self):
        self.accepted();before = copy.deepcopy(self.world.active)
        result = self.report();json.dumps(result, allow_nan=False)
        self.assertEqual(self.world.active, before)
        for secret in ('memory of', 'A deliberate fixture choice', 'options', 'deadline_at', 'permit'):
            # Scope prose names permits, so inspect only the public row payload.
            self.assertNotIn(secret, json.dumps(result['reviews']))
        self.assertEqual(result['reviews'][0]['provenance'], 'controlled_fixture')


class IndependentOwnerMetricsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = owner.OwnerWorkMetricsTests();self.fixture.setUp()
        self.state = self.fixture.society;self.obs = self.fixture.observation
        self.job = self.fixture.job;self.job.update(source_plan='source-7')
        binding = {'schema_version': 1, 'actor': 7, 'base_id': 70, 'event_id': 'fixture'}
        self.state['people']['7']['identity_binding'] = binding
        self.state['town'] = {'residents': {'7': {'id': 7, 'identity_binding': binding}},
            'daily': {'queue': [{'id': 'source-7', 'actor': 7, 'independent_review': 'wave', 'status': 'delegated'}]}}
        review = {'event_id': 'source-7', 'actor': 7, 'actor_base_id': 70, 'session': 'session',
            'wave_id': 'wave', 'claim_id': 'claim', 'phase': 'delegated', 'accepted': True,
            'action_id': 'owner-choice', 'plan_id': 'source-7', 'job_id': 'work-1', 'job_kind': 'owner_production',
            'claimed_at': 1, 'decided_at': 2, 'decided_day': .9, 'model': 'fixture'}
        plan = {'id': 'source-7', 'actor': 7, 'actor_base_id': 70, 'session': 'session',
            'kind': 'independent_review', 'independent_review': {k: review[k] for k in ('event_id', 'wave_id', 'claim_id')},
            'phase': 'delegated', 'own_work_terms': {**{k: self.job[k] for k in ('business_id', 'recipe_id', 'catalog_hash', 'recipe_hash')},
                'revision': self.job['business_revision'], 'policy': {'work_minutes': self.job['work_minutes']}}, 'work_job': 'work-1'}
        review['plan_hash'] = activity_plan_hash(plan)
        self.state.update(independent_reviews={'source-7': review}, independent_plans={'source-7': plan},
            independent_review_waves=[{'id': 'wave', 'claim_id': 'claim', 'session': 'session',
                'members': [{'actor': 7, 'source_event': 'source-7'}], 'results': [{'actor': 7,
                    'source_event': 'source-7', 'accepted': True, 'decision': {'action_id': 'owner-choice'}}]}])
        self.obs.update(ready=True, checkpoint=1, residents=[{'id': 7, 'baseId': 70, 'isPerson': True}])
        self.obs['owner_work_jobs']['session'] = 'session'

    def report(self):return independent_review_metrics(self.state, self.obs, True)

    def test_owner_work_exact_native_attendance_is_not_output(self):
        row = self.report()['reviews'][0]
        self.assertEqual(row['status'], 'native_attending')
        self.assertFalse(row['stages']['settled'])

    def test_owner_committed_output_without_release_is_not_settled(self):
        self.fixture.committed()
        self.assertFalse(self.report()['reviews'][0]['stages']['settled'])
        self.job.update(phase='complete', release_verified=True, receipt_hash='fixture-receipt', outcome='owner_work_completed')
        self.assertEqual(self.report()['reviews'][0]['status'], 'settled')
        self.state['production'] *= 2
        self.assertEqual(self.report()['counts']['settled'], 1)

    def test_owner_phase_only_or_conflicting_ledger_cannot_credit(self):
        self.job.update(phase='complete', release_verified=True, receipt_hash='fixture-receipt', outcome='owner_work_completed')
        self.assertIsNone(self.report()['reviews'][0]['stages']['settled'])
        self.fixture.committed();self.job.update(phase='complete')
        conflict = copy.deepcopy(self.state['production'][0]);conflict['status'] = 'held'
        self.state['production'].append(conflict)
        self.assertIsNone(self.report()['reviews'][0]['stages']['settled'])

    def test_owner_projection_and_raw_state_are_equivalent(self):
        expected = self.report()
        state = {**self.state, 'work_jobs': {'work-1': self.job}}
        state.pop('owner_work_jobs')
        self.assertEqual(independent_review_metrics(state, self.obs, True), expected)

    def test_different_owner_recipe_or_business_is_not_the_accepted_choice(self):
        for key, value in [('recipe_id', 'other'), ('business_id', 'other'), ('business_revision', 99), ('work_minutes', 100)]:
            state = copy.deepcopy(self.state);state['owner_work_jobs']['jobs'][0][key] = value
            row = independent_review_metrics(state, self.obs, True)['reviews'][0]
            self.assertFalse(row['job_linked']);self.assertIsNone(row['stages']['native_attending'])


if __name__ == '__main__':unittest.main()
