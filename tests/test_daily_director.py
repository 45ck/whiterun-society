import unittest
from unittest.mock import patch
from tools.run_daily_life import event_available,isolated_before_action,fair_pending

class DirectorTests(unittest.TestCase):
    def test_nearby_opportunity_requires_a_current_qualified_partner(self):
        state={'society':{'town':{'residents':{'7':{}}}},'bridge':{'observation':{}}}
        event={'kind':'social_opportunity','actor':None}
        with patch('tools.run_daily_life.social_candidates',return_value=[]):
            self.assertFalse(event_available(state,event))
        with patch('tools.run_daily_life.social_candidates',return_value=[{'id':8}]):
            self.assertTrue(event_available(state,event))

    def test_social_life_cannot_be_starved_by_higher_priority_hunger_queue(self):
        food=[{'id':str(i),'kind':'need_review','priority':1} for i in range(20)]
        social=[{'id':'s'+str(i),'kind':'social_review','priority':.45} for i in range(3)]
        result=fair_pending(food+social)
        self.assertEqual([e['kind'] for e in result[:6]],['social_review','need_review']*3)
        self.assertEqual(len(result),23)
        self.assertEqual(len({e['id'] for e in result}),23)
        self.assertEqual(fair_pending(food+social,False)[0]['kind'],'need_review')

    def test_only_verified_effect_free_failure_allows_other_residents_to_continue(self):
        event={'id':'need-1','kind':'need_review'}
        plan={'id':'need-1','phase':'held','effect_free_hold':True,'remembered':True,'decisions':[]}
        state={'society':{'plan':plan},'bridge':{}}
        self.assertTrue(isolated_before_action(state,event))
        for key,value in [('effect_free_hold',False),('remembered',False),('release_required',True),
                          ('travel',{'phase':'held'}),('decisions',[{'action':'seek_bread'}])]:
            with self.subTest(key=key):
                modified={**state,'society':{'plan':{**plan,key:value}}}
                self.assertFalse(isolated_before_action(modified,event))
        self.assertFalse(isolated_before_action({**state,'bridge':{'command':{'kind':'trade'}}},event))
        self.assertFalse(isolated_before_action(state,{**event,'kind':'social_review'}))
    def test_completed_partner_opportunity_and_unloaded_actor_are_skipped(self):
        event={'id':'social-1','kind':'social_review','actor':7,'status':'pending'}
        state={'society':{'town':{'daily':{'queue':[{**event,'status':'complete'}]}}},'bridge':{'observation':{'residents':[{'id':7,'isPerson':True}]}}}
        self.assertFalse(event_available(state,event))
        state['society']['town']['daily']['queue']=[event]
        state['bridge']['observation']['residents']=[]
        self.assertFalse(event_available(state,event))

    def test_pending_loaded_economic_event_is_available_without_social_partner(self):
        event={'id':'meal-1','kind':'need_review','actor':7,'status':'pending'}
        state={'society':{'town':{'daily':{'queue':[event]}}},'bridge':{'observation':{'residents':[{'id':7,'isPerson':True}]}}}
        self.assertTrue(event_available(state,event))

    def test_resident_followthrough_precedes_demo_social_alternation(self):
        meal={'id':'follow','actor':7,'kind':'need_review','priority':.4,'conversation_followups':[{'encounter_id':'heard'}]}
        ordinary=[{'id':'chat','kind':'social_review','priority':1},{'id':'food','kind':'need_review','priority':.9}]
        for social_first in (True,False):
            result=fair_pending(ordinary+[meal],social_first)
            self.assertEqual(result[0]['id'],'follow')
            self.assertEqual({e['id'] for e in result},{'follow','chat','food'})

if __name__=='__main__':unittest.main()
