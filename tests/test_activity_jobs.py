import copy
import unittest
from activity_jobs import ActivityJobs, activity_leases, reserved_activity_actors, reserved_activity_targets
from places import registered_venues
from legacy_fixture import author_fixture_identities
from resident_identity import resident_identity_status


class SavedJobs(ActivityJobs):
    """Explicit prepare/bind test boundary; no native engine is simulated."""
    def __init__(self, state):
        self.active = state;self.transition = None;self.error = None;self.session = 'test-session'
    def _agency_guard(self, observation):
        if self.transition or observation['session'] != self.session:raise ValueError('Unbound or wrong session')
    def agency_plan(self):return self.active['plans'][-1]
    def _write(self, state, reason):
        self.prepared = copy.deepcopy(state);self.transition = {'next': 1};return 1
    def bind(self):
        self.active = self.prepared;self.transition = None


class ActivityJobsTests(unittest.TestCase):
    def setUp(self):
        self.seats = list(registered_venues('rest_bench'))[:3]
        people = {str(actor): {'needs': {'fatigue': .9}, 'needs_clock': 3., 'memories': [], 'agency': {}} for actor in (1, 2, 3)}
        self.world = SavedJobs({'people': people, 'plans': [], 'pending': None,
                               'town': {'residents': {str(a): {'id':a,'observed_game_day': 3.} for a in (1, 2, 3)},
                                        'daily': {'queue': []}}})
        self.obs = {'session': self.world.session, 'checkpoint':0,'ready':True,'gameDays': 3.,
                    'activity_jobs': {'available': True, 'capacity': 2, 'receipts': []},
                    'residents': [{'id': a, 'baseId': 100 + a, 'isPerson': True, 'x': 0, 'y': 0, 'z': 0,
                                   'inventory': {'gold': 2, 'bread': 1}} for a in (1, 2, 3)],
                    'rest': {'available': True, 'sites': [
                        {'id': seat, 'position': [100, 0, 0], 'loaded': True, 'occupancy_known': True, 'occupied': False}
                        for seat in self.seats], 'sensors': {str(a): {'sit_available': True, 'furniture_reference_available': True,
                         'sit_state': 0, 'furniture': 0} for a in (1, 2, 3)}}}
        author_fixture_identities(self.world.active,self.obs)

    def intention(self, actor=1, seat=None):
        plan = {'id': 'plan-' + str(len(self.world.active['plans'])), 'actor': actor,
                'phase': 'ready_to_rest', 'rest_target': seat or self.seats[actor - 1], 'kind': 'need_review'}
        self.world.active['plans'].append(plan)
        self.world.active['town']['daily']['queue'].append({'id': plan['id'], 'actor': actor, 'kind': 'need_review', 'status': 'started',
                                                          'goal_followups': [{'goal_id': 'goal-' + str(actor)}]})
        return plan

    def delegate(self, actor=1, seat=None):
        result = self.world.delegate_rest(self.intention(actor, seat), self.obs)
        self.world.bind();return self.world.active['activity_jobs'][result['job_id']]

    def identity(self, job):
        return {'job_id': job['id'], **{k: job[k] for k in ('actor', 'target', 'slot', 'session', 'epoch')}}

    def receipt(self, job, **changes):
        evidence = {'actor': job['actor'], 'target': job['target'], 'rested_minutes': 30, 'seated_samples': 8,
                    'exact_furniture_verified': True, 'release_verified': True, **changes}
        return {**self.identity(job), 'status': 'applied', 'rest': evidence}

    def finish(self, job, receipt=None):
        self.obs['gameDays'] = 3. + 30 / 1440
        self.obs['activity_jobs'].update(epoch=job['epoch'], receipts=[receipt or self.receipt(job)])
        self.assertTrue(self.world.observe_activity_jobs(self.obs));self.world.bind()

    def test_two_saved_jobs_leave_events_nonterminal_and_lease_actor_seat_slot(self):
        before = copy.deepcopy(self.obs['residents']);first = self.delegate();second = self.delegate(2)
        self.assertEqual({first['slot'], second['slot']}, {0, 1})
        # Inspect saved execution leases; identity admission also needs a live observation.
        self.assertEqual(reserved_activity_actors(self.world.active,include_identity=False), {1, 2})
        self.assertEqual(reserved_activity_targets(self.world.active), set(self.seats[:2]))
        self.assertTrue(all(p['phase'] == 'delegated' for p in self.world.active['plans']))
        self.assertTrue(all(e['status'] == 'started' for e in self.world.active['town']['daily']['queue']))
        self.assertEqual(self.world.active['people']['1']['needs']['fatigue'], .9)
        self.assertEqual(self.obs['residents'], before)
        with self.assertRaisesRegex(ValueError, 'capacity'):self.world.delegate_rest(self.intention(3), self.obs)

    def test_exclusive_actor_and_seat_and_current_native_capability(self):
        self.delegate()
        for actor, seat in ((1, self.seats[1]), (2, self.seats[0])):
            with self.subTest(actor=actor, seat=seat):
                with self.assertRaisesRegex(ValueError, 'lease'):self.world.delegate_rest(self.intention(actor, seat), self.obs)
        self.obs['activity_jobs']['available'] = False
        with self.assertRaisesRegex(ValueError, 'unavailable'):self.world.delegate_rest(self.intention(2), self.obs)

    def test_start_ack_is_not_completion_and_prepared_command_is_idempotent(self):
        job = self.delegate();command = self.world.activity_pending_command()
        self.assertEqual(command, self.world.activity_pending_command())
        self.obs['ack'] = {**self.identity(job), 'id': command['id'], 'status': 'applied', 'accepted': True}
        self.assertTrue(self.world.observe_activity_jobs(self.obs))
        self.assertEqual(self.world.active['activity_jobs'][job['id']]['phase'], 'prepared')
        self.world.bind()
        self.assertEqual(self.world.active['activity_jobs'][job['id']]['phase'], 'running')
        self.assertIsNone(self.world.activity_pending_command())
        self.assertEqual(self.world.active['people']['1']['needs']['fatigue'], .9)

    def test_completion_updates_source_plan_and_exactly_once_recovery_then_ack_frees_lease(self):
        job = self.delegate();other = self.intention(3);other['phase'] = 'choose'
        self.finish(job)
        state = self.world.active;person = state['people']['1']
        self.assertEqual(state['plans'][0]['phase'], 'complete');self.assertEqual(state['plans'][-1]['phase'], 'choose')
        self.assertAlmostEqual(person['needs']['fatigue'], .5625)
        self.assertEqual(state['town']['daily']['queue'][0]['status'], 'complete')
        self.assertEqual(state['town']['daily']['queue'][0]['goal_followups'], [{'goal_id': 'goal-1'}])
        self.assertFalse(self.world.observe_activity_jobs(self.obs));self.assertEqual(len(state['rests']), 1)
        self.assertEqual(len(person['memories']), 1);self.assertIn(1, reserved_activity_actors(state,include_identity=False))
        command = self.world.activity_pending_command();self.assertEqual(command['kind'], 'activity_ack_receipt')
        self.obs['ack'] = {**self.identity(job), 'id': command['id'], 'status': 'applied', 'acknowledged': True}
        self.assertTrue(self.world.observe_activity_jobs(self.obs));self.world.bind()
        self.assertEqual(activity_leases(self.world.active), [])

    def test_invalid_attendance_held_and_unreleased_receipt_keeps_lease(self):
        job = self.delegate();self.finish(job, self.receipt(job, release_verified=False))
        self.assertEqual(self.world.active['activity_jobs'][job['id']]['phase'], 'held')
        self.assertEqual(self.world.active['people']['1']['needs']['fatigue'], .9)
        self.assertIsNone(self.world.activity_pending_command());self.assertEqual(len(activity_leases(self.world.active)), 1)
        self.obs['activity_jobs']['receipts'] = [self.receipt(job)]
        self.assertTrue(self.world.observe_activity_jobs(self.obs));self.world.bind()
        self.assertEqual(self.world.active['activity_jobs'][job['id']]['phase'], 'held')
        self.assertEqual(self.world.active['people']['1']['needs']['fatigue'], .9)
        self.assertFalse(self.world.active['plans'][0]['activity_release_required'])
        self.assertEqual(self.world.activity_pending_command()['kind'], 'activity_ack_receipt')

    def test_wrong_identity_receipt_cannot_complete_or_acknowledge(self):
        job = self.delegate();receipt = self.receipt(job);receipt['actor'] = 2
        self.obs['activity_jobs']['receipts'] = [receipt]
        self.assertFalse(self.world.observe_activity_jobs(self.obs));self.assertEqual(self.world.active['people']['1']['needs']['fatigue'], .9)

    def test_session_reset_holds_without_replay_or_recovery_but_can_ack_release(self):
        job = self.delegate();self.world.session = 'loaded-session';self.obs['session'] = 'loaded-session'
        self.assertTrue(self.world.observe_activity_jobs(self.obs));self.world.bind()
        self.assertIsNone(self.world.activity_pending_command())
        self.finish(job)
        self.assertEqual(self.world.active['activity_jobs'][job['id']]['phase'], 'held')
        self.assertEqual(self.world.active['people']['1']['needs']['fatigue'], .9)
        command = self.world.activity_pending_command()
        self.assertEqual(command['session'], 'loaded-session');self.assertEqual(command['job_session'], 'test-session')

    def test_rejected_start_only_frees_lease_with_explicit_no_effects_proof(self):
        job = self.delegate();command = self.world.activity_pending_command()
        self.obs['ack'] = {**self.identity(job), 'id': command['id'], 'status': 'held', 'accepted': False, 'no_effects_issued': True}
        self.assertTrue(self.world.observe_activity_jobs(self.obs));self.world.bind()
        self.assertEqual(activity_leases(self.world.active), [])
        self.assertEqual(self.world.active['plans'][0]['phase'], 'held')
        self.assertEqual(self.world.active['people']['1']['needs']['fatigue'], .9)

    def test_nonfinite_clock_and_forged_elapsed_receipt_cannot_recover(self):
        job = self.delegate();self.obs['activity_jobs']['receipts'] = [self.receipt(job)]
        self.obs['gameDays'] = float('nan')
        self.assertTrue(self.world.observe_activity_jobs(self.obs));self.world.bind()
        self.assertEqual(self.world.active['activity_jobs'][job['id']]['phase'], 'held')
        self.assertEqual(self.world.active['people']['1']['needs']['fatigue'], .9)

    def test_rolled_back_native_leases_still_exclude_actor_seat_and_slot(self):
        self.obs['activity_jobs']['jobs'] = [{'actor': 1, 'target': self.seats[0], 'slot': 0,
                                             'session': 'old-save', 'epoch': 'old-epoch', 'phase': 'held'}]
        with self.assertRaisesRegex(ValueError, 'lease'):
            self.world.delegate_rest(self.intention(1, self.seats[1]), self.obs)
        with self.assertRaisesRegex(ValueError, 'lease'):
            self.world.delegate_rest(self.intention(2, self.seats[0]), self.obs)
        job = self.delegate(2)
        self.assertEqual(job['slot'], 1)
        self.assertEqual(self.world.activity_pending_command()['actor_base_id'], 102)

    def test_early_receipt_and_short_or_nonfinite_attendance_do_not_grant_recovery(self):
        for minutes, day in ((30, 3.), (29.9, 3.1), (float('inf'), 3.1)):
            with self.subTest(minutes=minutes, day=day):
                self.setUp();job = self.delegate()
                self.obs['gameDays'] = day
                self.obs['activity_jobs']['receipts'] = [self.receipt(job, rested_minutes=minutes)]
                self.assertTrue(self.world.observe_activity_jobs(self.obs));self.world.bind()
                self.assertEqual(self.world.active['activity_jobs'][job['id']]['phase'], 'held')
                self.assertEqual(self.world.active['people']['1']['needs']['fatigue'], .9)

    def orphan(self, released=True):
        older = copy.deepcopy(self.world.active);job = self.delegate()
        receipt = self.receipt(job, release_verified=released)
        self.world.active = older;self.world.session = 'rollback-session';self.obs['session'] = self.world.session
        self.obs['activity_jobs']['receipts'] = [receipt]
        self.assertTrue(self.world.observe_activity_jobs(self.obs))
        return older, job, receipt

    def test_orphan_release_ack_requires_saved_checkpoint_and_never_imports_effects(self):
        older, job, receipt = self.orphan()
        self.assertIsNone(self.world.activity_pending_command())
        self.assertNotIn('activity_orphans', self.world.active)
        self.world.bind()
        self.assertEqual(reserved_activity_actors(self.world.active,include_identity=False), {1})
        self.assertEqual(self.world.active['people'], older['people'])
        self.assertEqual(self.world.active['plans'], older['plans'])
        self.assertEqual(self.world.active['town'], older['town'])
        self.assertNotIn('rests', self.world.active)
        command = self.world.activity_pending_command()
        self.assertEqual(command['kind'], 'activity_ack_receipt')
        self.assertEqual(command['session'], 'rollback-session')
        self.assertEqual(command['job_session'], job['session'])
        self.obs['ack'] = {**self.identity(job), 'id': command['id'], 'status': 'applied', 'acknowledged': True, 'slot': 1}
        self.assertFalse(self.world.observe_activity_jobs(self.obs))
        self.obs['ack']['slot'] = job['slot']
        self.assertTrue(self.world.observe_activity_jobs(self.obs))
        self.assertEqual(reserved_activity_actors(self.world.active,include_identity=False), {1})
        self.world.bind()
        self.assertEqual(activity_leases(self.world.active), [])
        history = self.world.activity_status()['history']
        self.assertTrue(history[0]['orphan'])
        self.assertEqual(history[0]['phase'], 'held')
        self.assertEqual(history[0]['outcome'], 'orphan_activity_held')
        self.assertFalse(history[0]['recovery_applied'])
        self.assertFalse(self.world.observe_activity_jobs(self.obs))
        self.assertEqual(self.world.active['people'], older['people'])

    def test_unreleased_orphan_remains_quarantined_until_later_exact_release_proof(self):
        older, job, receipt = self.orphan(released=False);self.world.bind()
        self.assertIsNone(self.world.activity_pending_command())
        self.assertEqual(reserved_activity_targets(self.world.active), {job['target']})
        self.obs['activity_jobs']['receipts'] = [self.receipt(job)]
        self.assertTrue(self.world.observe_activity_jobs(self.obs))
        self.assertIsNone(self.world.activity_pending_command())
        self.world.bind()
        self.assertEqual(self.world.activity_pending_command()['kind'], 'activity_ack_receipt')
        self.assertEqual(self.world.active['people'], older['people'])
        self.assertEqual(self.world.active['plans'], [])

    def test_missing_or_replaced_base_identity_cannot_admit_a_new_rest_job(self):
        plan=self.intention();before=copy.deepcopy(self.world.active)
        for base in (None,999):
            with self.subTest(base=base):
                if base is None:self.obs['residents'][0].pop('baseId',None)
                else:self.obs['residents'][0]['baseId']=base
                self.assertFalse(resident_identity_status(self.world.active,self.obs,1)['qualified'])
                with self.assertRaises(ValueError):
                    self.world.delegate_rest(plan,self.obs)
                self.assertEqual(self.world.active,before)
                self.assertIsNone(self.world.transition)
                self.assertIsNone(self.world.activity_pending_command())


