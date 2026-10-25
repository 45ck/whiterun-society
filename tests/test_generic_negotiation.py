"""Generic resident negotiation fixtures; not evidence of a deployed ore economy."""
import copy
import json
import unittest
from unittest.mock import patch
import economy_catalog as catalog
import market_policy
from catalog_fixture import native_catalog
from bargaining import record_quote, quote_valid
from food import allocation
from test_catalog_enterprises import expanded_catalog
import test_bargaining as fixtures


class GenericNegotiationTests(unittest.TestCase):
    tearDown=fixtures.BargainingTests.tearDown
    sync=fixtures.BargainingTests.sync
    census=fixtures.BargainingTests.census
    review=fixtures.BargainingTests.review
    claim=fixtures.BargainingTests.claim
    choose=fixtures.BargainingTests.choose
    decide=fixtures.BargainingTests.decide

    def setUp(self):
        fixtures.BargainingTests.setUp(self)
        expanded=expanded_catalog()
        patcher=patch.object(catalog,'ECONOMY_CATALOG',expanded);patcher.start();self.addCleanup(patcher.stop)
        policy=copy.deepcopy(market_policy.MARKET_POLICY);policy['catalog_hash']=catalog.catalog_hash()
        policy['goods'].append({'commodity':'ore','legacy_retail_capability':None,'max_quantity':10,
            'quantity_choices':[1,2,5,10],'price_min':2,'price_max':20,'price_choices':[2,3,4,5,10,20],
            'reserve_mode':'seller_choice'})
        patcher=patch.object(market_policy,'MARKET_POLICY',policy);patcher.start();self.addCleanup(patcher.stop)
        self.obs['economy_catalog']=native_catalog()
        for row in self.obs['residents']:row['inventory'].update(ore=15 if row['id']==501 else 0,ingot=0)
        self.obs['residents'][0]['inventory'].update(gold=20,bread=2)
        self.option={'id':'purchase-opaque-A','supplier':501,'business_id':'own-forge','business_revision':1,
            'recipe_id':'metal_recipe','recipe_hash':catalog.recipe_hash('metal_recipe'),
            'catalog_hash':catalog.catalog_hash(),'market_policy_hash':market_policy.policy_hash(),
            'commodity':'ore','quantity':5,'shortfall':10,'purpose':'production_input',
            'listing_business_id':'supplier','listing_revision':1}
        self.offers=patch('agency.input_procurement',return_value=[self.option]);self.offers.start();self.addCleanup(self.offers.stop)
        self.valid=patch('agency.validate_procurement',return_value=True);self.validator=self.valid.start();self.addCleanup(self.valid.stop)

    def arrive(self):
        claim=self.claim();self.choose(claim,self.option['id']);self.sync()
        plan=self.world.agency_plan()
        self.obs['ack']={'id':plan['travel_id'],'status':'applied','movement':{
            'hasOwnedPackage':True,'aliasesConfirmed':True,'adapter':'papyrus-mailbox','actor':99,'target':501}}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'quote')
        return claim

    def test_opaque_choice_preserves_product_quantity_and_private_own_terms(self):
        context=self.arrive()['context'];plan=self.world.agency_plan()
        self.assertEqual(context['purchase_options'][self.option['id']],self.option)
        self.assertEqual((plan['commodity'],plan['quantity'],plan['purpose']),('ore',5,'production_input'))
        self.assertFalse(plan['food_actions']);self.assertEqual(plan['procurement'],self.option)
        self.assertEqual(plan['procurement_claim_id'],plan['decisions'][0]['claim_id'])
        for secret in ('7139','Secret seller name','9173'):self.assertNotIn(secret,json.dumps(context))
        self.assertIn('5 ore',next(o['effect'] for o in context['options'] if o['id']==self.option['id']))

    def test_quantity_affordability_bounds_bid_and_counter_acceptance(self):
        self.arrive();context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual(context['price_options'],{'bid_price_2':2,'bid_price_3':3,'bid_price_4':4})
        self.decide('bid_price_2');seller=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertIn('sell_goods',[o['id'] for o in seller['options']]);self.assertNotIn('sell_bread',[o['id'] for o in seller['options']])
        self.assertEqual(seller['purchase_options'],{})
        self.decide('ask_price_5');buyer=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertNotIn('accept_counterprice',[o['id'] for o in buyer['options']])
        self.assertEqual((buyer['quantity'],buyer['cost']),(5,25))
        for secret in ('7139','counter_quote','Secret seller name'):self.assertNotIn(secret,json.dumps(buyer))

    def test_counterquote_pins_quantity_and_total_and_cannot_change_in_flight(self):
        self.arrive();self.decide('bid_price_2');self.decide('ask_price_3')
        plan=self.world.agency_plan();quote=plan['counter_quote']
        self.assertEqual((quote['commodity'],quote['quantity'],quote['cost']),('ore',5,15))
        self.assertEqual(quote['market_policy_hash'],market_policy.policy_hash())
        claim=self.world.claim_plan_decision(self.event['id'],self.obs)['claim'];self.sync()
        self.world.agency_plan()['quantity']=2
        with self.assertRaisesRegex(ValueError,'quote changed'):self.choose(claim,'accept_counterprice')
        self.assertIsNone(self.world.active['pending'])

    def test_seller_claim_cannot_accept_a_different_quantity_or_unit_price(self):
        self.arrive();self.decide('bid_price_2')
        claim=self.world.claim_plan_decision(self.event['id'],self.obs)['claim'];self.sync()
        self.world.agency_plan()['quantity']=2
        with self.assertRaisesRegex(ValueError,'Negotiation terms changed'):self.choose(claim,'sell_goods')
        self.assertNotIn('accepted_trade',self.world.agency_plan())

    def test_supplier_movement_does_not_change_frozen_commercial_terms(self):
        self.option['distance']=100
        claim=self.claim();self.option['distance']=110
        self.choose(claim,self.option['id']);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'travelling')
        self.assertEqual(self.world.agency_plan()['procurement']['distance'],100)

    def test_disabled_food_reserve_adapter_does_not_reappear_in_counterquote(self):
        bread=next(row for row in market_policy.MARKET_POLICY['goods'] if row['commodity']=='bread')
        bread['reserve_mode']='seller_choice'
        seller=self.world.active['people']['501'];seller['food_policy']={'mode':'household_all'}
        inventory=self.obs['residents'][1]['inventory']
        plan={'actor':99,'target':501,'unit_price':3,'commodity':'bread','quantity':2,
            'purpose':'production_input','market_policy_hash':market_policy.policy_hash()}
        context={'observed_inventory':copy.deepcopy(inventory),'own_food_allocation':allocation(seller,inventory),
            'inventory_catalog_hash':catalog.catalog_hash(),'market_policy_hash':market_policy.policy_hash()}
        record_quote(self.world.active,plan,context,3,'fixture-seller-claim')
        self.assertFalse(plan['counter_quote']['release_reserved'])
        seller['food_policy']={'mode':'fixed_reserve','reserve_target':0}
        self.assertTrue(quote_valid(self.world.active,plan,self.obs))

    def test_changed_opaque_listing_cannot_reuse_claim(self):
        claim=self.claim();self.option['listing_revision']=2
        with self.assertRaisesRegex(ValueError,'purchase terms changed'):self.choose(claim,self.option['id'])
        self.assertEqual(self.world.agency_plan()['phase'],'thinking')

    def test_changed_need_or_listing_at_arrival_is_held_without_offer(self):
        claim=self.claim();self.choose(claim,self.option['id']);self.sync();plan=self.world.agency_plan()
        self.validator.return_value=False
        self.obs['ack']={'id':plan['travel_id'],'status':'applied','movement':{
            'hasOwnedPackage':True,'aliasesConfirmed':True,'adapter':'papyrus-mailbox','actor':99,'target':501}}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held');self.assertNotIn('economic_speech',self.world.agency_plan())

    def test_old_unbound_intent_and_changed_market_policy_require_new_review(self):
        self.arrive();plan=self.world.agency_plan()
        for value in (None,'0'*64):
            with self.subTest(value=value):
                plan['market_policy_hash']=value
                with self.assertRaisesRegex(ValueError,'policy changed or is unbound'):self.world._plan_context(self.obs,plan)

    def test_direct_acceptance_retains_both_claims_and_exact_total_before_voice(self):
        self.arrive();self.decide('bid_price_3')
        self.world.agency_plan()['voiced_trade']=True
        self.decide('sell_goods');plan=self.world.agency_plan();accepted=plan['accepted_trade']
        self.assertEqual((accepted['commodity'],accepted['quantity'],accepted['unit_price'],accepted['cost']),('ore',5,3,15))
        self.assertEqual(accepted['buyer_claim_id'],plan['decisions'][-2]['claim_id'])
        self.assertEqual(accepted['seller_claim_id'],plan['decisions'][-1]['claim_id'])
        self.assertEqual(plan['phase'],'economic_attending');self.assertIsNone(self.world.active['pending'])


if __name__=='__main__':unittest.main()
