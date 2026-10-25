import copy
import unittest
from unittest.mock import patch
import economy_catalog as catalog
import market_policy
from catalog_fixture import native_catalog, native_ack
from test_catalog_enterprises import expanded_catalog
from production import Production
from labour import work_opportunities
from enterprises import current_work_terms


class Harness(Production):
    def __init__(self, plan):
        self.active={'plans':[plan],'pending':None,'people':{}}
        self.session='unit';self.writes=[]
    def _agency_guard(self, observation):pass
    def agency_plan(self):return self.active['plans'][-1]
    def agency_busy(self):return False
    def _write(self,state,reason):self.active=state;self.writes.append(reason)


class CatalogPaidProductionTests(unittest.TestCase):
    def setUp(self):
        self.catalog=expanded_catalog()
        bread=next(r for r in self.catalog['recipes'] if r['id']=='bread_recipe')
        bread['inputs']['grain']=2;bread['outputs']['bread']=3;bread['version']=2
        self.mock=patch.object(catalog,'ECONOMY_CATALOG',self.catalog);self.mock.start();self.addCleanup(self.mock.stop)
        policy=copy.deepcopy(market_policy.MARKET_POLICY);policy['catalog_hash']=catalog.catalog_hash()
        market=patch.object(market_policy,'MARKET_POLICY',policy);market.start();self.addCleanup(market.stop)
        self.plan={'id':'shift','actor':7,'target':8,'phase':'ready_to_work','travel':{'movement':{'expectedPackage':99}}}
        self.world=Harness(self.plan)
        self.obs={'session':'unit','economy_catalog':native_catalog(),'residents':[
            {'id':7,'isPerson':True,'inventory':{'gold':4,'bread':3,'grain':0,'ore':7,'ingot':9}},
            {'id':8,'isPerson':True,'inventory':{'gold':20,'bread':0,'grain':5,'ore':6,'ingot':11}}]}

    def test_paid_command_pins_recipe_and_preserves_unrelated_stock_and_gold_total(self):
        self.world.plan_production(self.obs,self.plan)
        command=self.world.active['pending']['command']
        self.assertEqual(command['catalog_hash'],catalog.catalog_hash())
        self.assertEqual(command['recipe_hash'],catalog.recipe_hash('bread_recipe'))
        self.assertEqual(command['recipe_id'],'bread_recipe')
        self.assertEqual(command['after']['employer'],{'gold':18,'bread':3,'grain':3,'ore':6,'ingot':11})
        self.assertEqual(command['after']['worker'],{'gold':6,'bread':3,'grain':0,'ore':7,'ingot':9})
        self.assertEqual(sum(row['gold'] for row in command['before'].values()),sum(row['gold'] for row in command['after'].values()))

    def test_missing_or_mismatched_native_catalog_never_creates_pending_effect(self):
        for proof in (None,{}, {**native_catalog(),'type_verified':False}, {**native_catalog(),'catalog_hash':'wrong'}):
            obs=copy.deepcopy(self.obs)
            if proof is None:obs.pop('economy_catalog')
            else:obs['economy_catalog']=proof
            with self.subTest(proof=proof),self.assertRaises(ValueError):self.world.plan_production(obs,self.plan)
            self.assertIsNone(self.world.active['pending']);self.assertEqual(self.world.writes,[])

    def test_input_shortage_overflow_or_unknown_account_prevents_new_intent(self):
        for role,item,value in [(1,'grain',1),(0,'gold',catalog.MAX_STOCK),(1,'bread',catalog.MAX_STOCK),(0,'ore',None)]:
            obs=copy.deepcopy(self.obs);obs['residents'][role]['inventory'][item]=value
            with self.subTest(item=item,role=role),self.assertRaises(ValueError):self.world.plan_production(obs,self.plan)
            self.assertEqual(self.world.writes,[])

    def test_existing_pending_without_catalog_proof_is_held_not_committed(self):
        self.world.plan_production(self.obs,self.plan)
        command=self.world.active['pending']['command'];command.pop('catalog_hash')
        for actor in self.obs['residents']:actor['inventory']=copy.deepcopy(command['after']['worker' if actor['id']==7 else 'employer'])
        self.obs['ack']={'id':command['id'],'status':'applied'}
        self.world.observe_production(self.obs)
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertNotIn('production',self.world.active)
        self.assertEqual(self.world.active['people'],{})

    def test_paid_settlement_requires_exact_receipt_pins_even_when_inventory_matches(self):
        for key in ('catalog_hash','recipe_hash','recipe_id'):
            for missing in (True,False):
                world=Harness(copy.deepcopy(self.plan));obs=copy.deepcopy(self.obs)
                world.plan_production(obs,world.agency_plan())
                command=world.active['pending']['command'];ack=native_ack(command)
                if missing:ack.pop(key)
                else:ack[key]='mismatched'
                obs['ack']=ack
                for actor in obs['residents']:actor['inventory']=copy.deepcopy(command['after']['worker' if actor['id']==7 else 'employer'])
                with self.subTest(key=key,missing=missing):
                    world.observe_production(obs)
                    self.assertEqual(world.active['pending']['status'],'held')
                    self.assertNotIn('production',world.active)
                    self.assertNotIn('cancelled_production',world.active)
                    self.assertEqual(world.active['people'],{})

    def test_supply_settlement_requires_exact_catalog_receipt_without_recipe_fields(self):
        for binding in ('missing','wrong','exact'):
            world=Harness(copy.deepcopy(self.plan));obs=copy.deepcopy(self.obs)
            obs['residents'][0]['id']=108186;obs['residents'][1]['id']=108149
            world.setup_production(obs);command=world.active['pending']['command']
            obs['ack']=native_ack(command)
            self.assertNotIn('recipe_hash',obs['ack'])
            if binding=='missing':obs['ack'].pop('catalog_hash')
            elif binding=='wrong':obs['ack']['catalog_hash']='mismatched'
            for actor in obs['residents']:actor['inventory']=copy.deepcopy(command['after']['worker' if actor['id']==108186 else 'employer'])
            with self.subTest(binding=binding):
                world.observe_production(obs)
                if binding=='exact':
                    self.assertIsNone(world.active['pending']);self.assertEqual(len(world.active['imports']),1)
                else:
                    self.assertEqual(world.active['pending']['status'],'held');self.assertNotIn('imports',world.active)
                self.assertNotIn('production',world.active)

    def test_unbound_no_effect_paid_receipt_cannot_cancel_reservation(self):
        self.world.plan_production(self.obs,self.plan)
        command=self.world.active['pending']['command']
        self.obs['ack']=native_ack(command,status='held',no_effects_issued=True)
        self.obs['ack'].pop('recipe_hash')
        self.world.observe_production(self.obs)
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertNotIn('cancelled_production',self.world.active)

    def test_catalog_drift_invalidates_agreed_enterprise_terms(self):
        self.plan['work_terms']={'business_id':'bakery','recipe_id':'bread_recipe',
            'catalog_hash':catalog.catalog_hash(),'recipe_hash':catalog.recipe_hash('bread_recipe')}
        self.catalog['version']='changed'
        with self.assertRaisesRegex(ValueError,'absent or stale'):current_work_terms(self.world.active,self.plan)

    def test_grain_procurement_uses_catalog_batch_quantities(self):
        from procurement import grain_procurement
        from entrepreneurship import learn_recipe
        state={'people':{'7':{},'8':{}},'town':{'residents':{'7':{},'8':{}},'businesses':{
            'bakery':{'owner':7,'custodian':7,'capabilities':['bread_recipe']},
            'supplier':{'owner':8,'custodian':8,'capabilities':['retail_goods'],'sale_commodities':['grain']}}}}
        learn_recipe(state['people']['7'],'authored-earlier-production','bread_recipe')
        self.obs['routing']={'available':True,'adapter':'papyrus-mailbox-v1'}
        choices=grain_procurement(state,self.obs,7)
        # Target8 minus3 carried bread needs2 batches of3, each consuming2 grain.
        self.assertTrue(choices)
        self.assertEqual({row['shortfall'] for row in choices},{4})
        self.assertEqual({row['supplier'] for row in choices},{8})
        self.assertTrue(all(row['quantity']<=4 for row in choices))

    def test_changed_bread_id_pair_is_generic_owner_only_not_paid_bread_alias(self):
        from owner_production import owner_work_opportunities
        from entrepreneurship import learn_recipe, recipe_knowledge
        recipe=next(r for r in self.catalog['recipes'] if r['id']=='bread_recipe')
        recipe.update(inputs={'ore':2},outputs={'ingot':1})
        self.obs['economy_catalog']=native_catalog()
        self.obs['resident_control']={'activities':[{'actor':7,'ownedPackage':True,'expectedPackage':99}]}
        self.obs['residents'][0].update(x=0,y=0,z=0,activity={'package_id':99,'scene_id':0,'in_combat':False,'sleep_state':0})
        state={'town':{'residents':{'7':{'id':7}},'businesses':{
            'own':{'owner':7,'custodian':7,'capabilities':['bread_recipe'],'revision':1,
                'recipe_policies':{'bread_recipe':{'target_output':20}}}}},
            'people':{'7':{'relationships':{},'memories':[]}}}
        self.assertEqual(work_opportunities(state,self.obs,7),[])
        choices=owner_work_opportunities(state,self.obs,7)
        self.assertEqual(len(choices),1)
        self.assertEqual(choices[0]['policy']['target_output'],20)
        self.assertNotIn('grain_per_shift',choices[0]['policy'])
        with self.assertRaisesRegex(ValueError,'grain-to-bread'):self.world.plan_production(self.obs,self.plan)
        person=state['people']['7'];learn_recipe(person,'generic-output','bread_recipe')
        self.assertTrue(recipe_knowledge(person)['recipes']['bread_recipe'])
        self.assertFalse(recipe_knowledge(person)['bread'])
        self.assertNotIn('bread',person['known_recipes'])

    def test_paid_menu_is_explicitly_bread_only_and_requires_complete_verified_accounts(self):
        state={'town':{'residents':{'7':{'id':7}},'businesses':{}},'people':{'7':{'relationships':{},'memories':[]}}}
        self.obs['routing']={'adapter':'papyrus-mailbox-v1','available':True}
        for a in self.obs['residents']:a.update(x=0,y=0,z=0)
        state['town']['businesses']['bakery']={'custodian':8,'capabilities':['bread_recipe'],'revision':1,'production_policy':{}}
        choices=work_opportunities(state,self.obs,7)
        self.assertEqual(len(choices),1)
        self.assertEqual(choices[0]['policy']['grain_per_shift'],2)
        self.assertEqual(choices[0]['recipe_hash'],catalog.recipe_hash('bread_recipe'))
        self.obs['residents'][1]['inventory']['grain']=1
        self.assertEqual(work_opportunities(state,self.obs,7),[])
        self.obs['residents'][1]['inventory']['grain']=5
        self.obs['economy_catalog']['type_verified']=False
        self.assertEqual(work_opportunities(state,self.obs,7),[])
        self.obs['economy_catalog']=native_catalog()
        state['town']['businesses']['bakery']['capabilities']=['metal_recipe']
        self.assertEqual(work_opportunities(state,self.obs,7),[])


