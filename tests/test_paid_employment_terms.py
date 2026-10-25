"""Generic employment eligibility and retained consent evidence, using authored fixtures."""
import copy
import json
import unittest
import test_generic_procurement as fixtures
from catalog_fixture import native_catalog
from labour import work_opportunities
from employment import validate_paid_consent, accept_contract, work_terms_hash, work_description
from enterprises import current_work_terms
from paid_work_policy import paid_work_capability


class PaidEmploymentTermsTests(unittest.TestCase):
    def setUp(self):
        fixtures.GenericProcurementTests.setUp(self)
        self.obs['economy_catalog']=native_catalog()
        self.obs['paid_employment']={'available':True,'protocol':2,'epoch':'paid-fixture','capacity':2}
        self.obs['residents'][0]['inventory'].update(ore=4)
        self.obs['residents'][1]['inventory']['gold']=7
        self.worker=8

    def terms(self):return work_opportunities(self.state,self.obs,self.worker)[0]

    def plan(self, voiced=False):
        terms=self.terms()
        plan={'id':'job-fixture','actor':8,'target':7,'work_terms':terms,'decisions':[],
              'phase':'ready_to_paid_work','voiced_trade':voiced}
        for action,actor in [('offer_shift',7),('take_shift',8)]:
            plan['decisions'].append({'actor_id':actor,'claim_id':action+'-claim',
                'decision':{'action_id':action},'model':'explicit-unit-fixture',
                'context':{'actor_id':actor,'session':self.obs['session'],'event':{'id':plan['id']},'work_terms':copy.deepcopy(terms),
                           'terms_hash':terms['terms_hash'],'options':[{'id':action}]}})
        if voiced:
            plan['economic_turns']=[]
            for act,actor,listener in [('work_offer',7,8),('work_accept',8,7)]:
                plan['economic_turns'].append({'act':act,'actor':actor,'listener':listener,
                    'delivered':True,'origin_session':self.obs['session'],'terms_hash':terms['terms_hash'],
                    'delivery_id':act+'-delivery','audio':{'seconds':1},
                    'playback':{'id':act+'-delivery','status':'ended','nearbyThroughout':True,'playedSeconds':1}})
        return plan

    def test_generic_recipe_public_terms_no_inventory_or_unknown_name_disclosure(self):
        before=copy.deepcopy((self.state,self.obs));terms=self.terms()
        self.assertEqual(terms['recipe_id'],'metal_recipe')
        self.assertEqual(terms['worker'],8);self.assertEqual(terms['employer'],7)
        self.assertEqual(terms['worker_base_id'],1008)
        self.assertEqual(terms['terms_hash'],work_terms_hash(terms))
        self.assertNotIn('inventory',json.dumps(terms));self.assertNotIn('Artisan',json.dumps(terms))
        self.assertEqual((self.state,self.obs),before)
        self.assertFalse(paid_work_capability()['available'])
        self.assertIn('ore',work_description(self.plan()))
        self.assertIn('ingot',work_description(self.plan()))

    def test_capability_absence_legacy_or_stale_cannot_offer(self):
        original=copy.deepcopy(self.obs['paid_employment'])
        for capability in ({},{**original,'protocol':1},{**original,'available':False},
                           {**original,'epoch':''},{**original,'capacity':True},
                           {**original,'session':'other'}):
            self.obs['paid_employment']=capability
            self.assertEqual(work_opportunities(self.state,self.obs,8),[])

    def test_recipe_knowledge_and_current_identity_are_required(self):
        original=copy.deepcopy(self.state)
        self.state['people']['7']['known_recipes']={}
        self.assertEqual(work_opportunities(self.state,self.obs,8),[])
        self.state=original;self.obs['residents'][0]['baseId']+=1
        self.assertEqual(work_opportunities(self.state,self.obs,8),[])

    def test_stock_demand_wage_overflow_and_inventory_freshness(self):
        original=copy.deepcopy(self.obs)
        for item,value in [('ore',0),('gold',0),('ingot',5)]:
            self.obs=copy.deepcopy(original);self.obs['residents'][0]['inventory'][item]=value
            self.assertEqual(work_opportunities(self.state,self.obs,8),[])
        self.obs=copy.deepcopy(original);self.obs['residents'][1]['inventory']['gold']=2**31-1
        self.assertEqual(work_opportunities(self.state,self.obs,8),[])
        self.obs=copy.deepcopy(original);self.obs['residents'][0]['inventory_checkpoint']=0
        self.assertEqual(work_opportunities(self.state,self.obs,8),[])

    def test_distinct_ordered_claims_and_exact_terms_required(self):
        plan=self.plan();proof=validate_paid_consent(self.state,plan,self.obs)
        self.assertEqual(proof['consent']['offer_claim_id'],'offer_shift-claim')
        self.assertEqual(proof['consent']['acceptance_claim_id'],'take_shift-claim')
        for change in ('missing','reversed','wrong_actor','changed_terms','stale_session','not_offered','transplanted_event'):
            altered=copy.deepcopy(plan)
            if change=='missing':altered['decisions'].pop()
            if change=='reversed':altered['decisions'].reverse()
            if change=='wrong_actor':altered['decisions'][0]['actor_id']=8
            if change=='changed_terms':altered['decisions'][0]['context']['work_terms']['policy']['wage_gold']+=1
            if change=='stale_session':altered['decisions'][0]['context']['session']='other'
            if change=='not_offered':altered['decisions'][0]['context']['options']=[]
            if change=='transplanted_event':altered['decisions'][0]['context']['event']['id']='previous-plan'
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_paid_consent(self.state,altered,self.obs)

    def test_voiced_consent_requires_both_heard_exact_deliveries(self):
        plan=self.plan(True);proof=validate_paid_consent(self.state,plan,self.obs)
        self.assertEqual(proof['consent']['offer_delivery_id'],'work_offer-delivery')
        for field,value in [('delivered',False),('terms_hash','wrong'),('listener',7)]:
            altered=copy.deepcopy(plan);altered['economic_turns'][0][field]=value
            with self.assertRaises(ValueError):validate_paid_consent(self.state,altered,self.obs)
        plan['economic_turns'][1]['playback']['nearbyThroughout']=False
        with self.assertRaises(ValueError):validate_paid_consent(self.state,plan,self.obs)

    def test_contract_records_proof_without_resources_or_work_credit(self):
        plan=self.plan();business=self.state['town']['businesses']['forge'];business['contracts']=[]
        before=copy.deepcopy((self.obs,self.state['people']))
        accept_contract(self.state,plan,self.obs);accept_contract(self.state,plan,self.obs)
        self.assertEqual(len(business['contracts']),1)
        self.assertEqual(business['contracts'][0]['consent_hash'],plan['paid_consent']['consent_hash'])
        self.assertEqual((self.obs,self.state['people']),before)
        self.assertNotIn('production',self.state)

    def test_revision_or_recipe_terms_change_invalidates_current_contract(self):
        plan=self.plan();self.state['town']['businesses']['forge']['revision']+=1
        with self.assertRaises(ValueError):current_work_terms(self.state,plan,self.obs)

    def test_multiple_recipes_are_distinct_and_activity_reservations_remain_binding(self):
        from entrepreneurship import learn_recipe
        business=self.state['town']['businesses']['forge']
        business['capabilities'].append('bread_recipe')
        self.obs['residents'][0]['inventory']['grain']=2
        learn_recipe(self.state['people']['7'],'explicit-prior-production-fixture','bread_recipe')
        choices=work_opportunities(self.state,self.obs,8)
        self.assertEqual({row['recipe_id'] for row in choices},{'bread_recipe','metal_recipe'})
        self.assertEqual(len({row['terms_hash'] for row in choices}),2)
        self.state['activity_jobs']={'busy':{'id':'busy','actor':7,'target':900,'phase':'running',
            'receipt_acknowledged':False}}
        self.assertEqual(work_opportunities(self.state,self.obs,8),[])

    def test_changed_duration_and_truncated_heard_audio_cannot_authorize(self):
        plan=self.plan(True)
        plan['economic_turns'][0]['playback']['playedSeconds']=0
        with self.assertRaisesRegex(ValueError,'heard in full'):
            validate_paid_consent(self.state,plan,self.obs)
        plan=self.plan()
        self.state['town']['businesses']['forge']['recipe_policies']['metal_recipe']['work_minutes']=18
        with self.assertRaisesRegex(ValueError,'terms changed'):
            validate_paid_consent(self.state,plan,self.obs)
