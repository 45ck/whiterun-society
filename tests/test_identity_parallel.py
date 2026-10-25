import copy
import unittest
import test_parallel_routines as fixtures


class IdentityParallelTests(unittest.TestCase):
    setUp=fixtures.ParallelRoutineTests.setUp
    tearDown=fixtures.ParallelRoutineTests.tearDown
    sync=fixtures.ParallelRoutineTests.sync
    census=fixtures.ParallelRoutineTests.census
    review=fixtures.ParallelRoutineTests.review
    start=fixtures.ParallelRoutineTests.start
    choose=fixtures.ParallelRoutineTests.choose
    complete=fixtures.ParallelRoutineTests.complete

    def change_identity(self):
        actor=self.batch['members'][0]['actor']
        row=next(r for r in self.obs['residents'] if r['id']==actor)
        row['baseId']+=1000
        return actor

    def test_changed_identity_cannot_accept_defer_or_write_old_biography(self):
        self.start();actor=self.change_identity()
        before=copy.deepcopy(self.world.active['people'][str(actor)])
        self.choose(('defer','defer'))
        batch=self.world.routine_batch();member=batch['members'][0]
        self.assertEqual(member['phase'],'held');self.assertEqual(member['outcome'],'journey_identity_conflict')
        self.assertTrue(member['identity_held']);self.assertEqual(batch['members'][1]['phase'],'complete')
        self.assertEqual(self.world.active['people'][str(actor)],before)
        self.assertIsNone(self.world.active['pending'])

    def test_changed_identity_cannot_receive_arrival_credit_but_release_stays_separate(self):
        self.start();self.choose();actor=self.change_identity()
        before=copy.deepcopy(self.world.active['people'][str(actor)])
        self.complete()
        batch=self.world.routine_batch();member=batch['members'][0]
        self.assertEqual(member['phase'],'held');self.assertEqual(member['outcome'],'journey_identity_conflict')
        self.assertEqual(member['receipt']['status'],'applied')
        self.assertTrue(batch['release_verified']);self.assertFalse(self.world.routines_busy())
        self.assertEqual(batch['members'][1]['phase'],'complete')
        self.assertEqual(self.world.active['people'][str(actor)],before)

    def test_identity_rejection_does_not_certify_missing_native_release(self):
        self.start();self.choose();actor=self.change_identity()
        before=copy.deepcopy(self.world.active['people'][str(actor)])
        self.complete(lambda rows:rows[0].update(release_verified=False))
        batch=self.world.routine_batch()
        self.assertTrue(batch['unverified_release']);self.assertFalse(batch['release_verified'])
        self.assertTrue(self.world.routines_busy())
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(self.world.active['people'][str(actor)],before)

    def test_old_unpinned_prepared_journey_is_held_without_upgrade_or_memory(self):
        self.start();self.choose()
        state=copy.deepcopy(self.world.active);before=copy.deepcopy(state['people'])
        for member in state['routine_batches'][-1]['members']:
            member.pop('actor_base_id');member['command'].pop('actor_base_id')
        for job in state['pending']['command']['jobs']:job.pop('actor_base_id')
        self.world._write(state,'Authored legacy unpinned prepared cohort fixture');self.sync()
        batch=self.world.routine_batch()
        self.assertEqual(batch['phase'],'held');self.assertTrue(batch['unverified_release'])
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(self.world.active['people'],before)
        self.assertTrue(all('actor_base_id' not in m['command'] for m in batch['members']))
        self.assertIsNone(self.world.pending(self.obs['session']))

    def test_late_exact_release_clears_only_lease_and_never_repeats_memories(self):
        self.start();self.choose();self.change_identity()
        self.complete(lambda rows:rows[0].update(release_verified=False))
        batch=copy.deepcopy(self.world.routine_batch());people=copy.deepcopy(self.world.active['people'])
        receipts=[copy.deepcopy(m['receipt']) for m in batch['members']]
        receipts[0]['release_verified']=True
        self.obs['ack']={'id':batch['id'],'status':'held','routines':receipts}
        self.assertTrue(self.world.observe_routines(self.obs));self.sync()
        self.assertEqual(self.world.active['people'],people)
        self.assertFalse(self.world.routines_busy());self.assertIsNone(self.world.active['pending'])
        self.assertEqual(self.world.routine_batch()['members'][0]['outcome'],'journey_identity_conflict')
        self.assertFalse(self.world.routine_batch()['members'][0]['initial_receipt']['release_verified'])

    def test_wrong_base_release_receipt_cannot_free_held_original_lease(self):
        self.start();self.choose();self.change_identity()
        self.complete(lambda rows:rows[0].update(release_verified=False))
        batch=copy.deepcopy(self.world.routine_batch());before=copy.deepcopy(self.world.active)
        receipts=[copy.deepcopy(m['receipt']) for m in batch['members']]
        receipts[0].update(release_verified=True,actor_base_id=receipts[0]['actor_base_id']+1000)
        self.obs['ack']={'id':batch['id'],'status':'held','routines':receipts}
        self.assertFalse(self.world.observe_routines(self.obs))
        self.assertEqual(self.world.active,before);self.assertTrue(self.world.routines_busy())

    def test_changed_base_suppresses_prepared_dispatch_then_records_hold(self):
        self.start();self.choose();self.change_identity()
        before=copy.deepcopy(self.world.active['people'])
        self.world.latest_observation=copy.deepcopy(self.obs)
        self.assertIsNone(self.world.pending(self.obs['session']))
        self.assertTrue(self.world.observe_routines(self.obs));self.sync()
        self.assertEqual(self.world.routine_batch()['phase'],'held')
        self.assertTrue(self.world.routine_batch()['unverified_release'])
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(self.world.active['people'],before)
        self.assertIsNone(self.world.pending(self.obs['session']))


if __name__=='__main__':unittest.main()
