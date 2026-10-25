import copy
import unittest
import test_resident_goals as fixtures
from goal_opportunities import focus_opportunities,opportunity_policy,pending_goal_review
from resident_goals import goal_context
from places import registered_venues


class GoalFollowthroughTests(unittest.TestCase):
    setUp=fixtures.ResidentGoalTests.setUp
    tearDown=fixtures.ResidentGoalTests.tearDown
    sync=fixtures.ResidentGoalTests.sync
    census=fixtures.ResidentGoalTests.census
    initialize=fixtures.ResidentGoalTests.initialize
    ready=fixtures.ResidentGoalTests.ready
    claim=fixtures.ResidentGoalTests.claim

    def start(self):
        fixtures.ResidentGoalTests.start(self)
        self.obs['routing']={'adapter':'papyrus-mailbox-v1','available':True,'places':True}
        for row in self.obs['residents']:
            row.setdefault('x',200);row.setdefault('y',0);row.setdefault('z',0)

    def finish(self,wave,actor,choice):
        results=[{'actor':m['actor'],'result':{'model':'test-jev','attempted':True,'decision':{
            'action_id':choice if m['actor']==actor else 'quiet','reason':'Explicit test intention','emotion':'calm'}}} for m in wave['members']]
        result=self.world.finish_resident_goals('wave',wave['claim_id'],results,self.obs);self.sync();return result

    def bench(self,actor=108186):
        self.bench_id=next(iter(registered_venues('rest_bench')))
        self.obs['rest']={'available':True,'sites':[{'id':self.bench_id,'name':registered_venues('rest_bench')[self.bench_id]['name'],'loaded':True,
            'position':[1000,0,0],'occupied':False,'occupancy_known':True}],
            'sensors':{str(actor):{'sit_available':True,'furniture_reference_available':True,'sit_state':0,'furniture':0}}}

    def arrive(self,actor=108186):
        goal=self.world.active['people'][str(actor)]['standing_goal'];slot=self.world.active['town']['resident_control']['assignments'][str(actor)]['slot']
        row=next(r for r in self.obs['residents'] if r['id']==actor)
        row.update(x=900,y=0,z=0,activity={'scene_id':0,'in_combat':False,'sleep_state':0,'package_id':9000+slot})
        self.obs['resident_control']['activities']=[{'actor':actor,'target':goal['target']['id'],'goal_id':goal['id'],
            'phase':'arrived','slot':slot,'expectedPackage':9000+slot,'ownedPackage':True,'distance':100}]
        self.world.observe(self.obs);self.sync()

    def test_immediate_food_intention_queues_decision_without_consumption_or_need_relief(self):
        self.start();before=copy.deepcopy(self.obs['residents']);needs=copy.deepcopy(self.world.active['people']['99']['needs'])
        self.finish(self.claim(),99,'review_food')
        goal=self.world.active['people']['99']['standing_goal'];follow=goal['follow_through']
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['id']==follow['event_id'])
        self.assertEqual(goal['phase'],'review_pending');self.assertEqual(event['kind'],'need_review')
        self.assertEqual(event['goal_followups'][0]['goal_id'],goal['id']);self.assertEqual(event['goal_followups'][0]['focus'],'food')
        self.assertEqual(before,self.obs['residents']);self.assertEqual(needs,self.world.active['people']['99']['needs'])
        self.assertEqual(self.world.active.get('consumptions',[]),[]);self.assertEqual(self.world.active['trades'],[])
        self.assertTrue(pending_goal_review(self.world.active,99))
        self.obs['gameDays']+=1
        later=self.world.claim_resident_goals('later',self.obs)['wave']
        self.assertNotIn(99,[m['actor'] for m in later['members']])

    def test_native_rest_destination_arrival_queues_new_choice_without_recovery(self):
        self.start();self.bench();before=copy.deepcopy(self.world.active['people']['108186']['needs'])
        self.finish(self.claim(),108186,'visit_rest_'+str(self.bench_id))
        goal=self.world.active['people']['108186']['standing_goal']
        self.assertEqual(goal['phase'],'travelling');self.assertNotIn('follow_through',goal)
        self.assertFalse(pending_goal_review(self.world.active,108186))
        self.arrive();goal=self.world.active['people']['108186']['standing_goal']
        self.assertEqual(goal['phase'],'arrived');self.assertEqual(goal['follow_through']['focus'],'rest')
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['id']==goal['follow_through']['event_id'])
        self.assertEqual(event['goal_followups'][0]['trigger'],'arrival');self.assertEqual(event['status'],'pending')
        self.assertEqual(before,self.world.active['people']['108186']['needs']);self.assertEqual(self.world.active.get('rests',[]),[])
        self.world.observe(self.obs);self.sync()
        self.assertEqual(sum(e['actor']==108186 and e['status']=='pending' for e in self.world.active['town']['daily']['queue']),1)

    def test_newly_occupied_bench_rejects_choice_or_records_unavailable_followup(self):
        self.start();self.bench();wave=self.claim();self.obs['rest']['sites'][0]['occupied']=True
        result=self.finish(wave,108186,'visit_rest_'+str(self.bench_id))
        self.assertEqual(next(r for r in result['results'] if r['actor']==108186)['failure'],'stale_or_invalid_choice')
        self.assertFalse(pending_goal_review(self.world.active,108186))

    def test_occupancy_changed_during_travel_does_not_turn_arrival_into_rest(self):
        self.start();self.bench();self.finish(self.claim(),108186,'visit_rest_'+str(self.bench_id))
        self.obs['rest']['sites'][0]['occupied']=True;self.arrive()
        goal=self.world.active['people']['108186']['standing_goal']
        self.assertEqual(goal['phase'],'arrived');self.assertEqual(goal['follow_through']['status'],'unavailable')
        self.assertFalse(pending_goal_review(self.world.active,108186));self.assertEqual(self.world.active.get('rests',[]),[])

    def test_existing_pending_review_is_reused_and_terminal_outcome_is_linked(self):
        self.start();self.world.active['town']['daily']={'last_day':self.obs['gameDays'],'sequence':1,'reviews':[],
            'queue':[{'id':'existing','actor':99,'kind':'need_review','status':'pending','priority':.7}]}
        self.finish(self.claim(),99,'review_food')
        goal=self.world.active['people']['99']['standing_goal'];self.assertEqual(goal['follow_through']['event_id'],'existing')
        queue=self.world.active['town']['daily']['queue'];self.assertEqual(len(queue),1)
        queue[0].update(status='complete',outcome='deferred')
        self.world.observe(self.obs);self.sync()
        goal=self.world.active['people']['99']['standing_goal']
        self.assertEqual(goal['phase'],'reviewed');self.assertEqual(goal['follow_through']['outcome'],'deferred')
        self.assertEqual(self.world.active['trades'],[])

    def test_social_intent_replaces_only_unstarted_invitation_and_preserves_consent(self):
        self.start();self.world.active['town']['daily']={'last_day':self.obs['gameDays'],'sequence':1,'reviews':[],
            'queue':[{'id':'old-food','actor':99,'kind':'need_review','status':'pending','priority':.7}]}
        self.finish(self.claim(),99,'review_social')
        queue=self.world.active['town']['daily']['queue'];self.assertEqual(queue[0]['status'],'superseded')
        event=next(e for e in queue if e['status']=='pending');self.assertEqual(event['kind'],'social_review')
        self.assertIsNone(self.world.conversation_status())
        self.world.start_conversation(event['id'],self.obs,99);self.sync()
        self.assertEqual(self.world.conversation_status()['phase'],'choose_partner')
        self.assertEqual(self.world.conversation_status()['turns'],[])

    def test_expired_social_intent_without_partners_releases_goal_after_cooldown(self):
        self.start();self.finish(self.claim(),99,'review_social')
        goal=self.world.active['people']['99']['standing_goal'];event_id=goal['follow_through']['event_id']
        self.obs['residents']=[r for r in self.obs['residents'] if r['id']==99]
        self.obs['residents'][0]['inventory'].update(bread=0,gold=0,grain=0)
        before=copy.deepcopy(self.obs['residents'])
        self.obs['gameDays']+=1
        self.world.review_population(self.obs);self.sync()
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['id']==event_id)
        self.assertEqual(event['status'],'superseded')
        self.assertEqual(event['outcome'],'goal_social_opportunity_unavailable')
        self.assertFalse(pending_goal_review(self.world.active,99))
        self.world.observe(self.obs);self.sync()
        goal=self.world.active['people']['99']['standing_goal']
        self.assertEqual(goal['phase'],'reviewed')
        self.assertEqual(goal['follow_through']['status'],'superseded')
        self.assertEqual(goal['follow_through']['outcome'],'goal_social_opportunity_unavailable')
        self.assertTrue(self.world.claim_resident_goals('too-soon',self.obs)['empty'])
        self.obs['gameDays']=goal['next_review_day']+1e-6
        result=self.world.claim_resident_goals('reconsider',self.obs)
        self.assertEqual([m['actor'] for m in result['wave']['members']],[99])
        self.assertEqual(self.obs['residents'],before)
        self.assertEqual(self.world.active['trades'],[])
        self.assertEqual(self.world.active.get('consumptions',[]),[])
        self.assertIsNone(self.world.conversation_status())

    def test_expired_social_intent_keeps_available_partners_and_started_work(self):
        for started,partners_remain in ((False,True),(True,False)):
            with self.subTest(started=started,partners_remain=partners_remain):
                self.tearDown();self.setUp();self.start();self.finish(self.claim(),99,'review_social')
                goal=self.world.active['people']['99']['standing_goal'];event_id=goal['follow_through']['event_id']
                event=next(e for e in self.world.active['town']['daily']['queue'] if e['id']==event_id)
                if started:event['status']='started'
                if not partners_remain:self.obs['residents']=[r for r in self.obs['residents'] if r['id']==99]
                next(r for r in self.obs['residents'] if r['id']==99)['inventory'].update(bread=0,gold=0,grain=0)
                self.obs['gameDays']+=1
                self.world.review_population(self.obs);self.sync()
                event=next(e for e in self.world.active['town']['daily']['queue'] if e['id']==event_id)
                self.assertEqual(event['status'],'started' if started else 'pending')
                self.assertTrue(pending_goal_review(self.world.active,99))

    def test_work_review_uses_public_charter_not_private_employer_inventory_or_name(self):
        self.start();self.world.active['town']['businesses']['new-shop']={'custodian':108149,'owner':108149,
            'capabilities':['bread_recipe'],'revision':1,'active':True}
        first=goal_context(self.world.active,self.obs,99)
        self.assertIn('review_work',[o['id'] for o in first['options']])
        employer=next(r for r in self.obs['residents'] if r['id']==108149)
        employer['inventory']={'gold':987654321,'bread':12345,'grain':0,'secret':'private resources'}
        self.world.active['people']['108149']['memories'].append({'secret':'private work history'})
        second=goal_context(self.world.active,self.obs,99)
        self.assertEqual(first['public_opportunities']['public_work'],second['public_opportunities']['public_work'])
        self.assertNotIn('987654321',str(second));self.assertNotIn('private resources',str(second));self.assertNotIn('private work history',str(second))
        self.assertEqual(second['public_opportunities']['public_work'][0]['employer']['name'],'an unfamiliar resident')
        self.world.active['town']['businesses']['new-shop']['active']=False
        self.assertNotIn('review_work',[o['id'] for o in goal_context(self.world.active,self.obs,99)['options']])

    def test_policy_can_disable_focus_without_removing_quiet_or_generic_exploration(self):
        self.start();policy=opportunity_policy();policy['enabled_focuses']=[]
        context=goal_context(self.world.active,self.obs,108186,opportunity_policy=policy)
        self.assertEqual({o['id'] for o in context['options']},{'quiet','visit_500'})
        for change in ({'priority_floor':True},{'maximum_followup_sources':0},{'enabled_focuses':['food','food']}):
            with self.assertRaises(ValueError):opportunity_policy({**policy,**change})
