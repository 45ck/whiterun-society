"""Actual Agency menu/claim flows; fresh census, authored prior and dynamic recipe.

The shared fixture uses fake native APIs. These tests stop before paid effects;
no manually constructed decision or accepted-contract records authorize work.
"""
import copy
import json
import unittest
import test_paid_employment_integration as fixture
from employment import validate_paid_consent


class PaidEmploymentChoiceTests(unittest.TestCase):
    def setUp(self):
        fixture.PaidEmploymentIntegrationTests.setUp(self)
        # Explicit private employer-stock sentinel, never part of offered wages.
        next(row for row in self.obs['residents'] if row['id']==self.employer)['inventory']['gold']=7139

    bind=fixture.PaidEmploymentIntegrationTests.bind
    stock=fixture.PaidEmploymentIntegrationTests.stock
    decide=fixture.PaidEmploymentIntegrationTests.decide

    def start(self):
        due=self.world.active['people'][str(self.worker)]['agency']['next_review_day']
        self.obs['gameDays']=max(self.obs['gameDays']+16/1440,due+1/1440)
        self.world.review_population(self.obs);self.bind()
        pending=next(row for row in self.world.active['town']['daily']['queue']
            if row['actor']==self.worker and row['kind']=='need_review' and row['status']=='pending')
        self.event=pending['id']
        self.world.begin_plan(self.event,self.obs,self.worker,'need_review');self.bind()
        claim=self.world.claim_plan_decision(self.event,self.obs)['claim'];self.bind()
        choices=[(action,terms) for action,terms in claim['context']['work_options'].items()
                 if action.startswith('seek_work_') and terms.get('business_id')==self.business
                 and terms.get('recipe_id')=='metal_recipe']
        self.assertEqual(len(choices),1)
        action,terms=choices[0]
        self.assertIn(action,{row['id'] for row in claim['context']['options']})
        self.assertEqual(terms['worker'],self.worker)
        self.assertEqual(terms['employer'],self.employer)
        return claim,action,terms

    def finish(self,claim,action):
        self.world.finish_plan_decision(self.event,claim['id'],{'model':'offline-menu-test',
            'decision':{'action_id':action,'reason':'An explicit test choice from the real menu.','emotion':'calm'}},self.obs)
        self.bind()

    def offered(self):
        claim,action,terms=self.start();self.finish(claim,action)
        self.assertEqual(self.world.agency_plan()['phase'],'job_offer')
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual(context['actor_id'],self.employer)
        self.assertEqual(context['work_terms'],terms)
        self.assertIn('offer_shift',{row['id'] for row in context['options']})
        self.assertIn('ore',json.dumps(context['options']))
        self.assertIn('ingot',json.dumps(context['options']))
        return terms

    def test_worker_discovers_specific_recipe_and_two_real_claims_authorize_only_consent(self):
        before=self.stock();terms=self.offered();self.decide('offer_shift')
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual(context['actor_id'],self.worker)
        self.assertEqual(context['observed_inventory'],self.stock()[str(self.worker)])
        self.assertNotIn('employer_inventory',context)
        self.assertNotIn('7139',json.dumps(context))
        self.assertEqual(context['terms_hash'],terms['terms_hash'])
        self.assertEqual({row['id'] for row in context['options']},{'take_shift','decline_work'})
        self.decide('take_shift')
        plan=self.world.agency_plan();proof=validate_paid_consent(self.world.active,plan,self.obs)
        records=plan['decisions']
        self.assertEqual([r['decision']['action_id'] for r in records[-2:]],['offer_shift','take_shift'])
        self.assertEqual(proof['consent']['offer_claim_id'],records[-2]['claim_id'])
        self.assertEqual(proof['consent']['acceptance_claim_id'],records[-1]['claim_id'])
        self.assertEqual(self.stock(),before)
        self.assertEqual(self.world.active.get('production',[]),[])
        self.assertEqual(self.world.active['town']['businesses'][self.business]['contracts'][0]['consent_hash'],proof['consent_hash'])

    def test_employer_refusal_is_real_option_without_contract_or_wage(self):
        before=self.stock();self.offered();self.decide('defer')
        self.assertEqual(self.world.agency_plan()['phase'],'complete')
        self.assertEqual(self.world.active['town']['businesses'][self.business]['contracts'],[])
        self.assertEqual(self.stock(),before)
        self.assertEqual(self.world.active.get('production',[]),[])

    def test_worker_decline_is_independent_of_employer_offer(self):
        before=self.stock();self.offered();self.decide('offer_shift');self.decide('decline_work')
        self.assertEqual(self.world.agency_plan()['outcome'],'work_declined')
        self.assertEqual(self.world.active['town']['businesses'][self.business]['contracts'],[])
        self.assertEqual(self.stock(),before)

    def test_changed_business_during_actual_selection_cannot_retarget_claim(self):
        claim,action,terms=self.start()
        self.world.active['town']['businesses'][self.business]['recipe_policies']['metal_recipe']['wage_gold']=4
        before=copy.deepcopy(self.world.active)
        with self.assertRaises(ValueError):self.finish(claim,action)
        self.assertEqual(self.world.active,before)
        self.assertIsNone(self.world.transition)

    def test_changed_accepted_terms_during_worker_inference_are_rejected(self):
        self.offered();self.decide('offer_shift')
        claim=self.world.claim_plan_decision(self.event,self.obs)['claim'];self.bind()
        self.world.active['town']['businesses'][self.business]['revision']+=1
        before=copy.deepcopy(self.world.active)
        with self.assertRaises(ValueError):self.finish(claim,'take_shift')
        self.assertEqual(self.world.active,before)
        self.assertEqual(self.world.active['town']['businesses'][self.business]['contracts'],[])
