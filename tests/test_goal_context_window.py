import copy
import io
import json
import unittest
from unittest.mock import patch

from context_window import bounded_goal_context,encoded_size
from decision_provider import infer_jev
from test_context_window import crowded_context


def goal_context_fixture():
    social=crowded_context(40)
    options=[{'id':'quiet','effect':'Remain here; no rest or food benefit.'}]
    options += [{'id':'visit_'+str(i),'effect':'Visit public place '+str(i)+' and reconsider your priorities. No economic effect or conversation is guaranteed.'} for i in range(20)]
    return {'actor_id':1,'profile':social['profile'],'own_inventory':{'gold':20,'grain':1,'bread':0},
            'own_memories':social['memories'],'own_commitments':[{'other':2,'gold':3,'source':'own promise'}],
            'previous_goal':{'id':'old','action_id':'quiet','phase':'quiet','next_review_day':2,
                             'policy':{'telemetry':'x'*1000},'source':'Own previous choice, no benefit'},
            'options':options,'destinations':[{'id':i,'name':'Public '+str(i),'position':[i,0,0]} for i in range(20)],
            'goal_actions':{o['id']:{'family':'visit_public_place','focus':None,'target_id':i,'trigger':'arrival'} for i,o in enumerate(options)},
            'public_opportunities':{'food':True,'social':True,'work':True,'rest':False,
                                   'food_sellers':[{'id':300,'name':'an unfamiliar resident','name_known':False,'identity_source':None}],
                                   'public_work':[{'business_id':'mill','terms':{'wage_gold':4,'work_minutes':10}}],
                                   'nearby_people':social['nearby_candidates']}}


class GoalContextWindowTests(unittest.TestCase):
    def test_crowded_goal_retains_every_choice_destination_resource_and_public_term(self):
        context=goal_context_fixture();before=copy.deepcopy(context)
        self.assertGreater(encoded_size(context),16000)
        result=bounded_goal_context(context)
        for key in ('options','destinations','goal_actions','own_inventory','own_commitments','profile'):
            self.assertEqual(result[key],context[key],key)
        for key in set(context['public_opportunities'])-{'nearby_people'}:
            self.assertEqual(result['public_opportunities'][key],context['public_opportunities'][key],key)
        self.assertEqual(result['previous_goal']['action_id'],'quiet')
        self.assertEqual(result['previous_goal']['source'],context['previous_goal']['source'])
        self.assertEqual(result['context_window']['previous_goal_executor_fields_omitted'],1)
        self.assertEqual(context,before)
        self.assertLessEqual(encoded_size(result),14000)
        self.assertLess(result['context_window']['nearby_people_considered'],40)
        self.assertEqual(result['context_window']['nearby_people_available'],40)

    def test_included_identity_knowledge_is_exact_and_omissions_are_not_forgotten_people(self):
        context=goal_context_fixture();first=context['public_opportunities']['nearby_people'][0]
        first.update(name='an unfamiliar resident',name_known=False,identity_source=None)
        result=bounded_goal_context(context)
        included=result['public_opportunities']['nearby_people']
        self.assertTrue(included)
        for old,new in zip(context['public_opportunities']['nearby_people'],included):
            for key in ('id','name','name_known','identity_source','distance'):
                self.assertEqual(old[key],new[key])
        self.assertIn('not forgetting',result['context_window']['scope'])

    def test_actual_provider_payload_fits_without_choice_removal(self):
        context=goal_context_fixture();result=bounded_goal_context(context)
        ids=[o['id'] for o in result['options']]
        response={'answers':{'action':{'choice':'quiet','probabilities':{k:int(k=='quiet') for k in ids}}}}
        with patch('decision_provider.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as call:
            infer_jev(result,{'model':'typesafe/jev-1.14','url':'https://openrouter.ai/api/alpha/decisions'},'offline-placeholder')
        payload=call.call_args.args[0].data
        self.assertLessEqual(len(payload),16000)
        self.assertEqual(set(json.loads(payload)['questions']['action']['criteria']),set(ids))

    def test_irreducible_context_fails_before_persisting_any_claim(self):
        from test_resident_goals import ResidentGoalTests
        fixture=ResidentGoalTests();fixture.setUp()
        try:
            fixture.start();fixture.world.active['people']['108186']['profile']['priority']='x'*20000
            before=copy.deepcopy(fixture.world.active)
            with self.assertRaisesRegex(ValueError,'Required personal-goal context'):
                fixture.world.claim_resident_goals('too-big',fixture.obs)
            self.assertEqual(fixture.world.active,before)
            self.assertIsNone(fixture.world.transition)
        finally:fixture.tearDown()

    def test_finish_uses_full_eligibility_without_second_attention_filter(self):
        from test_resident_goals import ResidentGoalTests
        fixture=ResidentGoalTests();fixture.setUp()
        try:
            fixture.start();wave=fixture.claim()
            with patch('resident_goals.bounded_goal_context',side_effect=AssertionError('Do not window fresh eligibility')):
                result=fixture.world.finish_resident_goals('wave',wave['claim_id'],fixture.results(wave),fixture.obs)
            self.assertTrue(all(r['accepted'] for r in result['results']))
        finally:fixture.tearDown()


if __name__=='__main__':unittest.main()
