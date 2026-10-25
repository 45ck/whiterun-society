import copy
import unittest

from activity_leases import (activity_conflict, identity_quarantine_actors,
    reserved_activity_actors, reserved_work_accounts, work_account_conflict)
from routing import route_available


class IdentityReservationTests(unittest.TestCase):
    def fixture(self):
        binding={'schema_version':1,'actor':17,'base_id':1017,'event_id':'census-a',
                 'source_checkpoint':1,'observed_session':'session-a'}
        state={'people':{'17':{'identity_binding':copy.deepcopy(binding)}},
               'town':{'residents':{'17':{'id':17,'identity_binding':binding}}}}
        obs={'ready':True,'session':'session-a','checkpoint':2,
             'routing':{'adapter':'papyrus-mailbox-v1','available':True},
             'residents':[{'id':17,'baseId':1017,'isPerson':True,'loaded':True},
                          {'id':19,'baseId':1019,'isPerson':True,'loaded':True}]}
        return state,obs

    def test_matching_identity_permits_disjoint_new_activity(self):
        state,obs=self.fixture()
        self.assertEqual(identity_quarantine_actors(state,obs),set())
        self.assertFalse(activity_conflict(state,actors=[17],observation=obs))
        self.assertTrue(route_available(obs,17,19,state))

    def test_changed_base_excludes_actor_route_and_business_account(self):
        state,obs=self.fixture();obs['residents'][0]['baseId']=2017
        before=copy.deepcopy(state)
        self.assertEqual(identity_quarantine_actors(state,obs),{17})
        self.assertEqual(reserved_work_accounts(state,obs),{'native-inventory:17'})
        self.assertTrue(work_account_conflict(state,actors=[17],observation=obs))
        self.assertFalse(route_available(obs,17,19,state))
        self.assertFalse(activity_conflict(state,actors=[19],observation=obs))
        self.assertEqual(state,before)

    def test_missing_or_duplicate_native_witness_cannot_certify_identity(self):
        for change in ('base','row','duplicate','observation'):
            with self.subTest(change=change):
                state,obs=self.fixture()
                if change=='base':obs['residents'][0].pop('baseId')
                elif change=='row':obs['residents'].pop(0)
                elif change=='duplicate':obs['residents'].append(copy.deepcopy(obs['residents'][0]))
                else:obs=None
                self.assertEqual(identity_quarantine_actors(state,obs),{17})

    def test_legacy_census_binding_cannot_be_inferred_from_current_base(self):
        state,obs=self.fixture()
        state['town']['residents']['17'].pop('identity_binding')
        state['people']['17'].pop('identity_binding')
        self.assertEqual(identity_quarantine_actors(state,obs),{17})
        self.assertNotIn('identity_binding',state['town']['residents']['17'])

    def test_conflicting_person_and_census_bindings_remain_excluded(self):
        state,obs=self.fixture();state['people']['17']['identity_binding']['base_id']=2017
        self.assertEqual(identity_quarantine_actors(state,obs),{17})

    def test_precensus_historical_people_do_not_gain_a_fabricated_binding(self):
        state,obs=self.fixture();state.pop('town')
        state['people']['17'].pop('identity_binding')
        before=copy.deepcopy(state)
        self.assertEqual(identity_quarantine_actors(state,obs),set())
        self.assertEqual(state,before)

    def test_cleanup_can_bypass_only_identity_admission_exclusion(self):
        state,obs=self.fixture();obs['residents'][0]['baseId']=2017
        self.assertTrue(activity_conflict(state,actors=[17],observation=obs))
        self.assertFalse(activity_conflict(state,actors=[17],observation=obs,include_identity=False))
        leases=[{'activity_jobs':{'job':{'actor':17,'receipt_acknowledged':False}}},
                {'work_jobs':{'job':{'actor':17,'receipt_acknowledged':False}}},
                {'pending':{'status':'held','command':{'kind':'inventory_trade','buyer':17,'seller':19}}},
                {'pending':{'status':'held','command':{'kind':'inventory_endowment','actor':17}}}]
        for lease in leases:
            with self.subTest(lease=lease):
                self.assertTrue(activity_conflict({**state,**lease},actors=[17],observation=obs,include_identity=False))

    def test_native_orphan_leases_survive_identity_cleanup_exception(self):
        state,obs=self.fixture();obs['residents'][0]['baseId']=2017
        obs['activity_jobs']={'reserved_actors':[17]}
        self.assertEqual(reserved_activity_actors(state,obs,include_identity=False),{17})


if __name__=='__main__':unittest.main()
