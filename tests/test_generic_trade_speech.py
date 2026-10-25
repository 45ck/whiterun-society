"""Catalog goods and batch terms remain exact across wording and hearing."""
import copy
import unittest
from unittest.mock import patch
import economy_catalog
from economic_language import trade_terms, validate_wording_candidate, TERMS
from economic_speech import EconomicSpeech
from trade_memory import remember_refusal_decision, remember_refusal_heard
from dashboard import town_dashboard
from metrics import simulation_metrics


class GenericTradeSpeechTests(unittest.TestCase):
    def setUp(self):
        self.catalog=copy.deepcopy(economy_catalog.ECONOMY_CATALOG)
        self.catalog['commodities'].append({
            'id':'iron','label':'Iron ingot','native':{'plugin':'Fixture.esp','local_form_id':200,'record_type':'MISC'},
            'currency':False,'provenance':'Authored test fixture; no real item resolution.'})
        self.patch=patch.object(economy_catalog,'ECONOMY_CATALOG',self.catalog)
        self.patch.start();self.addCleanup(self.patch.stop)
        self.plan={'id':'batch','actor':1,'target':2,'phase':'consent','voiced_trade':True,
            'commodity':'iron','quantity':5,'unit_price':7,'purpose':'production_input',
            'commodity_label':'MODEL INVENTED LABEL','procurement':{'shortfall':999,'private':'SECRET'}}
        self.state={'people':{'1':{'memories':[]},'2':{'memories':[]}}}
        self.speech=EconomicSpeech();self.speech.session='s'

    def test_all_trade_acts_pin_catalog_label_quantity_price_and_total(self):
        for act in ('offer','counteroffer','seller_counteroffer','buyer_accept','accept','refuse','receipt'):
            with self.subTest(act=act):
                plan=copy.deepcopy(self.plan);self.speech.queue_trade_speech(self.state,plan,act)
                turn=plan['economic_speech']
                for term in ('5 units of Iron ingot','7 gold each','35 gold total'):
                    self.assertIn(term,turn['canonical_line'])
                self.assertEqual(turn['terms']['cost'],35)
                for secret in ('MODEL INVENTED LABEL','grain','bread','SECRET','999'):
                    self.assertNotIn(secret,str(turn))
                plan.update(quantity=2,unit_price=1,commodity='bread')
                self.assertEqual(turn['terms']['quantity'],5)
                self.assertEqual(turn['terms']['commodity'],'iron')

    def test_unknown_or_inexact_trade_terms_fail_without_queued_speech(self):
        for change in ({'commodity':'missing'},{'commodity':'gold'},{'quantity':None},{'quantity':True},
                       {'quantity':0},{'unit_price':1.5},{'catalog_hash':'old'},
                       {'quantity':economy_catalog.MAX_STOCK,'unit_price':2}):
            with self.subTest(change=change):
                plan={**self.plan,**change}
                with self.assertRaises(ValueError):self.speech.queue_trade_speech(self.state,plan,'offer')
                self.assertNotIn('economic_speech',plan)
                self.assertNotIn('economic_pair',plan)

    def test_wrapper_cannot_add_unseen_goods_policy_or_counterparty_facts(self):
        context={'interaction':{'already_spoken':False},'event':{'canonical_terms':'Exact terms.'}}
        for extra in ('The iron is yours.', 'I include leather.', 'Everything is discounted.',
                      'My reserves are released.', 'You have plenty.', 'Tomorrow is cheaper.',
                      'Your family needs this.', 'I can deliver it later.', 'All sales are final.'):
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                validate_wording_candidate({'id':'option_1','line':extra+' '+TERMS,'tone':'calm','intention':'polite'},context)

    def test_catalog_stock_and_price_metrics_include_new_good_without_bread_fallback(self):
        state={'town':{'residents':{'1':{},'2':{}}},'plans':[
            {'id':'batch','phase':'complete','commodity':'iron','pricing_policy':'resident-bargaining-v1','trade_id':'sale'},
            {'id':'legacy','phase':'complete','pricing_policy':'resident-bargaining-v1','trade_id':'unknown'}],
            'trades':[{'id':'sale','status':'committed','command':{'commodity':'iron','quantity':5,'cost':35}},
                      {'id':'held','status':'held','command':{'commodity':'iron','quantity':10,'cost':1}},
                      {'id':'unknown','status':'committed','command':{'quantity':1,'cost':99}}]}
        result=town_dashboard(state,{'residents':[{'id':1,'isPerson':True,'inventory':{'iron':0}},
                                                {'id':2,'isPerson':True,'inventory':{'iron':9}}]})
        self.assertEqual(result['stock']['iron'],{'total':9,'accounts':2,'population':2})
        self.assertIsNone(result['stock']['bread']['total'])
        self.assertEqual(result['inventory_catalog']['commodity_labels']['iron'],'Iron ingot')
        bargaining=simulation_metrics(state)['economy']['bargaining']
        self.assertEqual(bargaining['by_commodity']['iron']['paid_prices']['median'],7)
        self.assertEqual(bargaining['by_commodity']['iron']['paid_prices']['n'],1)
        self.assertEqual(bargaining['by_commodity']['bread']['plans'],0)
        self.assertEqual(bargaining['by_commodity']['__unknown__']['plans'],1)
        self.assertEqual(bargaining['by_commodity']['__unknown__']['paid_prices']['median'],99)

    def test_generic_refusal_requires_heard_exact_terms_and_preserves_total(self):
        event=remember_refusal_decision(self.state,self.plan)
        turn={'refusal_event_id':event,'act':'refuse','actor':2,'listener':1,'delivered':True,
              'delivery_id':'heard','audio':{'seconds':2},
              'playback':{'id':'heard','status':'ended','playedSeconds':2,'nearbyThroughout':False}}
        self.assertFalse(remember_refusal_heard(self.state,self.plan,turn))
        self.assertEqual(self.state['people']['1']['memories'],[])
        turn['playback']['nearbyThroughout']=True
        self.assertTrue(remember_refusal_heard(self.state,self.plan,turn))
        memory=self.state['people']['1']['memories'][0]
        self.assertEqual((memory['commodity'],memory['quantity'],memory['unit_price'],memory['gold']),('iron',5,7,35))
        self.assertNotIn('SECRET',str(memory))

    def test_acceptance_teaches_snapshot_only_after_complete_nearby_playback(self):
        plan=copy.deepcopy(self.plan)
        self.speech.queue_trade_speech(self.state,plan,'accept')
        plan['phase']='economic_speaking'
        plan['economic_speech'].update(delivery_id='spoken',audio={'seconds':2})
        self.speech.active={**self.state,'plans':[plan],'trades':[]}
        self.speech.agency_plan=lambda:self.speech.active['plans'][-1]
        def write(state,reason):self.speech.active=state
        self.speech._write=write
        observation={'speech':{'id':'spoken','status':'playing'}}
        self.assertTrue(self.speech.observe_trade_speech(observation))
        self.assertTrue(all(not p['memories'] for p in self.speech.active['people'].values()))
        # A later mutable planning field must not rewrite what this audio said.
        plan.update(quantity=1,unit_price=99)
        observation['speech'].update(status='ended',playedSeconds=2,nearbyThroughout=True)
        self.assertTrue(self.speech.observe_trade_speech(observation))
        heard=self.speech.active['people']['1']['memories'][0]
        self.assertEqual(heard['kind'],'heard_speech')
        self.assertEqual((heard['terms']['commodity'],heard['terms']['quantity'],heard['terms']['cost']),('iron',5,35))
        self.assertIn('heard terms',heard['epistemic_status'])
        self.assertEqual(self.speech.active['trades'],[],'Heard agreement is not a completed physical sale')

    def test_catalog_ids_cannot_overwrite_memory_schema_fields(self):
        self.catalog['commodities'][-1]['id']='kind'
        self.plan['commodity']='kind'
        remember_refusal_decision(self.state,self.plan)
        memory=self.state['people']['2']['memories'][0]
        self.assertEqual(memory['kind'],'trade_offer_declined')
        self.assertEqual(memory['goods'],{'kind':5})

    def test_goodbye_does_not_teach_unspoken_economic_terms(self):
        self.speech.queue_trade_speech(self.state,self.plan,'leave')
        self.assertNotIn('terms',self.plan['economic_speech'])


if __name__=='__main__':unittest.main()
