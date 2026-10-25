"""Service fault cases use authored receipts; native interop is a separate suite."""
import copy
import unittest
from unittest.mock import patch
import test_endowments
from endowments import IDENTITY, observed_recipient
from resource_delivery_fixture import resource_ack


class ResourceDeliveryFaultTests(unittest.TestCase):
    setUp=test_endowments.EndowmentTests.setUp
    tearDown=test_endowments.EndowmentTests.tearDown
    census=test_endowments.EndowmentTests.census
    sync=test_endowments.EndowmentTests.sync
    plan=test_endowments.EndowmentTests.plan
    arm=test_endowments.EndowmentTests.arm
    deliver=test_endowments.EndowmentTests.deliver

    def recipient(self):
        return next(row for row in self.obs['residents']+self.obs.get('inventory_observations',[]) if row['id']==99)

    def held(self):
        self.sync();program=self.world.active['town']['resource_program']
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(program['reserved'],self.manifest['default_grant'])
        self.assertEqual(program['delivered'],{k:0 for k in self.manifest['capacity']})
        self.assertEqual(program['grants'],{})
        self.assertEqual(self.world.active['people']['99']['memories'],[])
        self.assertIsNone(self.world.pending(self.obs['session']))

    def final_ack(self):
        command=self.arm();self.recipient()['inventory']=command['after'].copy()
        return command,resource_ack(command)

    def accounting(self):
        # A new import requires a current visible identity. These lag cases keep
        # that evidence while the separate accounting-channel marker catches up.
        row=self.recipient()
        self.obs['inventory_observations']=[row];self.obs['inventory_checkpoint']=self.obs['checkpoint']

    def test_bind_reservation_waits_for_accounting_checkpoint_then_arms(self):
        self.accounting();old=self.obs['checkpoint']
        self.world.plan_endowment(99,self.obs,self.manifest['id'],self.manifest_hash)
        self.obs['checkpoint']=self.world.transition['next']
        self.obs['ack']={'id':'binding','status':'applied'};self.world.observe(self.obs)
        self.assertEqual(self.obs['inventory_checkpoint'],old)
        self.assertIsNone(self.world.transition)
        self.assertEqual(self.world.active['pending']['status'],'pending')
        command=self.world.pending(self.obs['session']);self.assertEqual(command['phase'],'arm')
        self.obs['ack']=resource_ack(command);self.world.observe(self.obs)
        self.assertEqual(self.world.active['pending']['phase'],'arm')
        self.assertIsNone(self.world.transition)
        self.obs['inventory_checkpoint']=self.obs['checkpoint'];self.world.observe(self.obs)
        self.assertIsNotNone(self.world.transition);self.sync()
        self.assertEqual(self.world.pending(self.obs['session'])['phase'],'deliver')

    def test_bind_permit_waits_for_accounting_checkpoint_then_credits(self):
        self.accounting();self.plan();arm=self.world.pending(self.obs['session'])
        self.obs['ack']=resource_ack(arm);self.world.observe(self.obs)
        old=self.obs['checkpoint'];self.obs['checkpoint']=self.world.transition['next']
        self.obs['ack']={'id':'binding'};self.world.observe(self.obs)
        self.assertEqual(self.obs['inventory_checkpoint'],old)
        command=self.world.pending(self.obs['session']);self.assertEqual(command['phase'],'deliver')
        self.recipient()['inventory']=command['after'].copy();self.obs['ack']=resource_ack(command)
        self.world.observe(self.obs)
        self.assertEqual(self.world.active['pending']['status'],'pending')
        self.assertEqual(self.world.active['town']['resource_program']['grants'],{})
        self.obs['inventory_checkpoint']=self.obs['checkpoint'];self.world.observe(self.obs);self.sync()
        self.assertIn('99',self.world.active['town']['resource_program']['grants'])

    def test_stale_accounting_does_not_hide_changed_base(self):
        self.accounting();self.plan();self.obs['inventory_checkpoint']-=1;self.recipient()['baseId']+=1
        self.world.observe(self.obs);self.held()

    def test_stale_accounting_does_not_hide_changed_session(self):
        self.accounting();self.plan();self.obs['inventory_checkpoint']-=1;self.obs['session']='new-session'
        self.world.observe(self.obs);self.held()

    def test_stale_accounting_does_not_hide_changed_epoch(self):
        self.accounting();self.plan();self.obs['inventory_checkpoint']-=1;self.obs['resource_import']['epoch']='new-epoch'
        self.world.observe(self.obs);self.held()

    def test_stale_accounting_does_not_hide_bad_leg_receipt(self):
        self.accounting();command,ack=self.final_ack();self.obs['inventory_checkpoint']-=1
        ack['legs'][0]['observed']=False;self.obs['ack']=ack;self.world.observe(self.obs);self.held()

    def test_changed_manifest_cannot_open_another_pool(self):
        self.plan();changed=copy.deepcopy(self.manifest);changed['id']='other-source'
        with patch('endowments.load_manifest',return_value=changed):self.world.observe(self.obs)
        self.held();self.assertEqual(self.world.active['town']['resource_program']['id'],self.manifest['id'])

    def test_unreviewed_scenario_cannot_create_pool(self):
        with self.assertRaises(ValueError):self.world.plan_endowment(99,self.obs,'wrong',self.manifest_hash)
        self.assertNotIn('resource_program',self.world.active['town'])

    def test_wrong_scenario_hash_cannot_create_pool(self):
        with self.assertRaises(ValueError):self.world.plan_endowment(99,self.obs,self.manifest['id'],'0'*64)
        self.assertNotIn('resource_program',self.world.active['town'])

    def test_stale_accounting_cannot_admit_new_reservation(self):
        self.accounting();self.obs['inventory_checkpoint']-=1
        with self.assertRaisesRegex(ValueError,'stale'):self.plan()
        self.assertNotIn('resource_program',self.world.active['town'])

    def test_accounting_only_recipient_cannot_admit_without_current_identity(self):
        self.accounting();self.obs['residents'].remove(self.recipient())
        with self.assertRaisesRegex(ValueError,'independent activity'):self.plan()
        self.assertNotIn('resource_program',self.world.active['town'])
        self.assertIsNone(self.world.active['pending'])

    def test_conflicting_visible_accounting_inventory_cannot_admit(self):
        self.obs['inventory_observations']=[copy.deepcopy(self.recipient())]
        self.obs['inventory_checkpoint']=self.obs['checkpoint']
        self.obs['inventory_observations'][0]['inventory']['gold']+=1
        with self.assertRaisesRegex(ValueError,'Conflicting'):self.plan()

    def test_balanced_but_unjournaled_pool_counters_hold(self):
        self.plan();program=self.world.active['town']['resource_program']
        program['available']['gold']-=1;program['reserved']['gold']+=1
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(program['grants'],{})

    def test_missing_persisted_arm_receipt_cannot_dispatch_delivery(self):
        self.arm();self.world.active['pending'].pop('arm_receipt')
        self.assertIsNone(self.world.pending(self.obs['session']))
        self.world.observe(self.obs);self.held()

    def test_inventory_after_without_receipt_never_credits(self):
        command=self.arm();self.recipient()['inventory']=command['after'].copy()
        self.obs.pop('ack',None);self.world.observe(self.obs)
        self.assertEqual(self.world.active['pending']['status'],'pending')
        self.assertEqual(self.world.active['town']['resource_program']['grants'],{})

    def test_partial_effect_hold_keeps_leg_witness_and_reservation(self):
        command=self.arm();self.recipient()['inventory']['gold']=command['after']['gold']
        ack=resource_ack(command);ack.update(status='held',accepted=False,phase='held')
        ack['legs']=ack['legs'][:1];self.obs['ack']=ack;self.world.observe(self.obs);self.held()
        self.assertEqual(self.world.active['pending']['evidence']['ack']['legs'],ack['legs'])

    def test_exact_terminal_replay_cannot_credit_twice(self):
        command=self.deliver();before=copy.deepcopy(self.world.active)
        self.obs['ack']=resource_ack(command);self.world.observe(self.obs)
        self.assertEqual(self.world.active,before)


