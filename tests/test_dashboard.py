import unittest
from dashboard import town_dashboard

class DashboardTests(unittest.TestCase):
    def test_control_is_mutually_exclusive_and_requires_current_native_package(self):
        society={'town':{'residents':{str(i):{} for i in range(1,7)}}}
        obs={'residents':[{'id':i,'isPerson':True,'activity':a} for i,a in [(1,{'package_id':55}),(2,{'scene_id':8,'package_id':2}),(3,{'package_id':9}),(4,{}),(5,{'package_id':66})]],
             'parallel_routines':{'activities':[{'actor':1,'ownedPackage':True,'expectedPackage':55},{'actor':5,'ownedPackage':True,'expectedPackage':55}]}}
        result=town_dashboard(society,obs)
        self.assertEqual(result['control'],{'agent':1,'scene':1,'native':2,'unknown':1,'unloaded':1})
        self.assertEqual(sum(result['control'].values()),result['population'])

    def test_resources_deduplicate_accounts_exclude_unknown_and_unmanaged(self):
        society={'town':{'residents':{'1':{},'2':{},'3':{}}}}
        obs={'residents':[{'id':1,'isPerson':True,'inventory':{'gold':7}},{'id':99,'isPerson':True,'inventory':{'gold':999}}],
             'inventory_observations':[{'id':1,'inventory':{'gold':100}},{'id':2,'inventory':{'gold':0,'bread':False}},{'id':3,'inventory':{'gold':-1}}]}
        result=town_dashboard(society,obs)
        self.assertEqual(result['stock']['gold'],{'total':7,'accounts':2,'population':3})
        self.assertEqual(result['stock']['bread']['total'],None)
        self.assertIsNone(result['economy']['committed_sales'])

    def test_needs_keep_missing_and_invalid_values_out_of_denominator(self):
        society={'town':{'residents':{str(i):{} for i in range(5)}},'people':{str(i):{'needs':{'hunger':v}} for i,v in enumerate([.7,0,None,float('nan'),True])}}
        result=town_dashboard(society,{})
        self.assertEqual(result['needs']['hunger'],{'high':1,'known':2,'threshold':.6})
        self.assertEqual(result['needs']['fatigue']['known'],0)
