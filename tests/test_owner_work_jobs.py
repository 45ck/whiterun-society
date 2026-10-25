import copy
import time
import unittest
from owner_work_jobs import OwnerWorkJobs, _identity, _command
from owner_production import owner_work_opportunities
from activity_leases import owner_work_leases


class OwnerSavedWorld(OwnerWorkJobs):
    """Explicit saved checkpoint boundary; native effects are supplied receipts."""
    def __init__(self, state):
        self.active = state;self.session = 'owner-test';self.marker = 1
        self.transition = None;self.error = None;self.foreground_busy = False;self.talking = False
    def _agency_guard(self, observation):
        if self.transition or self.active.get('pending'):raise ValueError('Unsettled writer')
    def agency_plan(self):return self.active['plans'][-1]
    def agency_busy(self):return self.foreground_busy
    def conversation_busy(self):return self.talking
    def agency_command(self, session):return None
    def speech_command(self, session):return None
    def _write(self, state, reason):
        self.prepared = copy.deepcopy(state);self.transition = {'next': self.marker + 1};return self.marker + 1
    def bind(self, observation):
        self.active = self.prepared;self.marker += 1;self.transition = None;observation['checkpoint'] = self.marker


class OwnerWorkJobsTests(unittest.TestCase):
    def setUp(self):
        self.state = {'plans': [], 'pending': None, 'people': {'1': {'needs': {'hunger': .9, 'fatigue': .7}, 'agency': {}, 'memories': []}},
            'town': {'businesses': {'shop': {'owner': 1, 'custodian': 1, 'active': True, 'revision': 1,
                                            'capabilities': ['bread_recipe']}}, 'daily': {'queue': []}}}
        self.world = OwnerSavedWorld(self.state)
        self.obs = {'session': self.world.session, 'checkpoint': 1, 'gameDays': 3.,
            'residents': [{'id': 1, 'baseId': 101, 'isPerson': True, 'x': 10, 'y': 20, 'z': 30,
                           'inventory': {'gold': 5, 'bread': 0, 'grain': 2},
                           'activity': {'package_id': 9000, 'scene_id': 0, 'in_combat': False, 'sleep_state': 0}}],
            'resident_control': {'activities': [{'actor': 1, 'slot': 10, 'expectedPackage': 9000, 'ownedPackage': True}]},
            'owner_work_jobs': {'available': True, 'capacity': 4, 'jobs': [], 'receipts': []}}

    def delegate(self):
        terms = owner_work_opportunities(self.world.active, self.obs, 1, require_owned=False)[0]
        plan = {'id': 'source', 'actor': 1, 'kind': 'need_review', 'phase': 'ready_to_self_work', 'own_work_terms': terms}
        self.world.active['plans'].append(plan)
        self.world.active['town']['daily']['queue'].append({'id': 'source', 'actor': 1, 'status': 'started',
                                                          'goal_followups': [{'goal_id': 'private-intent'}]})
        result = self.world.delegate_owner_work(plan, self.obs);self.world.bind(self.obs)
        return self.world.active['work_jobs'][result['job_id']]

    def attendance(self, job, **changes):
        now = time.time() * 1000
        evidence = {'token': 'native-single-use-token', 'slot': job['slot'], 'serial': 3,
                    'expected_package': 9000, 'anchor': [10, 20, 30], 'worked_minutes': job['work_minutes'],
                    'samples': 100, 'ready_at': now - 100, 'expires_at': now + 120000}
        return {**_identity(job), 'phase': 'attendance_verified', 'attendance': evidence,
                'effects_issued': False, 'committed_inventory_verified': False, 'release_verified': False, **changes}

    def qualified(self):
        job = self.delegate()
        self.obs['gameDays'] += job['work_minutes'] / 1440
        self.obs['owner_work_jobs']['receipts'] = [self.attendance(job)]
        self.assertTrue(self.world.observe_owner_work_jobs(self.obs));self.world.bind(self.obs)
        return self.world.active['work_jobs'][job['id']]

    def prepared_recipe(self):
        job = self.qualified()
        self.assertTrue(self.world.prepare_owner_work_recipe(self.obs));self.world.bind(self.obs)
        return self.world.active['work_jobs'][job['id']], self.world.active['pending']['command']

    def commit_ack(self, job, command):
        return {**_identity(job), 'id': command['id'], 'status': 'applied', 'commit_id': command['id'],
                'attendance_token': command['attendance_token'], 'inventory': copy.deepcopy(command['after']),
                'effects_issued': True, 'committed_inventory_verified': True,
                'mechanism': 'native_owner_recipe', 'animation_verified': False}

    def test_delegation_reserves_input_without_debit_and_leaves_event_started(self):
        inventory = copy.deepcopy(self.obs['residents']);job = self.delegate()
        self.assertEqual(self.world.agency_plan()['phase'], 'delegated')
        self.assertEqual(self.world.active['town']['daily']['queue'][0]['status'], 'started')
        self.assertEqual(job['input_reservation'], {'grain': 1})
        self.assertEqual(self.obs['residents'], inventory)
        self.assertEqual(self.world.active['people']['1']['memories'], [])
        self.assertEqual(self.world.owner_work_pending_command()['kind'], 'owner_work_start')
        self.assertEqual(self.world.owner_work_status()['capacity'], 4)
        self.assertFalse(self.world.owner_work_status()['jobs'][0]['productive_animation_verified'])

    def test_native_start_admission_is_not_labour_or_output(self):
        job = self.delegate();command = self.world.owner_work_pending_command()
        self.obs['ack'] = {**_identity(job), 'id': command['id'], 'status': 'applied', 'accepted': True}
        self.assertTrue(self.world.observe_owner_work_jobs(self.obs));self.world.bind(self.obs)
        self.assertEqual(self.world.active['work_jobs'][job['id']]['phase'], 'running')
        self.assertIsNone(self.world.active['pending'])
        self.assertNotIn('production', self.world.active)

    def test_qualified_attendance_is_durable_and_recipe_uses_fresh_inventory(self):
        job = self.qualified()
        self.assertNotIn('production', self.world.active);self.assertIsNone(self.world.active['pending'])
        self.obs['residents'][0]['inventory'].update(gold=8, grain=3, bread=1)
        self.assertTrue(self.world.prepare_owner_work_recipe(self.obs))
        self.assertIsNone(self.world.active['pending'])
        self.world.bind(self.obs);command = self.world.active['pending']['command']
        self.assertEqual(command['before'], {'owner': {'gold': 8, 'grain': 3, 'bread': 1}})
        self.assertEqual(command['after'], {'owner': {'gold': 8, 'grain': 2, 'bread': 3}})
        self.assertEqual(command['attendance_token'], job['attendance']['token'])

    def test_active_speech_foreground_and_unrelated_writer_prevent_recipe_preparation(self):
        self.qualified()
        for field in ('talking', 'foreground_busy'):
            setattr(self.world, field, True)
            self.assertFalse(self.world.prepare_owner_work_recipe(self.obs));self.assertIsNone(self.world.transition)
            setattr(self.world, field, False)
        pending = {'id': 'other-trade', 'status': 'pending'};self.world.active['pending'] = pending
        self.assertFalse(self.world.prepare_owner_work_recipe(self.obs));self.assertEqual(self.world.active['pending'], pending)

    def test_commit_records_output_once_but_source_plan_waits_for_release(self):
        job, command = self.prepared_recipe()
        self.world.active['plans'].append({'id': 'unrelated', 'actor': 2, 'phase': 'choose'})
        self.obs['residents'][0]['inventory'] = copy.deepcopy(command['after']['owner'])
        self.obs['ack'] = self.commit_ack(job, command)
        self.assertTrue(self.world.observe_owner_work_recipe(self.obs));self.world.bind(self.obs)
        saved = self.world.active['work_jobs'][job['id']]
        self.assertEqual(saved['phase'], 'recipe_committed')
        self.assertEqual(self.world.active['plans'][0]['phase'], 'delegated')
        self.assertEqual(self.world.agency_plan()['phase'], 'choose')
        self.assertEqual(len(self.world.active['production']), 1)
        self.assertEqual(len(self.world.active['people']['1']['memories']), 1)
        self.assertFalse(self.world.observe_owner_work_recipe(self.obs))
        self.obs['owner_work_jobs']['receipts'] = [{**_identity(job), 'phase': 'complete', 'effects_issued': True,
            'committed_inventory_verified': True, 'release_verified': True, 'commit_id': command['id']}]
        self.assertTrue(self.world.observe_owner_work_jobs(self.obs));self.world.bind(self.obs)
        self.assertEqual(self.world.active['plans'][0]['phase'], 'complete')
        self.assertEqual(self.world.active['plans'][-1]['phase'], 'choose')
        self.assertEqual(self.world.active['town']['daily']['queue'][0]['goal_followups'], [{'goal_id': 'private-intent'}])
        cleanup = self.world.owner_work_pending_command()
        self.obs['ack'] = {**_identity(job), 'id': cleanup['id'], 'status': 'applied', 'acknowledged': True}
        self.assertTrue(self.world.observe_owner_work_jobs(self.obs));self.world.bind(self.obs)
        self.assertEqual(owner_work_leases(self.world.active), [])
        self.assertEqual(len(self.world.active['production']), 1)

    def test_changed_charter_or_missing_grain_cancels_without_recipe(self):
        for reason in ('charter', 'grain'):
            with self.subTest(reason=reason):
                self.setUp();job = self.qualified()
                if reason == 'charter':self.world.active['town']['businesses']['shop']['revision'] += 1
                else:self.obs['residents'][0]['inventory']['grain'] = 0
                self.assertTrue(self.world.prepare_owner_work_recipe(self.obs));self.world.bind(self.obs)
                self.assertEqual(self.world.active['work_jobs'][job['id']]['phase'], 'held')
                self.assertIsNone(self.world.active['pending']);self.assertNotIn('production', self.world.active)

    def test_wrong_receipt_or_partial_inventory_holds_once_without_replay(self):
        job, command = self.prepared_recipe()
        self.obs['ack'] = self.commit_ack(job, command)
        self.obs['residents'][0]['inventory']['grain'] -= 1
        self.assertTrue(self.world.observe_owner_work_recipe(self.obs));self.world.bind(self.obs)
        self.assertEqual(self.world.active['pending']['status'], 'held')
        self.assertFalse(self.world.observe_owner_work_recipe(self.obs))
        self.assertIsNone(self.world.transition);self.assertNotIn('production', self.world.active)
        self.assertTrue(self.world.active['work_jobs'][job['id']]['effect_unreconciled'])

    def test_old_session_actual_before_or_after_never_reauthorizes_recipe(self):
        for after in (False, True):
            with self.subTest(after=after):
                self.setUp();job, command = self.prepared_recipe()
                if after:self.obs['residents'][0]['inventory'] = copy.deepcopy(command['after']['owner'])
                self.world.session = 'loaded-session';self.obs['session'] = self.world.session
                self.obs['ack'] = self.commit_ack(job, command)
                self.assertTrue(self.world.observe_owner_work_recipe(self.obs));self.world.bind(self.obs)
                self.assertEqual(self.world.active['pending']['status'], 'held')
                self.assertNotIn('production', self.world.active)
                self.assertFalse(self.world.observe_owner_work_recipe(self.obs))

    def test_rejected_recipe_with_no_effects_proof_clears_writer_but_retains_lease(self):
        job, command = self.prepared_recipe()
        self.obs['ack'] = {**_identity(job), 'id': command['id'], 'status': 'held', 'no_effects_issued': True}
        self.assertTrue(self.world.observe_owner_work_recipe(self.obs));self.world.bind(self.obs)
        self.assertIsNone(self.world.active['pending'])
        self.assertEqual(len(owner_work_leases(self.world.active)), 1)
        self.assertEqual(self.world.active['work_jobs'][job['id']]['phase'], 'held')

    def test_orphan_effect_unknown_stays_quarantined_without_output(self):
        before = copy.deepcopy(self.world.active);job = self.delegate()
        self.world.active = before
        self.obs['owner_work_jobs']['receipts'] = [{**_identity(job), 'phase': 'held',
            'effects_issued': None, 'release_verified': True}]
        self.assertTrue(self.world.observe_owner_work_jobs(self.obs));self.world.bind(self.obs)
        self.assertIsNone(self.world.owner_work_pending_command())
        self.assertEqual(self.world.active['people'], before['people'])
        self.assertEqual(self.world.active['plans'], [])

    def test_orphan_no_effects_release_is_checkpointed_before_ack(self):
        before = copy.deepcopy(self.world.active);job = self.delegate();self.world.active = before
        self.obs['owner_work_jobs']['receipts'] = [{**_identity(job), 'phase': 'held',
            'effects_issued': False, 'release_verified': True}]
        self.assertTrue(self.world.observe_owner_work_jobs(self.obs))
        self.assertIsNone(self.world.owner_work_pending_command());self.world.bind(self.obs)
        self.assertEqual(self.world.owner_work_pending_command()['kind'], 'owner_work_ack_receipt')
        self.assertNotIn('production', self.world.active)

    def test_mismatched_inventory_checkpoint_cannot_prepare_or_settle(self):
        self.qualified();self.obs['inventory_checkpoint'] = 0
        self.assertFalse(self.world.prepare_owner_work_recipe(self.obs))
        self.obs.pop('inventory_checkpoint')
        self.assertTrue(self.world.prepare_owner_work_recipe(self.obs));self.world.bind(self.obs)
        self.obs['inventory_checkpoint'] = 0
        self.assertFalse(self.world.observe_owner_work_recipe(self.obs))

    def test_four_independent_owner_mailboxes_reserve_without_using_rest_capacity(self):
        template = copy.deepcopy(self.obs['residents'][0])
        for actor in range(1, 5):
            if actor != 1:
                row = copy.deepcopy(template);row.update(id=actor, baseId=100 + actor)
                self.obs['residents'].append(row)
                self.obs['resident_control']['activities'].append({'actor': actor, 'slot': 9 + actor,
                    'expectedPackage': 9000, 'ownedPackage': True})
                self.world.active['people'][str(actor)] = {'needs': {}, 'agency': {}, 'memories': []}
                self.world.active['town']['businesses']['shop-' + str(actor)] = {
                    'owner': actor, 'custodian': actor, 'active': True, 'revision': 1, 'capabilities': ['bread_recipe']}
            terms = owner_work_opportunities(self.world.active, self.obs, actor, require_owned=False)[0]
            plan = {'id': 'work-' + str(actor), 'actor': actor, 'phase': 'ready_to_self_work', 'own_work_terms': terms}
            self.world.active['plans'].append(plan)
            self.world.delegate_owner_work(plan, self.obs);self.world.bind(self.obs)
        jobs = list(self.world.active['work_jobs'].values())
        self.assertEqual({j['slot'] for j in jobs}, {10, 11, 12, 13})
        self.assertTrue(all(p['phase'] == 'delegated' for p in self.world.active['plans']))
        plan = {'id': 'fifth', 'actor': 5, 'phase': 'ready_to_self_work'};self.world.active['plans'].append(plan)
        with self.assertRaisesRegex(ValueError, 'capacity'):self.world.delegate_owner_work(plan, self.obs)
        self.assertEqual(self.world.active.get('activity_jobs', {}), {})
        self.assertIsNone(self.world.active['pending'])


if __name__ == '__main__':unittest.main()
