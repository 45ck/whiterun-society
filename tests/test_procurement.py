import copy
import json
import unittest
import test_bargaining as fixtures
from bargaining import own_prices
from procurement import grain_procurement
from owner_production import owner_work_opportunities
from metrics import simulation_metrics


class ProcurementTests(unittest.TestCase):
    tearDown=fixtures.BargainingTests.tearDown
    sync=fixtures.BargainingTests.sync
    census=fixtures.BargainingTests.census
    review=fixtures.BargainingTests.review
    claim=fixtures.BargainingTests.claim
    choose=fixtures.BargainingTests.choose
    decide=fixtures.BargainingTests.decide
    settle_sale=fixtures.BargainingTests.settle_sale
    speak=fixtures.BargainingTests.speak

    def setUp(self):
        fixtures.BargainingTests.setUp(self)
        self.obs['residents'][0]['inventory'].update(gold=20,bread=2,grain=0)
        self.obs['residents'][1]['inventory'].update(grain=3)
        self.world.active['town']['businesses']={
            'bakery':{'owner':99,'custodian':99,'revision':1,'capabilities':['bread_recipe']},
            'supplier':{'owner':501,'custodian':501,'revision':1,'capabilities':['retail_grain']}}
        self.world.active['people']['501']['food_policy']={'mode':'household_all'}

    def arrive(self,voice=False):
        claim=self.claim();self.choose(claim,'procure_grain_501');self.sync()
        plan=self.world.agency_plan()
        if voice:plan['voiced_trade']=True
        self.obs['ack']={'id':plan['travel_id'],'status':'applied','movement':{
            'hasOwnedPackage':True,'aliasesConfirmed':True,'adapter':'papyrus-mailbox','actor':99,'target':501}}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'quote')
        return claim

    def test_procurement_uses_public_supplier_and_own_shortfall_without_stock_omniscience(self):
        context=self.arrive()['context']
        self.assertEqual(context['option_targets']['procure_grain_501'],501)
        self.assertEqual(context['work_options']['procure_grain_501'][0]['grain_shortfall'],3)
        for secret in ('7139','Secret seller name','Carlotta'):
            self.assertNotIn(secret,json.dumps(context))

    def test_verified_grain_purchase_preserves_bread_and_hunger_then_enables_production(self):
        self.arrive();hunger=self.world.active['people']['99']['needs']['hunger']
        self.decide('bid_price_2');context=self.decide('sell_grain');command=self.settle_sale()
        self.assertNotIn('sell_bread',[o['id'] for o in context['options']])
        self.assertEqual(command['commodity'],'grain')
        self.assertEqual(command['after']['buyer'],{'gold':18,'bread':2,'grain':1})
        self.assertEqual(command['after']['seller'],{'gold':7141,'bread':2,'grain':2})
        self.assertEqual(self.world.agency_plan()['outcome'],'bought_grain')
        self.assertEqual(self.world.active['people']['99']['needs']['hunger'],hunger)
        self.assertEqual(self.world.active['people']['501']['food_policy'],{'mode':'household_all'})
        self.assertFalse(own_prices(self.world.active['people']['99']))
        self.assertEqual(own_prices(self.world.active['people']['99'],'grain')[-1]['septims_per_unit'],2)
        self.obs['residents'][0]['activity']={'package_id':9000,'scene_id':0,'in_combat':False,'sleep_state':0}
        self.obs['resident_control']={'activities':[{'actor':99,'ownedPackage':True,'expectedPackage':9000}]}
        self.assertEqual(owner_work_opportunities(self.world.active,self.obs,99)[0]['business_id'],'bakery')
        metrics=simulation_metrics(self.world.active)['economy']
        self.assertEqual(metrics['grain_procurement_sales'],1)
        self.assertEqual(metrics['bargaining']['by_commodity']['grain']['paid_prices']['median'],2)
        self.assertEqual(metrics['bargaining']['paid_prices']['n'],0,'grain is not a loaf price')

    def test_grain_counteroffer_binds_stock_but_never_releases_household_bread(self):
        self.arrive();self.decide('bid_price_2');self.decide('ask_price_4')
        self.decide('accept_counterprice');command=self.settle_sale()
        self.assertEqual(command['cost'],4)
        self.assertNotIn('reserve_release',self.world.active['trades'][-1])

    def test_grain_quote_rejects_inventory_change_before_acceptance(self):
        self.arrive();self.decide('bid_price_2');self.decide('ask_price_4')
        claim=self.world.claim_plan_decision(self.event['id'],self.obs)['claim'];self.sync()
        self.obs['residents'][1]['inventory']['grain']-=1
        with self.assertRaisesRegex(ValueError,'quote changed'):self.choose(claim,'accept_counterprice')
        self.assertIsNone(self.world.active['pending'])

    def test_supplier_advertisement_does_not_guarantee_stock_and_adequate_inputs_stop_procurement(self):
        self.obs['residents'][1]['inventory']['grain']=0
        self.assertEqual(len(grain_procurement(self.world.active,self.obs,99)),1)
        self.arrive();self.decide('bid_price_1')
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual([o['id'] for o in context['options']],['decline'])
        self.obs['residents'][0]['inventory']['grain']=3
        self.assertEqual(grain_procurement(self.world.active,self.obs,99),[])

    def test_grain_speech_uses_correct_good_and_receipt_waits_for_native_exchange(self):
        self.arrive(voice=True);self.decide('bid_price_3')
        offer=self.speak();self.assertIn('grain',offer['line']);self.assertNotIn('loaf',offer['line'])
        self.decide('sell_grain');accepted=self.speak();self.assertIn('grain',accepted['line'])
        self.settle_sale();receipt=self.speak();self.assertIn('received one unit of grain',receipt['line'])
        self.assertEqual(self.world.agency_plan()['phase'],'complete')
        self.assertEqual(len(self.world.agency_plan()['decisions']),3,'no pointless single-choice inference after procurement')

    def test_old_save_cannot_inherit_grain_purchase_or_memory(self):
        self.arrive();old=copy.deepcopy(self.obs)
        self.decide('bid_price_2');self.decide('sell_grain');self.settle_sale()
        self.world.observe({**old,'session':'restored-input-save'})
        self.assertEqual(self.world.active['trades'],[])
        self.assertEqual(own_prices(self.world.active['people']['99'],'grain'),[])

    def test_grain_and_bread_prices_stay_separate_and_legacy_memories_remain_bread(self):
        p={'memories':[{'kind':'completed_trade','bread':1,'gold':7},
            {'kind':'completed_trade','commodity':'grain','quantity':1,'grain':1,'gold':2}]}
        self.assertEqual([r['septims_per_unit'] for r in own_prices(p)],[7])
        self.assertEqual([r['septims_per_unit'] for r in own_prices(p,'grain')],[2])
