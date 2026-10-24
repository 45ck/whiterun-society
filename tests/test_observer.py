import copy
import time
import unittest
from observer import camera_request,observer_state


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.obs={'residents':[{'id':99,'isPerson':True,'x':1,'y':2,'z':3,'inventory':{'gold':7}}]}
        self.society={'checkpoint':10,'town':{'residents':{'99':{'name':'Resident'},'100':{'name':'Unloaded'}}},'people':{'99':{'memories':[]}}}

    def test_camera_only_accepts_current_loaded_initialized_people(self):
        self.assertEqual(camera_request({'mode':'focus','id':99},self.obs,self.society)['id'],99)
        for actor in (100,True,'99',-1):
            with self.assertRaises(ValueError):camera_request({'mode':'focus','id':actor},self.obs,self.society)
        for distance in (float('inf'),float('nan'),0,4001,True):
            with self.assertRaises(ValueError):camera_request({'mode':'free','distance':distance},self.obs,self.society)

    def test_projection_retains_unloaded_people_and_never_exposes_bridge_command(self):
        before=copy.deepcopy(self.society)
        result=observer_state({'last_seen':time.time(),'observation':self.obs,'command':{'secret':'not for observer'}},self.society)
        self.assertTrue(result['connected']);self.assertEqual(len(result['residents']),2)
        self.assertFalse(result['residents'][1]['loaded']);self.assertIsNone(result['residents'][1]['inventory'])
        self.assertNotIn('command',result);self.assertEqual(before,self.society)
        result=observer_state({'last_seen':0,'observation':self.obs},self.society)
        self.assertFalse(result['connected'])