class LegacyOwnerReceiptTests(unittest.TestCase):
    def world(self):
        command={'id':'own-proof','kind':'inventory_self_produce','actor':7,'recipe_id':'bread_recipe',
            'catalog_hash':catalog.catalog_hash(),'recipe_hash':catalog.recipe_hash('bread_recipe'),
            'work_minutes':30,'before':{'owner':{'gold':3,'bread':0,'grain':1}},
            'after':{'owner':{'gold':3,'bread':2,'grain':0}}}
        world=Harness({'id':'own','actor':7,'phase':'working'})
        world.active.update(pending={'id':command['id'],'command':command,'status':'pending','business_id':'owned'},
            people={'7':{'memories':[]}})
        obs={'session':'unit','economy_catalog':native_catalog(),'residents':[{'id':7,'inventory':copy.deepcopy(command['after']['owner'])}]}
        return world,command,obs

    def test_owner_missing_or_mismatched_receipt_pin_never_commits_or_cancels(self):
        from owner_production import OwnerProduction
        for status in ('applied','held'):
            for key in ('catalog_hash','recipe_hash','recipe_id'):
                for missing in (True,False):
                    world,command,obs=self.world();obs['ack']=native_ack(command,status=status,no_effects_issued=status=='held')
                    if status=='held':obs['residents'][0]['inventory']=copy.deepcopy(command['before']['owner'])
                    if missing:obs['ack'].pop(key)
                    else:obs['ack'][key]='mismatched'
                    with self.subTest(status=status,key=key,missing=missing):
                        OwnerProduction.observe_owner_production(world,obs)
                        self.assertEqual(world.active['pending']['status'],'held')
                        self.assertNotIn('production',world.active)
                        self.assertNotIn('cancelled_production',world.active)
                        self.assertNotIn('known_recipes',world.active['people']['7'])
                        self.assertEqual(world.active['people']['7']['memories'],[])

    def test_exact_owner_receipt_plus_counts_can_commit_or_cancel(self):
        from owner_production import OwnerProduction
        for status in ('applied','held'):
            world,command,obs=self.world();obs['ack']=native_ack(command,status=status,no_effects_issued=status=='held')
            if status=='held':obs['residents'][0]['inventory']=copy.deepcopy(command['before']['owner'])
            OwnerProduction.observe_owner_production(world,obs)
            self.assertIsNone(world.active['pending'])
            if status=='applied':
                self.assertEqual(len(world.active['production']),1)
                self.assertIn('known_recipes',world.active['people']['7'])
            else:
                self.assertEqual(len(world.active['cancelled_production']),1)
                self.assertNotIn('known_recipes',world.active['people']['7'])


