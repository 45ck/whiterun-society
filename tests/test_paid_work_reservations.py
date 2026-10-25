import copy
import unittest

from activity_leases import (paid_work_reservations,paid_work_activity_actors,reserved_activity_actors,
    reserved_work_accounts,work_account_conflict,activity_conflict)


class PaidWorkReservationTests(unittest.TestCase):
    def job(self,**changes):
        return {'worker':17,'employer':19,'worker_base_id':1017,'employer_base_id':1019,
            'business_id':'bakery','phase':'running','receipt_acknowledged':False,
            'release_verified':False,'effect_unreconciled':False,**changes}

    def current(self):
        job=self.job(id='paid-job',job_id='paid-job',protocol=2,session='current',epoch='paid-epoch',phase='working')
        state={'paid_work_jobs':{'paid-job':job},'people':{'17':{},'19':{},'23':{}}}
        obs={'ready':True,'session':'current','residents':[
            {'id':actor,'baseId':actor+1000,'isPerson':True} for actor in (17,19,23)],
            'paid_employment':{'available':True,'protocol':2,'session':'current','epoch':'paid-epoch',
                'jobs':[],'receipts':[],'reserved_actors':[17,19]}}
        return state,obs,job

    def test_current_employer_can_move_and_socialize_while_both_purses_stay_reserved(self):
        state,obs,_=self.current()
        self.assertEqual(paid_work_activity_actors(state,obs),{17})
        self.assertEqual(reserved_activity_actors(state,obs),{17})
        self.assertFalse(activity_conflict(state,actors=[19,23],observation=obs))
        self.assertEqual(reserved_work_accounts(state,obs),{'native-inventory:17','native-inventory:19'})
        self.assertTrue(work_account_conflict(state,actors=[19],observation=obs))
        self.assertTrue(work_account_conflict(state,business_ids=['bakery'],observation=obs))

    def test_narrowing_never_subtracts_another_activity_or_account_hold(self):
        for extra in (
            {'activity_jobs':{'rest':{'actor':19}}},
            {'work_jobs':{'owner':{'actor':23,'custodian':19}}},
            {'pending':{'status':'held','command':{'kind':'inventory_trade','buyer':19,'seller':23}}},
            {'pending':{'status':'held','command':{'kind':'inventory_endowment','actor':19}}},
            {'conversation':{'phase':'held','release_required':True,'speakers':[19,23]}},
        ):
            with self.subTest(extra=extra):
                state,obs,_=self.current();state.update(extra)
                self.assertIn(19,reserved_activity_actors(state,obs))
        state,obs,job=self.current()
        state['paid_work_jobs']['other']={**job,'id':'other','job_id':'other','worker':19,'worker_base_id':1019,
            'employer':23,'employer_base_id':1023,'business_id':'forge'}
        self.assertEqual(paid_work_activity_actors(state,obs),{17,19})
        self.assertTrue(work_account_conflict(state,actors=[23],observation=obs))

    def test_no_observation_or_changed_identity_retains_both_participants(self):
        state,obs,_=self.current()
        self.assertEqual(paid_work_activity_actors(state),{17,19})
        for mutate in (
            lambda o:o.update(ready=False),lambda o:o.update(session='loaded-save'),
            lambda o:o['paid_employment'].update(epoch='new-native'),
            lambda o:o['paid_employment'].update(session='other-native'),
            lambda o:o['residents'][1].update(baseId=9999),
            lambda o:o['residents'].pop(1),lambda o:o['residents'].append(copy.deepcopy(o['residents'][1])),
        ):
            changed=copy.deepcopy(obs);mutate(changed)
            self.assertTrue({17,19}<=paid_work_activity_actors(state,changed))

    def test_orphan_held_and_native_only_identity_cannot_free_employer(self):
        for change in ({'phase':'held'},{'cancel_requested':True},{'reset_held':True},
                       {'invalidated':True},{'effect_unreconciled':True},{'orphan':True}):
            state,obs,job=self.current();job.update(change)
            self.assertEqual(paid_work_activity_actors(state,obs),{17,19})
        state,obs,job=self.current();state['paid_work_orphans']=state.pop('paid_work_jobs')
        self.assertEqual(paid_work_activity_actors(state,obs),{17,19})
        state,obs,job=self.current();obs['paid_employment']['jobs']=[job];state['paid_work_jobs']={}
        self.assertEqual(paid_work_activity_actors(state,obs),{17,19})

    def test_native_witness_and_conflicting_duplicate_can_only_add_physical_exclusions(self):
        state,obs,job=self.current();obs['paid_employment']['activity_reserved_actors']=[17,19]
        self.assertEqual(paid_work_activity_actors(state,obs),{17,19})
        state,obs,job=self.current();obs['paid_employment']['receipts']=[{**job,'employer':23,'employer_base_id':1023}]
        self.assertEqual(paid_work_activity_actors(state,obs),{17,19,23})

    def test_malformed_native_activity_hint_preserves_known_hints_and_population(self):
        state,obs,_=self.current();obs['paid_employment']['activity_reserved_actors']=[29,None]
        self.assertEqual(paid_work_activity_actors(state,obs),{17,19,23,29})
        obs['paid_employment'].pop('activity_reserved_actors');obs['paid_employment']['reserved_actors']=[None]
        self.assertEqual(paid_work_activity_actors(state,obs),{17,19,23})

    def test_worker_physical_hold_lasts_through_release_until_exact_ack(self):
        state,obs,job=self.current();job.update(phase='complete',release_verified=True)
        obs['paid_employment']['reserved_actors']=[]
        self.assertEqual(paid_work_activity_actors(state,obs),{17})
        job['receipt_acknowledged']=True
        self.assertEqual(paid_work_activity_actors(state,obs),set())
        self.assertEqual(reserved_work_accounts(state,obs),set())

    def test_qualified_projection_and_native_duplicate_do_not_mutate_authority(self):
        state,obs,job=self.current();state['paid_employment']={'jobs':[copy.deepcopy(job)],'history':[]}
        obs['paid_employment']['jobs']=[{key:value for key,value in job.items() if key!='id'}]
        before=copy.deepcopy((state,obs))
        self.assertEqual(paid_work_activity_actors(state,obs),{17})
        self.assertEqual((state,obs),before)

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