class ActivityJobsLineageTests(unittest.TestCase):
    def setUp(self):
        import test_rest
        test_rest.RestTests.setUp(self)
        self.obs['activity_jobs'] = {'available': True, 'capacity': 2, 'receipts': []}

    def tearDown(self):
        self.world.db.close();self.temp.cleanup()

    def sync(self):
        import test_food
        test_food.FoodTests.sync(self)

    def census(self):
        import test_population
        test_population.PopulationTests.census(self)

    def review(self, hours=0):
        import test_daily_life
        return test_daily_life.DailyLifeTests.review(self, hours)

    def decide(self, action, event):
        import test_food
        return test_food.FoodTests.decide(self, action, event)

    def test_save_bound_delegation_settles_old_plan_while_new_foreground_plan_waits(self):
        self.review();before = copy.deepcopy(self.obs)
        event = next(e for e in self.world.active['town']['daily']['queue'] if e['actor'] == 99)
        self.world.begin_plan(event['id'], self.obs, 99, 'need_review');self.sync()
        self.decide('rest_at_bench', event['id'])
        command = self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'], 'activity_start_rest')
        self.assertFalse(self.world.agency_busy())
        job = self.world.active['activity_jobs'][command['job_id']]
        identity = {key: command[key] for key in ('job_id', 'actor', 'target', 'slot', 'session', 'epoch')}
        self.obs['ack'] = {**identity, 'id': command['id'], 'status': 'applied', 'accepted': True}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['activity_jobs'][job['id']]['phase'], 'running')
        self.world.begin_plan('other-resident', self.obs, 108149, 'meal_time');self.sync()
        self.obs['gameDays'] += 30 / 1440
        self.obs['activity_jobs'].update(epoch=job['epoch'], receipts=[{**identity, 'status': 'applied',
            'rest': {'actor': 99, 'target': job['target'], 'rested_minutes': 30, 'seated_samples': 3,
                     'release_verified': True, 'exact_furniture_verified': True}}])
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['id'], 'other-resident')
        self.assertEqual(self.world.agency_plan()['phase'], 'choose')
        self.assertEqual(next(p for p in self.world.active['plans'] if p['id'] == event['id'])['phase'], 'complete')
        self.assertEqual(len(self.world.active['rests']), 1)
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['fatigue'], .5625)
        self.world.observe(self.obs);self.sync();self.assertEqual(len(self.world.active['rests']), 1)
        self.world.observe({**before, 'session': 'older-save'})
        self.assertEqual(self.world.active.get('activity_jobs', {}), {})
        self.assertEqual(self.world.active.get('rests', []), [])
        self.assertEqual(self.world.active['people']['99']['needs']['fatigue'], .9)


if __name__ == '__main__':unittest.main()
