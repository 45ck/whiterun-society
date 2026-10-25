import copy
import unittest

from paid_employment_metrics import STAGES, _conversion, _latency, _stage_summary, _digest, paid_employment_metrics


def metric_row(**stages):
    return {'stages': {stage: stages.get(stage) for stage in STAGES}}


class PaidEmploymentAggregateTests(unittest.TestCase):
    def test_missing_instrumentation_is_not_a_zero_job_sample(self):
        self.assertEqual(_stage_summary([], 'accepted', False),
                         {'success': None, 'n': None, 'unknown': None, 'percent': None})
        self.assertEqual(_stage_summary([], 'accepted', True),
                         {'success': 0, 'n': 0, 'unknown': 0, 'percent': None})

    def test_unknown_outcomes_are_not_failed_jobs_or_assessed_samples(self):
        rows = [metric_row(wage_paid=True), metric_row(wage_paid=False), metric_row()]
        self.assertEqual(_stage_summary(rows, 'wage_paid', True),
                         {'success': 1, 'n': 2, 'unknown': 1, 'percent': 50})

    def test_incomplete_conversion_cannot_look_like_full_success(self):
        rows = [metric_row(accepted=True, completed=True), metric_row(accepted=True),
                metric_row(accepted=False, completed=False)]
        self.assertEqual(_conversion(rows, 'accepted', 'completed'),
                         {'success': 1, 'eligible': 2, 'n': 1, 'unknown': 1, 'percent': None})

    def test_empty_conversion_denominator_is_not_zero_or_perfect_percent(self):
        result = _conversion([metric_row(accepted=False)], 'accepted', 'completed')
        self.assertEqual(result['eligible'], 0)
        self.assertIsNone(result['percent'])

    def test_game_and_wall_time_are_distinct_with_missing_coverage(self):
        jobs = [{'accepted_day': 1, 'attendance_verified_day': 1.5,
                 'accepted_at': 10, 'attendance_verified_at': 40},
                {'accepted_day': 2, 'attendance_verified_day': 1.9}]
        rows = [metric_row(accepted=True, attendance_qualified=True) for _ in jobs]
        result = _latency(jobs, rows)
        self.assertEqual(result['native_admission_to_attendance_game_minutes'],
                         {'n': 1, 'eligible': 2, 'unknown': 1, 'mean': 720, 'median': 720, 'p95': 720})
        self.assertEqual(result['native_admission_to_attendance_wall_seconds']['mean'], 30)
        self.assertEqual(result['native_admission_to_attendance_wall_seconds']['unknown'], 1)

    def test_timestamps_alone_cannot_create_verified_attendance_latency(self):
        result = _latency([{'accepted_at': 1, 'attendance_verified_at': 2}], [metric_row()])
        self.assertEqual(result['native_admission_to_attendance_wall_seconds']['n'], 0)
        self.assertIsNone(result['native_admission_to_attendance_wall_seconds']['mean'])

    def test_bad_clock_numbers_do_not_count_as_measured_zero(self):
        for bad in (True, -1, float('nan'), float('inf'), '3'):
            with self.subTest(value=bad):
                result = _latency([{'accepted_at': 0, 'completed_at': bad}],
                                  [metric_row(accepted=True, completed=True)])
                sample = result['native_admission_to_completion_wall_seconds']
                self.assertEqual((sample['n'], sample['unknown']), (0, 1))
                self.assertIsNone(sample['mean'])

    def test_zero_elapsed_time_is_a_valid_measured_sample(self):
        jobs = [{'accepted_at': 0, 'completed_at': 0}]
        before = copy.deepcopy(jobs)
        result = _latency(jobs, [metric_row(accepted=True, completed=True)])
        self.assertEqual(result['native_admission_to_completion_wall_seconds']['mean'], 0)
        self.assertEqual(jobs, before)


