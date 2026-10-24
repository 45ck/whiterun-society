import copy
import unittest
from tools.verify_plan_save import snapshot

class SaveObservationTests(unittest.TestCase):
    def setUp(self):
        self.state={'society':{'checkpoint':1,'plan':None,'people':{'7':{},'8':{}}},'world':{},'bridge':{'observation':{
            'residents':[{'id':7,'inventory':{'gold':3}},{'id':8,'inventory':{'gold':4}}],
            'inventory_observations':[{'id':7,'inventory':{'gold':3}},{'id':8,'inventory':{'gold':4}}]}}}
        self.before=copy.deepcopy(snapshot(self.state))

    def test_unloading_preserves_comparison_of_same_native_accounts(self):
        self.state['bridge']['observation']['residents'].pop()
        self.assertEqual(snapshot(self.state,self.before['inventory']),self.before)

    def test_unloaded_balance_change_or_missing_observation_still_fails(self):
        self.state['bridge']['observation']['residents'].pop()
        self.state['bridge']['observation']['inventory_observations'][1]['inventory']['gold']=0
        after=snapshot(self.state,self.before['inventory'])
        self.assertNotEqual(after['inventory'],self.before['inventory'])
        self.assertNotEqual(after['asset_inventory'],self.before['asset_inventory'])
        self.state['bridge']['observation']['inventory_observations'].pop()
        self.assertNotIn('8',snapshot(self.state,self.before['inventory'])['inventory'])

    def test_loaded_observation_cannot_be_hidden_by_stale_accounting_read(self):
        self.state['bridge']['observation']['residents'][1]['inventory']['gold']=0
        self.assertNotEqual(snapshot(self.state,self.before['inventory']),self.before)

if __name__=='__main__':unittest.main()
