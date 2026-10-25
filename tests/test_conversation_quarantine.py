import copy
import unittest
from activity_leases import activity_conflict,conversation_quarantine_actors,reserved_activity_actors
from routing import route_available
from resident_goals import occupied


class ConversationQuarantineTests(unittest.TestCase):
    def test_contradictory_cleanup_unions_evidence_without_picking_an_owner(self):
        conversation={'phase':'held','cleanup_review_required':True,'release_required':True,
            'meeting_route':{'actor':1,'target':2},'initiator':3,'partner':4,
            'speakers':[5,6],'scenario':{'participants':[7,8]}}
        state={'conversation':conversation};before=copy.deepcopy(state)
        self.assertEqual(conversation_quarantine_actors(state),set(range(1,9)))
        self.assertEqual(reserved_activity_actors(state),set(range(1,9)))
        self.assertEqual(state,before)
        self.assertTrue(set(range(1,9))<=occupied(state))

    def test_missing_identity_quarantines_all_managed_and_observed_without_fabricating_release(self):
        state={'conversation':{'phase':'held','cleanup_review_required':True,'speakers':[None,True,-1,'123']},
               'people':{'1':{},'02':{},'bad':{}},'town':{'residents':{'2':{}},'resident_control':{'assignments':{'slot':{'actor':3}}}}}
        obs={'residents':[{'id':4},{'id':False},{'id':-1},{'id':0x100000000}]}
        self.assertEqual(conversation_quarantine_actors(state,obs),{1,2,3,4})
        self.assertEqual(state['conversation']['speakers'],[None,True,-1,'123'])

    def test_flags_persist_reservations_until_both_cleared_and_do_not_block_disjoint_routes(self):
        state={'conversation':{'phase':'held','release_required':True,'speakers':[1,2]}}
        obs={'routing':{'adapter':'papyrus-mailbox-v1','available':True},
             'residents':[{'id':i,'isPerson':True} for i in range(1,5)]}
        self.assertFalse(route_available(obs,1,3,state));self.assertTrue(route_available(obs,3,4,state))
        state['conversation'].update(release_required=False,cleanup_review_required=True)
        self.assertFalse(route_available(obs,1,3,state))
        state['conversation']['cleanup_review_required']=False
        self.assertTrue(route_available(obs,1,3,state))

    def test_partial_or_malformed_pairs_expand_quarantine_and_preserve_known_unobserved_hints(self):
        for identity in ({'speakers':[9]}, {'initiator':9,'meeting_route':{'target':8}},
                         {'speakers':[8,9],'scenario':{}}, {'speakers':{},'meeting_route':{'actor':8,'target':9}}):
            with self.subTest(identity=identity):
                state={'conversation':{'phase':'held','release_required':True,**identity},'people':{'1':{},'2':{}}}
                expected={1,2,3,9} if identity=={'speakers':[9]} else {1,2,3,8,9}
                self.assertEqual(conversation_quarantine_actors(state,{'residents':[{'id':3}]}),expected)

    def test_active_and_releasing_claims_do_not_self_conflict_or_bypass_external_leases(self):
        for phase in ('meeting','speaking','releasing','complete'):
            with self.subTest(phase=phase):
                state={'conversation':{'phase':phase,'release_required':True,'speakers':[1,2]}}
                self.assertEqual(conversation_quarantine_actors(state),set())
                state['activity_jobs']={'rest':{'actor':1,'receipt_acknowledged':False}}
                self.assertTrue(activity_conflict(state,actors=[1]))


if __name__=='__main__':unittest.main()