class PaidEmploymentProofMetricsTests(unittest.TestCase):
    """Authored receipts checked by real service validators; no game evidence."""
    def setUp(self):
        from economy_catalog import catalog_hash, recipe_hash
        from employment import work_terms_hash
        self.terms = {'protocol': 2, 'worker': 7, 'worker_base_id': 70, 'employer': 8,
            'employer_base_id': 80, 'business_id': 'shop', 'revision': 1,
            'recipe_id': 'bread_recipe', 'catalog_hash': catalog_hash(),
            'recipe_hash': recipe_hash('bread_recipe'), 'currency': 'gold',
            'policy': {'wage_gold': 2, 'work_minutes': 30}}
        self.terms['terms_hash'] = work_terms_hash(self.terms)
        consent = {'protocol': 2, 'plan_id': 'offer', 'session': 'session',
            'worker': 7, 'employer': 8, 'terms_hash': self.terms['terms_hash'],
            'offer_claim_id': 'employer-choice', 'acceptance_claim_id': 'worker-choice'}
        self.job = {'id': 'job-1', 'job_id': 'job-1', 'protocol': 2, 'worker': 7, 'worker_base_id': 70,
            'employer': 8, 'employer_base_id': 80, 'slot': 0, 'session': 'session', 'epoch': 'epoch',
            'business_id': 'shop', 'business_revision': 1, 'recipe_id': 'bread_recipe',
            'catalog_hash': catalog_hash(), 'recipe_hash': recipe_hash('bread_recipe'),
            'terms_hash': self.terms['terms_hash'], 'consent_hash': _digest(consent),
            'work_minutes': 30, 'wage_gold': 2, 'currency': 'gold', 'expected_package': 99,
            'anchor': [0, 0, 0], 'cell_id': 77, 'source_plan': 'offer',
            'terms': copy.deepcopy(self.terms), 'consent': consent, 'phase': 'prepared',
            'created_day': 1, 'created_at': 50, 'accepted_day': 1, 'accepted_at': 55,
            'before': {'worker': {'gold': 1, 'bread': 0, 'grain': 0},
                       'employer': {'gold': 10, 'bread': 1, 'grain': 3}},
            'after': {'worker': {'gold': 3, 'bread': 0, 'grain': 0},
                      'employer': {'gold': 8, 'bread': 3, 'grain': 2}}, 'settlement': {}}
        plan = {'id': 'offer', 'actor': 7, 'target': 8, 'decisions': [], 'work_terms': copy.deepcopy(self.terms)}
        for actor, action, claim in ((8, 'offer_shift', 'employer-choice'), (7, 'take_shift', 'worker-choice')):
            plan['decisions'].append({'actor_id': actor, 'claim_id': claim,
                'decision': {'action_id': action}, 'model': 'explicit-metrics-unit-fixture',
                'context': {'actor_id': actor, 'session': 'session', 'event': {'id': 'offer'}, 'terms_hash': self.terms['terms_hash'],
                            'work_terms': copy.deepcopy(self.terms), 'options': [{'id': action}]}})
        self.state = {'paid_work_jobs': {'job-1': self.job}, 'plans': [plan], 'production': []}
        self.obs = {'session': 'session', 'ready': True,
                    'paid_employment': {'available': True, 'protocol': 2, 'epoch': 'epoch'}}

    def result(self):return paid_employment_metrics(self.state, self.obs, fresh=True)

    def voiced(self):
        plan = self.state['plans'][0];plan['voiced_trade'] = True;plan['economic_turns'] = []
        for act, speaker, listener, key in (('work_offer', 8, 7, 'offer_delivery_id'),
                                            ('work_accept', 7, 8, 'acceptance_delivery_id')):
            delivery = act + '-audio';self.job['consent'][key] = delivery
            plan['economic_turns'].append({'act': act, 'actor': speaker, 'listener': listener,
                'delivery_id': delivery, 'delivered': True, 'origin_session': 'session',
                'terms_hash': self.terms['terms_hash'], 'audio': {'seconds': 2},
                'playback': {'id': delivery, 'status': 'ended', 'nearbyThroughout': True, 'playedSeconds': 2}})
        self.job['consent_hash'] = _digest(self.job['consent'])

    def attendance(self):
        from paid_employment import paid_identity
        attendance = {'token': 'PRIVATE-NATIVE-PERMIT', 'slot': 0, 'serial': 2,
            'expected_package': 99, 'cell_id': 77, 'anchor': [0, 0, 0],
            'samples': 3, 'worked_minutes': 30, 'ready_at': 90000, 'expires_at': 200000}
        receipt = {**paid_identity(self.job), 'phase': 'attendance_verified',
                   'effects_issued': False, 'attendance': attendance}
        self.job.update(attendance=copy.deepcopy(attendance), attendance_receipt=receipt,
            attendance_receipt_hash=_digest(receipt), attendance_verified_day=1.1,
            attendance_verified_at=100, phase='attendance_verified')

    def effects(self, count=4, ledger=True):
        from paid_employment import paid_identity, paid_stages
        self.attendance()
        command = {**paid_identity(self.job), 'id': 'commit-1', 'commit_id': 'commit-1',
                   'kind': 'inventory_paid_work_commit', 'attendance_token': 'PRIVATE-NATIVE-PERMIT'}
        legs = [{**leg, 'issued': index < count, 'observed': index < count,
                 **({'issued_at': 100000 + index} if index < count else {})}
                for index, leg in enumerate(paid_stages(command))]
        actual = copy.deepcopy(legs[count - 1]['after'] if count else command['before'])
        receipt = {**paid_identity(self.job), 'id': command['id'], 'commit_id': command['id'],
            'status': 'applied' if count == 4 else 'held', 'phase': 'effects_verified' if count == 4 else 'held',
            'attendance_token': command['attendance_token'], 'effects_issued': count > 0,
            'effects_verified': count == 4, 'output_verified': count >= 2,
            'wage_debit_verified': count >= 3, 'wages_verified': count == 4,
            'legs': legs, 'inventory': actual}
        self.job.update(commit_command=command, effect_receipt=receipt, effect_receipt_hash=_digest(receipt),
                        effect_actual=actual, phase='effects_verified' if count == 4 else 'held')
        self.job['settlement'] = {'commit_id': command['id']}
        if count >= 2:self.job.update(output_verified_at=101, output_verified_day=1.11)
        if count == 4:self.job.update(wages_verified_at=104, wages_verified_day=1.12)
        if ledger:
            self.job['settlement'].update(phase='committed', production_record_id=command['id'])
            self.state['production'] = [{'id': command['id'], 'paid_work_job': self.job['id'], 'status': 'committed',
                'command': copy.deepcopy(command), 'evidence': {'actual': copy.deepcopy(actual),
                    'ack': copy.deepcopy(receipt), 'session': 'session'}}]

    def complete(self):
        self.effects()
        receipt = {**copy.deepcopy(self.job['effect_receipt']), 'phase': 'complete', 'release_verified': True}
        self.job.update(receipt=receipt, receipt_hash=_digest(receipt), phase='complete',
                        release_verified=True, release_verified_day=1.2, release_verified_at=110,
                        completed_day=1.2, completed_at=110)

    def test_offers_and_acceptance_do_not_imply_attendance_output_or_wages(self):
        result = self.result();stages = result['jobs'][0]['stages']
        self.assertTrue(stages['offered']);self.assertTrue(stages['accepted'])
        self.assertIsNone(stages['attendance_qualified']);self.assertIsNone(stages['output_verified'])
        self.assertIsNone(stages['wage_paid']);self.assertFalse(stages['completed'])
        self.assertIsNone(result['eligibility']['n'])

    def test_missing_schema_empty_schema_and_unknown_capability_are_distinct(self):
        missing = paid_employment_metrics({})
        self.assertFalse(missing['measured']);self.assertIsNone(missing['stages']['completed']['success'])
        self.assertIsNone(missing['committed_wage_gold'])
        empty = paid_employment_metrics({'paid_work_jobs': {}}, {}, fresh=True)
        self.assertTrue(empty['measured']);self.assertEqual(empty['retained_jobs'], 0)
        self.assertIsNone(empty['capability']['available'])

    def test_full_verified_completion_is_deduplicated_and_private_proofs_are_omitted(self):
        self.complete();self.state['production'].append(copy.deepcopy(self.state['production'][0]))
        result = self.result()
        for stage in STAGES[:-1]:self.assertEqual(result['stages'][stage]['success'], 1, stage)
        self.assertEqual(result['committed_output_goods'], {'bread': 2})
        self.assertEqual(result['committed_wage_gold'], 2)
        self.assertNotIn('PRIVATE-NATIVE-PERMIT', str(result))
        self.assertNotIn('employer-choice', str(result))

    def test_partial_output_and_employer_debit_are_not_paid_wages_or_committed_goods(self):
        self.effects(3, ledger=False);result = self.result();stages = result['jobs'][0]['stages']
        self.assertTrue(stages['output_verified']);self.assertFalse(stages['wage_paid'])
        self.assertTrue(result['jobs'][0]['wage_debit_verified'])
        self.assertEqual(result['partial_effects']['observed_output_goods'], {'bread': 2})
        self.assertEqual(result['partial_effects']['wage_debit_without_verified_credit'], 1)
        self.assertEqual(result['committed_output_goods'], {});self.assertEqual(result['committed_wage_gold'], 0)
        self.assertFalse(stages['completed'])

    def test_verified_effects_without_release_are_not_contract_completion(self):
        self.effects();result = self.result()
        self.assertTrue(result['jobs'][0]['stages']['wage_paid'])
        self.assertFalse(result['jobs'][0]['stages']['completed'])
        self.assertIsNone(result['jobs'][0]['stages']['released'])

    def test_ledger_missing_or_conflicting_never_credits_committed_output(self):
        self.complete();record = self.state['production'][0]
        self.state['production'] = [];self.assertEqual(self.result()['committed_output_goods'], {})
        self.state['production'] = [record, {**copy.deepcopy(record), 'status': 'held'}]
        self.assertEqual(self.result()['committed_output_goods'], {})

    def test_changed_receipt_hash_identity_or_actual_balances_remove_proof(self):
        self.complete();original = copy.deepcopy(self.state)
        mutations = [lambda job: job.update(effect_receipt_hash='wrong'),
            lambda job: job['effect_actual']['worker'].update(gold=9),
            lambda job: job['effect_receipt'].update(worker_base_id=999),
            lambda job: job['commit_command'].update(attendance_token='another-token')]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.state = copy.deepcopy(original);mutate(self.state['paid_work_jobs']['job-1'])
                result = self.result()
                self.assertIsNone(result['jobs'][0]['stages']['wage_paid'])
                self.assertEqual(result['committed_wage_gold'], 0)

    def test_phase_flags_and_after_balances_without_receipts_do_not_count(self):
        self.job.update(phase='complete', completed_day=2, release_verified=True,
                        settlement={'output_verified': True, 'wages_verified': True})
        result = self.result()
        self.assertEqual(result['stages']['completed']['success'], 0)
        self.assertIsNone(result['jobs'][0]['stages']['wage_paid'])

    def test_conflicting_public_job_copies_are_one_unknown_lineage(self):
        self.complete();other = copy.deepcopy(self.job);other['worker_base_id'] = 999
        self.state.pop('paid_work_jobs')
        self.state['paid_employment'] = {'jobs': [self.job], 'history': [other]}
        result = self.result()
        self.assertEqual(result['retained_jobs'], 1);self.assertEqual(result['conflicting_job_lineages'], 1)
        self.assertIsNone(result['jobs'][0]['stages']['completed'])

    def test_replayed_public_job_copies_count_once(self):
        self.complete();self.state.pop('paid_work_jobs')
        self.state['paid_employment'] = {'jobs': [self.job], 'history': [copy.deepcopy(self.job)]}
        result = self.result()
        self.assertEqual(result['retained_jobs'], 1);self.assertEqual(result['duplicate_rows_excluded'], 1)
        self.assertEqual(result['committed_wage_gold'], 2)

    def test_missing_or_reused_claims_are_not_verified_human_choices(self):
        self.complete();self.state['plans'][0]['decisions'][0]['claim_id'] = 'worker-choice'
        result = self.result()
        self.assertIsNone(result['jobs'][0]['stages']['accepted'])
        self.assertFalse(result['jobs'][0]['stages']['completed'])

    def test_cashflow_requires_full_committed_receipts_not_pending_or_partial_wages(self):
        from agency_metrics import account_cashflow
        self.complete();result = account_cashflow(self.state)
        rows = {row['actor']: row for row in result['accounts']}
        self.assertEqual(rows[7]['wages_received'], 2);self.assertEqual(rows[8]['wages_paid'], 2)
        self.assertEqual(rows[8]['production_events'], 1);self.assertIsNone(result['profit'])
        self.state['production'][0]['status'] = 'pending'
        self.assertEqual(account_cashflow(self.state)['accounts'], [])
        self.effects(3, ledger=True)
        self.assertEqual(account_cashflow(self.state)['accounts'], [])

    def test_cashflow_missing_attendance_is_not_a_fully_verified_paid_record(self):
        from agency_metrics import account_cashflow
        self.complete();self.job.pop('attendance_receipt')
        result = account_cashflow(self.state)
        self.assertEqual(result['accounts'], [])
        self.assertEqual(result['rejected_records']['unverified_paid_employment_cash_leg'], 1)

    def test_missing_actual_account_observation_cannot_credit_receipt_only_effects(self):
        self.complete();self.job.pop('effect_actual')
        self.state['production'][0]['evidence']['actual'] = None
        result = self.result()
        self.assertIsNone(result['jobs'][0]['stages']['wage_paid'])
        self.assertEqual(result['committed_wage_gold'], 0)

    def test_released_terminal_without_economic_proofs_is_not_completion(self):
        self.complete();self.job['receipt']['legs'] = []
        self.job['receipt_hash'] = _digest(self.job['receipt'])
        result = self.result()
        self.assertTrue(result['jobs'][0]['stages']['released'])
        self.assertFalse(result['jobs'][0]['stages']['completed'])
        self.assertEqual(result['committed_wage_gold'], 2)

    def test_stale_epoch_and_malformed_native_capability_remain_unknown(self):
        self.state['paid_work_epoch'] = 'different'
        self.assertIsNone(self.result()['capability']['available'])
        self.state.pop('paid_work_epoch')
        for value in ({}, {'available': False, 'protocol': 1},
                      {'available': 'yes', 'protocol': 2, 'epoch': 'epoch'}):
            self.obs['paid_employment'] = value
            self.assertIsNone(self.result()['capability']['available'])

    def test_fixture_provenance_does_not_become_autonomous_economic_evidence(self):
        self.complete();result = self.result()
        self.assertEqual(result['provenance_counts'], {'controlled_fixture': 1})
        self.assertEqual(result['jobs'][0]['provenance'], 'controlled_fixture')
        self.assertNotIn('realism_score', result)

    def test_protocol_one_or_unrelated_command_cannot_use_paid_cashflow_validator(self):
        from agency_metrics import account_cashflow
        self.complete();original = copy.deepcopy(self.state)
        for change in ('protocol', 'kind'):
            self.state = copy.deepcopy(original);job = self.state['paid_work_jobs']['job-1']
            if change == 'protocol':job['protocol'] = 1
            else:job['commit_command']['kind'] = 'inventory_trade'
            result = account_cashflow(self.state)
            self.assertEqual(result['accounts'], [])

    def test_transplanted_claim_event_is_not_historical_consent(self):
        self.complete()
        self.state['plans'][0]['decisions'][0]['context']['event']['id'] = 'another-plan'
        result = self.result()
        self.assertIsNone(result['jobs'][0]['stages']['accepted'])
        self.assertFalse(result['jobs'][0]['stages']['completed'])

    def test_incomplete_missing_or_invalid_playback_cannot_count_historical_consent(self):
        self.voiced();self.complete();baseline = copy.deepcopy(self.state)
        self.assertTrue(self.result()['jobs'][0]['stages']['completed'])
        for duration, elapsed in ((2, .1), (None, 2), (0, 2), (2, None), (2, True), (float('nan'), 2)):
            with self.subTest(duration=duration, elapsed=elapsed):
                self.state = copy.deepcopy(baseline)
                turn = self.state['plans'][0]['economic_turns'][1]
                turn['audio']['seconds'] = duration;turn['playback']['playedSeconds'] = elapsed
                result = self.result()
                self.assertIsNone(result['jobs'][0]['stages']['accepted'])
                self.assertFalse(result['jobs'][0]['stages']['completed'])

    def test_reused_delivery_id_or_duplicate_offer_cannot_count_historical_consent(self):
        self.voiced()
        turns = self.state['plans'][0]['economic_turns']
        turns[1]['delivery_id'] = turns[0]['delivery_id'];turns[1]['playback']['id'] = turns[0]['delivery_id']
        self.job['consent']['acceptance_delivery_id'] = turns[0]['delivery_id']
        self.job['consent_hash'] = _digest(self.job['consent']);self.complete()
        self.assertIsNone(self.result()['jobs'][0]['stages']['accepted'])
        self.setUp();self.complete()
        duplicate = copy.deepcopy(self.state['plans'][0]['decisions'][0]);duplicate['claim_id'] = 'another-offer'
        self.state['plans'][0]['decisions'].insert(1, duplicate)
        self.assertIsNone(self.result()['jobs'][0]['stages']['accepted'])

    def test_exact_retained_native_journal_counts_without_fabricating_ack_fields(self):
        from agency_metrics import account_cashflow
        self.complete();receipt = self.job['effect_receipt']
        receipt.pop('id');receipt.pop('status');self.job['effect_receipt_hash'] = _digest(receipt)
        evidence = self.state['production'][0]['evidence']
        evidence.update(ack=copy.deepcopy(receipt), receipt_source='retained_native_journal')
        before = copy.deepcopy(self.state);result = self.result()
        self.assertEqual(result['committed_wage_gold'], 2)
        self.assertEqual(account_cashflow(self.state)['accounts'][0]['wages_received'], 2)
        self.assertEqual(before, self.state)
        evidence.pop('receipt_source')
        self.assertEqual(self.result()['committed_wage_gold'], 0)

    def test_retained_journal_label_cannot_credit_partial_or_inexact_receipts(self):
        self.effects(3, ledger=True)
        self.state['production'][0]['evidence']['receipt_source'] = 'retained_native_journal'
        self.assertEqual(self.result()['committed_wage_gold'], 0)
        self.setUp();self.complete()
        self.state['production'][0]['evidence'].update(receipt_source='retained_native_journal')
        self.job['effect_receipt']['commit_id'] = 'different'
        self.job['effect_receipt_hash'] = _digest(self.job['effect_receipt'])
        self.state['production'][0]['evidence']['ack'] = copy.deepcopy(self.job['effect_receipt'])
        self.assertEqual(self.result()['committed_wage_gold'], 0)
