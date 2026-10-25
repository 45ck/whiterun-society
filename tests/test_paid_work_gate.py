"""Legacy paid work cannot turn observed balances into execution authority."""
import copy
import unittest
from production import Production
from paid_work_policy import paid_work_capability


class SavedWorld(Production):
    def __init__(self):
        self.writes=[]
        self.active={'pending':{'id':'produce-old','status':'pending','command':{
            'id':'produce-old','kind':'inventory_produce','worker':11,'employer':12,
            'before':{'worker':{'gold':2},'employer':{'gold':8}},
            'after':{'worker':{'gold':4},'employer':{'gold':6}}}},
            'plans':[{'id':'old','actor':11,'target':12,'phase':'working'},
                     {'id':'unrelated','actor':13,'target':14,'phase':'thinking'}],
            'production':[{'id':'historic','status':'committed'}],
            'people':{'11':{'memories':[],'known_recipes':[]}}}
    def _write(self,state,reason):
        self.active=state;self.writes.append(reason)


class PaidWorkGateTests(unittest.TestCase):
    def test_capability_is_unavailable_and_defensive(self):
        result=paid_work_capability();result['available']=True
        self.assertFalse(paid_work_capability()['available'])

    def test_direct_admission_rejects_before_guard_checkpoint_or_native_data(self):
        world=SavedWorld();before=copy.deepcopy(world.active)
        with self.assertRaisesRegex(ValueError,'legacy_paid_execution_unqualified'):
            world.plan_production({},None)
        self.assertEqual(world.active,before);self.assertEqual(world.writes,[])

    def test_no_ack_wrong_ack_applied_and_no_effect_acks_all_quarantine(self):
        for ack in (None,{'id':'other','status':'applied'},
                    {'id':'produce-old','status':'applied'},
                    {'id':'produce-old','status':'held','no_effects_issued':True}):
            with self.subTest(ack=ack):
                world=SavedWorld();before=copy.deepcopy(world.active)
                world.observe_production({'ack':ack})
                self.assertEqual(world.active['pending']['status'],'held')
                self.assertIsNone(world.active['pending']['effects_issued'])
                self.assertFalse(world.active['pending']['no_effects_issued'])
                self.assertEqual(world.active['plans'][0]['phase'],'held')
                self.assertEqual(world.active['plans'][1],before['plans'][1])
                self.assertEqual(world.active['people'],before['people'])
                self.assertEqual(world.active['production'],before['production'])
                self.assertNotIn('cancelled_production',world.active)
                world.observe_production({'ack':{'id':'produce-old','status':'applied'}})
                self.assertEqual(len(world.writes),1)

    def test_changed_participants_or_unrelated_plan_never_get_settled(self):
        for change in ({'actor':99},{'target':99},{'id':'different'},{'phase':'complete'}):
            world=SavedWorld();world.active['plans'][0].update(change)
            before=copy.deepcopy(world.active['plans'])
            world.observe_production({})
            self.assertEqual(world.active['plans'],before)
            self.assertEqual(world.active['pending']['status'],'held')

    def test_missing_charter_and_missing_history_still_hold_safely(self):
        world=SavedWorld();world.active['plans'][0]['work_terms']={'business_id':'gone'}
        world.observe_production({});self.assertEqual(world.active['pending']['status'],'held')
        world=SavedWorld();world.active.pop('plans');world.observe_production({})
        self.assertEqual(world.active['pending']['status'],'held')

    def test_matching_employment_contract_is_held_without_claiming_payment_or_hiring(self):
        world=SavedWorld();world.active['plans'][0]['work_terms']={'business_id':'shop'}
        world.active['town']={'businesses':{'shop':{'workers':[], 'contracts':[
            {'id':'old','status':'accepted'}, {'id':'prior','status':'completed','production_id':'historic'}]}}}
        world.observe_production({'ack':{'id':'produce-old','status':'applied'}})
        business=world.active['town']['businesses']['shop']
        self.assertEqual(business['contracts'][0],{'id':'old','status':'held','outcome':'reconciliation_required'})
        self.assertEqual(business['contracts'][1],{'id':'prior','status':'completed','production_id':'historic'})
        self.assertEqual(business['workers'],[])
