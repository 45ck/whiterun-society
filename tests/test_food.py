import copy
import tempfile
import unittest
from pathlib import Path
from lineage import TimelineEconomy
from food import allocation
from catalog_fixture import native_catalog, native_ack


class FoodTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.world=TimelineEconomy(Path(self.temp.name)/'timeline.sqlite')
        self.obs={'session':'food-test','checkpoint':0,'ready':True,'economy_catalog':native_catalog(),'residents':[
            {'id':108186,'x':0,'y':0,'z':0,'inventory':{'gold':12,'bread':1,'grain':0}},
            {'id':108149,'x':100,'y':0,'z':0,'inventory':{'gold':5,'bread':3,'grain':0}}]}
        self.obs['routing']={'adapter':'papyrus-mailbox-v1','available':True}
        for resident in self.obs['residents']:resident['isPerson']=True
        self.world.observe(self.obs);self.world.bootstrap(self.obs);self.sync()

    def tearDown(self):
        self.world.db.close();self.temp.cleanup()

    def sync(self):
        for _ in range(10):
            if not self.world.transition:return
            self.obs['checkpoint']=self.world.transition['next'];self.obs.pop('ack',None)
            self.world.observe(self.obs)
        self.fail('Checkpoint loop did not settle')

    def decide(self,action,event='food-1'):
        claim=self.world.claim_plan_decision(event,self.obs)['claim'];self.sync()
        self.world.finish_plan_decision(event,claim['id'],{'decision':{
            'action_id':action,'reason':'Authored test choice','emotion':'calm'}},self.obs)
        self.sync()

    def test_allocation_partitions_existing_stock_and_restricts_sale(self):
        before=copy.deepcopy(self.obs)
        self.world.begin_plan('food-1',self.obs,108149,'stock_review');self.sync();self.decide('reserve_one')
        person=self.world.status()['people']['108149']
        stock=allocation(person,{'bread':3})
        self.assertEqual((stock['household'],stock['for_sale']),(1,2))
        self.assertEqual(self.obs['residents'],before['residents'])
        self.assertEqual(person['needs']['hunger'],.4)
        with self.assertRaisesRegex(ValueError,'household reserve'):
            self.world.plan_trade('too-many',self.obs,108186,108149,quantity=3)
        self.world.plan_trade('surplus',self.obs,108186,108149,quantity=2)
        self.sync();self.assertEqual(self.world.pending('food-test')['after']['seller']['bread'],1)

    def test_reserve_policy_does_not_invent_stock_or_leak_to_buyer(self):
        self.world.begin_plan('food-1',self.obs,108149,'stock_review');self.sync();self.decide('reserve_two')
        stock=allocation(self.world.active['people']['108149'],{'bread':1})
        self.assertEqual((stock['household'],stock['for_sale']),(1,0))
        self.world.begin_plan('buyer',self.obs, 108186);self.sync()
        context=self.world.claim_plan_decision('buyer',self.obs)['claim']['context']
        self.assertEqual(context['own_food_allocation'],{'allocated':False,'unallocated':1})

    def test_consumption_binds_intent_then_observes_effect_before_hunger_changes(self):
        self.obs['residents'][0]['inventory']['grain']=4
        self.world.begin_plan('food-1',self.obs, 108186);self.sync()
        self.decide('eat_bread')
        c=self.world.pending('food-test')
        self.assertEqual(c['kind'],'inventory_consume')
        self.assertEqual(c['catalog_hash'],native_catalog()['catalog_hash'])
        self.assertEqual((c['before']['grain'],c['after']['grain']),(4,4))
        self.assertEqual(self.world.status()['people']['108186']['needs']['hunger'],.75)
        before=copy.deepcopy(self.obs)
        self.obs['residents'][0]['inventory']=c['after'].copy()
        self.obs['ack']=native_ack(c)
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['outcome'],'ate_bread')
        self.assertEqual(self.world.status()['people']['108186']['needs']['hunger'],.15)
        self.assertEqual(len(self.world.status()['consumptions']),1)
        self.assertEqual(self.world.state(),[])  # Food use is not counted as a sale.
        self.world.observe(self.obs);self.assertIsNone(self.world.transition)
        self.world.observe({**before,'session':'older-consumption-save'})
        self.assertEqual(self.world.pending('older-consumption-save')['kind'],'inventory_consume')
        self.assertEqual(self.world.status()['people']['108186']['needs']['hunger'],.75)

    def test_ack_without_inventory_effect_cannot_reduce_hunger(self):
        self.world.begin_plan('food-1',self.obs, 108186);self.sync();self.decide('eat_bread')
        c=self.world.pending('food-test');self.obs['ack']=native_ack(c)
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(self.world.status()['people']['108186']['needs']['hunger'],.75)
        self.assertEqual(self.world.status()['consumptions'],[])

    def test_consumption_rejects_unverified_catalog_without_food_or_need_effects(self):
        self.world.begin_plan('food-1',self.obs, 108186);self.sync()
        # Authored ready decision fixture isolates the inventory-intent boundary.
        self.world.agency_plan()['phase']='ready_to_eat'
        before=copy.deepcopy(self.world.active)
        for catalog in (None, {**native_catalog(),'catalog_hash':'other'}, {**native_catalog(),'type_verified':False}):
            obs=copy.deepcopy(self.obs)
            if catalog is None:obs.pop('economy_catalog')
            else:obs['economy_catalog']=catalog
            with self.assertRaisesRegex(ValueError,'catalog'):self.world.plan_consumption('unverified',obs,108186,'food-1')
            self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_loading_old_save_removes_later_stock_allocation(self):
        old=copy.deepcopy(self.obs)
        self.world.begin_plan('food-1',self.obs,108149,'stock_review');self.sync();self.decide('reserve_all')
        self.assertEqual(allocation(self.world.active['people']['108149'],{'bread':3})['for_sale'],0)
        self.world.observe({**old,'session':'before-policy'})
        self.assertNotIn('food_policy',self.world.active['people']['108149'])

    def test_event_reuse_cannot_change_actor_or_purpose(self):
        self.world.begin_plan('food-1',self.obs,108149,'stock_review');self.sync();self.decide('reserve_one')
        with self.assertRaisesRegex(ValueError,'reused'):
            self.world.begin_plan('food-1',self.obs,108186,'meal_time')

    def test_other_managed_residents_can_eat_without_asking_to_trade_with_themselves(self):
        self.world.begin_plan('food-1',self.obs,108149,'meal_time');self.sync()
        options=self.world._plan_context(self.obs,self.world.agency_plan())['options']
        self.assertIn('eat_bread',[o['id'] for o in options])
        self.assertNotIn('seek_bread',[o['id'] for o in options])
        self.decide('eat_bread')
        self.assertEqual(self.world.pending('food-test')['actor'],108149)
