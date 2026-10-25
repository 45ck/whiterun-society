import copy
import unittest

from activity_leases import (paid_work_reservations,reserved_activity_actors,
    reserved_work_accounts,work_account_conflict,activity_conflict)


class PaidWorkReservationTests(unittest.TestCase):
    def job(self,**changes):
        return {'worker':17,'employer':19,'worker_base_id':1017,'employer_base_id':1019,
            'business_id':'bakery','phase':'running','receipt_acknowledged':False,
            'release_verified':False,'effect_unreconciled':False,**changes}

    def test_worker_employer_accounts_and_business_remain_exclusive(self):
        state={'paid_work_jobs':{'job':self.job()}}
        self.assertEqual(reserved_activity_actors(state),{17,19})
        self.assertEqual(reserved_work_accounts(state),{'native-inventory:17','native-inventory:19'})
        self.assertTrue(work_account_conflict(state,business_ids=['bakery']))
        self.assertFalse(work_account_conflict(state,actors=[23],business_ids=['forge']))
        self.assertTrue(activity_conflict(state,actors=[19],include_identity=False))

    def test_cleanup_requires_all_three_proofs(self):
        released=self.job(phase='complete',receipt_acknowledged=True,release_verified=True,effect_unreconciled=False)
        self.assertEqual(paid_work_reservations({'paid_work_jobs':{'job':released}}),(set(),set()))
        for key,value in (('receipt_acknowledged',False),('release_verified',False),('effect_unreconciled',True),('effect_unreconciled',None)):
            with self.subTest(key=key,value=value):
                self.assertEqual(paid_work_reservations({'paid_work_jobs':{'job':{**released,key:value}}})[0],{17,19})

    def test_native_orphans_and_explicit_reserved_accounts_survive_saved_rollback(self):
        obs={'paid_employment':{'jobs':[],'receipts':[self.job(phase='held',effect_unreconciled=True)],'reserved_actors':[23]}}
        self.assertEqual(paid_work_reservations({},obs),({17,19,23},{'bakery'}))
        self.assertTrue(work_account_conflict({},actors=[19],observation=obs))

    def test_public_history_is_free_only_when_ack_release_and_reconciliation_are_proved(self):
        complete=self.job(phase='complete',receipt_acknowledged=True,release_verified=True)
        state={'paid_employment':{'jobs':[],'history':[complete]}}
        self.assertEqual(paid_work_reservations(state),(set(),set()))
        state['paid_employment']['history'][0]['effect_unreconciled']=True
        self.assertEqual(paid_work_reservations(state),({17,19},{'bakery'}))

    def test_malformed_orphan_preserves_known_hints_and_quarantines_available_accounts(self):
        state={'people':{'31':{}},'town':{'residents':{'37':{}},'businesses':{'forge':{}}},
            'paid_work_orphans':{'orphan':self.job(worker=None,employer=19,business_id=None)}}
        obs={'residents':[{'id':41}],'inventory_observations':[{'id':43}]}
        self.assertEqual(paid_work_reservations(state,obs),({19,31,37,41,43},{'forge'}))

    def test_malformed_native_collection_never_means_no_active_jobs(self):
        for bad in (None,False,{'unexpected':'map'}):
            with self.subTest(bad=bad):
                self.assertEqual(paid_work_reservations({'people':{'17':{}}},
                    {'paid_employment':{'receipts':bad}})[0],{17})

    def test_identity_cleanup_exception_cannot_drop_partial_wage_reservations(self):
        state={'paid_work_orphans':{'old':self.job(phase='held',release_verified=True,effect_unreconciled=True)}}
        self.assertTrue(activity_conflict(state,actors=[17,19],include_identity=False))
        self.assertTrue(work_account_conflict(state,business_ids=['bakery']))

    def test_reading_reservations_does_not_mutate_jobs_or_reassign_changed_bases(self):
        state={'paid_work_jobs':{'job':self.job()}};before=copy.deepcopy(state)
        obs={'residents':[{'id':17,'baseId':2017},{'id':19,'baseId':2019}]}
        self.assertEqual(paid_work_reservations(state,obs)[0],{17,19})
        self.assertEqual(state,before)


if __name__=='__main__':unittest.main()
