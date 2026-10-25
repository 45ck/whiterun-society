import unittest
from activity_leases import trade_quarantine_actors, reserved_activity_actors, reserved_work_accounts


class TradeReservationTests(unittest.TestCase):
    def record(self,status='held',buyer=7,seller=8):
        return {'status':status,'command':{'kind':'inventory_trade','buyer':buyer,'seller':seller}}

    def test_saved_and_native_trade_leases_reserve_both_people_and_accounts(self):
        for key in ('pending','unsettled_effect'):
            for status in ('pending','held'):
                state={key:self.record(status)}
                obs={'trade_execution':{'reserved_actors':[9,10]}}
                self.assertEqual(reserved_activity_actors(state,obs),{7,8,9,10})
                self.assertEqual(reserved_work_accounts(state,obs),{'native-inventory:'+str(a) for a in (7,8,9,10)})

    def test_completed_history_does_not_lease_accounts(self):
        self.assertEqual(trade_quarantine_actors({'pending':self.record('committed'),'trades':[self.record()]}),set())

    def test_unknown_participant_reserves_every_observed_account(self):
        state={'pending':self.record(buyer=None),'people':{'7':{},'0003':{}},'town':{'residents':{'9':{}}}}
        obs={'residents':[{'id':11}],'inventory_observations':[{'id':12}]}
        self.assertEqual(trade_quarantine_actors(state,obs),{7,8,9,11,12})

    def test_invalid_native_lease_does_not_free_population(self):
        self.assertEqual(trade_quarantine_actors({'people':{'7':{}}}, {'trade_execution':{'reserved_actors':[None]}}),{7})


if __name__=='__main__':unittest.main()
