import copy
import unittest
import test_resident_goals as goal_fixture
import test_parallel_routines as routine_fixture
import test_social as social_fixture
import test_agency as agency_fixture
import test_endowments as endowment_fixture
import test_owner_production as owner_fixture
from activity_leases import activity_leases,reserved_activity_actors,reserved_activity_targets,activity_conflict
from routing import route_available
from opportunities import food_sellers
from labour import work_opportunities
from resident_goals import goal_context,occupied
from goal_opportunities import focus_opportunities
from parallel_routines import select_routine_events
from social import social_candidates
from owner_production import owner_work_opportunities


def lease(actor,target=700):
    return {'id':'rest-test','actor':actor,'target':target,'slot':0,'session':'a','epoch':'test',
        'source_plan':'rest-plan','phase':'held','receipt_acknowledged':False}


class ActivityReservationUnitTests(unittest.TestCase):
    def test_terminal_jobs_remain_leased_until_exact_acknowledgement(self):
        state={'activity_jobs':{'j':lease(1)}}
        for phase in ('prepared','running','held','complete'):
            state['activity_jobs']['j']['phase']=phase
            self.assertTrue(activity_conflict(state,actors=[1]));self.assertTrue(activity_conflict(state,targets=[700]))
        state['activity_jobs']['j']['release_verified']=True
        self.assertEqual(reserved_activity_actors(state),{1})
        state['activity_jobs']['j']['receipt_acknowledged']=True
        self.assertEqual(activity_leases(state),[]);self.assertEqual(reserved_activity_targets(state),set())

    def test_old_native_quarantine_survives_saved_rollback_and_completed_phase(self):
        obs={'activity_jobs':{'session':'old','jobs':[lease(1)],'receipts':[{'actor':2,'target':701,'status':'applied'}],
             'reserved_actors':[3,True,-1]}}
        self.assertEqual(reserved_activity_actors({},obs),{1,2,3})
        self.assertEqual(reserved_activity_targets({},obs),{700,701})
        self.assertTrue(activity_conflict({},actors=[2],observation=obs))
        self.assertEqual(reserved_activity_actors({},{}),set())

    def test_durable_orphan_reserves_even_when_native_observation_is_empty(self):
        state={'activity_orphans':{'orphan':{**lease(1),'orphan':True,'release_verified':True}}}
        self.assertEqual(reserved_activity_actors(state,{}),{1});self.assertEqual(reserved_activity_targets(state,{}),{700})
        state['activity_orphans']['orphan']['receipt_acknowledged']=True
        self.assertEqual(reserved_activity_actors(state,{}),set())

    def test_held_routine_with_unverified_release_is_not_available_for_goals(self):
        state={'routine_batches':[{'phase':'held','unverified_release':True,
            'members':[{'actor':1,'phase':'held','receipt':{'release_verified':False}}]}]}
        self.assertIn(1,occupied(state))
        state['routine_batches'][0]['members'][0]['receipt']['release_verified']=True
        self.assertNotIn(1,occupied(state))

    def test_routes_reject_saved_or_native_resident_reservations(self):
        obs={'routing':{'adapter':'papyrus-mailbox-v1','available':True},
             'residents':[{'id':108186,'isPerson':True},{'id':108149,'isPerson':True}]}
        self.assertTrue(route_available(obs,108186,108149))
        for actor in (108186,108149):
            state={'activity_jobs':{'j':lease(actor)}}
            self.assertFalse(route_available(obs,108186,108149,state))
            native={**obs,'activity_jobs':{'jobs':[lease(actor)]}}
            self.assertFalse(route_available(native,108186,108149))


class ReservedOpportunityTests(unittest.TestCase):
    setUp=social_fixture.SocialTests.setUp
    tearDown=social_fixture.SocialTests.tearDown
    sync=social_fixture.SocialTests.sync
    census=social_fixture.SocialTests.census
    review=social_fixture.SocialTests.review
    begin=social_fixture.SocialTests.begin

    def test_leased_people_are_not_partners_sellers_employers_or_review_candidates(self):
        self.assertIn(108149,[p['id'] for p in social_candidates(self.world.active,self.obs,99)])
        self.assertIn(108149,[p['id'] for p in food_sellers(self.world.active,self.obs,99)])
        self.world.active['activity_jobs']={'j':lease(108149)}
        self.assertNotIn(108149,[p['id'] for p in social_candidates(self.world.active,self.obs,99)])
        self.assertEqual(food_sellers(self.world.active,self.obs,99),[])
        self.assertEqual(work_opportunities(self.world.active,self.obs,99),[])
        self.assertEqual(social_candidates(self.world.active,self.obs,108149),[])
        self.assertFalse(any(focus_opportunities(self.world.active,self.obs,108149)[k] for k in ('food','rest','work','social')))

    def test_partner_newly_leased_during_choice_is_rejected_atomically(self):
        self.begin();claim=self.world.claim_conversation(self.event['id'],self.obs)['claim'];self.sync()
        self.obs['activity_jobs']={'jobs':[lease(108149)]}
        before=copy.deepcopy(self.world.active)
        with self.assertRaises(ValueError):self.world.finish_conversation_inference(self.event['id'],claim['id'],
            {'model':'test','decision':{'action_id':'approach_108149','reason':'Test','emotion':'calm'}},self.obs)
        self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_daily_needs_age_without_queuing_new_work_for_leased_actor(self):
        self.obs['activity_jobs']={'jobs':[lease(99)]};before=self.world.active['people']['99']['needs']['hunger']
        self.review(4)
        self.assertGreater(self.world.active['people']['99']['needs']['hunger'],before)
        self.assertNotIn(99,[e['actor'] for e in self.world.active['town']['daily']['queue']])


