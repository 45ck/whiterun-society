"""Qualified employer mobility never releases the paid contract's economic accounts."""
import copy
import unittest
import test_daily_life as fixture
from activity_leases import reserved_activity_actors, work_account_conflict, activity_conflict
from social import social_candidates
from routing import route_available
from rest import rest_opportunities
from labour import work_opportunities
from procurement import input_procurement
from opportunities import food_sellers
from owner_production import owner_work_opportunities
from market_policy import policy_hash
from economy_catalog import catalog_hash
from entrepreneurship import learn_recipe


class EmployerEconomicExclusionTests(unittest.TestCase):
    tearDown=fixture.DailyLifeTests.tearDown
    sync=fixture.DailyLifeTests.sync
    census=fixture.DailyLifeTests.census

    def setUp(self):
        fixture.DailyLifeTests.setUp(self)
        self.employer=108149;self.worker=99;self.other=108186
        for row in self.obs['residents']:
            row.update(x=100,y=0,z=0)
        self.obs['residents'][1]['inventory'].update(grain=3,gold=12)
        learn_recipe(self.world.active['people'][str(self.employer)],'explicit-test-prior-production','bread_recipe')
        self.obs['paid_employment']={'available':True,'protocol':2,'capacity':4,'epoch':'paid-split',
                                    'session':self.obs['session'],'jobs':[],'receipts':[]}
        self.obs['rest']={'available':True,'sites':[{'id':0x8f15b,'position':[200,0,0],
            'loaded':True,'occupancy_known':True,'occupied':False}],
            'sensors':{str(self.employer):{'sit_available':True,'furniture_reference_available':True,
                                        'sit_state':0,'furniture':0}}}

    def lease(self):
        rows={r['id']:r for r in self.obs['residents']}
        job={'id':'paid-mobility','job_id':'paid-mobility','protocol':2,'worker':self.worker,
            'worker_base_id':rows[self.worker]['baseId'],'employer':self.employer,
            'employer_base_id':rows[self.employer]['baseId'],'business_id':'business-108149',
            'phase':'working','session':self.obs['session'],'epoch':'paid-split','effect_unreconciled':False,
            'receipt_acknowledged':False,'release_verified':False}
        self.world.active['paid_work_jobs']={'paid-mobility':job}
        return job

    def plan(self,phase='choose',actor=None,target=None):
        actor=self.employer if actor is None else actor
        plan={'id':'employer-context','actor':actor,'target':target,'kind':'need_review','phase':phase,
            'decisions':[],'quantity':1,'commodity':'bread','purpose':'food','unit_price':3,
            'market_policy_hash':policy_hash(),'catalog_hash':catalog_hash(),'food_actions':True,'refusals_recorded':0}
        return plan

    def test_employer_can_move_socialise_rest_but_neither_party_can_spend(self):
        self.lease();state=self.world.active
        blocked=reserved_activity_actors(state,self.obs)
        self.assertNotIn(self.employer,blocked);self.assertIn(self.worker,blocked)
        self.assertTrue(route_available(self.obs,self.employer,self.other,state))
        self.assertIn(self.other,{r['id'] for r in social_candidates(state,self.obs,self.employer)})
        self.assertTrue(rest_opportunities(state,self.obs,self.employer))
        self.assertTrue(work_account_conflict(state,actors=(self.employer,),observation=self.obs))
        self.assertTrue(work_account_conflict(state,actors=(self.worker,),observation=self.obs))
        context=self.world._plan_context(self.obs,self.plan())
        choices={r['id'] for r in context['options']}
        self.assertIn('visit_person_'+str(self.other),choices);self.assertIn('rest_at_bench',choices)
        self.assertNotIn('eat_bread',choices);self.assertNotIn('review_food_reserve',choices)
        self.assertFalse(context['work_options']);self.assertFalse(context['purchase_options'])
        self.assertFalse(context['enterprise_options'])

    def test_seller_buyer_procurement_and_both_paid_roles_exclude_reserved_account(self):
        self.assertTrue(food_sellers(self.world.active,self.obs,self.other))
        self.assertTrue(work_opportunities(self.world.active,self.obs,self.other))
        self.lease();state=self.world.active
        self.assertEqual(food_sellers(state,self.obs,self.other),[])
        self.assertEqual(food_sellers(state,self.obs,self.employer),[])
        self.assertEqual(work_opportunities(state,self.obs,self.other),[])
        self.assertEqual(work_opportunities(state,self.obs,self.employer),[])
        self.assertEqual(input_procurement(state,self.obs,self.employer),[])
        self.assertEqual(owner_work_opportunities(state,self.obs,self.employer),[])
        context=self.world._plan_context(self.obs,self.plan('consent',actor=self.other,target=self.employer))
        self.assertEqual({r['id'] for r in context['options']},{'decline'})

    def test_consumption_supply_and_owner_effect_builders_reject_before_writing(self):
        self.lease();plan=self.plan('ready_to_eat');self.world.active['plans']=[plan]
        before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'independent activity'):
            self.world.plan_consumption('reserved-meal',self.obs,self.employer,plan['id'])
        self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)
        plan.update(phase='ready_to_self_work',own_work_terms={'recipe_id':'bread_recipe'})
        self.obs['owner_work_jobs']={'available':True,'capacity':4}
        before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'reserved economic account'):
            self.world.plan_owner_production(self.obs,plan)
        self.assertEqual(self.world.active,before)
        self.world.active['plans']=[]
        with self.assertRaisesRegex(ValueError,'independent activity'):
            self.world.setup_production(self.obs)
        self.assertIsNone(self.world.transition)

    def test_eat_choice_claimed_before_reservation_cannot_spend_after_it(self):
        self.world.begin_plan('before-paid',self.obs,self.employer,'meal_time');self.sync()
        claim=self.world.claim_plan_decision('before-paid',self.obs)['claim'];self.sync()
        self.assertIn('eat_bread',{r['id'] for r in claim['context']['options']})
        self.lease();before=copy.deepcopy(self.world.active)
        with self.assertRaises(ValueError):
            self.world.finish_plan_decision('before-paid',claim['id'],{'decision':{
                'action_id':'eat_bread','reason':'Stale economic choice fixture.','emotion':'calm'}},self.obs)
        self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_direct_trade_rejects_mobile_employer_account_in_either_role(self):
        self.lease()
        self.assertFalse(activity_conflict(self.world.active,actors=(self.employer,self.other),observation=self.obs))
        self.assertTrue(work_account_conflict(self.world.active,actors=(self.employer,),observation=self.obs))
        self.assertTrue(work_account_conflict(self.world.active,actors=(self.worker,),observation=self.obs))
        before=copy.deepcopy(self.world.active);observed=copy.deepcopy(self.obs)
        for buyer,seller in ((self.other,self.employer),(self.employer,self.other)):
            with self.subTest(buyer=buyer),self.assertRaisesRegex(ValueError,'^A trade participant inventory account is reserved$'):
                self.world.plan_trade('blocked-mobile-trade',self.obs,buyer,seller)
            self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)
            self.assertEqual(self.obs,observed)
        # Remove only the paid lease: the same observation and complete native
        # protocol prerequisites now admit an effect-free arm intention.
        self.world.active['paid_work_jobs']={}
        result=self.world.plan_trade('blocked-mobile-trade',self.obs,self.other,self.employer)
        self.assertEqual(result['command']['phase'],'arm')
        self.assertEqual(result['command']['seller'],self.employer)
        self.assertIsNotNone(self.world.transition)
        self.assertEqual(self.obs,observed)

    def test_direct_resource_import_rejects_only_reserved_employer_account(self):
        from resource_manifest import load_manifest,manifest_hash
        from resource_delivery_fixture import resource_status
        manifest=load_manifest();digest=manifest_hash(manifest)
        self.obs['resource_import']=resource_status()
        self.lease()
        self.assertFalse(activity_conflict(self.world.active,actors=(self.employer,),observation=self.obs))
        self.assertTrue(work_account_conflict(self.world.active,actors=(self.employer,),observation=self.obs))
        self.assertTrue(work_account_conflict(self.world.active,actors=(self.worker,),observation=self.obs))
        before=copy.deepcopy(self.world.active);observed=copy.deepcopy(self.obs)
        with self.assertRaisesRegex(ValueError,'^The resource recipient inventory account is reserved$'):
            self.world.plan_endowment(self.employer,self.obs,manifest['id'],digest)
        self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)
        self.assertNotIn('resource_program',self.world.active['town'])
        self.assertEqual(self.obs,observed)
        # Identical reviewed manifest, actor identity and native capabilities:
        # removing only the lease permits reservation, never an immediate grant.
        self.world.active['paid_work_jobs']={}
        result=self.world.plan_endowment(self.employer,self.obs,manifest['id'],digest)
        self.assertIn('checkpoint',result)
        self.assertIsNotNone(self.world.transition)
        self.assertEqual(self.obs,observed)
