import copy
import unittest
from unittest.mock import patch
import test_population
from resource_manifest import load_manifest, manifest_hash
from resource_delivery_fixture import resource_status, resource_ack


class EndowmentTests(unittest.TestCase):
    tearDown=test_population.PopulationTests.tearDown
    census=test_population.PopulationTests.census

    def setUp(self):
        test_population.PopulationTests.setUp(self);self.census()
        self.manifest=load_manifest();self.manifest_hash=manifest_hash(self.manifest)
        self.obs['resource_import']=resource_status()
        for row in self.obs['residents']:row['baseId']=100000+row['id']
        self.world.initialize_population('start','seed',self.obs);self.sync()

    def sync(self):
        for _ in range(10):
            if not self.world.transition:return
            self.obs['checkpoint']=self.world.transition['next'];self.obs.pop('ack',None)
            if self.obs.get('inventory_observations'):self.obs['inventory_checkpoint']=self.obs['checkpoint']
            self.world.observe(self.obs)
        self.fail('Checkpoint loop did not settle')

    def plan(self,actor=99):
        result=self.world.plan_endowment(actor,self.obs,self.manifest['id'],self.manifest_hash)
        self.sync();return result

    def arm(self,actor=99):
        self.plan(actor);command=self.world.pending(self.obs['session'])
        self.assertEqual(command['phase'],'arm')
        self.obs['ack']=resource_ack(command);self.world.observe(self.obs);self.sync()
        return self.world.pending(self.obs['session'])

    def deliver(self,actor=99):
        command=self.arm(actor)
        native=next(a for a in self.obs['residents']+self.obs.get('inventory_observations',[]) if a['id']==actor)
        native['inventory']=command['after'].copy();self.obs['ack']=resource_ack(command)
        self.world.observe(self.obs);self.sync();return command

    def test_reservation_precedes_arm_and_permit_checkpoint_precedes_delivery(self):
        before=copy.deepcopy(self.obs)
        self.world.plan_endowment(99,self.obs,self.manifest['id'],self.manifest_hash)
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'bind_checkpoint')
        self.assertEqual(self.obs,before);self.sync()
        arm=self.world.pending(self.obs['session']);program=self.world.active['town']['resource_program']
        self.assertEqual(program['reserved'],self.manifest['default_grant'])
        self.assertEqual(program['remaining'],self.manifest['capacity'])
        self.obs['ack']=resource_ack(arm);self.world.observe(self.obs)
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'bind_checkpoint')
        self.sync();delivery=self.world.pending(self.obs['session'])
        self.assertEqual(delivery['phase'],'deliver');self.assertNotEqual(delivery['id'],arm['id'])
        self.assertIn('arm_receipt',self.world.active['pending'])

    def test_complete_delivery_debits_once_and_creates_only_external_resource_memory(self):
        command=self.deliver();program=self.world.active['town']['resource_program']
        self.assertEqual(program['delivered'],self.manifest['default_grant'])
        self.assertTrue(all(v==0 for v in program['reserved'].values()))
        self.assertEqual(program['available'],program['remaining'])
        self.assertEqual(self.world.state(),[]);self.assertEqual(self.world.status()['production'],[])
        self.assertEqual(self.world.active['people']['99']['memories'][-1]['event_id'],command['grant_id'])
        before=copy.deepcopy(self.world.active)
        result=self.world.plan_endowment(99,self.obs,self.manifest['id'],self.manifest_hash)
        self.assertTrue(result['duplicate']);self.assertEqual(self.world.active,before)

    def test_original_special_recipient_receives_same_uniform_default(self):
        command=self.deliver(108149)
        self.assertEqual(command['grant'],self.manifest['default_grant'])
        self.assertEqual(command['grant']['gold'],20)

    def test_false_final_ack_holds_reservation_without_delivery_credit_or_memory(self):
        command=self.arm();self.obs['ack']=resource_ack(command)
        self.world.observe(self.obs);self.sync()
        program=self.world.active['town']['resource_program']
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(program['reserved'],command['grant'])
        self.assertTrue(all(v==0 for v in program['delivered'].values()))
        self.assertEqual(self.world.active['people']['99']['memories'],[])

    def test_load_before_reservation_restores_original_source_and_memory(self):
        old=copy.deepcopy(self.obs);self.deliver();self.world.observe({**old,'session':'past'})
        self.assertNotIn('resource_program',self.world.active['town'])
        self.assertEqual(self.world.active['people']['99']['memories'],[])

    def test_load_mid_delivery_holds_instead_of_rebinding_session(self):
        command=self.arm();self.obs['residents'][2]['inventory']['gold']=command['after']['gold']
        self.obs['session']='reload-middle';self.world.observe(self.obs);self.sync()
        self.assertIsNone(self.world.pending(self.obs['session']))
        self.assertEqual(self.world.active['pending']['status'],'held')
        program=self.world.active['town']['resource_program']
        self.assertEqual(program['reserved'],command['grant']);self.assertEqual(program['grants'],{})

    def test_native_epoch_reset_holds_even_if_inventory_equals_after(self):
        command=self.arm();self.obs['residents'][2]['inventory']=command['after'].copy()
        self.obs['resource_import']['epoch']='cold-start';self.obs['ack']=resource_ack(command)
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(self.world.active['town']['resource_program']['grants'],{})

    def test_admitted_delivery_can_settle_from_checkpoint_pinned_accounting_after_unload(self):
        # Admission and native arm see the qualified actor. Only the later
        # receipt is reconciled from accounting after the delivered actor unloads.
        command=self.arm()
        actor=self.obs['residents'].pop(2);actor['loaded']=False
        actor['inventory']=command['after'].copy()
        self.obs['inventory_observations']=[actor];self.obs['inventory_checkpoint']=self.obs['checkpoint']
        self.obs['ack']=resource_ack(command);self.world.observe(self.obs);self.sync()
        record=self.world.active['town']['resource_program']['grants']['99']
        self.assertEqual(record['status'],'committed')
        self.assertEqual(record['command']['actor_base_id'],actor['baseId'])
        self.assertEqual(record['evidence']['ack']['actor_base_id'],actor['baseId'])
        self.assertNotIn(99,[a['id'] for a in self.obs['residents']])

    def test_unloaded_accounting_cannot_authorize_initial_resource_admission(self):
        actor=self.obs['residents'].pop(2);actor['loaded']=False
        self.obs['inventory_observations']=[actor];self.obs['inventory_checkpoint']=self.obs['checkpoint']
        with self.assertRaisesRegex(ValueError,'independent activity'):self.plan()
        self.assertIsNone(self.world.active['pending'])
        self.assertNotIn('resource_program',self.world.active['town'])

    def test_legacy_program_remains_readable_but_new_api_cannot_migrate_or_allocate(self):
        legacy={'id':'founding-resources-v1','capacity':{'gold':1000,'bread':100,'grain':100},
            'remaining':{'gold':980,'bread':98,'grain':100},'grants':{'99':{'id':'old','status':'committed','command':{'actor':99}}}}
        self.world.active['town']['resource_program']=copy.deepcopy(legacy)
        with self.assertRaisesRegex(ValueError,'Legacy'):self.plan()
        self.assertEqual(self.world.status()['town']['resource_program'],legacy)

    def test_legacy_pending_import_is_held_without_new_identity_or_memory(self):
        command={'id':'legacy-import','kind':'inventory_endowment','actor':99,'catalog_hash':self.manifest['catalog_hash']}
        self.world.active['pending']={'id':'legacy-import','status':'pending','command':command}
        self.assertIsNone(self.world.pending(self.obs['session']))
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(self.world.active['pending']['command'],command)
        self.assertEqual(self.world.active['people']['99']['memories'],[])
