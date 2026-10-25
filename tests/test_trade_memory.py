import json
import unittest
import test_economic_speech as fixtures
from trade_memory import remember_refusal_decision, remember_refusal_heard


class RefusalMemoryTests(unittest.TestCase):
    def setUp(self):
        self.state={'people':{'1':{'memories':[]},'2':{'memories':[]}}}
        self.plan={'id':'sale','actor':1,'target':2,'voiced_trade':True,'unit_price':3,'commodity':'bread','quantity':1,
            'offer_round':1,'decisions':[{'claim_id':'choice-1','decision':{'reason':'PRIVATE_STOCK_REASON'},
                'context':{'reserved_stock':999}}]}

    def turn(self,event,delivery='heard-1'):
        return {'refusal_event_id':event,'act':'refuse','actor':2,'listener':1,'delivered':True,
            'delivery_id':delivery,'audio':{'seconds':2},'playback':{'id':delivery,'status':'ended',
                'playedSeconds':2,'nearbyThroughout':True}}

    def test_decision_is_private_and_hearing_is_once_without_private_context(self):
        event=remember_refusal_decision(self.state,self.plan)
        self.assertEqual(remember_refusal_decision(self.state,self.plan),event)
        self.assertEqual(self.state['people']['1']['memories'],[])
        self.assertEqual(len(self.state['people']['2']['memories']),1)
        self.assertEqual(self.plan['refusals_recorded'],1)
        turn=self.turn(event)
        self.assertTrue(remember_refusal_heard(self.state,self.plan,turn))
        self.assertFalse(remember_refusal_heard(self.state,self.plan,turn))
        self.assertEqual(len(self.state['people']['1']['memories']),1)
        self.assertEqual(self.plan['refusals_recorded'],1)
        memories=json.dumps(self.state)
        self.assertNotIn('PRIVATE_STOCK_REASON',memories);self.assertNotIn('999',memories)

    def test_rounds_and_same_price_new_decisions_are_distinct_and_use_snapshot(self):
        first=remember_refusal_decision(self.state,self.plan)
        self.plan.update(unit_price=5,offer_round=2)
        self.plan['decisions'].append({'claim_id':'choice-2'})
        second=remember_refusal_decision(self.state,self.plan)
        self.plan['decisions'].append({'claim_id':'choice-3'})
        third=remember_refusal_decision(self.state,self.plan)
        self.assertEqual(len({first,second,third}),3)
        for index,event in enumerate((first,second,third)):
            self.assertTrue(remember_refusal_heard(self.state,self.plan,self.turn(event,'heard-'+str(index))))
        self.assertEqual([m['gold'] for m in self.state['people']['1']['memories']],[3,5,5])
        self.assertEqual(self.plan['refusals_recorded'],3)

    def test_failed_partial_distant_wrong_delivery_or_party_does_not_create_knowledge(self):
        event=remember_refusal_decision(self.state,self.plan)
        for field,value in [('status','failed'),('playedSeconds',.1),('nearbyThroughout',False),
                            ('id','wrong'),('playedSeconds',float('nan'))]:
            with self.subTest(field=field,value=value):
                turn=self.turn(event);turn['playback'][field]=value
                self.assertFalse(remember_refusal_heard(self.state,self.plan,turn))
        turn=self.turn(event);turn['listener']=2
        self.assertFalse(remember_refusal_heard(self.state,self.plan,turn))
        self.assertEqual(self.state['people']['1']['memories'],[])

    def test_legacy_unvoiced_feedback_is_explicitly_nonspoken(self):
        self.plan['voiced_trade']=False
        remember_refusal_decision(self.state,self.plan);remember_refusal_decision(self.state,self.plan)
        memory=self.state['people']['1']['memories'][0]
        self.assertIn('non-spoken',memory['source']);self.assertNotIn('delivery_id',memory)
        self.assertEqual(len(self.state['people']['1']['memories']),1)

    def test_multiunit_refusal_remembers_frozen_quantity_and_total_only_after_hearing(self):
        self.plan.update(commodity='grain',quantity=5,unit_price=4)
        event=remember_refusal_decision(self.state,self.plan)
        self.assertEqual(self.state['people']['1']['memories'],[])
        self.plan.update(quantity=1,unit_price=99)
        self.assertTrue(remember_refusal_heard(self.state,self.plan,self.turn(event)))
        memory=self.state['people']['1']['memories'][0]
        self.assertEqual((memory['commodity'],memory['quantity'],memory['grain'],memory['unit_price'],memory['cost'],memory['gold']),('grain',5,5,4,20,20))

    def test_missing_or_unknown_terms_do_not_create_refusal_knowledge(self):
        for changes in ({'commodity':None},{'commodity':'unconfigured'},{'quantity':None},{'quantity':True}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                remember_refusal_decision(self.state,{**self.plan,**changes})
        self.assertTrue(all(not p['memories'] for p in self.state['people'].values()))


class RefusalSpeechIntegrationTests(unittest.TestCase):
    setUp=fixtures.EconomicSpeechTests.setUp
    tearDown=fixtures.EconomicSpeechTests.tearDown
    sync=fixtures.EconomicSpeechTests.sync
    decide=fixtures.EconomicSpeechTests.decide
    arrive=fixtures.EconomicSpeechTests.arrive
    start=fixtures.EconomicSpeechTests.start
    speak=fixtures.EconomicSpeechTests.speak

    def refusals(self,actor):
        return [m for m in self.world.active['people'][str(actor)]['memories'] if m['kind']=='trade_offer_declined']

    def test_seller_private_then_buyer_hears_each_offer_once(self):
        self.start();self.speak();self.decide('decline')
        self.assertEqual(len(self.refusals(108149)),1);self.assertEqual(self.refusals(108186),[])
        self.speak();self.assertEqual(len(self.refusals(108186)),1)
        self.world.observe(self.obs);self.sync();self.assertEqual(len(self.refusals(108186)),1)
        self.decide('bid_price_5');self.speak();self.decide('decline')
        self.assertEqual(len(self.refusals(108149)),2);self.assertEqual(len(self.refusals(108186)),1)
        self.speak();self.assertEqual([m['gold'] for m in self.refusals(108186)],[3,5])
        self.assertEqual(self.world.agency_plan()['refusals_recorded'],2)

    def test_incomplete_refusal_cannot_tell_buyer_what_seller_decided(self):
        self.start();self.speak();self.decide('decline');self.speak(complete=False)
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(self.refusals(108186),[]);self.assertEqual(len(self.refusals(108149)),1)
        self.assertEqual(self.world.agency_plan()['refusals_recorded'],1)
