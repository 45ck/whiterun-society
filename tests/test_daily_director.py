import unittest
from tools.run_daily_life import event_available,isolated_before_action

class DirectorTests(unittest.TestCase):
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

if __name__=='__main__':unittest.main()
