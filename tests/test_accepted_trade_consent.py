"""Accepted generic action IDs do not authorize another price, partner or account."""
import copy
import unittest
from economy_catalog import catalog_hash
from market_policy import policy_hash
from trade_consent import accepted_trade_consent


class AcceptedTradeConsentTests(unittest.TestCase):
    def setUp(self):
        self.inventory={'buyer':{'gold':20,'bread':2,'grain':0},'seller':{'gold':7,'bread':1,'grain':5}}
        terms={'buyer':1,'seller':2,'commodity':'grain','quantity':2,'unit_price':3,'cost':6,
            'catalog_hash':catalog_hash(),'market_policy_hash':policy_hash(),'purpose':'other'}
        decisions=[]
        for role,actor,other,action in [('buyer',1,2,'bid_price_3'),('seller',2,1,'sell_goods')]:
            decisions.append({'actor_id':actor,'claim_id':role+'-claim','decision':{'action_id':action},'context':{
                'actor_id':actor,'commodity':'grain','quantity':2,'unit_price':3,'cost':6,'purpose':'other',
                'inventory_catalog_hash':catalog_hash(),'market_policy_hash':policy_hash(),'observed_inventory':copy.deepcopy(self.inventory[role]),
                'event':{'id':'plan'},'economic_counterparty':{'id':other},'options':[{'id':action}],
                'price_options':{action:3} if role=='buyer' else {}}})
        self.plan={'id':'plan','trade_id':'trade','phase':'ready_to_trade','actor':1,'target':2,'commodity':'grain','quantity':2,
            'unit_price':3,'purpose':'other','decisions':decisions,'accepted_trade':{**terms,'buyer_claim_id':'buyer-claim','seller_claim_id':'seller-claim'}}
        self.state={'plans':[self.plan],'people':{'1':{},'2':{}}}

    def consent(self):return accepted_trade_consent(self.state,'trade',1,2,2,3,'plan',self.inventory,'grain')

    def test_qualified_claims_bind_terms_and_source_without_private_prompt_copy(self):
        result=self.consent();self.assertEqual(result['payload']['source_kind'],'resident_decisions')
        self.assertEqual(result['payload']['quantity'],2);self.assertEqual(result['payload']['purpose'],'other')
        self.assertNotIn('observed_inventory',result['payload']);self.assertEqual(len(result['payload']['decision_proof']),2)

    def test_old_displayed_price_does_not_override_a_qualified_bid_choice(self):
        self.plan['decisions'][0]['context'].update(unit_price=1,cost=2)
        self.assertEqual(self.consent()['payload']['unit_price'],3)

    def test_changed_seller_price_is_not_accepted_by_generic_action_id(self):
        self.plan['decisions'][1]['context'].update(unit_price=4,cost=8)
        with self.assertRaisesRegex(ValueError,'price or total'):self.consent()

    def test_changed_buyer_or_seller_account_invalidates_saved_acceptance(self):
        for role in ('buyer','seller'):
            with self.subTest(role=role):
                self.inventory[role]['grain']+=1
                with self.assertRaisesRegex(ValueError,'qualified context'):self.consent()
                self.inventory[role]['grain']-=1

    def test_other_counterparty_claim_cannot_be_reused(self):
        self.plan['decisions'][1]['context']['economic_counterparty']['id']=3
        with self.assertRaisesRegex(ValueError,'another encounter'):self.consent()

    def test_other_purpose_claim_cannot_be_reused(self):
        self.plan['decisions'][1]['context']['purpose']='food'
        with self.assertRaisesRegex(ValueError,'another encounter'):self.consent()

    def test_missing_seller_claim_or_duplicate_claim_is_not_consent(self):
        self.plan['accepted_trade']['seller_claim_id']='absent'
        with self.assertRaisesRegex(ValueError,'provenance'):self.consent()
        self.plan['accepted_trade']['seller_claim_id']='seller-claim'
        self.plan['decisions'].append(copy.deepcopy(self.plan['decisions'][-1]))
        with self.assertRaisesRegex(ValueError,'provenance'):self.consent()

    def test_generic_action_context_without_option_authority_is_rejected(self):
        self.plan['decisions'][1]['context']['options']=[]
        with self.assertRaisesRegex(ValueError,'qualified context'):self.consent()
