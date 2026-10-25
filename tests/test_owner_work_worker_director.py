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
from tools import run_resident_event as worker
from tools import run_daily_life as director
from legacy_fixture import author_fixture_identities


def work_state(phase='running'):
    job={'id':'owner-job','source_plan':'need-1','actor':7,'custodian':7,'slot':0,'session':'a','epoch':'epoch',
         'business_id':'bakery','business_revision':1,'phase':phase,'work_minutes':10,
         'receipt_acknowledged':False,'release_verified':False,
         'settlement':{'phase':'not_prepared','committed_inventory_verified':False}}
    state={'bridge':{'session':'a','last_seen':1000,'command':None,'observation':{
                'ready':True,'session':'a','checkpoint':0,
                'residents':[{'id':7,'baseId':1007,'isPerson':True},{'id':8,'baseId':1008,'isPerson':True}]}},
            'society':{'error':None,'transition':None,'conversation':None,
                'people':{'7':{},'8':{}},
                'plan':{'id':'need-1','actor':7,'phase':'delegated','work_job':'owner-job','decisions':[{}]},
                'owner_work_jobs':{'epoch':'epoch','capacity':4,'jobs':[job],'history':[]},
                'town':{'residents':{'7':{'id':7},'8':{'id':8}},'daily':{'queue':[]}}}}
    author_fixture_identities(state['society'],state['bridge']['observation'])
    return state


def completed(job):
    job.update(phase='complete',release_verified=True,receipt_hash='terminal-hash',receipt_acknowledged=True,
        outcome='owner_work_completed',settlement={'phase':'committed','commit_id':'recipe-1',
        'production_record_id':'recipe-1','committed_inventory_verified':True})


