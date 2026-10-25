import unittest
from activity_leases import resource_quarantine_actors, reserved_activity_actors, reserved_work_accounts, activity_conflict, work_account_conflict


class ResourceReservationTests(unittest.TestCase):
    def record(self,actor=17,status='pending'):
        return {'status':status,'command':{'kind':'inventory_endowment','actor':actor,'protocol':2}}

    def test_pending_and_held_imports_reserve_recipient_and_account(self):
        for status in ('pending','held'):
            with self.subTest(status=status):
                state={'pending':self.record(status=status)}
                self.assertEqual(reserved_activity_actors(state),{17})
                self.assertEqual(reserved_work_accounts(state),{'native-inventory:17'})
                self.assertTrue(activity_conflict(state,actors=[17]))
                self.assertTrue(work_account_conflict(state,actors=[17]))
                self.assertFalse(activity_conflict(state,actors=[19]))

    def test_projected_delivery_and_native_arms_survive_absent_saved_pending(self):
        state={'resource_delivery':self.record(23,'held')}
        obs={'resource_import':{'reserved_actors':[29]}}
        self.assertEqual(resource_quarantine_actors(state,obs),{23,29})
        self.assertTrue(work_account_conflict(state,actors=[29],observation=obs))

    def test_completed_history_does_not_reserve_purses(self):
        state={'pending':self.record(status='committed'),'resource_delivery':self.record(status='complete'),
            'town':{'resource_program':{'grants':{'17':self.record(status='held')}}}}
        self.assertEqual(resource_quarantine_actors(state),set())

    def test_conflicting_known_recipient_identities_reserve_the_union(self):
        record=self.record();record.update(actor=19,recipient={'actor':23})
        self.assertEqual(resource_quarantine_actors({'pending':record}),{17,19,23})

    def test_missing_identity_reserves_all_managed_and_observed_accounts(self):
        state={'pending':self.record(None,'held'),'people':{'17':{},'0018':{},'bad':{}},'town':{'residents':{'19':{}}}}
        obs={'residents':[{'id':23},{'id':True}],'inventory_observations':[{'id':29}]}
        self.assertEqual(resource_quarantine_actors(state,obs),{17,19,23,29})

    def test_malformed_native_reservations_remain_conservative(self):
        for native in ([None],False,{'17':True}):
            with self.subTest(native=native):
                self.assertEqual(resource_quarantine_actors({'people':{'17':{}}},{'resource_import':{'reserved_actors':native}}),{17})

    def test_non_resource_pending_is_not_a_resource_lease(self):
        self.assertEqual(resource_quarantine_actors({'pending':{'status':'held','command':{'kind':'walk_to','actor':17}}}),set())


if __name__=='__main__':unittest.main()
