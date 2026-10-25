"""Charter sale declarations remain public intent without resources or knowledge."""
import copy
import unittest
from unittest.mock import patch

import economy_catalog
import market_policy
from enterprises import apply_enterprise_change, executable_capabilities
from test_market_policy import fourth_catalog


class MarketEnterpriseTests(unittest.TestCase):
    def setUp(self):
        self.state={'town':{'residents':{'99':{'id':99}},'businesses':{}},'people':{'99':{}}}
        self.observation={'residents':[{'id':99,'isPerson':True}], 'gameDays':1}
        self.spec={'id':'shop','expected_revision':0,'name':'Resident shop','custodian':99,
                   'capabilities':['retail_goods'],'sale_commodities':['grain'],'active':True}

    def apply(self):return apply_enterprise_change(self.state,'charter',self.spec,self.observation,'Explicit test charter')

    def test_explicit_charter_is_revised_without_stock_or_knowledge_effects(self):
        people=copy.deepcopy(self.state['people']);observation=copy.deepcopy(self.observation)
        business,event=self.apply()
        self.assertEqual(business['sale_commodities'],['grain'])
        self.assertEqual(market_policy.advertised_goods(business),('grain',))
        self.assertEqual(event['inventory_effect'],'none')
        self.assertEqual(self.state['people'],people);self.assertEqual(self.observation,observation)
        with self.assertRaisesRegex(ValueError,'revision'):self.apply()

    def test_generic_retail_requires_explicit_nonempty_valid_unique_goods(self):
        for supplied in (None,[],['gold'],['unknown'],['grain','grain'],[True]):
            with self.subTest(goods=supplied):
                if supplied is None:self.spec.pop('sale_commodities',None)
                else:self.spec['sale_commodities']=supplied
                before=copy.deepcopy(self.state)
                with self.assertRaises(ValueError):self.apply()
                self.assertEqual(self.state,before)

    def test_old_alias_charter_remains_explicit_and_producer_is_not_retailer(self):
        self.spec.pop('sale_commodities');self.spec['capabilities']=['retail_food']
        business,_=self.apply()
        self.assertNotIn('sale_commodities',business)
        self.assertEqual(market_policy.advertised_goods(business),('bread',))
        self.spec.update(expected_revision=1,capabilities=['bread_recipe'])
        business,_=self.apply();self.assertEqual(market_policy.advertised_goods(business),())

    def test_existing_explicit_legacy_alias_declaration_is_supported(self):
        self.spec.update(capabilities=['retail_food'],sale_commodities=['bread'])
        business,_=self.apply();self.assertEqual(market_policy.advertised_goods(business),('bread',))
        self.spec.update(expected_revision=1,sale_commodities=['grain'])
        with self.assertRaisesRegex(ValueError,'retail capability'):self.apply()

    def test_active_owner_work_lease_blocks_retail_charter_change(self):
        self.state['work_jobs']={'job':{'actor':99,'business_id':'shop','phase':'running','receipt_acknowledged':False}}
        before=copy.deepcopy(self.state)
        with self.assertRaisesRegex(ValueError,'reserves'):self.apply()
        self.assertEqual(self.state,before)

    def test_synthetic_fourth_good_requires_only_reviewed_catalog_and_policy_data(self):
        catalog=fourth_catalog();policy=market_policy.load_policy()
        with patch.object(economy_catalog,'ECONOMY_CATALOG',catalog):
            policy['catalog_hash']=economy_catalog.catalog_hash()
            policy['goods'].append({**copy.deepcopy(policy['goods'][1]),'commodity':'test_clay','legacy_retail_capability':None})
            with patch.object(market_policy,'MARKET_POLICY',policy):
                self.spec['sale_commodities']=['test_clay']
                business,_=self.apply()
                self.assertEqual(market_policy.advertised_goods(business),('test_clay',))
                self.assertIn('retail_goods',executable_capabilities())

    def test_recipe_alias_collision_cannot_implicitly_make_producer_a_retailer(self):
        policy=market_policy.load_policy();policy['goods'][0]['legacy_retail_capability']='bread_recipe'
        with patch.object(market_policy,'MARKET_POLICY',policy):
            with self.assertRaisesRegex(ValueError,'conflicts'):executable_capabilities()
            with self.assertRaisesRegex(ValueError,'conflicts'):
                market_policy.advertised_goods({'capabilities':['bread_recipe']})

    def test_reserved_generic_retail_name_cannot_also_be_a_recipe(self):
        catalog=copy.deepcopy(economy_catalog.ECONOMY_CATALOG)
        catalog['recipes'][0]['id']='retail_goods'
        policy=market_policy.load_policy()
        with patch.object(economy_catalog,'ECONOMY_CATALOG',catalog):
            policy['catalog_hash']=economy_catalog.catalog_hash()
            with patch.object(market_policy,'MARKET_POLICY',policy):
                with self.assertRaisesRegex(ValueError,'conflicts'):executable_capabilities()
                with self.assertRaisesRegex(ValueError,'conflicts'):
                    market_policy.advertised_goods({'capabilities':['retail_goods'],'sale_commodities':['grain']})