class ReservedGoalTests(unittest.TestCase):
    setUp=goal_fixture.ResidentGoalTests.setUp
    tearDown=goal_fixture.ResidentGoalTests.tearDown
    sync=goal_fixture.ResidentGoalTests.sync
    census=goal_fixture.ResidentGoalTests.census
    initialize=goal_fixture.ResidentGoalTests.initialize
    ready=goal_fixture.ResidentGoalTests.ready
    start=goal_fixture.ResidentGoalTests.start
    claim=goal_fixture.ResidentGoalTests.claim
    results=goal_fixture.ResidentGoalTests.results

    def test_new_goal_claims_exclude_saved_actors_and_native_occupied_destinations(self):
        self.start();self.world.active['activity_jobs']={'rest-test':{**lease(108149),'session':self.obs['session']}}
        self.obs['activity_jobs']={'jobs':[lease(999,500)]}
        context=goal_context(self.world.active,self.obs,108186)
        self.assertEqual(context['destinations'],[])
        wave=self.claim();self.assertNotIn(108149,[m['actor'] for m in wave['members']])
        self.assertIn(108149,occupied(self.world.active,self.obs))

    def test_reservation_arriving_during_goal_inference_cannot_change_saved_assignment(self):
        self.start();wave=self.claim();before=copy.deepcopy(self.world.active['town']['resident_control']['assignments']['108186'])
        self.obs['activity_jobs']={'jobs':[lease(108186)]}
        result=self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs);self.sync()
        receipt=next(r for r in result['results'] if r['actor']==108186)
        self.assertFalse(receipt['accepted']);self.assertEqual(receipt['failure'],'resident_unavailable')
        self.assertEqual(self.world.active['town']['resident_control']['assignments']['108186'],before)

    def test_saved_arrival_is_not_settled_until_native_reservation_disappears(self):
        self.start();wave=self.claim();self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs);self.sync()
        goal=copy.deepcopy(self.world.active['people']['108186']['standing_goal'])
        slot=self.world.active['town']['resident_control']['assignments']['108186']['slot']
        next(r for r in self.obs['residents'] if r['id']==108186).update(x=900,activity={'package_id':9000})
        self.obs['resident_control']['activities']=[{'actor':108186,'target':500,'goal_id':goal['id'],
            'phase':'arrived','ownedPackage':True,'distance':100,'slot':slot,'expectedPackage':9000}]
        self.obs['activity_jobs']={'jobs':[lease(108186)]}
        self.world.observe_resident_goals(self.obs)
        self.assertEqual(self.world.active['people']['108186']['standing_goal'],goal)
        self.obs['activity_jobs']={'jobs':[],'receipts':[],'reserved_actors':[]}
        self.world.observe_resident_goals(self.obs);self.sync()
        self.assertEqual(self.world.active['people']['108186']['standing_goal']['phase'],'arrived')


class ReservedRoutineTests(unittest.TestCase):
    setUp=routine_fixture.ParallelRoutineTests.setUp
    tearDown=routine_fixture.ParallelRoutineTests.tearDown
    sync=routine_fixture.ParallelRoutineTests.sync
    census=routine_fixture.ParallelRoutineTests.census
    review=routine_fixture.ParallelRoutineTests.review
    start=routine_fixture.ParallelRoutineTests.start
    choose=routine_fixture.ParallelRoutineTests.choose

    def test_later_batch_member_lease_rejects_whole_admission_atomically(self):
        self.obs['activity_jobs']={'jobs':[lease(self.ids[1])]};before=copy.deepcopy(self.world.active)
        with self.assertRaises(ValueError):self.world.begin_routines('blocked',self.events,self.obs)
        self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_new_native_seat_reservation_blocks_batch_options_and_departure(self):
        target=self.obs['places'][0]['id'];self.start()
        self.obs['activity_jobs']={'receipts':[{'actor':999,'target':target,'status':'held'}]}
        self.choose();self.assertEqual(self.world.routine_batch()['phase'],'held')
        self.assertIsNone(self.world.pending(self.obs['session']))

    def test_director_selector_does_not_offer_reserved_actor(self):
        self.obs['residents']=[r for r in self.obs['residents'] if r['id']!=108149]
        self.obs['activity_jobs']={'jobs':[lease(99)]}
        events=select_routine_events(self.world.active,self.obs,self.world.active['town']['daily']['queue'])
        self.assertEqual([e['actor'] for e in events],[108186])


