import copy
import unittest
import test_enterprises as enterprise_fixture
import test_endowments as endowment_fixture
from activity_leases import (activity_leases,owner_work_leases,reserved_activity_actors,
    reserved_activity_targets,reserved_work_accounts,reserved_work_businesses,work_account_conflict,activity_conflict)
from enterprises import apply_enterprise_change
from entrepreneurship import enterprise_choices
from opportunities import food_sellers
from social import social_candidates
from resident_goals import occupied


def work(actor=7,**extra):
    return {'id':'work-'+str(actor),'actor':actor,'custodian':actor,'account_actor':actor,
            'business_id':'mill-bakery','business_revision':1,'phase':'ready',
            'receipt_acknowledged':False,'input_reservation':{'grain':1},**extra}


class OwnerWorkLeaseTests(unittest.TestCase):
    def test_rest_iteration_stays_separate_but_reservations_union_work(self):
        saved=work();orphan=work(9,phase='held')
        state={'activity_jobs':{'rest':{'actor':8,'target':500}},'work_jobs':{'w':saved},'work_orphans':{'orphan':orphan}}
        self.assertEqual(len(activity_leases(state)),1);self.assertEqual(len(owner_work_leases(state)),2)
        self.assertEqual(reserved_activity_actors(state),{7,8,9})
        self.assertEqual(reserved_activity_targets(state),{500})
        self.assertEqual(reserved_work_accounts(state),{'native-inventory:7','native-inventory:9'})
        self.assertEqual(reserved_work_businesses(state),{'mill-bakery'})
        self.assertTrue(work_account_conflict(state,business_ids=['mill-bakery']))

    def test_public_active_jobs_native_orphans_and_accounts_all_block_until_ack(self):
        projection={'owner_work_jobs':{'epoch':'new','capacity':32,'jobs':[work(7,phase='complete',release_verified=True)],
                                     'history':[work(8,receipt_acknowledged=True)]}}
        native={'owner_work_jobs':{'epoch':'old','jobs':[work(9)],'receipts':[work(10,phase='held')],
                                  'reserved_actors':[11]}}
        self.assertEqual(reserved_activity_actors(projection,native),{7,9,10,11})
        projection['owner_work_jobs']['jobs'][0]['receipt_acknowledged']=True
        self.assertEqual(reserved_activity_actors(projection,native),{9,10,11})
        self.assertTrue(activity_conflict(projection,actors=[10],observation=native))
        self.assertFalse(activity_conflict(projection,actors=[8],observation=native))

    def test_shared_account_metadata_cannot_hide_a_leased_custodian(self):
        state={'work_jobs':{'w':work(7,custodian=8,account_actor=9,resource_account='native-inventory:10')}}
        self.assertEqual(reserved_activity_actors(state),{7,8,9,10})
        for actor in (7,8,9,10):self.assertTrue(work_account_conflict(state,actors=[actor]))
        self.assertFalse(work_account_conflict(state,actors=[11]))


class OwnerWorkEnterpriseGuardTests(unittest.TestCase):
    setUp=enterprise_fixture.EnterpriseTests.setUp
    tearDown=enterprise_fixture.EnterpriseTests.tearDown
    sync=enterprise_fixture.EnterpriseTests.sync
    configure=enterprise_fixture.EnterpriseTests.configure

    def test_old_new_custodian_and_business_identity_changes_are_atomic(self):
        self.configure()
        scenarios=[(work(7),{**self.spec,'expected_revision':1,'custodian':9}),
                   (work(9,business_id='other'),{**self.spec,'expected_revision':1,'custodian':9}),
                   (work(9),{**self.spec,'expected_revision':1}),
                   (work(7),{**self.spec,'id':'second-business','expected_revision':0})]
        for job,spec in scenarios:
            with self.subTest(actor=job['actor'],business=spec['id']):
                self.obs['owner_work_jobs']={'receipts':[job]}
                before=copy.deepcopy(self.world.active)
                with self.assertRaisesRegex(ValueError,'Unsettled owner work'):
                    self.world.configure_enterprise('blocked',spec,self.obs)
                self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_common_mutator_blocks_resident_and_operator_paths_but_disjoint_charter_allowed(self):
        self.configure();self.world.active['work_jobs']={'w':work(7)}
        before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'Unsettled owner work'):
            apply_enterprise_change(self.world.active,'resident-edit',{**self.spec,'expected_revision':1},self.obs,'fixture')
        self.assertEqual(self.world.active,before)
        updated=copy.deepcopy(before)
        business,_=apply_enterprise_change(updated,'disjoint',{**self.spec,'id':'other','custodian':9},self.obs,'fixture')
        self.assertEqual(business['custodian'],9)
        self.assertEqual(self.world.active,before)

    def test_public_menus_and_goal_occupancy_hide_working_owner_without_private_details(self):
        self.configure()
        state={**self.world.active,'owner_work_jobs':{'jobs':[work(7)],'history':[],'capacity':32,'epoch':'e'}}
        self.assertEqual(food_sellers(state,self.obs,8),[])
        self.assertNotIn(7,[p['id'] for p in social_candidates(state,self.obs,8)])
        self.assertEqual(enterprise_choices(state,self.obs,7),[])
        self.assertIn(7,occupied(state,self.obs))


class OwnerWorkDirectEffectTests(unittest.TestCase):
    setUp=endowment_fixture.EndowmentTests.setUp
    tearDown=endowment_fixture.EndowmentTests.tearDown
    sync=endowment_fixture.EndowmentTests.sync
    census=endowment_fixture.EndowmentTests.census

    def test_all_direct_effects_reject_owner_account_without_partial_writes(self):
        for method,phase in [('food','ready_to_eat'),('paid','ready_to_work'),('owner','ready_to_self_work'),
                             ('grant',None),('supply',None),('trade',None)]:
            with self.subTest(method=method):
                actor=108186 if method=='supply' else 99
                self.world.active['plans']=[{'id':'effect','actor':actor,'target':108149,'phase':phase}] if phase else []
                self.obs['owner_work_jobs']={'jobs':[work(actor)]};before=copy.deepcopy(self.world.active)
                with self.assertRaises(ValueError):
                    if method=='food':self.world.plan_consumption('eat',self.obs,actor,'effect')
                    elif method=='paid':self.world.plan_production(self.obs,self.world.agency_plan())
                    elif method=='owner':self.world.plan_owner_production(self.obs,self.world.agency_plan())
                    elif method=='grant':self.world.plan_endowment(actor,self.obs,self.manifest['id'],self.manifest_hash)
                    elif method=='supply':self.world.setup_production(self.obs)
                    else:self.world.plan_trade('trade',self.obs,actor,108149)
                self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_disjoint_native_purse_can_receive_grant(self):
        self.obs['owner_work_jobs']={'jobs':[work(108149)]}
        self.world.plan_endowment(99,self.obs,self.manifest['id'],self.manifest_hash)
        self.assertIsNotNone(self.world.transition)
