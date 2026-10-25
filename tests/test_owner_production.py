import copy
import unittest
import test_daily_life as fixtures
from owner_production import owner_work_opportunities
from metrics import simulation_metrics


class OwnerProductionTests(unittest.TestCase):
    tearDown=fixtures.DailyLifeTests.tearDown
    sync=fixtures.DailyLifeTests.sync
    census=fixtures.DailyLifeTests.census
    review=fixtures.DailyLifeTests.review

    def setUp(self):
        fixtures.DailyLifeTests.setUp(self)
        self.actor=next(a for a in self.obs['residents'] if a['id']==99)
        self.actor.update(x=1,y=2,z=3,activity={'package_id':9000,'scene_id':0,'in_combat':False,'sleep_state':0})
        self.actor['inventory']={'gold':0,'bread':0,'grain':3}
        self.obs['resident_control']={'activities':[{'actor':99,'ownedPackage':True,'expectedPackage':9000}]}
        self.world.active['town']['businesses']={'new-owner':{'owner':99,'custodian':99,'active':True,'capabilities':['bread_recipe'],
            'revision':1,'production_policy':{'wage_gold':4,'work_minutes':10,'target_bread':8}}}
        self.world.active['people']['99']['needs'].update(hunger=.9,fatigue=.1)
        self.policy={'mode':'household_all','observed_bread':0,'reviewed_day':self.obs['gameDays']}
        self.world.active['people']['99']['food_policy']=copy.deepcopy(self.policy)
        self.review();self.event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)

    def start(self):
        self.world.begin_plan(self.event['id'],self.obs,99,'need_review');self.sync()
        claim=self.world.claim_plan_decision(self.event['id'],self.obs)['claim'];self.sync()
        return claim

    def decide(self,claim):
        self.world.finish_plan_decision(self.event['id'],claim['id'],{'model':'test-owner','decision':{'action_id':'work_own_new-owner','reason':'Use my grain','emotion':'calm'}},self.obs);self.sync()

    def test_dynamic_owner_without_money_can_choose_finite_production(self):
        claim=self.start();self.assertIn('work_own_new-owner',[o['id'] for o in claim['context']['options']])
        before=copy.deepcopy(self.obs);self.decide(claim);command=self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'],'inventory_self_produce');self.assertEqual(command['after']['owner'],{'gold':0,'bread':2,'grain':2})
        self.assertEqual(self.actor['inventory'],next(a['inventory'] for a in before['residents'] if a['id']==99))
        self.actor['inventory']=command['after']['owner'].copy();self.obs['ack']={'id':command['id'],'status':'applied'}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['outcome'],'owner_work_completed')
        self.assertEqual(self.world.active['people']['99']['food_policy'],self.policy)
        self.assertEqual(self.world.active['people']['99']['needs']['hunger'],.9)
        metrics=simulation_metrics(self.world.active)['economy'];self.assertEqual(metrics['owner_production_batches'],1);self.assertEqual(metrics['gold_conservation']['percent'],100)
        self.world.observe({**before,'session':'previous-owner-save'})
        self.assertEqual(self.world.status()['production'],[])

    def test_owner_cannot_work_other_accounts_missing_grain_or_unowned_package(self):
        self.assertEqual(len(owner_work_opportunities(self.world.active,self.obs,99)),1)
        for field,value in [('owner',108149),('custodian',108149),('active',False)]:
            state=copy.deepcopy(self.world.active);state['town']['businesses']['new-owner'][field]=value
            self.assertEqual(owner_work_opportunities(state,self.obs,99),[])
        self.actor['inventory']['grain']=0;self.assertEqual(owner_work_opportunities(self.world.active,self.obs,99),[])
        self.actor['inventory']['grain']=3;self.actor['activity']['package_id']=42;self.assertEqual(owner_work_opportunities(self.world.active,self.obs,99),[])

    def test_changed_charter_cannot_change_an_inflight_owner_choice(self):
        claim=self.start();self.world.active['town']['businesses']['new-owner']['revision']=2
        with self.assertRaisesRegex(ValueError,'terms changed'):self.decide(claim)
        self.assertEqual(self.world.status()['production'],[])

    def test_ack_without_output_is_held_not_committed(self):
        self.decide(self.start());command=self.world.pending(self.obs['session']);self.obs['ack']={'id':command['id'],'status':'applied'}
        self.world.observe(self.obs);self.sync();self.assertEqual(self.world.agency_plan()['phase'],'held');self.assertEqual(self.world.status()['production'],[])

    def test_interrupted_unstarted_work_preserves_stock_and_can_settle(self):
        self.decide(self.start());command=self.world.pending(self.obs['session']);self.obs['ack']={'id':command['id'],'status':'held','no_effects_issued':True}
        self.world.observe(self.obs);self.sync();self.assertEqual(self.world.agency_plan()['outcome'],'owner_work_interrupted');self.assertIsNone(self.world.active['pending'])
        self.assertEqual(self.actor['inventory'],command['before']['owner']);self.assertEqual(self.world.status()['production'],[])
