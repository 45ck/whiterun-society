import copy
import unittest
import test_social as fixtures
from social import social_candidates, social_context
from metrics import simulation_metrics


class SocialFollowthroughTests(unittest.TestCase):
    setUp=fixtures.SocialTests.setUp
    tearDown=fixtures.SocialTests.tearDown
    sync=fixtures.SocialTests.sync
    census=fixtures.SocialTests.census
    review=fixtures.SocialTests.review
    begin=fixtures.SocialTests.begin
    decide=fixtures.SocialTests.decide
    meet=fixtures.SocialTests.meet
    speak=fixtures.SocialTests.speak
    release=fixtures.SocialTests.release

    def conversation(self):
        self.begin();self.meet();self.decide('chat')
        self.speak();self.speak();self.release()

    def test_heard_exchange_drives_a_queued_review_and_verified_meal(self):
        self.conversation();inventory=copy.deepcopy(self.obs['residents'])
        context=self.decide('review_food_after_talk');self.decide('neutral')
        c=self.world.conversation_status();follow=c['follow_through'][0]
        self.assertEqual(inventory,self.obs['residents'])
        self.assertEqual(follow['actor'],99);self.assertEqual(follow['focus'],'food')
        self.assertEqual(self.world.active['people']['99']['agency']['state'],'decision_pending')
        self.assertEqual(len(follow['heard']),1)
        self.assertEqual(follow['heard'][0]['speaker'],108149)
        self.assertNotIn('other_inventory',context)
        self.world.begin_plan(follow['event_id'],self.obs,99,'need_review');self.sync()
        claim=self.world.claim_plan_decision(follow['event_id'],self.obs)['claim'];self.sync()
        self.assertEqual(claim['context']['conversation_followups'][0]['encounter_id'],c['id'])
        self.assertEqual(claim['context']['conversation_followups'][0]['heard'],follow['heard'])
        self.world.finish_plan_decision(follow['event_id'],claim['id'],{'model':'test-jev','decision':{
            'action_id':'eat_bread','reason':'The conversation reminded me to eat.','emotion':'calm'}},self.obs);self.sync()
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'inventory_consume')
        actor=next(r for r in self.obs['residents'] if r['id']==99)
        self.assertNotEqual(actor['inventory'],command['after'])
        actor['inventory']=copy.deepcopy(command['after']);self.obs['ack']={'id':command['id'],'status':'applied'}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['outcome'],'ate_bread')
        self.assertEqual(self.world.agency_plan()['conversation_followups'][0]['encounter_id'],c['id'])
        # The same completion cannot consume a second loaf.
        before=copy.deepcopy(actor['inventory']);self.world.observe(self.obs);self.sync()
        self.assertEqual(actor['inventory'],before)

    def test_unheard_words_cannot_trigger_followthrough(self):
        self.begin();self.meet();self.decide('chat')
        c=self.world.conversation_status()
        options=social_context(self.world.active,c,self.obs,'reflect_first')['options']
        self.assertFalse(any(o['id'].endswith('_after_talk') for o in options))
        self.assertNotIn('follow_through',c)

    def test_existing_food_review_receives_source_without_duplicate_errand(self):
        self.conversation()
        self.world.active['town']['daily']['queue'].append({'id':'existing-food','actor':99,'kind':'need_review',
            'status':'pending','priority':.4,'reason':'Existing need review','created_day':self.obs['gameDays']})
        self.decide('review_food_after_talk');self.decide('neutral')
        pending=[e for e in self.world.active['town']['daily']['queue'] if e['actor']==99 and e['kind']=='need_review' and e['status']=='pending']
        self.assertEqual(len(pending),1);self.assertEqual(pending[0]['id'],'existing-food')
        self.assertEqual(len(pending[0]['conversation_followups']),1)

    def test_older_checkpoint_does_not_inherit_a_future_followup(self):
        self.conversation();before=copy.deepcopy(self.obs)
        self.decide('review_food_after_talk');self.decide('neutral')
        self.assertTrue(self.world.conversation_status()['follow_through'])
        self.world.observe({**before,'session':'before-followup'})
        self.assertNotIn('follow_through',self.world.conversation_status())
        self.assertFalse(any(e.get('conversation_followups') for e in self.world.active['town']['daily']['queue']))

    def test_all_nearby_people_are_options_including_guards_with_duties(self):
        for i in range(8):
            actor=1000+i;key=str(actor)
            self.world.active['people'][key]=copy.deepcopy(self.world.active['people']['99'])
            self.world.active['people'][key]['commitments']=[{'kind':'duty'}]
            self.world.active['town']['residents'][key]=copy.deepcopy(self.world.active['town']['residents']['99'])
            self.obs['residents'].append({'id':actor,'isPerson':True,'isGuard':True,'name':'New guard',
                'x':210+i,'y':0,'z':0,'inventory':{'gold':3,'bread':1,'grain':0}})
        candidates=social_candidates(self.world.active,self.obs,99)
        self.assertTrue(set(range(1000,1008)).issubset({c['id'] for c in candidates}))

    def test_counterparty_does_not_receive_the_buyers_private_heard_context(self):
        self.conversation();self.decide('review_food_after_talk');self.decide('neutral')
        follow=self.world.conversation_status()['follow_through'][0]
        self.world.begin_plan(follow['event_id'],self.obs,99,'need_review');self.sync()
        plan=copy.deepcopy(self.world.agency_plan());plan.update(phase='consent',target=108149)
        context=self.world._plan_context(self.obs,plan)
        self.assertEqual(context['actor_id'],108149)
        self.assertEqual(context['conversation_followups'],[])
        self.assertNotIn('You chose this review after a conversation',context['event']['information'])


if __name__=='__main__':unittest.main()
