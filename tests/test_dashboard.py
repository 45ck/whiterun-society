import unittest
import copy
from dashboard import town_dashboard

class DashboardTests(unittest.TestCase):
    def test_background_activity_control_requires_matching_job_rest_and_current_owned_package(self):
        job={'id':'rest-1','actor':1,'target':8,'slot':0,'session':'s','epoch':'e','phase':'running'}
        society={'town':{'residents':{'1':{}}},'activity_jobs':{'epoch':'e','jobs':[job],'history':[]}}
        native={**job,'job_id':'rest-1','phase':'resting','rest':{'id':'rest-1','actor':1,'target':8,
            'route':{'actor':1,'ownedPackage':True,'expectedPackage':55}}}
        obs={'session':'s','residents':[{'id':1,'isPerson':True,'activity':{'package_id':55}}],
             'activity_jobs':{'session':'s','epoch':'e','capacity':2,'jobs':[native]}}
        self.assertEqual(town_dashboard(society,obs)['control']['agent'],1)
        cases=[('actor_package',66),('owned',False),('expected',None),('expected',True),
               ('session','old'),('inner_actor',2),('inner_id','old'),('route_actor',2)]
        for field,value in cases:
            with self.subTest(field=field,value=value):
                current=copy.deepcopy(obs);row=current['activity_jobs']['jobs'][0]
                if field=='actor_package':current['residents'][0]['activity']['package_id']=value
                elif field=='session':row['session']=value
                elif field=='inner_actor':row['rest']['actor']=value
                elif field=='inner_id':row['rest']['id']=value
                elif field=='route_actor':row['rest']['route']['actor']=value
                else:row['rest']['route']['ownedPackage' if field=='owned' else 'expectedPackage']=value
                self.assertEqual(town_dashboard(society,current)['control']['agent'],0)

    def test_control_is_mutually_exclusive_and_requires_current_native_package(self):
        society={'town':{'residents':{str(i):{} for i in range(1,7)}}}
        obs={'residents':[{'id':i,'isPerson':True,'activity':a} for i,a in [(1,{'package_id':55}),(2,{'scene_id':8,'package_id':2}),(3,{'package_id':9}),(4,{}),(5,{'package_id':66})]],
             'parallel_routines':{'activities':[{'actor':1,'ownedPackage':True,'expectedPackage':55},{'actor':5,'ownedPackage':True,'expectedPackage':55}]}}
        result=town_dashboard(society,obs)
        self.assertEqual(result['control'],{'agent':1,'standby':0,'scene':1,'native':2,'unknown':1,'unloaded':1})
        self.assertEqual(sum(result['control'].values()),result['population'])

    def test_resources_deduplicate_accounts_exclude_unknown_and_unmanaged(self):
        society={'town':{'residents':{'1':{},'2':{},'3':{}}}}
        obs={'residents':[{'id':1,'isPerson':True,'inventory':{'gold':7}},{'id':99,'isPerson':True,'inventory':{'gold':999}}],
             'inventory_observations':[{'id':1,'inventory':{'gold':100}},{'id':2,'inventory':{'gold':0,'bread':False}},{'id':3,'inventory':{'gold':-1}}]}
        result=town_dashboard(society,obs)
        self.assertEqual(result['stock']['gold'],{'total':7,'accounts':2,'population':3})
        self.assertEqual(result['stock']['bread']['total'],None)
        self.assertIsNone(result['economy']['committed_sales'])

    def test_standby_is_separate_from_meaningful_activity_and_stale_evidence(self):
        society={'town':{'residents':{str(i):{} for i in range(1,5)}}}
        obs={'residents':[{'id':i,'isPerson':True,'activity':{'package_id':100 if i!=2 else 42,**({'scene_id':888} if i==3 else {})}} for i in range(1,4)],
             'resident_control':{'activities':[{'actor':i,'ownedPackage':True,'expectedPackage':100} for i in range(1,5)]}}
        self.assertEqual(town_dashboard(society,obs)['control'],{'agent':0,'standby':1,'scene':1,'native':1,'unknown':0,'unloaded':1})

    def test_needs_keep_missing_and_invalid_values_out_of_denominator(self):
        society={'town':{'residents':{str(i):{} for i in range(5)}},'people':{str(i):{'needs':{'hunger':v}} for i,v in enumerate([.7,0,None,float('nan'),True])}}
        result=town_dashboard(society,{})
        self.assertEqual(result['needs']['hunger'],{'high':1,'known':2,'threshold':.6})
        self.assertEqual(result['needs']['fatigue']['known'],0)