class OwnerWorkAdmissionTests(unittest.TestCase):
    def test_prepared_waits_and_running_admission_does_not_claim_output_or_attendance(self):
        state=work_state('prepared')
        self.assertIsNone(worker.delegated_activity_admission(state,'need-1',7,'a'))
        state['society']['owner_work_jobs']['jobs'][0]['phase']='running'
        result=worker.delegated_activity_admission(state,'need-1',7,'a')
        self.assertEqual(result,{'activity_job_id':'owner-job','work_job_id':'owner-job','activity_phase':'running',
            'activity_kind':'owner_production','admission_verified':True,'completion_confirmed':False})
        state['society']['transition']={'next':2}
        self.assertIsNone(worker.delegated_activity_admission(state,'need-1',7,'a'))

    def test_missed_running_observation_accepts_valid_later_progress_without_completion(self):
        for phase in ('attendance_verified','recipe_prepared','recipe_committed'):
            with self.subTest(phase=phase):
                state=work_state(phase);job=state['society']['owner_work_jobs']['jobs'][0]
                with self.assertRaises(ValueError):worker.delegated_activity_admission(state,'need-1',7,'a')
                job['attendance_receipt_hash']='verified-attendance'
                if phase=='recipe_committed':job['settlement'].update(phase='committed',committed_inventory_verified=True)
                result=worker.delegated_activity_admission(state,'need-1',7,'a')
                self.assertTrue(result['admission_verified']);self.assertFalse(result['completion_confirmed'])

    def test_fast_completion_in_history_requires_release_and_matching_ledger_commit(self):
        state=work_state();status=state['society']['owner_work_jobs'];job=status['jobs'].pop();completed(job)
        status['history']=[job];state['society']['plan'].update(phase='complete',remembered=True)
        self.assertTrue(worker.delegated_activity_admission(state,'need-1',7,'a')['completion_confirmed'])
        for field,value in [('committed_inventory_verified',False),('production_record_id','wrong'),('commit_id',''),('phase','prepared')]:
            broken=copy.deepcopy(state);broken['society']['owner_work_jobs']['history'][0]['settlement'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                worker.delegated_activity_admission(broken,'need-1',7,'a')

    def test_wrong_identity_or_held_or_ambiguous_protocol_is_not_admission(self):
        for key,value in [('actor',8),('source_plan','other'),('session','old'),('id','wrong'),('orphan',True),('phase','held')]:
            state=work_state();state['society']['owner_work_jobs']['jobs'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):worker.delegated_activity_admission(state,'need-1',7,'a')
        state=work_state();state['society']['plan']['activity_job']='rest-job'
        with self.assertRaises(ValueError):worker.delegated_activity_admission(state,'need-1',7,'a')

    def test_rest_receipt_with_same_id_cannot_complete_owner_job(self):
        state=work_state('held');rest=copy.deepcopy(state['society']['owner_work_jobs']['jobs'][0]);completed(rest)
        state['society']['activity_jobs']={'jobs':[],'history':[rest]}
        with self.assertRaises(ValueError):worker.delegated_activity_admission(state,'need-1',7,'a')


class OwnerWorkWorkerDirectorTests(unittest.TestCase):
    def run_worker(self,corrupt=False,fast=False):
        state=work_state('prepared');clock=[0.];reads=[0];routes=[]
        def request(route,data=None):
            routes.append(route)
            if route=='/agency/event':return {'plan':state['society']['plan']}
            if route!='/state':raise AssertionError(route)
            reads[0]+=1;result=copy.deepcopy(state)
            if reads[0]==2:result['society']['transition']={'next':2}
            if reads[0]>=4:
                status=result['society']['owner_work_jobs'];job=status['jobs'][0];job['phase']='running'
                if fast:
                    completed(job);status['history']=[status['jobs'].pop()]
                    result['society']['plan'].update(phase='complete',remembered=True,outcome='owner_work_completed')
            if corrupt:result['society']['owner_work_jobs']['jobs'][0]['actor']=9
            return result
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'bridge-config.json').write_text(json.dumps({'port':1,'token':'placeholder'}))
            (root/'model-config.json').write_text(json.dumps({'model':'fixture','key_env':'TEST_OWNER_WORK_KEY'}))
            argv=['worker','--runtime',folder,'--event-id','need-1','--actor','7','--kind','need_review']
            with patch.dict(os.environ,{'TEST_OWNER_WORK_KEY':'placeholder'}),patch('sys.argv',argv),\
                 patch.object(worker,'CheckpointHTTP',return_value=request),patch.object(worker,'infer') as infer,\
                 patch.object(worker.time,'time',return_value=1000),patch.object(worker.time,'monotonic',side_effect=lambda:clock[0]),\
                 patch.object(worker.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)),patch('sys.stdout',new_callable=io.StringIO):
                if corrupt:
                    with self.assertRaises(ValueError):worker.main()
                else:worker.main()
                infer.assert_not_called()
            receipt=json.loads((root/('resident-event-'+hashlib.sha256(b'need-1').hexdigest()[:12]+'.json')).read_text())
        return receipt,routes,clock[0]

    def test_worker_exits_after_owner_admission_without_waiting_or_spending_model_calls(self):
        receipt,routes,elapsed=self.run_worker()
        self.assertEqual(receipt['status'],'delegated');self.assertEqual(receipt['work_job_id'],'owner-job')
        self.assertFalse(receipt['completion_confirmed']);self.assertEqual(receipt['model_calls'],0)
        self.assertLess(elapsed,1);self.assertNotIn('/agency/hold',routes)

    def test_worker_observation_failure_does_not_cancel_independent_owner_cleanup(self):
        receipt,routes,_=self.run_worker(corrupt=True)
        self.assertTrue(receipt['independent_job_owns_cleanup']);self.assertNotIn('/agency/hold',routes)

    def test_worker_fast_completion_uses_owner_history_and_verified_settlement(self):
        receipt,_,_=self.run_worker(fast=True)
        self.assertEqual(receipt['status'],'complete');self.assertTrue(receipt['completion_confirmed'])
        self.assertEqual(receipt['activity_kind'],'owner_production')

    def run_director(self,finish=False,overclaim=False):
        state=work_state();state['society']['plan']=None;state['society']['owner_work_jobs']['jobs']=[]
        clock=[0.];calls=[]
        events=[{'id':id,'actor':actor,'kind':'need_review','status':'pending','priority':priority}
                for id,actor,priority in [('need-1',7,1),('same-owner',7,.9),('need-2',8,.8)]]
        state['society']['town']['daily']['queue']=events
        def request(route,data=None):
            if route=='/state':return copy.deepcopy(state)
            if route=='/town/review':return {'duplicate':True}
            raise AssertionError(route)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';runtime.mkdir()
            (runtime/'bridge-config.json').write_text(json.dumps({'port':1,'token':'placeholder'}))
            def launch(command,**kwargs):
                event=command[command.index('--event-id')+1];calls.append(event)
                if event=='need-1':
                    admitted=work_state();state['society']['plan']=admitted['society']['plan']
                    state['society']['owner_work_jobs']=admitted['society']['owner_work_jobs'];events[0]['status']='started'
                    admission=worker.delegated_activity_admission(state,event,7,'a')
                    (runtime/('resident-event-'+hashlib.sha256(event.encode()).hexdigest()[:12]+'.json')).write_text(json.dumps(
                        {'event_id':event,'status':'complete' if overclaim else 'delegated','model_calls':1,**admission,'before':{'bridge':{'session':'a'}}}))
                else:
                    self.assertEqual(event,'need-2');self.assertTrue(state['society']['owner_work_jobs']['jobs'])
                    state['society']['plan']={'id':event,'actor':8,'phase':'complete','outcome':'deferred','decisions':[{}]}
                    if finish:
                        status=state['society']['owner_work_jobs'];job=status['jobs'].pop();completed(job);status['history'].append(job)
                return subprocess.CompletedProcess(command,0)
            output=root/'receipt.json';argv=['director','--root',folder,'--max-events','2','--watch-seconds','30',
                                           '--model-config','unused.json','--receipt',str(output)]
            with patch('sys.argv',argv),patch.object(director,'CheckpointHTTP',return_value=request),\
                 patch.object(director.subprocess,'run',side_effect=launch),patch.object(director.time,'time',return_value=1000),\
                 patch.object(director.time,'monotonic',side_effect=lambda:clock[0]),\
                 patch.object(director.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)),patch('sys.stdout',new_callable=io.StringIO):director.main()
            receipt=json.loads(output.read_text())
        return receipt,calls

    def test_director_runs_disjoint_actor_without_reusing_working_owner(self):
        receipt,calls=self.run_director()
        self.assertEqual(calls,['need-1','need-2']);self.assertEqual(receipt['events'][0]['activity_kind'],'owner_production')
        self.assertEqual(receipt['event_counts']['confirmed_completions'],1)
        self.assertEqual(receipt['event_counts']['admitted_activities_without_confirmed_completion'],1)

    def test_later_source_job_completion_is_tracked_while_another_plan_is_current(self):
        receipt,calls=self.run_director(finish=True)
        self.assertEqual(calls,['need-1','need-2']);self.assertEqual(receipt['events'][0]['status'],'delegated')
        self.assertTrue(receipt['events'][0]['completion_confirmed'])
        self.assertEqual(receipt['events'][0]['activity_outcome'],'owner_work_completed')
        self.assertEqual(receipt['event_counts']['confirmed_completions'],2)

    def test_worker_complete_label_cannot_upgrade_running_admission_to_output(self):
        with self.assertRaisesRegex(ValueError,'admission was not verified'):self.run_director(overclaim=True)

    def test_later_unmatched_or_attendance_only_receipt_cannot_count_completion(self):
        state=work_state('attendance_verified');job=state['society']['owner_work_jobs']['jobs'][0]
        event={'id':'need-1','actor':7,'status':'delegated','work_job_id':'owner-job','activity_job_id':'owner-job',
               'activity_kind':'owner_production','admission_verified':True,'completion_confirmed':False}
        evidence={'events':[event]};director.observe_delegated_completions(evidence,state)
        self.assertFalse(event['completion_confirmed'])
        completed(job);job['source_plan']='other';director.observe_delegated_completions(evidence,state)
        self.assertFalse(event['completion_confirmed'])
