"""Employment must leave its meeting before taking an independent worker lease."""
import copy
import unittest
from unittest.mock import patch
from agency import Agency


class World(Agency):
    def __init__(self):
        self.session='paid-routing';self.marker=7;self.delegated=[]
        self.active={'people':{},'plans':[{'id':'job-meeting','actor':101,'target':202,
            'phase':'ready_to_work','work_terms':{'protocol':2},'release_required':True,
            'economic_pair':[101,202],'voiced_trade':True}]}

    def _write(self,state,reason):
        self.active=state;return self.marker+1

    def observe_trade_speech(self,observation):return False
    def delegate_paid_work(self,plan,observation):
        self.delegated.append(copy.deepcopy(plan))
    def hold_plan(self,event_id,reason,observation):
        self.active['plans'][-1].update(phase='held',error=reason)


class PaidAgencyRoutingTests(unittest.TestCase):
    def setUp(self):
        self.world=World()
        self.observation={'session':self.world.session,'checkpoint':7,'residents':[
            {'id':101,'x':0,'y':0,'z':0},{'id':202,'x':1,'y':1,'z':0}]}

    def begin_release(self):
        with patch('agency.current_work_terms'):
            self.world._agency_observe(self.observation)
        self.assertEqual(self.world.agency_plan()['phase'],'paid_work_releasing')

    def test_exact_meeting_release_precedes_delegation(self):
        self.begin_release()
        command=self.world.agency_command(self.world.session)
        self.assertEqual(command['kind'],'release_routine')
        self.assertEqual(command['participants'],[101,202])
        self.assertEqual(self.world.delegated,[])
        self.observation['ack']={'id':command['id'],'status':'applied','released':True}
        self.world._agency_observe(self.observation)
        self.assertEqual(self.world.agency_plan()['phase'],'ready_to_paid_work')
        self.assertFalse(self.world.agency_plan()['release_required'])
        self.world._agency_observe(self.observation)
        self.assertEqual(len(self.world.delegated),1)
        self.assertEqual(self.world.delegated[0]['paid_work_release'],self.observation['ack'])

    def test_applied_without_release_does_not_start_work(self):
        self.begin_release()
        self.observation['ack']={'id':'release-job-meeting','status':'applied'}
        self.world._agency_observe(self.observation)
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertTrue(self.world.agency_plan()['release_required'])
        self.assertEqual(self.world.delegated,[])

    def test_another_release_cannot_finish_the_meeting(self):
        self.begin_release()
        self.observation['ack']={'id':'another-meeting','status':'applied','released':True}
        self.world._agency_observe(self.observation)
        self.assertEqual(self.world.agency_plan()['phase'],'paid_work_releasing')
        self.assertEqual(self.world.delegated,[])

    def test_departed_participants_cannot_start_work(self):
        self.observation['residents'][1]['x']=5000
        self.world._agency_observe(self.observation)
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(self.world.delegated,[])


if __name__=='__main__':unittest.main()
