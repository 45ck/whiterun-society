import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import run_daily_life as director
from tools import run_resident_event as worker


def activity_state(phase='running'):
    job={'id':'rest-job','source_plan':'need-1','actor':7,'target':50,'slot':0,'session':'a','epoch':'epoch',
         'phase':phase,'rest_minutes':30,'receipt_acknowledged':False,'release_verified':False}
    return {'bridge':{'session':'a','last_seen':1000,'command':None,'observation':{'residents':[{'id':7,'isPerson':True},{'id':8,'isPerson':True}]}},
            'society':{'error':None,'transition':None,'conversation':None,
                       'plan':{'id':'need-1','actor':7,'phase':'delegated','activity_job':'rest-job','decisions':[{}]},
                       'activity_jobs':{'epoch':'epoch','capacity':2,'jobs':[job],'history':[]},
                       'town':{'residents':{'7':{},'8':{}},'daily':{'queue':[]}}}}


class ActivityWorkerDirectorTests(unittest.TestCase):
    def test_prepared_is_not_native_admission_and_running_is_not_completion(self):
        state=activity_state('prepared')
        self.assertIsNone(worker.delegated_activity_admission(state,'need-1',7,'a'))
        state['society']['activity_jobs']['jobs'][0]['phase']='running'
        result=worker.delegated_activity_admission(state,'need-1',7,'a')
        self.assertTrue(result['admission_verified']);self.assertFalse(result['completion_confirmed'])
        state['society']['transition']={'checkpoint':2}
        self.assertIsNone(worker.delegated_activity_admission(state,'need-1',7,'a'))

    def test_fast_acknowledged_completion_is_found_in_history_and_requires_receipt(self):
        state=activity_state('complete');status=state['society']['activity_jobs'];job=status['jobs'].pop()
        status['history']=[job];state['society']['plan'].update(phase='complete',remembered=True)
        with self.assertRaises(ValueError):worker.delegated_activity_admission(state,'need-1',7,'a')
        job.update(receipt_acknowledged=True,release_verified=True,receipt_hash='verified')
        self.assertTrue(worker.delegated_activity_admission(state,'need-1',7,'a')['completion_confirmed'])

    def test_wrong_actor_source_plan_or_session_is_not_admission(self):
        for key,value in (('actor',9),('source_plan','other'),('session','b'),('id','other')):
            state=activity_state();state['society']['activity_jobs']['jobs'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):worker.delegated_activity_admission(state,'need-1',7,'a')

    def run_worker(self,corrupt=False):
        clock=[0.0];routes=[];reads=[0]
        state=activity_state('prepared')
        def request(route,data=None):
            routes.append(route)
            if route=='/agency/event':return {'plan':state['society']['plan']}
            if route!='/state':raise AssertionError('Unexpected action '+route)
            reads[0]+=1
            result=copy.deepcopy(state)
            if reads[0]==2:result['society']['transition']={'checkpoint':2}
            if reads[0]>=4:result['society']['activity_jobs']['jobs'][0]['phase']='running'
            if corrupt:result['society']['activity_jobs']['jobs'][0]['actor']=9
            return result
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'bridge-config.json').write_text(json.dumps({'port':1,'token':'placeholder'}))
            (root/'model-config.json').write_text(json.dumps({'model':'fixture','key_env':'TEST_ACTIVITY_KEY'}))
            argv=['worker','--runtime',folder,'--event-id','need-1','--actor','7','--kind','need_review']
            with patch.dict(os.environ,{'TEST_ACTIVITY_KEY':'placeholder'}),patch('sys.argv',argv),\
                 patch.object(worker,'CheckpointHTTP',return_value=request),patch.object(worker,'infer') as infer,\
                 patch.object(worker.time,'time',return_value=1000),patch.object(worker.time,'monotonic',side_effect=lambda:clock[0]),\
                 patch.object(worker.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)),patch('sys.stdout',new_callable=io.StringIO):
                if corrupt:
                    with self.assertRaises(ValueError):worker.main()
                else:worker.main()
                infer.assert_not_called()
            receipt=json.loads((root/('resident-event-'+hashlib.sha256(b'need-1').hexdigest()[:12]+'.json')).read_text())
        return receipt,routes,clock[0],reads[0]

    def test_worker_returns_after_committed_admission_without_waiting_for_rest(self):
        receipt,routes,elapsed,reads=self.run_worker()
        self.assertEqual(receipt['status'],'delegated');self.assertEqual(receipt['outcome'],'independent_activity_admitted')
        self.assertFalse(receipt['completion_confirmed']);self.assertEqual(receipt['activity_job_id'],'rest-job')
        self.assertLess(elapsed,1);self.assertGreaterEqual(reads,4);self.assertNotIn('/agency/hold',routes)

    def test_worker_cannot_cancel_independent_job_on_observation_failure(self):
        receipt,routes,_,_=self.run_worker(corrupt=True)
        self.assertEqual(receipt['status'],'held');self.assertTrue(receipt['independent_job_owns_cleanup'])
        self.assertNotIn('/agency/hold',routes)

    def run_director(self,complete_during_other_event=False):
        state=activity_state();state['society']['plan']=None
        state['society']['activity_jobs']['jobs']=[];clock=[0.0];calls=[]
        events=[{'id':name,'actor':actor,'kind':'need_review','status':'pending','priority':priority}
                for name,actor,priority in [('need-1',7,1),('do-not-reuse-actor',7,.9),('need-2',8,.8)]]
        state['society']['town']['daily']['queue']=events
        def request(route,data=None):
            if route=='/state':return copy.deepcopy(state)
            if route=='/town/review':return {'duplicate':True}
            raise AssertionError(route)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';runtime.mkdir()
            (runtime/'bridge-config.json').write_text(json.dumps({'port':1,'token':'placeholder'}))
            def launch(command,**kwargs):
                event_id=command[command.index('--event-id')+1];calls.append(event_id)
                if event_id=='need-1':
                    admitted=activity_state();state['society']['plan']=admitted['society']['plan']
                    state['society']['activity_jobs']=admitted['society']['activity_jobs'];events[0]['status']='started'
                    (runtime/('resident-event-'+hashlib.sha256(event_id.encode()).hexdigest()[:12]+'.json')).write_text(json.dumps(
                        {'event_id':event_id,'status':'delegated','model_calls':1,'activity_job_id':'rest-job','admission_verified':True,
                         'before':{'bridge':{'session':'a'}}}))
                else:
                    self.assertEqual(event_id,'need-2')
                    self.assertTrue(state['society']['activity_jobs']['jobs'])
                    state['society']['plan']={'id':event_id,'actor':8,'phase':'complete','outcome':'deferred','decisions':[{}]}
                    if complete_during_other_event:
                        job=state['society']['activity_jobs']['jobs'].pop()
                        job.update(phase='complete',release_verified=True,receipt_acknowledged=True,receipt_hash='verified',outcome='rested_at_bench')
                        state['society']['activity_jobs']['history'].append(job)
                return subprocess.CompletedProcess(command,0)
            output=root/'receipt.json';argv=['director','--root',folder,'--max-events','2','--watch-seconds','30',
                                           '--model-config','unused.json','--receipt',str(output)]
            with patch('sys.argv',argv),patch.object(director,'CheckpointHTTP',return_value=request),\
                 patch.object(director.subprocess,'run',side_effect=launch),patch.object(director.time,'time',return_value=1000),\
                 patch.object(director.time,'monotonic',side_effect=lambda:clock[0]),\
                 patch.object(director.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)),patch('sys.stdout',new_callable=io.StringIO):
                director.main()
            receipt=json.loads(output.read_text())
        return receipt,calls

    def test_director_continues_other_actor_but_never_reuses_accepted_rest_actor(self):
        receipt,calls=self.run_director()
        self.assertEqual(calls,['need-1','need-2'])
        self.assertEqual([e['status'] for e in receipt['events']],['delegated','complete'])
        self.assertEqual(receipt['event_counts']['independent_activity_admissions'],1)
        self.assertEqual(receipt['event_counts']['confirmed_completions'],1)
        self.assertEqual(receipt['event_counts']['admitted_activities_without_confirmed_completion'],1)

    def test_later_verified_activity_completion_updates_separate_completion_count(self):
        receipt,calls=self.run_director(complete_during_other_event=True)
        self.assertEqual(calls,['need-1','need-2'])
        self.assertEqual(receipt['event_counts']['confirmed_completions'],2)
        self.assertEqual(receipt['event_counts']['admitted_activities_without_confirmed_completion'],0)
        self.assertEqual(receipt['events'][0]['status'],'delegated')
        self.assertTrue(receipt['events'][0]['completion_confirmed'])


if __name__=='__main__':unittest.main()
