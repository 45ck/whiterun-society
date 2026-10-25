from catalog_fixture import native_ack
import copy
import unittest
import test_food
from production import work_inventory


def register_authored_employer(case):
    """Explicit test census/charter; registration creates no stock or consent."""
    case.obs['gameDays']=3.5
    for actor in case.obs['residents']:
        actor.update(name='Fixture resident '+str(actor['id']),isPerson=True,isGuard=False,baseId=actor['id']+1000000)
        # Explicit test history, not census silently adopting today's identity.
        case.world.active['people'][str(actor['id'])]['identity_binding']={
            'schema_version':1,'actor':actor['id'],'base_id':actor['baseId'],'event_id':'authored-work-identity'}
    before=copy.deepcopy(case.obs['residents'])
    case.world.initialize_population('work-fixture-census','authored-work-fixture',case.obs);case.sync()
    case.world.configure_enterprise('work-fixture-charter',{
        'id':'fixture-employer','expected_revision':0,'name':'Authored fixture bakery',
        'custodian':108149,'capabilities':['bread_recipe'],'active':True,
        'production_policy':{'target_bread':8,'wage_gold':2,'work_minutes':30}},case.obs)
    case.sync()
    case.assertEqual(case.obs['residents'],before)


class ProductionTests(unittest.TestCase):
    # Reuse fixtures, not inherited test cases.
    def setUp(self):
        test_food.FoodTests.setUp(self)
        for actor in self.obs['residents']:
            actor['inventory']['grain'] = 2 if actor['id']==108149 else 0
        register_authored_employer(self)

    tearDown = test_food.FoodTests.tearDown
    sync = test_food.FoodTests.sync
    decide = test_food.FoodTests.decide

    def archived_work(self):
        """Install an explicit pre-gate saved intent; never bypass current admission."""
        before=work_inventory(self.obs,108186,108149);after=copy.deepcopy(before)
        after['employer']['grain']-=1;after['employer']['bread']+=2
        after['employer']['gold']-=2;after['worker']['gold']+=2
        from economy_catalog import catalog_hash, recipe_hash
        c={'id':'produce-job','kind':'inventory_produce','worker':108186,'employer':108149,
           'recipe_id':'bread_recipe','catalog_hash':catalog_hash(),'recipe_hash':recipe_hash('bread_recipe'),
           'work_minutes':30,'wage_gold':2,'before':before,'after':after}
        self.world.active.setdefault('plans',[]).append({'id':'job','kind':'work_shift','actor':108186,'target':108149,'phase':'working'})
        self.world.active['pending']={'id':c['id'],'command':c,'status':'pending'}
        return c

    def test_stock_and_charter_do_not_advertise_unqualified_paid_execution(self):
        from labour import work_opportunities
        from paid_work_policy import paid_work_capability
        self.assertEqual(work_opportunities(self.world.active,self.obs,108186),[])
        self.assertFalse(paid_work_capability()['available'])
        before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'No feasible paid-work'):
            self.world.begin_plan('job',self.obs,108186,kind='work_shift')
        self.assertEqual(self.world.active,before)
        self.assertIsNone(self.world.transition)

    def test_input_and_wage_shortage_prevent_job_offer(self):
        stock=copy.deepcopy(self.obs['residents'][1]['inventory'])
        for item,value in [('grain',0),('gold',1)]:
            with self.subTest(shortage=item):
                self.obs['residents'][1]['inventory']={**stock,item:value}
                before=copy.deepcopy(self.world.active)
                with self.assertRaisesRegex(ValueError,'No feasible paid-work'):
                    self.world.begin_plan('job',self.obs,108186,kind='work_shift')
                self.assertEqual(self.world.active,before)
                self.assertIsNone(self.world.transition)
                self.assertIsNone(self.world.active['pending'])

    def test_direct_production_cannot_bypass_disabled_offer_menu(self):
        before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'legacy_paid_execution_unqualified'):
            self.world.plan_production(self.obs,{'id':'forged','phase':'ready_to_work'})
        self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_observed_names_and_stock_without_charter_cannot_create_a_job(self):
        self.world.active['town']['businesses']={}
        before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'No feasible paid-work'):
            self.world.begin_plan('job',self.obs,108186,kind='work_shift')
        self.assertEqual(self.world.active,before)
        self.assertIsNone(self.world.transition)

    def test_matching_legacy_applied_ack_and_after_inventory_cannot_commit_or_teach(self):
        c=self.archived_work();people=copy.deepcopy(self.world.active['people'])
        for a in self.obs['residents']:a['inventory']=c['after']['worker' if a['id']==108186 else 'employer'].copy()
        self.obs['ack']=native_ack(c)
        self.world.observe_production(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(self.world.status()['production'],[])
        self.assertEqual(self.world.active['people'],people)
        self.assertIsNone(self.world.pending(self.obs['session']))

    def test_ack_without_effects_stays_held_without_no_effect_claim_or_success_memory(self):
        c=self.archived_work();people=copy.deepcopy(self.world.active['people'])
        self.obs['ack']=native_ack(c,status='held',no_effects_issued=True)
        self.world.observe_production(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertIsNone(self.world.active['pending']['effects_issued'])
        self.assertFalse(self.world.active['pending']['no_effects_issued'])
        self.assertEqual(self.world.status()['production'],[])
        self.assertEqual(self.world.active['people'],people)

    def test_explicit_import_is_bounded_persistent_and_separate_from_production(self):
        self.world.setup_production(self.obs);self.sync();c=self.world.pending(self.obs['session'])
        self.obs['residents'][1]['inventory']=c['after']['employer'].copy()
        self.obs['ack']=native_ack(c);self.world.observe(self.obs);self.sync()
        self.assertTrue(self.world.setup_production(self.obs)['duplicate'])
        self.assertEqual(len(self.world.status()['imports']),1)
        self.assertEqual(self.world.status()['production'],[])
