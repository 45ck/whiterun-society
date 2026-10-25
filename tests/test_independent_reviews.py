"""Real source selection/delegation, with explicit saved checkpoint boundaries."""
import copy
import json
import time
import unittest
from unittest.mock import patch
import test_activity_jobs as fixtures
from activity_jobs import ActivityJobs
from agency import Agency
from independent_reviews import IndependentReviews,independent_review_candidates,independent_review_context,load_policy
from activity_plan_sources import activity_plan_hash,find_activity_plan,independent_plan_authorized
from activity_leases import reserved_activity_actors
from catalog_fixture import native_catalog


class ReviewWorld(IndependentReviews,fixtures.SavedJobs):
    _agency_guard=Agency._agency_guard
    def __init__(self,state):
        super().__init__(state);self.marker=0
    def routines_busy(self):return True
    def bind(self,observation):
        super().bind();self.marker+=1;observation['checkpoint']=self.marker


class IndependentReviewTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.ActivityJobsTests();fixture.setUp()
        self.obs=fixture.obs;self.seats=fixture.seats;self.world=ReviewWorld(fixture.world.active)
        self.obs['weather']={'name':'rain'}
        for actor,person in self.world.active['people'].items():
            person['profile']={'name':'resident '+actor,'priorities':['rest','work']}
            person['memories']=[{'private':'memory of '+actor}]
        self.world.active['plans']=[{'id':'foreground','actor':3,'target':4,'phase':'consent'}]
        self.world.active['conversation']={'id':'chat','phase':'speaking','initiator':3,'partner':4,'speakers':[3,4]}
        for actor in (1,2):self.event(actor)

    def event(self,actor,event_id=None,focus='rest'):
        event={'id':event_id or 'source-'+str(actor),'actor':actor,'kind':'need_review','status':'pending',
               'goal_followups':[{'goal_id':'goal-'+str(actor),'focus':focus}]}
        self.world.active['town']['daily']['queue'].append(event);return event

    def claim(self,limit=32,wave_id='wave'):
        result=self.world.claim_independent_reviews(wave_id,self.obs,limit)
        if self.world.transition:self.world.bind(self.obs)
        return result['wave']

    def finish(self,wave,choices=None):
        choices=choices or {}
        result=self.world.finish_independent_reviews(wave['id'],wave['claim_id'],[
            {'actor':m['actor'],'result':{'decision':{'action_id':choices.get(m['actor'],'defer'),
             'reason':'A deliberate fixture choice','emotion':'calm'},'model':'fixture','attempted':True}}
            for m in wave['members']],self.obs)
        self.world.bind(self.obs);return result

    def test_foreground_encounter_continues_while_disjoint_claims_are_saved_without_leases(self):
        before=copy.deepcopy(self.world.active);wave=self.claim()
        self.assertEqual([m['actor'] for m in wave['members']],[1,2])
        self.assertEqual(self.world.active['plans'],before['plans'])
        self.assertEqual(self.world.active['conversation'],before['conversation'])
        self.assertEqual(self.world.active['people'],before['people'])
        self.assertEqual(reserved_activity_actors(self.world.active,self.obs),set())
        self.assertTrue(all(e['status']=='started' for e in self.world.active['town']['daily']['queue']))
        self.assertNotIn('activity_jobs',self.world.active)
        self.assertEqual(self.world.claim_independent_reviews('wave',self.obs)['wave'],wave)
        with self.assertRaisesRegex(ValueError,'already claimed'):self.world.claim_independent_reviews('second',self.obs)

    def test_context_offers_all_available_benches_and_only_own_private_state(self):
        wave=self.claim();context=wave['members'][0]['context']
        self.assertEqual({o['id'] for o in context['options']},{'defer','foreground_review',*('rest_'+str(s) for s in self.seats)})
        self.assertIn('memory of 1',json.dumps(context));self.assertNotIn('memory of 2',json.dumps(context))
        self.assertEqual(context['weather'],{'name':'rain'});self.assertEqual(context['game_days'],3.)

    def test_choice_then_serial_delegation_keeps_foreground_and_no_recovery_before_native_receipt(self):
        wave=self.claim();self.finish(wave,{1:'rest_'+str(self.seats[0]),2:'rest_'+str(self.seats[1])})
        self.assertNotIn('activity_jobs',self.world.active)
        foreground=copy.deepcopy(self.world.active['plans'])
        for actor in (1,2):
            self.assertTrue(self.world.prepare_independent_review_jobs(self.obs));self.world.bind(self.obs)
            self.assertTrue(self.world.observe_independent_reviews(self.obs));self.world.bind(self.obs)
            self.assertEqual(self.world.active['independent_reviews']['source-'+str(actor)]['phase'],'delegated')
        self.assertEqual(len(self.world.active['activity_jobs']),2)
        self.assertEqual(self.world.active['plans'],foreground)
        self.assertEqual(self.world.active['people']['1']['needs']['fatigue'],.9)
        self.assertEqual({j['source_plan'] for j in self.world.active['activity_jobs'].values()},{'source-1','source-2'})
        self.assertFalse(self.world.prepare_independent_review_jobs(self.obs))

    def test_competing_seat_is_revalidated_after_saved_choices(self):
        wave=self.claim();self.finish(wave,{1:'rest_'+str(self.seats[0]),2:'rest_'+str(self.seats[0])})
        self.world.prepare_independent_review_jobs(self.obs);self.world.bind(self.obs)
        self.world.prepare_independent_review_jobs(self.obs);self.world.bind(self.obs)
        self.assertEqual(len(self.world.active['activity_jobs']),1)
        self.assertEqual(self.world.active['independent_plans']['source-2']['phase'],'held')
        self.assertTrue(self.world.active['independent_reviews']['source-2']['accepted'])
        self.assertEqual(self.world.active['people']['2']['needs']['fatigue'],.9)

    def test_foreground_handoff_is_once_and_defer_never_grants_rest(self):
        wave=self.claim();self.finish(wave,{1:'foreground_review'})
        events=self.world.active['town']['daily']['queue']
        self.assertEqual([e['status'] for e in events],['pending','complete'])
        self.assertTrue(events[0]['independent_review_handed_back'])
        self.assertEqual(independent_review_candidates(self.world.active,self.obs),[])
        self.assertEqual(self.world.active.get('independent_plans',{}),{})
        self.assertEqual(self.world.active['people']['2']['needs']['fatigue'],.9)
        with self.assertRaisesRegex(ValueError,'Stale'):self.finish(wave)

    def test_replaced_identity_or_changed_available_seat_holds_choice_without_effect(self):
        for changed in ('base','seat'):
            with self.subTest(changed=changed):
                self.setUp();wave=self.claim(1)
                if changed=='base':self.obs['residents'][0]['baseId']=999
                else:self.obs['rest']['sites'][0]['occupied']=True
                result=self.finish(wave,{1:'rest_'+str(self.seats[0])})
                self.assertFalse(result['results'][0]['accepted'])
                self.assertEqual(self.world.active['independent_reviews']['source-1']['phase'],'held')
                self.assertNotIn('activity_jobs',self.world.active)

    def test_invalid_result_actor_coverage_atomic_and_malformed_member_per_actor_held(self):
        wave=self.claim();before=copy.deepcopy(self.world.active)
        with self.assertRaises(ValueError):self.world.finish_independent_reviews('wave',wave['claim_id'],[{'actor':1,'result':{}},{'actor':1,'result':{}}],self.obs)
        self.assertEqual(before,self.world.active);self.assertIsNone(self.world.transition)
        result=self.world.finish_independent_reviews('wave',wave['claim_id'],[{'actor':1,'result':None},{'actor':2,'result':{'failure':'deadline','attempted':False}}],self.obs)
        self.world.bind(self.obs)
        self.assertTrue(all(not r['accepted'] for r in result['results']))
        self.assertEqual(result['results'][1]['attempted'],False)
        self.assertTrue(all(r['result_recorded_at']>0 for r in result['results']))

    def test_deadline_and_session_hold_claim_without_retry(self):
        for change in ('deadline','session'):
            with self.subTest(change=change):
                self.setUp();wave=self.claim()
                if change=='deadline':self.world.active['independent_review_waves'][0]['deadline_at']=0
                elif change=='missing':self.obs['residents']=self.obs['residents'][1:]
                else:self.world.session='new';self.obs['session']='new'
                self.assertTrue(self.world.observe_independent_reviews(self.obs));self.world.bind(self.obs)
                self.assertEqual(self.world.active['independent_review_waves'][0]['phase'],'held')
                self.assertTrue(all(r['phase']=='held' for r in self.world.active['independent_reviews'].values()))
                self.assertNotIn('activity_jobs',self.world.active)

    def test_missing_member_is_held_without_rejecting_unaffected_peer(self):
        wave=self.claim();self.obs['residents']=[r for r in self.obs['residents'] if r['id']!=2]
        self.world.observe_independent_reviews(self.obs);self.world.bind(self.obs)
        self.assertEqual(self.world.active['independent_review_waves'][0]['phase'],'thinking')
        self.assertEqual(self.world.active['independent_reviews']['source-2']['phase'],'held')
        self.assertFalse(self.world.observe_independent_reviews(self.obs))
        result=self.finish(wave,{1:'rest_'+str(self.seats[0]),2:'rest_'+str(self.seats[1])})
        self.assertEqual([r['accepted'] for r in result['results']],[True,False])
        self.assertEqual(set(self.world.active['independent_plans']),{'source-1'})

    def test_no_state_and_bad_observations_are_inert(self):
        self.assertFalse(self.world.observe_independent_reviews({}))
        self.assertFalse(self.world.prepare_independent_review_jobs({}))
        wave=self.claim();self.finish(wave,{1:'rest_'+str(self.seats[0])})
        before=copy.deepcopy(self.world.active)
        for field,value in [('session','other'),('checkpoint',99),('ready',False),('paused',True),('gameDays',float('nan'))]:
            observation={**self.obs,field:value}
            self.assertFalse(self.world.observe_independent_reviews(observation))
            self.assertFalse(self.world.prepare_independent_review_jobs(observation))
        self.assertEqual(before,self.world.active)

    def test_accepted_actor_cannot_claim_second_source_and_tampering_cannot_delegate(self):
        wave=self.claim(1);self.finish(wave,{1:'rest_'+str(self.seats[0])})
        self.event(1,'source-another')
        self.assertEqual([e['actor'] for e in independent_review_candidates(self.world.active,self.obs)],[2])
        plan=self.world.active['independent_plans']['source-1'];self.assertTrue(independent_plan_authorized(self.world.active,plan,'ready_to_rest'))
        plan['rest_target']=self.seats[1]
        self.assertFalse(independent_plan_authorized(self.world.active,plan,'ready_to_rest'))
        self.world.prepare_independent_review_jobs(self.obs);self.world.bind(self.obs)
        self.assertEqual(self.world.active['independent_plans']['source-1']['phase'],'held')
        self.assertNotIn('activity_jobs',self.world.active)

    def test_terminal_native_source_outcome_is_not_overwritten_by_generic_review_status(self):
        wave=self.claim(1);self.finish(wave,{1:'rest_'+str(self.seats[0])})
        self.world.prepare_independent_review_jobs(self.obs);self.world.bind(self.obs)
        self.world.active['independent_reviews']['source-1']['accepted_deadline_at']=0
        self.world.observe_independent_reviews(self.obs);self.world.bind(self.obs)
        self.assertEqual(self.world.active['independent_reviews']['source-1']['phase'],'delegated')
        plan=self.world.active['independent_plans']['source-1'];plan.update(phase='complete',outcome='rested_at_bench')
        self.world.active['town']['daily']['queue'][0].update(status='complete',outcome='rested_at_bench')
        self.world.observe_independent_reviews(self.obs);self.world.bind(self.obs)
        self.assertEqual(self.world.active['town']['daily']['queue'][0]['outcome'],'rested_at_bench')
        self.assertFalse(self.world.observe_independent_reviews(self.obs))

    def test_owner_recipe_is_real_own_option_and_stock_change_invalidates_it(self):
        self.world.active['town']['daily']['queue'][0]['goal_followups'][0]['focus']='work'
        self.world.active['town']['businesses']={'own':{'owner':1,'custodian':1,'active':True,'revision':1,'capabilities':['bread_recipe']}}
        self.obs['economy_catalog']=native_catalog();self.obs['owner_work_jobs']={'available':True,'capacity':4}
        self.obs['resident_control']={'activities':[{'actor':1,'expectedPackage':9000}]}
        self.obs['residents'][0]['inventory']={'gold':5,'grain':3,'bread':0}
        wave=self.claim(1);keys=[o['id'] for o in wave['members'][0]['context']['options'] if o['id'].startswith('owner_')]
        self.assertEqual(len(keys),1)
        self.obs['residents'][0]['inventory']['grain']=0
        result=self.finish(wave,{1:keys[0]});self.assertFalse(result['results'][0]['accepted'])
        self.assertNotIn('work_jobs',self.world.active)

    def test_accepted_timeout_is_snapshot_bound_and_grants_no_effect(self):
        wave=self.claim(1);self.finish(wave,{1:'rest_'+str(self.seats[0])})
        record=self.world.active['independent_reviews']['source-1']
        record['accepted_deadline_at']=time.time()-1
        with patch('independent_reviews.load_policy',side_effect=AssertionError('Do not reload in-flight policy')):
            self.assertTrue(self.world.observe_independent_reviews(self.obs));self.world.bind(self.obs)
        self.assertEqual(self.world.active['independent_reviews']['source-1']['phase'],'held')
        self.assertEqual(self.world.active['independent_plans']['source-1']['phase'],'held')
        self.assertTrue(self.world.active['independent_reviews']['source-1']['accepted'])
        self.assertNotIn('activity_jobs',self.world.active)
        self.assertEqual(self.world.active['people']['1']['needs']['fatigue'],.9)
        self.assertFalse(self.world.observe_independent_reviews(self.obs))

    def test_foreground_actor_and_explicit_non_review_sources_are_not_claimed(self):
        self.event(3,'foreground-source')
        self.event(1,'food-source','food')
        self.event(2,'regular-source')['goal_followups']=[]
        self.assertEqual([e['id'] for e in independent_review_candidates(self.world.active,self.obs)],['source-1','source-2'])
        self.world.active['town']['daily']['queue'].append(copy.deepcopy(self.world.active['town']['daily']['queue'][0]))
        self.assertEqual([e['id'] for e in independent_review_candidates(self.world.active,self.obs)],['source-2'])

    def test_shared_inference_wave_guard_and_duplicate_source_identity(self):
        from resident_goals import ResidentGoals
        self.world.active['town']['goal_waves']=[{'id':'goal-wave','phase':'thinking'}]
        before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'inference wave'):self.claim()
        self.assertEqual(before,self.world.active)
        self.world.active['town']['goal_waves']=[]
        self.claim(1)
        self.world.active['town']['resident_control']={'enabled':True}
        self.obs['resident_control']={'goal_destinations':True}
        with self.assertRaisesRegex(ValueError,'inference wave'):
            ResidentGoals.claim_resident_goals(self.world,'goal-wave',self.obs)
        wave=self.world.active['independent_review_waves'][0]
        self.finish(wave,{1:'rest_'+str(self.seats[0])})
        plan=self.world.active['independent_plans']['source-1']
        self.world.active['town']['daily']['queue'].append(copy.deepcopy(self.world.active['town']['daily']['queue'][0]))
        self.assertFalse(independent_plan_authorized(self.world.active,plan,'ready_to_rest'))

    def test_changed_source_actor_rejected_at_choice_not_only_later_delegation(self):
        wave=self.claim(1);self.world.active['town']['daily']['queue'][0]['actor']=2
        result=self.finish(wave,{1:'rest_'+str(self.seats[0])})
        self.assertFalse(result['results'][0]['accepted'])
        self.assertNotIn('independent_plans',self.world.active)

    def test_generic_owner_recipe_enters_goal_review_and_independent_choice(self):
        import economy_catalog
        from test_catalog_enterprises import expanded_catalog
        from goal_opportunities import focus_opportunities
        self.enterContext(patch.object(economy_catalog,'ECONOMY_CATALOG',expanded_catalog()))
        import market_policy
        policy=copy.deepcopy(market_policy.MARKET_POLICY);policy['catalog_hash']=economy_catalog.catalog_hash()
        self.enterContext(patch.object(market_policy,'MARKET_POLICY',policy))
        self.world.active['town']['businesses']={'forge':{'owner':1,'custodian':1,'active':True,'revision':2,
            'capabilities':['metal_recipe'],'recipe_policies':{'metal_recipe':{'work_minutes':18,'wage_gold':3,'target_output':9}}}}
        self.obs['economy_catalog']=native_catalog();self.obs['owner_work_jobs']={'available':True,'capacity':4}
        self.obs['resident_control']={'activities':[{'actor':1,'expectedPackage':9000}]}
        self.obs['residents'][0]['inventory']={'gold':5,'grain':0,'bread':0,'ore':4,'ingot':0}
        available=focus_opportunities(self.world.active,self.obs,1)
        self.assertTrue(available['work']);self.assertEqual(available['public_work'][0]['recipe_id'],'metal_recipe')
        self.world.active['town']['daily']['queue'][0]['goal_followups'][0]['focus']='work'
        wave=self.claim(1)
        action=next(key for key,value in wave['members'][0]['actions'].items() if value['kind']=='owner_production')
        self.finish(wave,{1:action})
        terms=self.world.active['independent_plans']['source-1']['own_work_terms']
        self.assertEqual(terms['recipe_id'],'metal_recipe');self.assertEqual(terms['policy']['work_minutes'],18)
        self.assertNotIn('work_jobs',self.world.active);self.assertNotIn('production',self.world.active)

if __name__=='__main__':unittest.main()