def final_receipt_fault(field,value,remove=False):
    def test(self):
        command,ack=self.final_ack()
        if remove:ack.pop(field,None)
        else:ack[field]=copy.deepcopy(value)
        self.obs['ack']=ack;self.world.observe(self.obs);self.held()
    return test


for field in IDENTITY:
    setattr(ResourceDeliveryFaultTests,'test_final_receipt_requires_'+field,final_receipt_fault(field,None,True))
for name,field,value in [('protocol_missing','protocol',None),('protocol_legacy','protocol',1),
    ('protocol_bool','protocol',True),('accepted_false','accepted',False),('permit_mismatch','permit','other'),
    ('legs_missing','legs',[]),('inventory_incomplete','inventory',{}),('unknown_effects','effects_issued',None)]:
    setattr(ResourceDeliveryFaultTests,'test_final_'+name,final_receipt_fault(field,value))


def arm_receipt_fault(field,value):
    def test(self):
        self.plan();command=self.world.pending(self.obs['session']);ack=resource_ack(command)
        ack[field]=value;self.obs['ack']=ack;self.world.observe(self.obs);self.held()
    return test


for name,field,value in [('protocol','protocol',None),('accepted','accepted',False),
    ('inventory','inventory',{}),('effects','effects_issued',True),('permit','permit',''),('legs','legs',[{}])]:
    setattr(ResourceDeliveryFaultTests,'test_arm_requires_'+name,arm_receipt_fault(field,value))
