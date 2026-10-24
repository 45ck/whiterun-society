import unittest
from tools.run_daily_life import event_available

class DirectorTests(unittest.TestCase):
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
