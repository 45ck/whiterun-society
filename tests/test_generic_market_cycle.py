"""Real choice/listing/procurement -> actual JS exchange -> production opportunity.

Catalog assets and actor/form APIs are synthetic fixtures. No game deployment,
model response quality, labour completion or productive animation is claimed.
"""
import copy
import json
from unittest.mock import patch

import economy_catalog
import market_policy
from entrepreneurship import learn_recipe
from owner_production import owner_work_opportunities
from procurement import input_procurement, validate_procurement
from test_catalog_enterprises import expanded_catalog
import test_trade_protocol_interop as interop


class GenericMarketCycleTests(interop.TradeInteropBase):
    commodity='ore'

    def setUp(self):
        self.enterContext(patch.object(economy_catalog,'ECONOMY_CATALOG',expanded_catalog()))
        policy=copy.deepcopy(market_policy.MARKET_POLICY)
        policy['catalog_hash']=economy_catalog.catalog_hash()
        policy['goods'].append({'commodity':'ore','legacy_retail_capability':None,
            'max_quantity':10,'quantity_choices':[1,2,5,10],
            'price_min':2,'price_max':20,'price_choices':[2,3,5,10,20],'reserve_mode':'seller_choice'})
        self.enterContext(patch.object(market_policy,'MARKET_POLICY',market_policy.validate_policy(policy)))
        super().setUp()
        stock={'buyer':{'gold':30,'bread':2,'grain':0,'ore':0,'ingot':0},
               'seller':{'gold':7139,'bread':2,'grain':0,'ore':27,'ingot':0}}
        self.observe_native(self.native.request('external_stock',stock=stock));self.bind()
        self.obs['routing']={'available':True,'adapter':'papyrus-mailbox-v1'}
        self.obs['residents'][1]['name']='Private seller name'
        self.world.active['people']['902']['profile']['name']='Private seller name'
        self.world.active['people']['901']['needs'].update(hunger=.9,fatigue=.1)
        for event,spec in [('fixture-forge',{'id':'forge','expected_revision':0,'name':'Public forge',
            'custodian':901,'capabilities':['metal_recipe'],'active':True,
            'recipe_policies':{'metal_recipe':{'target_output':5}}}),
            ('fixture-supplier',{'id':'supplier','expected_revision':0,'name':'Public ore supplier',
             'custodian':902,'capabilities':['retail_goods'],'sale_commodities':['ore'],'active':True})]:
            self.world.configure_enterprise(event,spec,self.obs);self.bind()
        # Explicit prior verified-production fixture; a public charter teaches nothing.
        learn_recipe(self.world.active['people']['901'],'fixture-prior-metal-production','metal_recipe')
        self.world.review_population(self.obs);self.bind()
        self.event=next(row for row in self.world.active['town']['daily']['queue']
                        if row['actor']==901 and row['kind']=='need_review' and row['status']=='pending')

    def claim(self):
        result=self.world.claim_plan_decision(self.event['id'],self.obs)['claim'];self.bind()
        return result

    def choose(self,claim,action):
        self.world.finish_plan_decision(self.event['id'],claim['id'],{'model':'deterministic-test-choice',
            'decision':{'action_id':action,'reason':'Explicit integration fixture choice','emotion':'calm'}},self.obs)
        self.bind()

    def start(self):
        self.world.begin_plan(self.event['id'],self.obs,901,'need_review');self.bind()
        claim=self.claim()
        selected=next(row for row in claim['context']['purchase_options'].values()
                      if row['commodity']=='ore' and row['quantity']==5 and row['supplier']==902)
        self.assertTrue(validate_procurement(self.world.active,self.obs,901,selected))
        self.assertEqual(selected['shortfall'],10)
        return claim,selected

    def arrive(self,claim,selected):
        self.choose(claim,selected['id'])
        travel=self.world.pending(self.obs['session'])
        self.assertEqual((travel['actor'],travel['target']),(901,902))
        self.obs['ack']={'id':travel['id'],'status':'applied','movement':{
            'id':travel['id'],'actor':901,'target':902,'adapter':'papyrus-mailbox',
            'aliasesConfirmed':True,'hasOwnedPackage':True}}
        self.world.observe(self.obs);self.bind()
        self.assertEqual(self.world.agency_plan()['phase'],'quote')

    def test_real_listings_choices_and_native_exchange_enable_owned_recipe_without_hunger_relief(self):
        claim,selected=self.start()
        for secret in ('7139','Private seller name','"ore": 27'):
            self.assertNotIn(secret,json.dumps(claim['context']))
        self.assertEqual(self.native.request('state')['calls'],[])
        self.arrive(claim,selected)
        hunger=self.world.active['people']['901']['needs']['hunger']
        before=copy.deepcopy(self.native.request('state')['stock'])
        buyer=self.claim();self.assertEqual(buyer['context']['actor_id'],901)
        self.assertEqual(buyer['context']['quantity'],5)
        self.choose(buyer,'bid_price_3')
        seller=self.claim();self.assertEqual(seller['context']['actor_id'],902)
        self.assertIn('sell_goods',[row['id'] for row in seller['context']['options']])
        self.assertNotIn('sell_bread',[row['id'] for row in seller['context']['options']])
        self.choose(seller,'sell_goods')
        command=self.world.pending(self.obs['session'])
        self.assertEqual((command['phase'],command['commodity'],command['quantity'],command['cost']),('arm','ore',5,15))
        armed=self.native.request('step',command=command)
        self.assertEqual(armed['result']['ack']['phase'],'armed')
        self.assertEqual(armed['calls'],[]);self.assertEqual(armed['stock'],before)
        self.observe_native(armed)
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'bind_checkpoint')
        self.assertEqual(self.world.active['trades'],[])
        self.bind();delivery=self.world.pending(self.obs['session'])
        self.assertEqual(delivery['phase'],'deliver')
        for _ in range(5):
            result=self.native.request('step',command=delivery)
            if result['result']['done']:break
            self.assertEqual(result['queued'],1)
            self.native.request('apply')
        else:self.fail('Actual native trade controller did not finish bounded exchange')
        self.assertEqual(result['result']['ack']['phase'],'complete')
        self.assertEqual(result['calls'],[
            {'from':'seller','to':'buyer','item':'ore','amount':5},
            {'from':'buyer','to':'seller','item':'gold','amount':15}])
        self.observe_native(result);self.bind()
        self.assertEqual(result['stock']['buyer'],{'gold':15,'bread':2,'grain':0,'ore':5,'ingot':0})
        self.assertEqual(result['stock']['seller'],{'gold':7154,'bread':2,'grain':0,'ore':22,'ingot':0})
        for item in economy_catalog.commodity_ids():
            self.assertEqual(sum(row[item] for row in before.values()),sum(row[item] for row in result['stock'].values()))
        self.assertEqual(self.world.agency_plan()['outcome'],'purchased_input')
        self.assertEqual(self.world.active['people']['901']['needs']['hunger'],hunger)
        memories=[row for row in self.world.active['people']['901']['memories'] if row['kind']=='completed_trade']
        self.assertEqual(len(memories),1)
        self.assertEqual({key:memories[0][key] for key in ('commodity','quantity','gold','purpose')},
                         {'commodity':'ore','quantity':5,'gold':15,'purpose':'production_input'})
        replay=self.native.request('step',command=delivery)
        self.assertEqual(len(replay['calls']),2)
        self.observe_native(replay);self.bind()
        self.assertEqual(len(self.world.active['trades']),1)
        self.obs['residents'][0]['activity']={'package_id':9000,'scene_id':0,'in_combat':False,'sleep_state':0}
        self.obs['resident_control']={'activities':[{'actor':901,'ownedPackage':True,'expectedPackage':9000}]}
        options=owner_work_opportunities(self.world.active,self.obs,901)
        self.assertEqual([(row['business_id'],row['recipe_id']) for row in options],[('forge','metal_recipe')])
        self.assertEqual(self.world.active.get('production',[]),[],'buying ore does not create ingots or prove labour')

    def test_changed_public_listing_invalidates_original_resident_choice(self):
        claim,selected=self.start()
        self.world.active['town']['businesses']['supplier']['sale_commodities']=[]
        self.world.active['town']['businesses']['supplier']['revision']+=1
        self.assertFalse(validate_procurement(self.world.active,self.obs,901,selected))
        with self.assertRaises(ValueError):self.choose(claim,selected['id'])
        self.assertIsNone(self.world.active['pending'])
        self.assertEqual(self.native.request('state')['calls'],[])

    def test_unknown_personal_recipe_blocks_input_intent_despite_public_charters(self):
        self.world.active['people']['901']['known_recipes']={}
        self.assertEqual(input_procurement(self.world.active,self.obs,901),[])
        self.world.begin_plan(self.event['id'],self.obs,901,'need_review');self.bind()
        self.assertEqual(self.claim()['context']['purchase_options'],{})
        self.assertEqual(self.world.active['town']['businesses']['supplier']['sale_commodities'],['ore'])
        self.assertEqual(self.native.request('state')['calls'],[])
