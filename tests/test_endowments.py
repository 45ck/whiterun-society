import copy
import unittest
import test_population
from endowments import CAPACITY


class EndowmentTests(unittest.TestCase):
    tearDown=test_population.PopulationTests.tearDown
    sync=test_population.PopulationTests.sync
    census=test_population.PopulationTests.census
    def setUp(self):
        test_population.PopulationTests.setUp(self);self.census()
        self.world.initialize_population('start','seed',self.obs);self.sync()

    def deliver(self,actor=99):
        self.world.plan_endowment(actor,self.obs);self.sync()
        command=self.world.pending(self.obs['session'])
        native=next(a for a in self.obs['residents'] if a['id']==actor)
        native['inventory']=command['after'].copy()
        self.obs['ack']={'id':command['id'],'status':'applied'}
        self.world.observe(self.obs);self.sync();return command

    def test_delivery_requires_bound_intent_then_debits_the_finite_pool(self):
        before=copy.deepcopy(self.obs);self.world.plan_endowment(99,self.obs)
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'bind_checkpoint')
        self.assertEqual(self.obs,before);self.sync()
        command=self.world.pending(self.obs['session']);self.assertEqual(command['grant'],{'gold':20,'bread':2,'grain':0})
        self.assertEqual(self.world.active['town']['resource_program']['remaining'],CAPACITY)
        self.obs['residents'][2]['inventory']=command['after'].copy()
        self.obs['ack']={'id':command['id'],'status':'applied'};self.world.observe(self.obs);self.sync()
        program=self.world.status()['town']['resource_program']
        self.assertEqual(program['remaining'],{'gold':980,'bread':98,'grain':100})
        self.assertEqual(self.world.state(),[]);self.assertEqual(self.world.status()['production'],[])
        self.assertEqual(self.world.active['people']['99']['memories'][-1]['kind'],'starting_resources_received')

    def test_repeated_request_cannot_mint_again_under_another_event_id(self):
        self.deliver();before=copy.deepcopy(self.world.active)
        self.assertTrue(self.world.plan_endowment(99,self.obs)['duplicate']);self.assertEqual(before,self.world.active)

    def test_business_receives_finite_inputs_and_working_cash_in_owner_inventory(self):
        command=self.deliver(108149)
        self.assertEqual(command['grant'],{'gold':100,'bread':2,'grain':20})
        self.assertEqual(self.world.active['town']['resource_program']['remaining'],{'gold':900,'bread':98,'grain':80})

    def test_pool_exhaustion_does_not_partially_prepare_a_grant(self):
        self.deliver();self.world.active['town']['resource_program']['remaining']['bread']=1
        old=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'exhausted'):self.world.plan_endowment(108149,self.obs)
        self.assertEqual(old,self.world.active);self.assertIsNone(self.world.transition)

    def test_false_acknowledgement_holds_without_debit_or_memory(self):
        self.world.plan_endowment(99,self.obs);self.sync();command=self.world.pending(self.obs['session'])
        self.obs['ack']={'id':command['id'],'status':'applied'};self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.status()['resource_delivery']['status'],'held')
        self.assertEqual(self.world.active['town']['resource_program']['remaining'],CAPACITY)
        self.assertEqual(self.world.active['people']['99']['memories'],[])

    def test_load_before_grant_removes_future_resources_and_memory_from_accounting(self):
        old=copy.deepcopy(self.obs);self.deliver();self.world.observe({**old,'session':'past'})
        self.assertNotIn('resource_program',self.world.active['town'])
        self.assertEqual(self.world.active['people']['99']['memories'],[])

    def test_load_mid_delivery_reuses_the_same_contract_and_records_once(self):
        self.world.plan_endowment(99,self.obs);self.sync();command=self.world.pending(self.obs['session'])
        self.obs['residents'][2]['inventory']['gold']=command['after']['gold']
        self.obs['session']='reload-middle';self.world.observe(self.obs)
        self.assertEqual(self.world.pending(self.obs['session'])['id'],command['id'])
        self.obs['residents'][2]['inventory']=command['after'].copy();self.obs['ack']={'id':command['id'],'status':'applied'}
        self.world.observe(self.obs);self.sync();self.world.observe(self.obs)
        self.assertEqual(len(self.world.active['town']['resource_program']['grants']),1)
        self.assertEqual(self.world.active['town']['resource_program']['remaining']['gold'],980)

    def test_unknown_or_unclassified_resident_cannot_receive_resources(self):
        with self.assertRaisesRegex(ValueError,'Initialize'):self.world.plan_endowment(100,self.obs)
        self.obs['residents'][2]['isPerson']=False
        with self.assertRaisesRegex(ValueError,'classified'):self.world.plan_endowment(99,self.obs)
        self.assertIsNone(self.world.transition)

    def test_unloaded_accounting_observation_can_receive_grant_without_becoming_a_visible_resident(self):
        actor=self.obs['residents'].pop(2);actor['loaded']=False
        self.obs['inventory_observations']=[actor]
        self.world.plan_endowment(99,self.obs);self.sync();command=self.world.pending(self.obs['session'])
        actor['inventory']=command['after'].copy();self.obs['ack']={'id':command['id'],'status':'applied'}
        self.world.observe(self.obs);self.sync()
        self.assertIn('99',self.world.active['town']['resource_program']['grants'])
        self.assertNotIn(99,[a['id'] for a in self.obs['residents']])