class GenericOwnerContextTests(unittest.TestCase):
    def test_nonbread_pair_keeps_distinct_owner_choices_without_paid_bread_or_private_catalog(self):
        import json
        import test_owner_production as fixture
        from agency import owner_work_choice_id
        case=fixture.OwnerProductionTests();case.setUp()
        try:
            data=expanded_catalog()
            recipe=next(r for r in data['recipes'] if r['id']=='bread_recipe')
            recipe.update(inputs={'ore':2},outputs={'ingot':1})
            with patch.object(catalog,'ECONOMY_CATALOG',data):
                policy=copy.deepcopy(market_policy.MARKET_POLICY);policy['catalog_hash']=catalog.catalog_hash()
                market=patch.object(market_policy,'MARKET_POLICY',policy);market.start();self.addCleanup(market.stop)
                case.obs['economy_catalog']=native_catalog()
                for actor in case.obs['residents']:actor['inventory'].update(ore=4,ingot=0)
                business=case.world.active['town']['businesses']['new-owner']
                business['capabilities']=['bread_recipe','metal_recipe']
                business['recipe_policies']={'bread_recipe':{'target_output':20},'metal_recipe':{'target_output':20}}
                case.world.begin_plan(case.event['id'],case.obs,99,'need_review');case.sync()
                context=case.world._plan_context(case.obs,case.world.agency_plan())
                choices=context['owner_work_actions']
                self.assertEqual(len(set(choices)),2)
                self.assertEqual({context['work_options'][action]['recipe_id'] for action in choices},{'bread_recipe','metal_recipe'})
                for action in choices:
                    self.assertEqual(action,owner_work_choice_id(context['work_options'][action]))
                    effect=next(o['effect'] for o in context['options'] if o['id']==action)
                    self.assertIn('Use 2 ore to produce 1 ingot',effect)
                for forbidden in ('local_form_id','record_type','TestFixture.esp'):
                    self.assertNotIn(forbidden,json.dumps(context))
                self.assertFalse(context['own_recipe_knowledge']['bread'])
                self.assertEqual(context['own_recipe_knowledge']['recipes'],{'bread_recipe':False,'metal_recipe':False})
        finally:case.tearDown()


if __name__=='__main__':unittest.main()
