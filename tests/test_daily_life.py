import copy
import unittest
import test_population


class DailyLifeTests(unittest.TestCase):
    tearDown=test_population.PopulationTests.tearDown
    sync=test_population.PopulationTests.sync
    census=test_population.PopulationTests.census

    def setUp(self):
        test_population.PopulationTests.setUp(self)
        self.census()
        self.world.initialize_population('census','daily-seed',self.obs);self.sync()
        self.world.configure_enterprise('fixture-bakery', {'id':'business-108149','expected_revision':0,
            'name':'Fixture food enterprise','custodian':108149,'capabilities':['bread_recipe','retail_food'],
            'active':True}, self.obs);self.sync()
        for p in self.world.active['people'].values():
            if 'agency' in p:p['needs']['hunger']=.4
        self.world.active['people']['108149']['food_policy']={'mode':'fixed_reserve','reserve_target':1,
            'reviewed_day':self.obs['gameDays'],'observed_bread':self.obs['residents'][1]['inventory']['bread']}

    def review(self,hours=0):
        self.obs['gameDays']+=hours/24
        result=self.world.review_population(self.obs);self.sync();return result

    def test_elapsed_game_time_changes_needs_without_minting_resources(self):
        stock=copy.deepcopy(self.obs['residents']);before=copy.deepcopy(self.world.active['people'])
        result=self.review(4)
        for key in self.world.active['town']['residents']:
            person=self.world.active['people'][key]
            self.assertAlmostEqual(person['needs']['hunger'],.62)
            self.assertGreater(person['needs']['fatigue'],before[key]['needs']['fatigue'])
        self.assertEqual(stock,self.obs['residents']);self.assertEqual(len(result['new_events']),3)

    def test_paused_clock_and_repeated_review_do_not_repeat_growth_or_queue(self):
        self.review(4);before=copy.deepcopy(self.world.active)
        self.assertTrue(self.review()['duplicate']);self.assertEqual(before,self.world.active)
        self.review(1);self.assertEqual(len(self.world.active['town']['daily']['queue']),3)

    def test_scheduled_event_does_not_add_authored_meal_time_hunger(self):
        self.review(4)
        e=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        hunger=self.world.active['people']['99']['needs']['hunger']
        self.world.begin_plan(e['id'],self.obs,99,'need_review');self.sync()
        self.assertEqual(self.world.active['people']['99']['needs']['hunger'],hunger)
        context=self.world.claim_plan_decision(e['id'],self.obs)['claim']['context']
        self.assertEqual({o['id'] for o in context['options']},{'defer','eat_bread'})

    def test_unsupported_hungry_resident_stays_unmet_without_model_request(self):
        self.obs['residents'][2]['inventory']['bread']=0
        self.review(4)
        self.assertEqual(self.world.active['people']['99']['agency']['state'],'unmet_food_need')
        self.assertNotIn(99,[e['actor'] for e in self.world.active['town']['daily']['queue']])

    def test_router_allows_new_resident_to_seek_food_without_inventing_a_sale(self):
        self.obs['residents'][2]['inventory']['bread']=0
        self.obs['routing']={'adapter':'papyrus-mailbox-v1','available':True}
        self.review(4)
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.world.begin_plan(event['id'],self.obs,99,'need_review');self.sync()
        claim=self.world.claim_plan_decision(event['id'],self.obs);self.sync()
        options={o['id'] for o in claim['claim']['context']['options']}
        self.assertIn('seek_bread',options)
        self.assertEqual(self.obs['residents'][2]['inventory'],{'gold':7,'bread':0,'grain':0})
        self.assertTrue(self.world.active['people']['99']['agency']['native_route_supported'])
        self.world.finish_plan_decision(event['id'],claim['claim']['id'],{'decision':{
            'action_id':'seek_bread','reason':'Authored test choice','emotion':'calm'}},self.obs);self.sync()
        command=self.world.pending(self.obs['session'])
        self.assertTrue(command['dynamic']);self.assertEqual(command['actor'],99)
        self.obs['residents'][2].update(x=100,y=0,z=0)
        self.obs['ack']={'id':command['id'],'status':'applied','movement':{'hasOwnedPackage':True}}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held')

    def test_dynamic_owned_arrival_requires_matching_papyrus_acknowledgement(self):
        self.obs['residents'][2]['inventory']['bread']=0
        self.obs['routing']={'adapter':'papyrus-mailbox-v1','available':True}
        self.review(4)
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.world.begin_plan(event['id'],self.obs,99,'need_review');self.sync()
        claim=self.world.claim_plan_decision(event['id'],self.obs)['claim'];self.sync()
        self.world.finish_plan_decision(event['id'],claim['id'],{'decision':{
            'action_id':'seek_bread','reason':'Authored test choice','emotion':'calm'}},self.obs);self.sync()
        command=self.world.pending(self.obs['session']);self.obs['residents'][2].update(x=100,y=0,z=0)
        self.obs['ack']={'id':command['id'],'status':'applied','movement':{'hasOwnedPackage':True,
            'aliasesConfirmed':True,'adapter':'papyrus-mailbox','actor':99,'target':108149}}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'quote')
        self.assertEqual(self.world.agency_plan()['offer_round'],0)
        self.assertIsNone(self.world.active['pending'])  # Arrival has not chosen a price or exchanged goods.

    def test_missing_seller_or_unclassified_resident_cannot_gain_router_opportunity(self):
        self.obs['residents'][2]['inventory']['bread']=0
        self.obs['routing']={'adapter':'papyrus-mailbox-v1','available':True}
        self.obs['residents']=[a for a in self.obs['residents'] if a['id']!=108149]
        self.review(4)
        self.assertEqual(self.world.active['people']['99']['agency']['state'],'unmet_food_need')

    def test_unloaded_residents_age_but_get_no_fictitious_execution(self):
        self.obs['residents']=[a for a in self.obs['residents'] if a['id']!=99]
        self.review(4)
        self.assertEqual(self.world.active['people']['99']['agency']['state'],'unloaded')
        self.assertEqual(self.world.active['people']['99']['memories'],[])

    def test_quiet_review_makes_no_events_and_clock_reversal_is_rejected(self):
        self.assertEqual(self.review()['new_events'],[])
        self.obs['gameDays']-=1
        with self.assertRaisesRegex(ValueError,'backwards'):self.world.review_population(self.obs)

    def test_load_before_review_removes_future_aging_and_events(self):
        old=copy.deepcopy(self.obs);self.review(4)
        self.world.observe({**old,'session':'older-day'})
        self.assertNotIn('daily',self.world.active['town'])

    def test_previous_consumption_prevents_aging_hunger_for_pre_meal_time(self):
        p=self.world.active['people']['99'];p['needs']['hunger']=.1;p['hunger_clock']=self.obs['gameDays']+3/24
        self.review(4)
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['hunger'],.155)

    def test_arbitrary_scheduled_event_cannot_bypass_queue(self):
        with self.assertRaisesRegex(ValueError,'matching pending'):self.world.begin_plan('invented',self.obs,99,'need_review')

    def queued_social(self, status='pending'):
        self.review()
        self.world.active['town']['daily']['queue'].append({'id':'old-social', 'actor':99,
            'kind':'social_review','status':status,'priority':.45,'created_day':self.obs['gameDays'],
            'reason':'A previously available conversation'})
        self.world.active['people']['99']['agency']['next_review_day']=self.obs['gameDays']+1

    def test_urgent_food_supersedes_unaccepted_invitation_without_changing_inventory(self):
        self.queued_social();stock=copy.deepcopy(self.obs['residents'])
        self.review(4)
        events=[e for e in self.world.active['town']['daily']['queue'] if e['actor']==99]
        self.assertEqual([(e['kind'],e['status']) for e in events],
                         [('social_review','superseded'),('need_review','pending')])
        self.assertEqual(stock,self.obs['residents'])
        self.assertEqual(self.world.active['people']['99']['memories'],[])
        with self.assertRaises(ValueError):
            self.world.start_conversation('old-social',self.obs,99)

    def test_started_invitation_and_unexecutable_need_are_not_preempted(self):
        self.queued_social('started');self.review(4)
        self.assertEqual([e['status'] for e in self.world.active['town']['daily']['queue'] if e['actor']==99],['started'])
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['id']=='old-social')
        event['status']='pending';self.obs['residents'][2]['inventory']['bread']=0
        self.review(1)
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['id']=='old-social')
        self.assertEqual(event['status'],'pending')

    def test_pending_need_priority_tracks_current_needs_without_duplicate_event(self):
        self.review(4)
        old=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)['id']
        self.review(4)
        events=[e for e in self.world.active['town']['daily']['queue'] if e['actor']==99]
        self.assertEqual(len(events),1);self.assertEqual(events[0]['id'],old)
        self.assertGreaterEqual(events[0]['priority'],.84)

    def test_interrupted_claim_is_certified_effect_free_but_retains_claim_audit(self):
        self.review(4)
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.world.begin_plan(event['id'],self.obs,99,'need_review');self.sync()
        claim=self.world.claim_plan_decision(event['id'],self.obs)['claim'];self.sync()
        self.obs['residents']=[a for a in self.obs['residents'] if a['id']!=99]
        self.world.hold_plan(event['id'],'Participant left during inference',self.obs);self.sync()
        self.assertTrue(self.world.agency_plan()['effect_free_hold'])
        self.assertEqual(self.world.agency_plan()['claim']['id'],claim['id'])
        self.assertEqual(self.world.agency_plan()['decisions'],[])
        self.assertIsNone(self.world.pending(self.obs['session']))

    def test_scheduled_consumption_settles_queue_and_ages_only_post_meal_time(self):
        self.review(4)
        e=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.world.begin_plan(e['id'],self.obs,99,'need_review');self.sync()
        claim=self.world.claim_plan_decision(e['id'],self.obs)['claim'];self.sync()
        self.obs['gameDays']+=3/24
        self.world.finish_plan_decision(e['id'],claim['id'],{'decision':{
            'action_id':'eat_bread','reason':'Authored test choice','emotion':'calm'}},self.obs);self.sync()
        command=self.world.pending(self.obs['session'])
        actor=next(a for a in self.obs['residents'] if a['id']==99)
        actor['inventory'].update(command['after'])
        self.obs['ack']={'id':command['id'],'status':'applied'}
        self.world.observe(self.obs);self.sync()
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['hunger'],.185)
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.assertEqual(event['status'],'complete');self.assertEqual(event['outcome'],'ate_bread')
        self.review(1)
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['hunger'],.24)


if __name__=='__main__':unittest.main()
