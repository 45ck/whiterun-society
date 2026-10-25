import copy
import json
import unittest
import test_dynamic_economy as fixtures
from bargaining import price_choices, own_prices, MAX_ECONOMIC_CALLS
from metrics import simulation_metrics


class BargainingTests(unittest.TestCase):
    setUp=fixtures.DynamicEconomyTests.setUp
    tearDown=fixtures.DynamicEconomyTests.tearDown
    sync=fixtures.DynamicEconomyTests.sync
    census=fixtures.DynamicEconomyTests.census
    review=fixtures.DynamicEconomyTests.review
    claim=fixtures.DynamicEconomyTests.claim
    choose=fixtures.DynamicEconomyTests.choose

    def decide(self,action):
        claim=self.world.claim_plan_decision(self.event['id'],self.obs)['claim'];self.sync()
        self.choose(claim,action);self.sync()
        return claim['context']

    def arrive(self,voice=False):
        self.obs['residents'][0]['inventory']['gold']=20
        self.choose(self.claim());self.sync()
        plan=self.world.agency_plan()
        if voice:plan['voiced_trade']=True
        self.obs['ack']={'id':plan['travel_id'],'status':'applied','movement':{
            'hasOwnedPackage':True,'aliasesConfirmed':True,'adapter':'papyrus-mailbox','actor':99,'target':501}}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'quote')

    def settle_sale(self):
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'inventory_trade')
        for actor,role in ((99,'buyer'),(501,'seller')):
            resident=next(r for r in self.obs['residents'] if r['id']==actor)
            resident['inventory'].update(command['after'][role])
        self.obs['ack']={'id':command['id'],'status':'applied'}
        self.world.observe(self.obs);self.sync()
        return command

    def test_initial_bid_and_final_higher_bid_are_resident_choices(self):
        self.arrive();opening=self.decide('bid_price_2')
        self.assertNotIn('7139',json.dumps(opening))
        self.assertEqual(self.world.agency_plan()['unit_price'],2)
        self.decide('decline');second=self.decide('bid_price_7')
        self.assertNotIn('bid_price_2',[o['id'] for o in second['options']])
        self.decide('sell_bread');command=self.settle_sale()
        self.assertEqual(command['cost'],7)
        self.decide('keep_food')
        self.assertEqual(len(self.world.agency_plan()['decisions']),MAX_ECONOMIC_CALLS)
        self.assertEqual(own_prices(self.world.active['people']['99'])[-1]['septims_per_loaf'],7)

    def test_reserved_seller_counteroffer_requires_buyer_acceptance_and_preserves_policy(self):
        seller=self.world.active['people']['501'];seller['food_policy']={'mode':'household_all'}
        self.arrive();self.decide('bid_price_2');self.decide('ask_price_7')
        self.assertIsNone(self.world.active['pending'])
        self.assertEqual(self.world.agency_plan()['phase'],'reconsider')
        context=self.decide('accept_counterprice')
        for secret in ('7139','counter_quote','reserved loaf','Secret seller name'):
            self.assertNotIn(secret,json.dumps(context))
        command=self.settle_sale();self.assertEqual(command['cost'],7)
        self.assertEqual(self.world.active['people']['501']['food_policy'],{'mode':'household_all'})
        self.assertTrue(self.world.active['trades'][-1]['reserve_release'])

    def test_unaffordable_counteroffer_can_only_be_declined_or_left(self):
        self.arrive();self.decide('bid_price_2');self.decide('ask_price_50')
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertNotIn('accept_counterprice',[o['id'] for o in context['options']])
        self.decide('leave_without_food');self.assertEqual(self.world.active['trades'],[])

    def test_changed_quote_stock_or_policy_invalidates_acceptance(self):
        self.arrive();self.decide('bid_price_2');self.decide('ask_price_7')
        claim=self.world.claim_plan_decision(self.event['id'],self.obs)['claim'];self.sync()
        self.obs['residents'][1]['inventory']['bread']-=1
        with self.assertRaisesRegex(ValueError,'quote changed'):self.choose(claim,'accept_counterprice')
        self.assertIsNone(self.world.active['pending'])

    def test_second_refusal_ends_bargaining_without_silent_price_escalation(self):
        self.arrive();self.decide('bid_price_1');self.decide('decline');self.decide('bid_price_4')
        seller=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertFalse(any(o['id'].startswith('ask_price_') for o in seller['options']))
        self.decide('decline')
        self.assertEqual(self.world.agency_plan()['outcome'],'seller_declined')
        self.assertIsNone(self.world.active['pending'])

    def test_one_septim_buyer_is_not_excluded_by_old_three_septim_rule(self):
        self.obs['residents'][0]['inventory']['gold']=1
        context=self.claim()['context']
        self.assertIn('seek_bread',[o['id'] for o in context['options']])

    def test_price_history_is_personal_and_ignores_unverified_rumours(self):
        person={'memories':[{'kind':'completed_trade','gold':46,'bread':2,'role':'bought'},
                            {'kind':'heard_speech','gold':90,'bread':1}]}
        self.assertEqual([r['septims_per_loaf'] for r in own_prices(person)],[23])
        prices=price_choices(person,24,above=20)
        self.assertEqual(prices,[21,22,23,24])
        self.assertEqual(price_choices(person,1),[1]);self.assertEqual(price_choices(person,0),[])
        self.assertLessEqual(max(price_choices(person,10000)),100)

    def speak(self):
        plan=self.world.agency_plan()
        if plan['phase']=='economic_attending':
            self.obs['conversationAttendance']={'id':'economic-attend-'+plan['id'],'phase':'attending',
                'participants':[{'actor':a,'ownedPackage':True,'loaded':True} for a in (99,501)]}
            self.obs['ack']={'id':'economic-attend-'+plan['id'],'status':'applied'}
            self.world.observe(self.obs);self.sync()
        audio={'file':'a'*64+'.wav','sha256':'a'*64,'seconds':2,'voice':'bf_emma','engine':'kokoro-onnx-0.6.1'}
        self.world.prepare_trade_speech(plan['id'],audio,self.obs);self.sync()
        command=self.world.pending(self.obs['session'])
        self.obs['speech']={'id':command['id'],'status':'ended','playedSeconds':2,'nearbyThroughout':True}
        self.world.observe(self.obs);self.sync()
        return command

    def test_voiced_counteroffer_and_buyer_acceptance_precede_physical_effects(self):
        self.arrive(voice=True);self.decide('bid_price_4')
        self.assertEqual(self.speak()['actor'],99)
        self.decide('ask_price_7');ask=self.speak()
        self.assertEqual(ask['actor'],501);self.assertIn('7 gold',ask['line'])
        self.decide('accept_counterprice');self.assertIsNone(self.world.active['pending'])
        accepted=self.speak();self.assertEqual(accepted['actor'],99)
        self.assertIn('7 gold',accepted['line'])
        self.settle_sale();self.assertEqual(self.speak()['actor'],99)
        self.assertEqual(len(self.world.agency_plan()['economic_turns']),4)

    def test_old_save_does_not_inherit_future_bid_or_counterquote(self):
        self.arrive();old=copy.deepcopy(self.obs)
        self.decide('bid_price_4');self.decide('ask_price_7')
        self.world.observe({**old,'session':'restored-save'})
        plan=self.world.agency_plan()
        self.assertEqual(plan['phase'],'quote');self.assertNotIn('counter_quote',plan)
        self.assertEqual(plan['offer_round'],0)
