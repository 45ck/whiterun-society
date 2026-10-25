"""Worker orchestration tests; authored service projections, no provider/native calls."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
from legacy_fixture import author_fixture_identities
import unittest
from unittest.mock import patch
from tools import run_resident_event as worker
from tools import run_daily_life as director
import test_owner_work_worker_director as owner_fixture


def paid_state(phase='working'):
    state=owner_fixture.work_state()
    terms={'worker':7,'worker_base_id':1007,'employer':8,'employer_base_id':1008,
           'business_id':'forge','revision':1,'recipe_id':'metal_recipe','catalog_hash':'catalog',
           'recipe_hash':'recipe','terms_hash':'terms'}
    job={'id':'paid-job','job_id':'paid-job','protocol':2,'source_plan':'need-1',**terms,
         'business_revision':1,'consent_hash':'consent','session':'a','epoch':'paid-epoch','phase':phase,
         'accepted_at':1000,'release_verified':False,'receipt_acknowledged':False,'effect_unreconciled':False,
         'settlement':{'phase':'not_prepared','output_verified':False,'wage_debit_verified':False,
                       'wages_verified':False,'inventory_verified':False}}
    state['society']['owner_work_jobs']={'jobs':[],'history':[]}
    state['society']['plan']={'id':'need-1','actor':7,'target':8,'phase':'delegated',
                            'paid_work_job':'paid-job','work_terms':terms,'decisions':[{}]}
    state['society']['paid_employment']={'epoch':'paid-epoch','protocol':2,'jobs':[job],'history':[]}
    state['bridge']['observation']['paid_employment']={'available':True,'protocol':2,'epoch':'paid-epoch'}
    return state


def complete(job):
    job.update(phase='complete',release_verified=True,receipt_acknowledged=True,receipt_hash='terminal',
        effect_receipt_hash='effects',outcome='paid_employment_completed')
    job['settlement'].update(phase='committed',commit_id='commit-paid',production_record_id='commit-paid',
        output_verified=True,wage_debit_verified=True,wages_verified=True,inventory_verified=True)


class PaidWorkerDirectorTests(unittest.TestCase):
    def test_prepared_waits_working_admits_and_advanced_progress_does_not_complete(self):
        state=paid_state('prepared');self.assertIsNone(worker.delegated_activity_admission(state,'need-1',7,'a'))
        job=state['society']['paid_employment']['jobs'][0];job['phase']='working'
        proof=worker.delegated_activity_admission(state,'need-1',7,'a')
        self.assertEqual(proof['activity_kind'],'paid_employment');self.assertEqual(proof['paid_work_job_id'],'paid-job')
        self.assertTrue(proof['admission_verified']);self.assertFalse(proof['completion_confirmed'])
        for phase in ('attendance_verified','commit_prepared','effects_verified'):
            job['phase']=phase;job.pop('attendance_receipt_hash',None)
            with self.assertRaises(ValueError):worker.delegated_activity_admission(state,'need-1',7,'a')
            job['attendance_receipt_hash']='attendance'
            if phase=='effects_verified':job['settlement'].update(phase='committed',output_verified=True,
                wage_debit_verified=True,wages_verified=True,inventory_verified=True)
            self.assertFalse(worker.delegated_activity_admission(state,'need-1',7,'a')['completion_confirmed'])

    def test_wrong_protocol_party_base_epoch_and_unadmitted_status_reject(self):
        for field,value in [('worker',9),('worker_base_id',999),('employer',9),('employer_base_id',999),
            ('terms_hash','wrong'),('source_plan','other'),('protocol',1),('session','old'),('epoch','old'),
            ('phase','held'),('orphan',True),('accepted_at',None)]:
            state=paid_state();state['society']['paid_employment']['jobs'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):worker.delegated_activity_admission(state,'need-1',7,'a')
        state=paid_state();state['society']['plan']['work_job']='owner-job'
        with self.assertRaises(ValueError):worker.delegated_activity_admission(state,'need-1',7,'a')

    def test_fast_complete_requires_separate_output_both_wages_inventory_and_release(self):
        state=paid_state();status=state['society']['paid_employment'];job=status['jobs'].pop();complete(job)
        status['history']=[job];state['society']['plan'].update(phase='complete',remembered=True)
        self.assertTrue(worker.delegated_activity_admission(state,'need-1',7,'a')['completion_confirmed'])
        for field in ('output_verified','wage_debit_verified','wages_verified','inventory_verified'):
            changed=copy.deepcopy(state);changed['society']['paid_employment']['history'][0]['settlement'][field]=False
            with self.subTest(field=field),self.assertRaises(ValueError):worker.delegated_activity_admission(changed,'need-1',7,'a')
        for field,value in [('release_verified',False),('receipt_hash',None),('effect_receipt_hash',None),('effect_unreconciled',True)]:
            changed=copy.deepcopy(state);changed['society']['paid_employment']['history'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):worker.delegated_activity_admission(changed,'need-1',7,'a')

    def run_worker(self,corrupt=False):
        state=paid_state('prepared');clock=[0.];reads=[0];routes=[]
        def request(route,data=None):
            routes.append(route)
            if route=='/agency/event':return {'plan':state['society']['plan']}
            self.assertEqual(route,'/state');reads[0]+=1;result=copy.deepcopy(state)
            if reads[0]==2:result['society']['transition']={'next':2}
            if reads[0]>=4:result['society']['paid_employment']['jobs'][0]['phase']='working'
            if corrupt:result['society']['paid_employment']['jobs'][0]['employer_base_id']=999
            return result
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'bridge-config.json').write_text(json.dumps({'port':1,'token':'placeholder'}))
            (root/'model-config.json').write_text(json.dumps({'model':'fixture','key_env':'TEST_PAID_KEY'}))
            argv=['worker','--runtime',folder,'--event-id','need-1','--actor','7','--kind','need_review']
            with patch.dict(os.environ,{'TEST_PAID_KEY':'placeholder'}),patch('sys.argv',argv),\
                patch.object(worker,'CheckpointHTTP',return_value=request),patch.object(worker,'infer') as infer,\
                patch.object(worker.time,'time',return_value=1000),patch.object(worker.time,'monotonic',side_effect=lambda:clock[0]),\
                patch.object(worker.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)),patch('sys.stdout',new_callable=io.StringIO):
                if corrupt:
                    with self.assertRaises(ValueError):worker.main()
                else:worker.main()
                infer.assert_not_called()
            receipt=json.loads((root/('resident-event-'+hashlib.sha256(b'need-1').hexdigest()[:12]+'.json')).read_text())
        return receipt,routes,clock[0]

    def test_actual_worker_stops_polling_at_admission_without_completion_or_inference(self):
        receipt,routes,elapsed=self.run_worker()
        self.assertEqual(receipt['status'],'delegated');self.assertEqual(receipt['paid_work_job_id'],'paid-job')
        self.assertEqual(receipt['model_calls'],0);self.assertFalse(receipt['completion_confirmed'])
        self.assertLess(elapsed,1);self.assertNotIn('/agency/hold',routes)

    def test_corrupt_observation_leaves_independent_cleanup_authority_intact(self):
        receipt,routes,_=self.run_worker(True)
        self.assertTrue(receipt['independent_job_owns_cleanup']);self.assertNotIn('/agency/hold',routes)

    def event(self,state):
        return {'id':'need-1','actor':7,'status':'delegated',**worker.delegated_activity_admission(state,'need-1',7,'a')}

    def test_director_reconciles_original_job_after_foreground_moves_and_separates_held(self):
        state=paid_state();event=self.event(state);evidence={'events':[event]}
        state['society']['plan']={'id':'another-person','actor':9,'phase':'choose'}
        job=state['society']['paid_employment']['jobs'][0];job.update(phase='held',outcome='paid_employment_held')
        director.observe_delegated_completions(evidence,state)
        self.assertFalse(event['completion_confirmed']);self.assertEqual(event['activity_outcome'],'paid_employment_held')
        complete(job);state['society']['paid_employment']['history']=[state['society']['paid_employment']['jobs'].pop()]
        director.observe_delegated_completions(evidence,state)
        self.assertTrue(event['completion_confirmed']);self.assertEqual(event['status'],'delegated')
        self.assertEqual(director.event_counts([event])['confirmed_completions'],1)

    def test_director_cannot_credit_changed_identity_or_another_source_job(self):
        for field,value in [('source_plan','wrong'),('employer_base_id',999),('terms_hash','wrong'),('consent_hash','wrong'),('epoch','old')]:
            state=paid_state();event=self.event(state);job=state['society']['paid_employment']['jobs'][0]
            complete(job);job[field]=value;director.observe_delegated_completions({'events':[event]},state)
            self.assertFalse(event['completion_confirmed'],field)

    def run_director(self,finish=False,overclaim=False):
        state=paid_state();state['society']['plan']=None;state['society']['paid_employment']['jobs']=[]
        state['society']['people']['9']={};state['society']['town']['residents']['9']={'id':9}
        state['bridge']['observation']['residents'].append({'id':9,'baseId':1009,'isPerson':True})
        author_fixture_identities(state['society'],state['bridge']['observation'])
        clock=[0.];calls=[]
        events=[{'id':key,'actor':actor,'kind':'need_review','status':'pending','priority':priority}
            for key,actor,priority in [('need-1',7,1),('same-worker',7,.9),('same-employer',8,.85),('need-9',9,.8)]]
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
                    admitted=paid_state();state['society']['plan']=admitted['society']['plan']
                    state['society']['paid_employment']=admitted['society']['paid_employment'];events[0]['status']='delegated'
                    admission=worker.delegated_activity_admission(state,event,7,'a')
                    (runtime/('resident-event-'+hashlib.sha256(event.encode()).hexdigest()[:12]+'.json')).write_text(json.dumps(
                        {'event_id':event,'status':'complete' if overclaim else 'delegated','model_calls':0,**admission,'before':{'bridge':{'session':'a'}}}))
                else:
                    self.assertEqual(event,'need-9','Neither paid party may be scheduled again')
                    state['society']['plan']={'id':event,'actor':9,'phase':'complete','outcome':'deferred','decisions':[]}
                    if finish:
                        status=state['society']['paid_employment'];job=status['jobs'].pop();complete(job);status['history'].append(job)
                return subprocess.CompletedProcess(command,0)
            output=root/'receipt.json';argv=['director','--root',folder,'--max-events','2','--watch-seconds','30',
                '--model-config','unused.json','--receipt',str(output)]
            with patch('sys.argv',argv),patch.object(director,'CheckpointHTTP',return_value=request),                patch.object(director.subprocess,'run',side_effect=launch),patch.object(director.time,'time',return_value=1000),                patch.object(director.time,'monotonic',side_effect=lambda:clock[0]),                patch.object(director.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)),patch('sys.stdout',new_callable=io.StringIO):
                director.main()
            receipt=json.loads(output.read_text())
        return receipt,calls

    def test_actual_director_continues_third_actor_without_reusing_worker_or_employer(self):
        receipt,calls=self.run_director()
        self.assertEqual(calls,['need-1','need-9'])
        self.assertEqual(receipt['events'][0]['activity_kind'],'paid_employment')
        self.assertFalse(receipt['events'][0]['completion_confirmed'])
        self.assertEqual(receipt['event_counts']['confirmed_completions'],1)
        self.assertEqual(receipt['event_counts']['admitted_activities_without_confirmed_completion'],1)

    def test_actual_director_tracks_completed_old_job_and_rejects_worker_overclaim(self):
        receipt,calls=self.run_director(finish=True)
        self.assertEqual(calls,['need-1','need-9'])
        self.assertTrue(receipt['events'][0]['completion_confirmed'])
        self.assertEqual(receipt['events'][0]['status'],'delegated')
        self.assertEqual(receipt['event_counts']['confirmed_completions'],2)
        with self.assertRaisesRegex(ValueError,'admission was not verified'):
            self.run_director(overclaim=True)
