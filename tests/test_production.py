from catalog_fixture import native_ack
import copy
import unittest
import test_food
from production import work_inventory


class ProductionTests(unittest.TestCase):
    # Reuse fixtures, not inherited test cases.
    def setUp(self):
        test_food.FoodTests.setUp(self)
        for actor in self.obs['residents']:
            actor['inventory']['grain'] = 2 if actor['id']==108149 else 0

    tearDown = test_food.FoodTests.tearDown
    sync = test_food.FoodTests.sync
    decide = test_food.FoodTests.decide

    def start_work(self):
        self.world.begin_plan('job',self.obs, 108186,kind='work_shift');self.sync()
        self.decide('offer_shift','job');self.decide('take_shift','job')
        plan=self.world.agency_plan()
        self.obs['ack']={'id':plan['travel_id'],'status':'applied','movement':{'hasOwnedPackage':True,'expectedPackage':99}}
        self.world.observe(self.obs);self.sync()

    def test_offer_and_worker_consent_precede_any_effect(self):
        self.world.begin_plan('job',self.obs, 108186,kind='work_shift');self.sync()
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual(context['actor_id'],108149)
        self.decide('offer_shift','job')
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual(context['actor_id'],108186)
        self.assertEqual(context['observed_inventory']['grain'],0)
        self.decide('decline_work','job')
        self.assertEqual(self.world.agency_plan()['outcome'],'work_declined')
        self.assertEqual(self.world.status()['production'],[])

    def test_input_and_wage_shortage_prevent_job_offer(self):
        self.obs['residents'][1]['inventory']['grain']=0
        self.world.begin_plan('job',self.obs, 108186,kind='work_shift');self.sync()
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual([o['id'] for o in context['options']],['defer'])

    def test_paid_work_is_committed_only_after_inventory_verification(self):
        self.start_work();c=self.world.pending(self.obs['session'])
        self.assertEqual(c['kind'],'inventory_produce')
        before=copy.deepcopy(self.obs)
        for a in self.obs['residents']:a['inventory']=c['after']['worker' if a['id']==108186 else 'employer'].copy()
        self.obs['ack']=native_ack(c)
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['outcome'],'paid_work_completed')
        self.assertEqual(len(self.world.status()['production']),1)
        self.assertEqual(self.world.state(),[])
        self.assertEqual(sum(a['inventory']['gold'] for a in self.obs['residents']),17)
        self.world.observe({**before,'session':'prior-work-save'})
        self.assertEqual(self.world.status()['production'],[])
        self.assertEqual(self.world.pending('prior-work-save')['kind'],'inventory_produce')

    def test_ack_without_production_effect_holds_no_success_memory(self):
        self.start_work();c=self.world.pending(self.obs['session'])
        self.obs['ack']=native_ack(c);self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(self.world.status()['production'],[])

    def test_explicit_import_is_bounded_persistent_and_separate_from_production(self):
        self.world.setup_production(self.obs);self.sync();c=self.world.pending(self.obs['session'])
        self.obs['residents'][1]['inventory']=c['after']['employer'].copy()
        self.obs['ack']=native_ack(c);self.world.observe(self.obs);self.sync()
        self.assertTrue(self.world.setup_production(self.obs)['duplicate'])
        self.assertEqual(len(self.world.status()['imports']),1)
        self.assertEqual(self.world.status()['production'],[])