class ReservedAuthoredConversationTests(unittest.TestCase):
    setUp=agency_fixture.AgencyTests.setUp
    tearDown=agency_fixture.AgencyTests.tearDown
    sync=agency_fixture.AgencyTests.sync

    def test_legacy_authored_encounter_cannot_bypass_native_quarantine(self):
        self.obs['activity_jobs']={'jobs':[lease(108149)]};before=copy.deepcopy(self.world.active)
        with self.assertRaises(ValueError):self.world.start_conversation('blocked',self.obs)
        self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)


class ReservedDirectEffectTests(unittest.TestCase):
    setUp=endowment_fixture.EndowmentTests.setUp
    tearDown=endowment_fixture.EndowmentTests.tearDown
    sync=endowment_fixture.EndowmentTests.sync
    census=endowment_fixture.EndowmentTests.census

    def test_direct_food_work_owner_and_grant_admissions_cannot_steal_actor(self):
        for method,phase in [('food','ready_to_eat'),('work','ready_to_work'),('owner','ready_to_self_work'),('grant',None),('supply',None)]:
            with self.subTest(method=method):
                actor=108186 if method=='supply' else 99
                self.world.active['plans']=[{'id':'effect','actor':actor,'target':108149,'phase':phase}] if phase else []
                self.obs['activity_jobs']={'jobs':[lease(actor)]};before=copy.deepcopy(self.world.active)
                with self.assertRaisesRegex(ValueError,'independent activity'):
                    if method=='food':self.world.plan_consumption('eat',self.obs,actor,'effect')
                    elif method=='work':self.world.plan_production(self.obs,self.world.agency_plan())
                    elif method=='owner':self.world.plan_owner_production(self.obs,self.world.agency_plan())
                    elif method=='grant':self.world.plan_endowment(actor,self.obs,self.manifest['id'],self.manifest_hash)
                    else:self.world.setup_production(self.obs)
                self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_paid_work_also_reserves_employer_not_only_worker(self):
        self.world.active['plans']=[{'id':'effect','actor':99,'target':108149,'phase':'ready_to_work'}]
        self.obs['activity_jobs']={'receipts':[{'actor':108149,'target':700,'status':'held'}]};before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'independent activity'):
            self.world.plan_production(self.obs,self.world.agency_plan())
        self.assertEqual(self.world.active,before)

    def test_disjoint_resource_recipient_is_still_admitted(self):
        self.obs['activity_jobs']={'jobs':[lease(108149)]}
        self.world.plan_endowment(99,self.obs,self.manifest['id'],self.manifest_hash)
        self.assertIsNotNone(self.world.transition)

    def test_disjoint_consuming_actor_is_still_admitted(self):
        self.world.active['plans']=[{'id':'effect','actor':99,'phase':'ready_to_eat'}]
        next(r for r in self.obs['residents'] if r['id']==99)['inventory']['bread']=1
        self.obs['activity_jobs']={'jobs':[lease(108149)]}
        self.world.plan_consumption('eat',self.obs,99,'effect')
        self.assertIsNotNone(self.world.transition)


class ReservedOwnerOpportunityTests(unittest.TestCase):
    setUp=owner_fixture.OwnerProductionTests.setUp
    tearDown=owner_fixture.OwnerProductionTests.tearDown
    sync=owner_fixture.OwnerProductionTests.sync
    census=owner_fixture.OwnerProductionTests.census
    review=owner_fixture.OwnerProductionTests.review

    def test_owner_work_menu_excludes_leased_owner_without_blocking_disjoint_work(self):
        self.assertTrue(owner_work_opportunities(self.world.active,self.obs,99))
        self.obs['activity_jobs']={'jobs':[lease(108149)]}
        self.assertTrue(owner_work_opportunities(self.world.active,self.obs,99))
        self.obs['activity_jobs']['jobs'].append(lease(99,701))
        self.assertEqual(owner_work_opportunities(self.world.active,self.obs,99),[])
