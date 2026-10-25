"""Offline contract tests: no HTTP, native game or voice process is invoked."""
import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from tools.qualify_owner_work import (Qualification, authored_dialogue, exact_identity,
    main, native_working, overlap_metrics, preflight, qualification_summary, read_plan_proofs, verify_result)


def world(actors=(17, 29)):
    society = {'people': {}, 'town': {'businesses': {}, 'residents': {}, 'daily': {'queue': []}}}
    obs = {'ready': True, 'session': 'native-session', 'gameDays': 5., 'residents': [],
           'resident_control': {'activities': []}, 'owner_work_jobs': {'available': True, 'capacity': 4, 'jobs': [], 'receipts': []}}
    for slot, actor in enumerate(actors):
        society['people'][str(actor)] = {'needs': {}, 'agency': {}, 'memories': []}
        society['town']['residents'][str(actor)] = {'id': actor}
        society['town']['businesses']['shop-' + str(actor)] = {
            'owner': actor, 'custodian': actor, 'active': True, 'revision': 3, 'capabilities': ['bread_recipe']}
        society['town']['daily']['queue'].append({'id': 'need-' + str(actor), 'actor': actor, 'kind': 'need_review', 'status': 'pending'})
        obs['residents'].append({'id': actor, 'baseId': actor + 1000, 'isPerson': True, 'x': actor, 'y': 0, 'z': 0,
            'inventory': {'gold': 9, 'bread': 0, 'grain': 2},
            'activity': {'package_id': 9000 + slot, 'scene_id': 0, 'in_combat': False, 'sleep_state': 0}})
        obs['resident_control']['activities'].append({'actor': actor, 'slot': slot, 'expectedPackage': 9000 + slot, 'ownedPackage': True})
    return {'society': society, 'bridge': {'session': 'native-session', 'last_seen': time.time(), 'observation': obs}}


def completed_world():
    state = world();owner = preflight(state)['selected_owners'][0]
    job = {'job_id': 'job-a', 'actor': owner['actor'], 'actor_base_id': owner['actor_base_id'], 'slot': owner['slot'],
           'session': 'native-session', 'epoch': 'epoch-a', 'business_id': owner['business_id'], 'business_revision': 3,
           'recipe_id': 'bread_recipe', 'policy_version': 'policy-a', 'work_minutes': 30,
           'source_plan': owner['source_plan'], 'inventory_before': owner['inventory_before'], 'expected_package': owner['expected_package']}
    before = {'owner': copy.deepcopy(owner['inventory_before'])}
    after = {'owner': {'gold': 9, 'bread': 2, 'grain': 1}}
    identity = {k:v for k, v in job.items() if k not in ('source_plan', 'inventory_before', 'expected_package')}
    command = {**identity, 'id': 'commit-a', 'kind': 'inventory_self_produce_commit', 'commit_id': 'commit-a',
               'attendance_token': 'single-use-token', 'before': before, 'after': after}
    ack = {**identity, 'id': 'commit-a', 'commit_id': 'commit-a', 'status': 'applied', 'attendance_token': 'single-use-token',
           'inventory': copy.deepcopy(after), 'effects_issued': True, 'committed_inventory_verified': True, 'mechanism': 'native_owner_recipe'}
    saved = {**identity, 'id': job['job_id'], 'phase': 'complete', 'release_verified': True, 'receipt_acknowledged': True,
             'receipt_hash': 'terminal-proof', 'attendance_receipt_hash': 'attendance-proof',
             'attendance': {'token': 'single-use-token', 'worked_minutes': 30, 'samples': 150, 'slot': job['slot'],
                            'expected_package': owner['expected_package'], 'serial': 3, 'anchor': [17, 0, 0]},
             'settlement': {'phase': 'committed', 'commit_id': 'commit-a', 'production_record_id': 'commit-a', 'committed_inventory_verified': True}}
    state['society']['owner_work_jobs'] = {'jobs': [], 'history': [saved]}
    state['society']['production'] = [{'id': 'commit-a', 'work_job': job['job_id'], 'status': 'committed', 'command': command,
        'evidence': {'actual': copy.deepcopy(after), 'ack': ack, 'session': job['session']}}]
    state['bridge']['observation']['residents'][0]['inventory'] = copy.deepcopy(after['owner'])
    plans = [{'id': job['source_plan'], 'actor': job['actor'], 'work_job': job['job_id'], 'phase': 'complete', 'outcome': 'owner_work_completed'}]
    return state, job, plans


