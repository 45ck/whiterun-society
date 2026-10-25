"""Real configured demand/listings, independent of mocked agency options."""
import copy
import json
import unittest
from unittest.mock import patch
import economy_catalog as catalog
import market_policy
from test_catalog_enterprises import expanded_catalog
from population import person_seed
from entrepreneurship import learn_recipe, enterprise_choices
from procurement import input_procurement, validate_procurement, validate_procurement_terms
from opportunities import commodity_sellers


class GenericProcurementTests(unittest.TestCase):
    def setUp(self):
        expanded=expanded_catalog()
        p=patch.object(catalog,'ECONOMY_CATALOG',expanded);p.start();self.addCleanup(p.stop)
        policy=copy.deepcopy(market_policy.MARKET_POLICY);policy['catalog_hash']=catalog.catalog_hash()
        for item in ('ore','ingot'):
            policy['goods'].append({'commodity':item,'legacy_retail_capability':None,'max_quantity':10,
                'quantity_choices':[1,2,5,10],'price_min':2,'price_max':20,'price_choices':[2,3,5,10,20],
                'reserve_mode':'seller_choice'})
        p=patch.object(market_policy,'MARKET_POLICY',policy);p.start();self.addCleanup(p.stop)
        self.obs={'routing':{'available':True,'adapter':'papyrus-mailbox-v1'},'residents':[
            {'id':7,'isPerson':True,'x':0,'y':0,'z':0,'name':'Artisan','inventory':{'gold':20,'bread':2,'grain':0,'ore':0,'ingot':0}},
            {'id':8,'isPerson':True,'x':100,'y':0,'z':0,'name':'Secret seller','inventory':{'gold':7139,'bread':2,'grain':0,'ore':27,'ingot':0}}]}
        self.state={'people':{str(r['id']):person_seed(r,'fixture',1) for r in self.obs['residents']},
            'town':{'residents':{'7':{},'8':{}},'businesses':{
                'forge':{'owner':7,'custodian':7,'revision':1,'capabilities':['metal_recipe'],
                    'recipe_policies':{'metal_recipe':{'target_output':5}}},
                'supply':{'owner':8,'custodian':8,'revision':3,'capabilities':['retail_goods'],'sale_commodities':['ore']}}}}
        learn_recipe(self.state['people']['7'],'fixture-prior-production','metal_recipe')

    def choices(self):return input_procurement(self.state,self.obs,7)

    def test_configured_quantities_use_own_need_and_one_shared_purse(self):
        before=copy.deepcopy((self.state,self.obs));rows=self.choices()
        self.assertEqual([r['quantity'] for r in rows],[1,2,5,10])
        self.assertEqual({r['shortfall'] for r in rows},{10})
        self.assertEqual(len({r['id'] for r in rows}),4)
        self.assertEqual((self.state,self.obs),before,'opportunities allocate nothing')
        for secret in ('7139','Secret seller','"inventory"'):self.assertNotIn(secret,json.dumps(rows))
        self.assertFalse(any(value==27 for row in rows for value in row.values()))
        self.obs['residents'][0]['inventory']['gold']=7
        self.assertEqual([r['quantity'] for r in self.choices()],[1,2])

    def test_known_recipe_is_required_but_public_listing_does_not_reveal_stock(self):
        self.obs['residents'][1]['inventory']['ore']=0
        self.assertEqual(len(self.choices()),4)
        self.state['people']['7']['known_recipes']={}
        self.assertEqual(self.choices(),[])
        self.assertEqual(len(commodity_sellers(self.state,self.obs,7,'ore')),1)

    def test_current_need_and_revision_revalidated_without_pinning_distance(self):
        selected=self.choices()[2]
        self.obs['residents'][1]['x']=150
        self.obs['residents'][0]['inventory']['ore']=4
        self.assertTrue(validate_procurement(self.state,self.obs,7,selected))
        self.obs['residents'][0]['inventory']['ore']=6
        self.assertFalse(validate_procurement(self.state,self.obs,7,selected))
        self.obs['residents'][0]['inventory']['ore']=0
        self.state['town']['businesses']['supply']['revision']+=1
        self.assertFalse(validate_procurement(self.state,self.obs,7,selected))

    def test_production_or_names_alone_never_advertise_a_seller(self):
        self.state['town']['businesses']['supply']={'owner':8,'custodian':8,'capabilities':['metal_recipe']}
        self.assertEqual(self.choices(),[])
        self.assertEqual(commodity_sellers({'people':self.state['people']},self.obs,7,'bread'),[])

    def test_multiple_charters_are_alternatives_not_summed_shortfalls(self):
        self.state['town']['businesses']['second-forge']=copy.deepcopy(self.state['town']['businesses']['forge'])
        rows=self.choices()
        self.assertEqual(len(rows),8);self.assertEqual(len({r['id'] for r in rows}),8)
        self.assertEqual({r['shortfall'] for r in rows},{10})
        self.obs['residents'][0]['inventory']['ore']=10
        self.assertEqual(self.choices(),[])

    def test_generic_retail_registration_is_a_choice_and_preserves_existing_sales(self):
        self.obs['residents'][0]['inventory']['ore']=3
        choices=enterprise_choices(self.state,self.obs,7)
        offer=next(r for r in choices if r['id'].startswith('offer_goods_') and r['specification'].get('sale_commodities')==['ore'])
        self.assertEqual(offer['specification']['sale_commodities'],['ore'])
        self.assertIn('retail_goods',offer['specification']['capabilities'])
        self.assertNotIn('retail_goods',self.state['town']['businesses']['forge']['capabilities'])

    def test_forged_or_removed_listing_and_changed_policy_do_not_revalidate(self):
        selected=self.choices()[0]
        self.assertFalse(validate_procurement(self.state,self.obs,7,{**selected,'quantity':10}))
        self.state['town']['businesses']['supply']['sale_commodities']=[]
        self.assertFalse(validate_procurement(self.state,self.obs,7,selected))
        self.state['town']['businesses']['supply']['sale_commodities']=['ore']
        market_policy.MARKET_POLICY['id']='reviewed-new-policy'
        self.assertFalse(validate_procurement(self.state,self.obs,7,selected))

    def test_structural_terms_survive_their_own_inventory_transfer_and_lease(self):
        selected=self.choices()[2]
        self.state['pending']={'status':'pending','command':{'kind':'inventory_trade','buyer':7,'seller':8}}
        self.obs['residents'][0]['inventory'].update(ore=10,gold=0)
        self.assertFalse(validate_procurement(self.state,self.obs,7,selected))
        self.assertTrue(validate_procurement_terms(self.state,7,selected))
        self.state['town']['businesses']['forge']['revision']+=1
        self.assertFalse(validate_procurement_terms(self.state,7,selected))

    def test_underscores_in_goods_and_business_names_do_not_collide(self):
        item=copy.deepcopy(next(row for row in catalog.ECONOMY_CATALOG['commodities'] if row['id']=='ore'))
        item.update(id='ore_x',label='ore x');item['native']['local_form_id']=4098
        catalog.ECONOMY_CATALOG['commodities'].append(item)
        policy=market_policy.MARKET_POLICY;policy['catalog_hash']=catalog.catalog_hash()
        row=copy.deepcopy(next(row for row in policy['goods'] if row['commodity']=='ore'));row['commodity']='ore_x'
        policy['goods'].append(row)
        for resident in self.obs['residents']:resident['inventory']['ore_x']=2
        self.obs['residents'][0]['inventory']['ore']=2
        self.state['town']['businesses']['x_forge']=copy.deepcopy(self.state['town']['businesses']['forge'])
        choices=enterprise_choices(self.state,self.obs,7)
        ids=[row['id'] for row in choices]
        self.assertEqual(len(ids),len(set(ids)))
        goods=[row for row in choices if row['id'].startswith('offer_goods_')]
        self.assertEqual(len(goods),4)


if __name__=='__main__':unittest.main()
