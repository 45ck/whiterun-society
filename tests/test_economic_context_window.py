import copy
import io
import json
import unittest
from unittest.mock import patch

from context_window import bounded_economic_context,encoded_size
from decision_provider import infer_jev


def economic_context():
    background={'kind':'authored_shared_town_background','epistemic_status':'scenario initial acquaintance, not witnessed interaction or canonical lore','event_id':'authored-neighbours'}
    relations={str(i):{'affinity':-.2,'familiarity':.35,'heard_turns':3,
                       'background':copy.deepcopy(background),
                       'appraisals':[{'event_id':str(j),'basis':'subjective heard claim, not verified truth','choice':'wary'} for j in range(8)]}
               for i in range(100,125)}
    context={'actor_id':1,'session':'same-session','profile':{'name':'Deciding resident'},
             'event':{'kind':'need_review','information':'Choose freely; these are authored terms, not guaranteed employment.'},
             'economic_counterparty':{'id':100,'name':'an unfamiliar resident','name_known':False,'identity_source':None},
             'observed_inventory':{'gold':56,'bread':0,'grain':1},'own_food_allocation':{'reserved':0},
             'scenario_state':{'needs':{'hunger':1,'fatigue':1}},
             'my_relationships':relations,'trust':{str(i):.5 for i in range(100,130)},
             'option_targets':{'visit_person_'+str(i):i for i in range(100,118)},
             'options':[{'id':'visit_person_'+str(i),'effect':'Visit an unfamiliar resident; arrival is not permission to speak.'} for i in range(100,118)],
             'price_options':{'bid_price_2':2},'work_options':{'seek_work':{'employer':100,'policy':{'wage_gold':4,'work_minutes':10,'target_bread':12}}},
             'enterprise_options':{'keep_shop':{'owner':1}},'market_options':{'visit_market':{'site':2}},
             'own_price_history':[{'commodity':'bread','price':3}],
             'own_commitments':[{'kind':'repay','gold':2,'other':100,'source':'own promise'}],
             'conversation_followups':[{'actor':1,'heard_words':'I might offer work.','epistemic_status':'heard, unverified'}],
             'own_goal_followups':[{'actor':1,'focus':'find livelihood','source':'own selected goal; no wage earned'}],
             'memories':[{'kind':'travel','target':120,'event_id':str(i),'source':'observed arrival only','model':'unused','timing_scope':'telemetry '*100} for i in range(8)]}
    context['options'] += [{'id':'bid_price_2','effect':'Offer exactly 2 septims for one loaf; seller can refuse.'},
                           {'id':'seek_work','effect':'Ask about 4 gold for 10 game minutes of work; consent required.'}]
    return context


class EconomicContextWindowTests(unittest.TestCase):
    def test_every_financial_option_and_term_survives_while_history_fits(self):
        context=economic_context();before=copy.deepcopy(context)
        self.assertGreater(encoded_size(context),16000)
        result=bounded_economic_context(context)
        for key in set(context)-{'memories','my_relationships','trust'}:
            self.assertEqual(result[key],context[key],key)
        self.assertEqual(context,before)
        self.assertLessEqual(encoded_size(result),12000)
        self.assertEqual(len(result['options']),20)
        self.assertEqual(set(result['my_relationships']),{str(i) for i in range(100,118)})
        self.assertEqual(set(result['trust']),{str(i) for i in range(100,118)})
        self.assertEqual(len(result['my_relationships']['100']['appraisals']),2)
        self.assertTrue(all(not r['appraisals'] for k,r in result['my_relationships'].items() if k!='100'))
        self.assertEqual(result['context_window']['relationships_available'],25)
        self.assertEqual(result['context_window']['trust_entries_omitted'],12)
        self.assertEqual(result['context_window']['appraisals_available'],200)
        self.assertEqual(result['context_window']['appraisals_included'],2)

    def test_unknown_identity_and_exact_epistemic_background_are_preserved(self):
        context=economic_context();result=bounded_economic_context(context)
        self.assertEqual(result['economic_counterparty'],context['economic_counterparty'])
        for key,relation in result['my_relationships'].items():
            ref=relation['background']['source_ref']
            self.assertEqual(result['economic_evidence_sources'][ref],context['my_relationships'][key]['background'])

    def test_older_relevant_refusal_survives_later_travel_receipts(self):
        context=economic_context()
        relevant={'kind':'refused_offer','seller':100,'gold':2,'source':'own negotiation','provenance':'heard refusal, motive unknown'}
        memories=[relevant]+[{'kind':'travel','target':120,'event_id':str(i),'source':'observed arrival only'} for i in range(40)]
        result=bounded_economic_context(context,memories)
        self.assertIn(relevant,result['memories'])
        self.assertLessEqual(len(result['memories']),8)
        self.assertEqual(result['context_window']['memories_available'],41)
        self.assertEqual(memories[0],relevant)

    def test_counterparty_relationship_retained_without_visit_option_and_no_other_private_state_added(self):
        context=economic_context();context['option_targets']={}
        result=bounded_economic_context(context)
        self.assertEqual(set(result['my_relationships']),{'100'})
        self.assertNotIn('inventory',result['economic_counterparty'])
        self.assertNotIn('needs',result['economic_counterparty'])

    def test_jev_payload_is_under_guard_and_preserves_all_criteria(self):
        context=economic_context();result=bounded_economic_context(context)
        ids=[o['id'] for o in result['options']]
        response={'answers':{'action':{'choice':ids[0],'probabilities':{k:int(k==ids[0]) for k in ids}}}}
        with patch('decision_provider.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as call:
            infer_jev(result,{'model':'typesafe/jev-1.14','url':'https://openrouter.ai/api/alpha/decisions'},'test-placeholder')
        payload=call.call_args.args[0].data
        self.assertLessEqual(len(payload),16000)
        self.assertEqual(json.loads(payload)['questions']['action']['criteria'],{o['id']:o['effect'] for o in context['options']})

    def test_irreducible_terms_fail_without_dropping_options_or_calling_provider(self):
        context=economic_context();context['options'][0]['effect']='Required contract terms '*1000
        with patch('decision_provider.urllib.request.urlopen') as call:
            with self.assertRaisesRegex(ValueError,'Required economic context'):bounded_economic_context(context)
            call.assert_not_called()


if __name__=='__main__':unittest.main()