class OwnerWorkQualificationTests(unittest.TestCase):
    def test_selection_uses_current_dynamic_actors_without_mutation(self):
        state = world((401, 509));before = copy.deepcopy(state)
        report = preflight(state)
        self.assertTrue(report['ready']);self.assertEqual([p['actor'] for p in report['selected_owners']], [401, 509])
        self.assertEqual(state, before);self.assertEqual(report['cloud_model_calls'], 0)
        self.assertFalse(report['freshness_checked'])

    def test_one_recipe_charter_reports_gap_without_inventing_second(self):
        state = world();state['society']['town']['businesses']['shop-29']['capabilities'] = ['metalwork_planned']
        before = copy.deepcopy(state);report = preflight(state)
        self.assertFalse(report['ready']);self.assertEqual(len(report['eligible_owners']), 1)
        self.assertIn('found 1 eligible owners', ' '.join(report['gaps']));self.assertEqual(state, before)
        self.assertEqual(report['observed_charters'][1]['capabilities'], ['metalwork_planned'])

    def test_distinct_charters_do_not_duplicate_one_owner_account(self):
        state = world((17,));business = state['society']['town']['businesses']['shop-17']
        state['society']['town']['businesses']['other-charter'] = copy.deepcopy(business)
        self.assertFalse(preflight(state)['ready'])

    def test_changed_stock_custody_base_slot_and_pending_review_fail_closed(self):
        for mutation in ('stock', 'custody', 'base', 'slot', 'review'):
            with self.subTest(mutation=mutation):
                state = world();obs = state['bridge']['observation']
                if mutation == 'stock':obs['residents'][1]['inventory']['grain'] = 0
                if mutation == 'custody':state['society']['town']['businesses']['shop-29']['custodian'] = 17
                if mutation == 'base':obs['residents'][1].pop('baseId')
                if mutation == 'slot':obs['resident_control']['activities'][1]['slot'] = 0
                if mutation == 'review':state['society']['town']['daily']['queue'][1]['status'] = 'complete'
                self.assertFalse(preflight(state)['ready'])

    def test_stale_live_metadata_and_running_director_are_not_ready(self):
        state = world();state['bridge']['last_seen'] -= 20
        self.assertFalse(preflight(state, now=time.time())['ready'])
        self.assertFalse(preflight(world(), director_running=True)['ready'])
        state = world();state['bridge']['observation']['owner_work_jobs']['capacity'] = 1
        self.assertFalse(preflight(state)['ready'])

    def test_native_work_requires_self_target_exact_identity_and_owned_package(self):
        state, job, _ = completed_world();obs = state['bridge']['observation']
        obs['owner_work_jobs']['jobs'] = [{**job, 'phase': 'working', 'samples': 3, 'worked_minutes': 1}]
        control = obs['resident_control']['activities'][0]
        control.update(mode='await_decision', target=job['actor'], phase='work_holding', serial=3,
                       work_hold_id='owner-work-job-a', goal_id='owner-work-job-a')
        self.assertTrue(native_working(obs, job))
        for field, value in (('target', 29), ('ownedPackage', False), ('serial', 0), ('work_hold_id', 'other-job')):
            altered = copy.deepcopy(obs);altered['resident_control']['activities'][0][field] = value
            self.assertFalse(native_working(altered, job))
        altered = copy.deepcopy(obs);altered['residents'][0]['baseId'] += 1
        self.assertFalse(native_working(altered, job))
        altered = copy.deepcopy(obs);altered['owner_work_jobs']['jobs'][0]['epoch'] = 'old'
        self.assertFalse(native_working(altered, job))
        self.assertFalse(exact_identity({**job, 'actor': str(job['actor'])}, job))

    def test_overlap_is_cumulative_but_never_interpolates_gap_or_unverified_voice(self):
        _, job, _ = completed_world()
        samples = [{'elapsed_seconds': t, 'native_received_at': 100 + t, 'working_job_ids': ['a', 'b'], 'playing_delivery_id': delivery,
                    'work_observations': [{**job, 'job_id': j, 'serial': 3, 'samples': i + 2, 'worked_minutes': t} for j in ('a', 'b')]}
                   for i, (t, delivery) in enumerate([(0, 'voice'), (.5, 'voice'), (1., 'voice'), (4., 'voice'), (4.5, None), (5., None)])]
        result = overlap_metrics(samples, ['voice'])
        self.assertEqual(result['two_qualified_work_seconds'], 2.)
        self.assertEqual(result['longest_continuous_work_seconds'], 1.)
        self.assertEqual(result['verified_voice_and_two_work_seconds'], 1.)
        self.assertEqual(overlap_metrics(samples)['verified_voice_and_two_work_seconds'], 0)
        self.assertEqual(overlap_metrics([{**s, 'working_job_ids': ['a', 'a']} for s in samples])['two_qualified_work_seconds'], 0)
        cached = [{**s, 'native_received_at': 100} for s in samples]
        self.assertEqual(overlap_metrics(cached, ['voice'])['two_qualified_work_seconds'], 0)
        stalled = [{**s, 'work_observations': samples[0]['work_observations']} for s in samples]
        self.assertEqual(overlap_metrics(stalled, ['voice'])['two_qualified_work_seconds'], 0)

    def test_complete_proof_requires_bound_inventory_attendance_plan_and_cleanup(self):
        state, job, plans = completed_world();result = verify_result(state, job, plans)
        self.assertTrue(result['qualified']);self.assertEqual(result['inventory_delta'], {'gold': 0, 'bread': 2, 'grain': -1})
        self.assertFalse(result['productive_animation_verified'])
        for mutation in ('duplicate', 'gold', 'token', 'base', 'session', 'release', 'ack', 'source', 'attendance'):
            with self.subTest(mutation=mutation):
                altered, admission, source = completed_world();record = altered['society']['production'][0]
                saved = altered['society']['owner_work_jobs']['history'][0]
                if mutation == 'duplicate':altered['society']['production'].append(copy.deepcopy(record))
                if mutation == 'gold':record['command']['after']['owner']['gold'] += 1
                if mutation == 'token':record['evidence']['ack']['attendance_token'] = 'other-token'
                if mutation == 'base':record['evidence']['ack']['actor_base_id'] += 1
                if mutation == 'session':altered['bridge']['session'] = 'new-session'
                if mutation == 'release':saved['release_verified'] = False
                if mutation == 'ack':saved['receipt_acknowledged'] = False
                if mutation == 'source':source[0]['work_job'] = 'unrelated'
                if mutation == 'attendance':saved['attendance']['worked_minutes'] = 0
                self.assertFalse(verify_result(altered, admission, source)['qualified'])

    def test_overall_acceptance_requires_four_deliveries_and_meaningful_work_voice_overlap(self):
        _, job, _ = completed_world()
        samples = [{'elapsed_seconds': t, 'native_received_at': 100 + t, 'working_job_ids': ['a', 'b'], 'playing_delivery_id': 'speech-1',
                    'work_observations': [{**job, 'job_id': j, 'serial': 3, 'samples': t + 2, 'worked_minutes': t} for j in ('a', 'b')]}
                   for t in range(12)]
        deliveries = ['speech-1', 'speech-2', 'speech-3', 'speech-4']
        results = [{'qualified': True}, {'qualified': True}]
        chat = {'id': 'conversation', 'phase': 'complete'}
        self.assertTrue(qualification_summary(results, samples, deliveries, 'conversation', chat, 10)['qualified'])
        no_voice = qualification_summary(results, samples, [], None, {}, 10)
        self.assertEqual(no_voice['status'], 'work_only');self.assertFalse(no_voice['qualified'])
        self.assertFalse(qualification_summary(results, samples[:3], deliveries, 'conversation', chat, 10)['qualified'])
        self.assertFalse(qualification_summary(results, samples, deliveries[:3], 'conversation', chat, 10)['qualified'])
        self.assertFalse(qualification_summary(results[:1], samples, deliveries, 'conversation', chat, 10)['qualified'])

    def test_partial_inventory_or_unknown_effects_do_not_count_as_output(self):
        state, job, plans = completed_world()
        record = state['society']['production'][0];record['status'] = 'held'
        record['evidence']['ack']['effects_issued'] = None
        state['bridge']['observation']['residents'][0]['inventory']['bread'] = 0
        result = verify_result(state, job, plans)
        self.assertFalse(result['output_verified']);self.assertFalse(result['qualified'])

    def test_exact_checkpoint_read_ignores_newer_plan_and_excludes_private_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / 'timeline.sqlite'
            with closing(sqlite3.connect(database)) as db:
                db.execute('CREATE TABLE checkpoints(id INTEGER PRIMARY KEY,payload TEXT,sha256 TEXT)')
                for marker, phase in ((1, 'complete'), (2, 'held')):
                    payload = json.dumps({'plans': [{'id': 'source', 'actor': 17, 'phase': phase, 'private': 'do-not-copy'}, {'id': 'other'}], 'private': 'do-not-copy'})
                    db.execute('INSERT INTO checkpoints VALUES (?,?,?)', (marker, payload, hashlib.sha256(payload.encode()).hexdigest()))
                db.commit()
            result = read_plan_proofs(database, 1, {'source'})
            self.assertEqual(result['plans'][0]['phase'], 'complete');self.assertNotIn('private', json.dumps(result))
            with self.assertRaises(ValueError):read_plan_proofs(database, 3, {'source'})
            with closing(sqlite3.connect(database)) as db:
                db.execute("UPDATE checkpoints SET sha256='wrong' WHERE id=1");db.commit()
            with self.assertRaises(ValueError):read_plan_proofs(database, 1, {'source'})

    def test_trial_requires_authorization_before_http_output_or_voice(self):
        with tempfile.TemporaryDirectory() as temporary:
            client = Mock();voice = Mock();output = Path(temporary) / 'evidence.json'
            runner = Qualification(client, temporary, output, voice_factory=voice)
            with self.assertRaises(PermissionError):runner.run()
            client.assert_not_called();voice.assert_not_called();self.assertFalse(output.exists())

    def test_missing_prerequisite_never_mutates_or_starts_voice(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = world((17,));state['society']['checkpoint'] = 1
            def read_only(route, data=None):
                self.assertIsNone(data)
                return {'director': {'running': False}} if route == '/observer/state' else state
            voice = Mock();runner = Qualification(read_only, temporary, Path(temporary) / 'proof.json', voice_factory=voice)
            report = runner.run(authorized=True)
            self.assertFalse(report['qualified']);self.assertEqual(report['admissions'], []);voice.assert_not_called()
            self.assertIn('1 eligible owners', ' '.join(report['preflight']['gaps']))

    def test_timeout_does_not_cancel_release_or_replay_uncertain_effect(self):
        with tempfile.TemporaryDirectory() as temporary:
            client = Mock();runner = Qualification(client, temporary, Path(temporary) / 'proof.json')
            runner.deadline = time.monotonic() - 1
            report = runner.run(authorized=True)
            client.assert_not_called();self.assertEqual(report['error_type'], 'TimeoutError')
            self.assertIn('No work cancellation', report['cleanup'])

    def test_offline_cli_never_constructs_http_or_voice(self):
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = Path(temporary) / 'state.json';output = Path(temporary) / 'report.json'
            snapshot.write_text(json.dumps(world((17,))), encoding='utf-8')
            with patch('tools.qualify_owner_work.CheckpointHTTP') as http, patch('tools.qualify_owner_work.VoiceWorker') as voice:
                main(['--state-file', str(snapshot), '--output', str(output)])
                http.assert_not_called();voice.assert_not_called()
            report = json.loads(output.read_text());self.assertFalse(report['executed']);self.assertEqual(report['mode'], 'offline')

    def test_authored_dialogue_cannot_change_partner_or_claim_available_actions(self):
        context = {'options': [{'id': 'approach_29'}]}
        result = authored_dialogue('choose_partner', context, 0, 29)
        self.assertTrue(result['authored_test_fixture']);self.assertFalse(result['model_generated'])
        with self.assertRaises(ValueError):authored_dialogue('choose_partner', context, 0, 17)
        with self.assertRaises(ValueError):authored_dialogue('propose', {}, 4, 29)

    def test_failed_trial_cli_returns_failure_without_real_client_or_native_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);(root / 'runtime').mkdir()
            (root / 'runtime/bridge-config.json').write_text(json.dumps({'port': 1, 'token': 'offline-placeholder'}))
            with patch('tools.qualify_owner_work.CheckpointHTTP') as client, patch.object(Qualification, 'run', return_value={'qualified': False, 'status': 'work_only'}) as trial:
                result = main(['--root', str(root), '--execute-authorized-trial', '--output', str(root / 'result.json')])
                self.assertEqual(result, 1);client.return_value.assert_not_called();trial.assert_called_once_with(authorized=True)


if __name__ == '__main__':unittest.main()
