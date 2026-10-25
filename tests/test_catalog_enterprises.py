"""Catalog extensibility is a controlled fixture, not a deployed new industry."""
import copy
import unittest
from unittest.mock import patch
import economy_catalog as catalog
from enterprises import apply_enterprise_change, executable_capabilities, production_policy
from entrepreneurship import enterprise_choices, knows_recipe, learn_recipe, recipe_knowledge, apply_resident_enterprise
from agency_metrics import account_cashflow
from metrics import simulation_metrics


def expanded_catalog():
    data=copy.deepcopy(catalog.ECONOMY_CATALOG)
    for key,form in [('ore',4096),('ingot',4097)]:
        data['commodities'].append({'id':key,'label':key,'native':{'plugin':'TestFixture.esp',
            'local_form_id':form,'record_type':'MISC'},'currency':False,
            'provenance':'Controlled unit fixture; not a verified game asset'})
    data['recipes'].append({'id':'metal_recipe','version':1,'inputs':{'ore':2},'outputs':{'ingot':1},
        'work_minutes':{'minimum':12,'default':15,'maximum':24},
        'provenance':'Controlled unit fixture; not a deployed production mechanism'})
    return catalog.validate_catalog(data)


class CatalogEnterpriseTests(unittest.TestCase):
    def setUp(self):
        self.catalog=expanded_catalog()
        self.mock=patch.object(catalog,'ECONOMY_CATALOG',self.catalog);self.mock.start();self.addCleanup(self.mock.stop)
        self.inventory={'gold':7,'bread':3,'grain':8,'ore':4,'ingot':2}
        self.state={'town':{'residents':{'7':{'id':7}},'businesses':{}},
            'people':{'7':{'profile':{'name':'An unknown artisan'},'memories':[]}}}
        self.obs={'residents':[{'id':7,'isPerson':True,'inventory':self.inventory}]}
        self.spec={'id':'new-forge','expected_revision':0,'name':'Proposed forge','custodian':7,
            'capabilities':['metal_recipe'],'active':True,
            'recipe_policies':{'metal_recipe':{'target_output':9,'wage_gold':3,'work_minutes':18}}}

    def test_catalog_recipe_enables_explicit_charter_without_stock_or_knowledge_grant(self):
        stock=copy.deepcopy(self.obs);people=copy.deepcopy(self.state['people'])
        business,event=apply_enterprise_change(self.state,'register',self.spec,self.obs,'unit fixture')
        self.assertIn('metal_recipe',executable_capabilities())
        self.assertEqual(business['costs']['metal_recipe'],{'ore':2,'wage_gold':3,'labour_game_minutes':18})
        self.assertEqual(production_policy(business,'metal_recipe')['target_output'],9)
        self.assertEqual(event['inventory_effect'],'none')
        self.assertEqual(self.obs,stock);self.assertEqual(self.state['people'],people)
        self.assertFalse(knows_recipe(self.state['people']['7'],'metal_recipe'))

    def test_policy_duration_and_quantities_follow_catalog_without_overrides(self):
        self.assertEqual(production_policy({},'metal_recipe')['work_minutes'],15)
        for value in ({'work_minutes':11},{'work_minutes':25},{'ore_per_shift':1},{'wage_gold':0}):
            with self.subTest(value=value),self.assertRaises(ValueError):
                production_policy({'recipe_policies':{'metal_recipe':value}},'metal_recipe')
        bread=next(r for r in self.catalog['recipes'] if r['id']=='bread_recipe')
        bread['inputs']['grain']=2;bread['outputs']['bread']=3
        self.assertEqual(production_policy({})['grain_per_shift'],2)
        self.assertEqual(production_policy({})['bread_per_shift'],3)
        with self.assertRaises(ValueError):production_policy({'production_policy':{'grain_per_shift':1}})

    def test_planned_capability_and_unregistered_policy_cannot_become_executable(self):
        original=copy.deepcopy(self.state)
        for spec in ({**self.spec,'capabilities':['metalwork_planned']},
                     {**self.spec,'capabilities':['retail_food']},
                     {**self.spec,'recipe_policies':{'missing_recipe':{}}}):
            with self.subTest(spec=spec),self.assertRaises(ValueError):
                apply_enterprise_change(self.state,'bad',spec,self.obs,'fixture')
        self.assertEqual(self.state,original)

    def test_knowledge_is_specific_to_verified_participation_and_own_actor(self):
        person=self.state['people']['7'];person['memories']=[{'kind':'heard_recipe','recipe_id':'metal_recipe'}]
        self.assertFalse(knows_recipe(person,'metal_recipe'))
        learn_recipe(person,'bread-commit','bread_recipe')
        self.assertFalse(knows_recipe(person,'metal_recipe'))
        self.assertTrue(recipe_knowledge(person)['bread'])
        self.assertNotIn('register_recipe_metal_recipe_resident-7',{o['id'] for o in enterprise_choices(self.state,self.obs,7)})
        learn_recipe(person,'metal-commit','metal_recipe')
        choices={o['id']:o for o in enterprise_choices(self.state,self.obs,7)}
        self.assertIn('register_recipe_metal_recipe_resident-7',choices)
        self.assertEqual(choices['register_recipe_metal_recipe_resident-7']['specification']['capabilities'],['metal_recipe'])
        self.assertEqual(person['known_recipes']['metal_recipe']['event_id'],'metal-commit')
        self.assertFalse(knows_recipe({'known_recipes':{}},'metal_recipe'))
        with self.assertRaises(ValueError):learn_recipe(person,'fake','metalwork_planned')

    def test_recipe_revision_does_not_silently_grant_changed_transform_knowledge(self):
        person=self.state['people']['7'];learn_recipe(person,'old-proof','metal_recipe')
        definition=next(r for r in self.catalog['recipes'] if r['id']=='metal_recipe')
        definition['outputs']['ingot']=2;definition['version']=2
        self.assertFalse(knows_recipe(person,'metal_recipe'))
        learn_recipe(person,'new-proof','metal_recipe')
        self.assertTrue(knows_recipe(person,'metal_recipe'))
        self.assertEqual(person['known_recipes']['metal_recipe']['event_id'],'new-proof')

    def test_direct_resident_registration_cannot_bypass_own_knowledge(self):
        plan={'actor':7,'id':'new-plan','decisions':[{'claim_id':'decision'}]}
        with self.assertRaisesRegex(ValueError,'not learned'):
            apply_resident_enterprise(self.state,plan,self.spec,self.obs)
        self.assertEqual(self.state['town']['businesses'],{})

    def command(self):
        return {'id':'commit','kind':'inventory_self_produce_commit','actor':7,'recipe_id':'metal_recipe',
            'catalog_hash':catalog.catalog_hash(),'recipe_hash':catalog.recipe_hash('metal_recipe'),
            'before':{'owner':copy.deepcopy(self.inventory)},
            'after':{'owner':catalog.apply_recipe(self.inventory,'metal_recipe')}}

    def test_generic_committed_recipe_reconciles_zero_cash_and_conserves_unrelated_stock(self):
        command=self.command();record={'id':'commit','status':'committed','command':command}
        result=account_cashflow({'production':[record,copy.deepcopy(record)]})
        self.assertEqual(result['record_coverage'],{'success':1,'n':1,'percent':100})
        self.assertEqual(result['duplicate_records_excluded'],1)
        self.assertEqual(result['owner_recipe_receipts'],{'metal_recipe':1})
        self.assertEqual(result['owner_recipe_evidence'],{'validated_catalog_transform':1})
        self.assertEqual(result['accounts'][0]['net_operating_cashflow'],0)
        self.assertIsNone(result['profit'])
        self.assertEqual(command['after']['owner']['bread'],command['before']['owner']['bread'])
        for field in ('gold','bread','grain','ore','ingot'):
            broken=copy.deepcopy(record);broken['command']['after']['owner'][field]+=1
            with self.subTest(field=field):
                self.assertEqual(account_cashflow({'production':[broken]})['record_coverage']['success'],0)

    def test_missing_wrong_hash_and_uncommitted_recipe_cannot_claim_output(self):
        for change in (lambda c:c.pop('catalog_hash'),lambda c:c.update(recipe_hash='bad'),
                       lambda c:c.update(recipe_id='metalwork_planned'),
                       lambda c:c['before']['owner'].pop('bread')):
            command=self.command();change(command)
            result=account_cashflow({'production':[{'id':'commit','status':'committed','command':command}]})
            self.assertEqual(result['accounts'],[])
            self.assertEqual(result['owner_recipe_receipts'],{})
        self.assertEqual(account_cashflow({'production':[{'id':'commit','status':'prepared','command':self.command()}]})['owner_recipe_receipts'],{})

    def test_reporting_distinguishes_configured_catalog_from_observed_production(self):
        result=simulation_metrics({})['economy']
        self.assertEqual(result['supported_production_recipes'],2)
        self.assertEqual(result['production_catalog']['recipe_ids'],['bread_recipe','metal_recipe'])
        self.assertEqual(result['owner_production_batches'],0)
        self.assertEqual(result['supported_sale_goods'],2)
        self.assertIn('not observed activity',result['production_catalog']['scope'])

    def test_historical_bread_receipt_is_readable_without_claiming_catalog_hash_proof(self):
        old={'id':'old','status':'committed','command':{'kind':'inventory_self_produce_commit','actor':7,
            'before':{'owner':{'gold':2,'grain':1,'bread':0}},'after':{'owner':{'gold':2,'grain':0,'bread':2}}}}
        result=account_cashflow({'production':[old]})
        self.assertEqual(result['owner_recipe_receipts'],{'bread_recipe':1})
        self.assertEqual(result['owner_recipe_evidence'],{'legacy_fixed_bread_transform':1})
        old['command']['recipe_id']='metal_recipe'
        self.assertEqual(account_cashflow({'production':[old]})['owner_recipe_receipts'],{})


if __name__=='__main__':unittest.main()
