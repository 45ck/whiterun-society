import copy
import unittest
from unittest.mock import patch
import test_daily_life
from test_goal_scheduler import snapshot
from tools.goal_scheduler import due_residents
from tools.run_daily_life import routine_dispatch_prefix


class ProductiveIntegrationTests(unittest.TestCase):
    def daily(self):
        f=test_daily_life.DailyLifeTests('test_elapsed_game_time_changes_needs_without_minting_resources')
        f.setUp();self.addCleanup(f.tearDown);return f

    def test_chosen_goal_reaches_economic_context_and_allows_different_action(self):
        f=self.daily();f.review(4)
        event=next(e for e in f.world.active['town']['daily']['queue'] if e['actor']==99)
        event['goal_followups']=[{'actor':99,'focus':'work','goal_id':'chosen-work','source':'own model decision'}]
        before=copy.deepcopy(f.obs['residents'])
        f.world.begin_plan(event['id'],f.obs,99,'need_review');f.sync()
        claim=f.world.claim_plan_decision(event['id'],f.obs)['claim'];f.sync()
        self.assertEqual(claim['context']['own_goal_followups'][0]['focus'],'work')
        self.assertIn('eat_bread',[o['id'] for o in claim['context']['options']])
        f.world.finish_plan_decision(event['id'],claim['id'],{'decision':{'action_id':'eat_bread','reason':'Changed priorities','emotion':'calm'}},f.obs);f.sync()
        self.assertEqual(f.world.agency_plan()['phase'],'consuming')
        self.assertEqual(f.world.active['pending']['command']['kind'],'inventory_consume')
        self.assertEqual(f.obs['residents'],before)
        self.assertFalse(f.world.active.get('consumptions'))

    def test_hungry_merchant_can_choose_reserve_review_without_automatic_effect(self):
        f=self.daily();f.review(4)
        event=next(e for e in f.world.active['town']['daily']['queue'] if e['actor']==108149)
        f.world.begin_plan(event['id'],f.obs,108149,'need_review');f.sync()
        before=copy.deepcopy(f.obs['residents']);policy=copy.deepcopy(f.world.active['people']['108149']['food_policy'])
        claim=f.world.claim_plan_decision(event['id'],f.obs)['claim'];f.sync()
        self.assertIn('review_food_reserve',[o['id'] for o in claim['context']['options']])
        f.world.finish_plan_decision(event['id'],claim['id'],{'decision':{'action_id':'review_food_reserve','reason':'Reconsider stock','emotion':'calm'}},f.obs);f.sync()
        self.assertEqual(f.world.agency_plan()['phase'],'allocate')
        self.assertEqual(f.world.active['people']['108149']['food_policy'],policy)
        self.assertEqual(f.obs['residents'],before)

    def test_chosen_social_review_has_bounded_protection_then_urgent_need_can_supersede(self):
        f=self.daily();day=f.obs['gameDays']
        f.world.active['town']['daily']={'last_day':day-1,'sequence':0,'reviews':[],'queue':[{
            'id':'chosen-social','actor':99,'kind':'social_review','status':'pending','priority':.45,'created_day':day,
            'goal_followups':[{'goal_id':'social-intent','actor':99,'focus':'social'}],'review_expires_day':day+1/24}]}
        f.world.active['people']['99']['needs']['hunger']=.9
        f.review();event=f.world.active['town']['daily']['queue'][0]
        self.assertEqual(event['status'],'pending')
        f.review(2);events=f.world.active['town']['daily']['queue']
        self.assertEqual(next(e for e in events if e['id']=='chosen-social')['status'],'superseded')
        self.assertTrue(any(e['actor']==99 and e['kind']=='need_review' and e['status']=='pending' for e in events))

    def test_native_travel_batch_cannot_jump_over_older_self_care_or_narrow_goal_menu(self):
        events=[{'id':'old-food'},{'id':'journey'},{'id':'next-journey'}]
        with patch('tools.run_daily_life.select_routine_events',side_effect=lambda s,o,es,n:[] if es[0]['id']=='old-food' else es):
            self.assertEqual(routine_dispatch_prefix({}, {}, events),[])
            self.assertEqual(routine_dispatch_prefix({}, {},events[1:]),events[1:])
            events[1]['goal_followups']=[{'focus':'work'}]
            self.assertEqual(routine_dispatch_prefix({}, {},events[1:]),[])

    def test_pending_personal_review_does_not_spawn_empty_repeated_goal_workers(self):
        state=snapshot();state['society']['town']['daily']={'queue':[{'actor':1,'status':'pending','goal_followups':[{'focus':'food'}]}]}
        self.assertNotIn(1,due_residents(state));self.assertIn(2,due_residents(state))


if __name__=='__main__':unittest.main()
