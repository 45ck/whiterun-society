import copy
import unittest
from routing import actor_route_supported, dynamic_route, route_available


class UniformRoutingTests(unittest.TestCase):
    def observation(self, pair=(108186,108149)):
        return {'session':'current','routing':{'adapter':'papyrus-mailbox-v1','available':True},
                'residents':[{'id':actor,'isPerson':True,'activity':{
                    'scene_id':0,'in_combat':False,'sleep_state':0}} for actor in pair]}

    def test_original_and_discovered_pairs_require_the_same_current_executor(self):
        for pair in ((108186,108149),(108156,108186),(800001,800002)):
            with self.subTest(pair=pair):
                observation=self.observation(pair)
                self.assertTrue(dynamic_route(*pair))
                self.assertTrue(route_available(observation,*pair))
                for capability in (None,{}, {'available':False,'adapter':'papyrus-mailbox-v1'},
                                   {'available':True,'adapter':'fixed-quest'}, {'available':1,'adapter':'papyrus-mailbox-v1'}):
                    self.assertFalse(route_available({**observation,'routing':capability},*pair))

    def test_both_parties_must_be_observed_classified_and_available(self):
        for index in (0,1):
            for patch in ({'isPerson':None},{'isPerson':False},{'isChild':True},{'isDead':True},
                          {'loaded':False},{'activity':{}},{'activity':{'scene_id':7,'in_combat':False,'sleep_state':0}},
                          {'session':'older'}):
                with self.subTest(index=index,patch=patch):
                    observation=self.observation();observation['residents'][index].update(patch)
                    self.assertFalse(route_available(observation,108186,108149))
        self.assertFalse(route_available(self.observation(),108186,108186))
        self.assertFalse(route_available(self.observation(),108186,900001))

    def test_support_projection_preserves_unknown_false_and_stale_evidence(self):
        observation=self.observation()
        self.assertIs(actor_route_supported(observation,108186),True)
        self.assertIsNone(actor_route_supported({**observation,'routing':None},108186))
        observation['routing']['available']=False
        self.assertIs(actor_route_supported(observation,108186),False)
        observation['routing'].update(available=True,session='older')
        self.assertIsNone(actor_route_supported(observation,108186))
        observation=self.observation();observation['residents'].append(copy.deepcopy(observation['residents'][0]))
        self.assertIsNone(actor_route_supported(observation,108186))

    def test_rest_work_and_native_orphan_reservations_still_block_uniform_routes(self):
        observation=self.observation()
        for actor in (108186,108149):
            for key in ('activity_jobs','work_jobs','activity_orphans','work_orphans'):
                with self.subTest(actor=actor,key=key):
                    state={key:{'job':{'id':'job','actor':actor,'target':999,'receipt_acknowledged':False}}}
                    self.assertFalse(route_available(observation,108186,108149,state))
                    state[key]['job']['receipt_acknowledged']=True
                    self.assertTrue(route_available(observation,108186,108149,state))
            native={**observation,'owner_work_jobs':{'reserved_actors':[actor]}}
            self.assertFalse(route_available(native,108186,108149))
        # Projection says the executor supports this person; leases are a separate availability boundary.
        self.assertIs(actor_route_supported(observation,108186),True)


if __name__=='__main__':unittest.main()
