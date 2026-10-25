import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import run_daily_life as director


class DirectorDeadlineTests(unittest.TestCase):
    def exercise(self,seconds,flags=(),expire_at=None):
        clock=[0.0];routes=[];launches=[];goal_launches=[];drains=[]
        events=[{'id':'need-'+str(i),'actor':i,'kind':'need_review','status':'pending','priority':1,'created_day':0} for i in (1,2)]
        state={'bridge':{'session':'test-session','last_seen':1000,'command':None,
                         'observation':{'gameDays':1,'residents':[{'id':i,'isPerson':True} for i in (1,2)]}},
               'society':{'error':None,'transition':None,'plan':None,'conversation':None,'scene_handoffs':[],
                          'town':{'residents':{},'daily':{'queue':events}}}}
        def client(route,data=None):
            routes.append(route)
            if route=='/state':return copy.deepcopy(state)
            if route=='/town/review':
                if expire_at=='review':clock[0]=2
                return {'reviewed':True}
            if route=='/town/scene-handoff':
                state['society']['scene_handoffs'].append({'id':data['id'],'status':'complete'})
                if expire_at=='scene':clock[0]=2
                return {'accepted':True}
            raise AssertionError('Unexpected route '+route)
        def worker(command,**kwargs):
            launches.append(command)
            event_id=command[command.index('--event-id')+1]
            state['society']['plan']={'id':event_id,'phase':'complete','outcome':'deferred','decisions':[]}
            next(e for e in events if e['id']==event_id)['status']='complete'
            if expire_at=='worker':clock[0]=2
            return subprocess.CompletedProcess(command,0)
        def available(*args):
            if expire_at=='availability':clock[0]=2
            return True
        class Goals:
            def __init__(self,*args,**kwargs):pass
            def tick(self,snapshot,allow_launch=True):
                if allow_launch:goal_launches.append(clock[0])
            def drain(self):drains.append(clock[0])
            def run_foreground(self,command,*args):return worker(command)
        def select(*args):
            if expire_at=='cohort_selection':clock[0]=2
            return events
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'runtime').mkdir()
            (root/'runtime/bridge-config.json').write_text(json.dumps({'port':1,'token':'offline-placeholder'}))
            receipt=root/'receipt.json'
            argv=['director','--root',str(root),'--max-events','2','--watch-seconds',str(seconds),
                  '--model-config',str(root/'unused.json'),'--receipt',str(receipt),*flags]
            with patch.object(director.sys,'argv',argv),patch.object(director,'CheckpointHTTP',return_value=client),\
                 patch.object(director.time,'time',return_value=1000),patch.object(director.time,'monotonic',side_effect=lambda:clock[0]),\
                 patch.object(director.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)),\
                 patch.object(director.subprocess,'run',side_effect=worker),patch.object(director,'GoalScheduler',Goals),\
                 patch.object(director,'event_available',side_effect=available),\
                 patch.object(director,'scene_candidates',return_value=[{'id':1,'activity':{'scene_id':99}}]),\
                 patch.object(director,'routine_dispatch_prefix',return_value=events),\
                 patch.object(director,'select_routine_events',side_effect=select),patch('sys.stdout',new_callable=io.StringIO):
                director.main()
            evidence=json.loads(receipt.read_text())
        return evidence,routes,launches,goal_launches,drains

    def test_zero_window_reviews_only_with_every_launch_option_enabled(self):
        evidence,routes,workers,goals,drains=self.exercise(0,('--resident-goals','--scene-handoffs','--parallel-journeys',
                                                               '--social-opportunities','--language-config','unused.json'))
        self.assertIn('/town/review',routes)
        self.assertNotIn('/town/scene-handoff',routes)
        self.assertEqual(workers,[]);self.assertEqual(goals,[])
        self.assertEqual(evidence['events'],[]);self.assertTrue(drains)

    def test_expiry_during_review_does_not_launch_cached_foreground_work(self):
        evidence,routes,workers,_,_=self.exercise(1,expire_at='review')
        self.assertEqual(workers,[]);self.assertEqual(evidence['events'],[])
        self.assertEqual(evidence['status'],'complete')

    def test_started_foreground_completes_then_no_second_worker_and_goals_drain(self):
        evidence,_,workers,goals,drains=self.exercise(1,('--resident-goals',),expire_at='worker')
        self.assertEqual(len(workers),1)
        self.assertEqual(len(evidence['events']),1)
        self.assertEqual(evidence['events'][0]['status'],'complete')
        self.assertEqual(goals,[0])
        self.assertIn(2,drains)

    def test_expiry_after_cohort_selection_rechecks_before_launch(self):
        evidence,_,workers,_,_=self.exercise(1,('--parallel-journeys',),expire_at='cohort_selection')
        self.assertEqual(workers,[]);self.assertEqual(evidence['events'],[])

    def test_started_scene_settles_after_deadline_without_starting_goals_or_events(self):
        evidence,routes,workers,goals,drains=self.exercise(1,('--scene-handoffs','--resident-goals'),expire_at='scene')
        self.assertEqual(routes.count('/town/scene-handoff'),1)
        self.assertEqual(len(evidence['scene_handoffs']),1)
        self.assertEqual(workers,[]);self.assertEqual(goals,[]);self.assertTrue(drains)

    def test_last_moment_expiry_removes_unlaunched_started_receipt(self):
        evidence,_,workers,_,_=self.exercise(1,expire_at='availability')
        self.assertEqual(workers,[]);self.assertEqual(evidence['events'],[])


if __name__=='__main__':unittest.main()
