import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from tools.run_resident_goals import main,settlement_deadline,wait_settled


class GoalResultSettlementTests(unittest.TestCase):
    def wait_with_snapshots(self,states,wave,phase):
        clock=[0.0];reads=[]
        def request(route):
            self.assertEqual(route,'/state');reads.append(route)
            return states.pop(0)
        with patch('tools.run_resident_goals.time.monotonic',side_effect=lambda:clock[0]),\
             patch('tools.run_resident_goals.time.time',return_value=1000),\
             patch('tools.run_resident_goals.time.sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)):
            result=wait_settled(request,'a',wave=wave,expected_phase=phase,require_idle=False)
        return result,reads

    def snapshot(self,waves,transition=None,session='a'):
        return {'bridge':{'session':session,'last_seen':1000,'command':None},
                'society':{'error':None,'transition':transition,'unsettled_effect':None,'town':{'goal_waves':waves}}}

    def test_claim_binding_waits_for_new_wave_without_rejecting_previous_snapshot(self):
        wave={'id':'new','claim_id':'new-claim','session':'a','phase':'thinking'}
        old={'id':'old','claim_id':'old-claim','session':'a','phase':'complete'}
        states=[self.snapshot([old],{'checkpoint':2}),self.snapshot([old],{'checkpoint':2}),self.snapshot([wave])]
        result,reads=self.wait_with_snapshots(states,wave,'thinking')
        self.assertEqual(len(reads),3);self.assertEqual(result['society']['town']['goal_waves'],[wave])

    def test_result_binding_can_expose_previous_thinking_wave_until_commit(self):
        wave={'id':'new','claim_id':'new-claim','session':'a','phase':'thinking'}
        complete={**wave,'phase':'complete'}
        states=[self.snapshot([wave],{'checkpoint':3}),self.snapshot([complete])]
        result,reads=self.wait_with_snapshots(states,wave,'complete')
        self.assertEqual(len(reads),2);self.assertEqual(result['society']['town']['goal_waves'],[complete])

    def test_true_wrong_claim_after_commit_still_fails(self):
        wave={'id':'new','claim_id':'new-claim','session':'a','phase':'thinking'}
        wrong={**wave,'claim_id':'other-claim'}
        with self.assertRaisesRegex(ValueError,'claim changed'):
            self.wait_with_snapshots([self.snapshot([],{'checkpoint':2}),self.snapshot([wrong])],wave,'thinking')

    def test_session_change_still_fails_during_checkpoint_binding(self):
        wave={'id':'new','claim_id':'new-claim','session':'a','phase':'thinking'}
        with self.assertRaisesRegex(ValueError,'Session changed'):
            self.wait_with_snapshots([self.snapshot([],{'checkpoint':2},session='b')],wave,'thinking')

    def exercise(self,expiry=1800,change_session_at=None,post_error=None,busy_until=110):
        clock=[0.0];posts=[];paid=[];clients=[];wave={'id':'wave','claim_id':'claim','session':'a','phase':'thinking',
            'deadline_at':1000+expiry,'members':[{'actor':7,'context':{'options':[{'id':'quiet','effect':'Quiet'}]}}]}
        class Client:
            def __init__(self,*args):self.checkpoint_wait=40;self.timeout=30;clients.append(self)
            def __call__(self,route,data=None):
                if route=='/goals/claim':return {'wave':copy.deepcopy(wave)}
                if route=='/goals/result':
                    posts.append(copy.deepcopy(data))
                    if post_error:raise post_error
                    wave['phase']='complete';return {'checkpoint':4}
                if route!='/state':raise AssertionError(route)
                session='b' if change_session_at is not None and clock[0]>=change_session_at else 'a'
                # A new unrelated native effect after submission must not delay
                # observation of the already-accepted goal result.
                busy=bool(paid) and (clock[0]<busy_until or wave['phase']=='complete')
                return {'bridge':{'session':session,'last_seen':1000+clock[0],'command':None},
                        'society':{'error':None,'transition':None,'unsettled_effect':{'kind':'rest'} if busy else None,
                                   'town':{'goal_waves':[copy.deepcopy(wave)]}}}
        def infer(*args,**kwargs):
            clock[0]+=1;paid.append(7)
            return {'model':'fixture','decision':{'action_id':'quiet','reason':'Wait','emotion':'calm'},'usage':{'cost':.001}}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';runtime.mkdir()
            (runtime/'bridge-config.json').write_text(json.dumps({'port':1,'token':'placeholder'}))
            model=root/'model.json';model.write_text(json.dumps({'model':'fixture','key_env':'TEST_GOAL_KEY'}))
            caught=None
            with patch.dict(os.environ,{'TEST_GOAL_KEY':'placeholder'}),\
                 patch('sys.argv',['worker','--root',folder,'--id','wave','--model-config',str(model)]),\
                 patch('tools.run_resident_goals.CheckpointHTTP',Client),\
                 patch('tools.run_resident_goals.infer',side_effect=infer) as call,\
                 patch('tools.run_resident_goals.time.monotonic',side_effect=lambda:clock[0]),\
                 patch('tools.run_resident_goals.time.time',side_effect=lambda:1000+clock[0]),\
                 patch('tools.run_resident_goals.time.sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)),patch('builtins.print'):
                try:main()
                except Exception as error:caught=error
            receipt=json.loads((runtime/('resident-goals-'+hashlib.sha256(b'wave').hexdigest()[:12]+'.json')).read_text())
        return receipt,posts,call.call_count,clock[0],caught,clients[0]

    def test_paid_result_survives_109_second_rest_and_is_submitted_once(self):
        receipt,posts,calls,elapsed,error,client=self.exercise()
        self.assertIsNone(error);self.assertEqual(receipt['status'],'complete')
        self.assertEqual(calls,1);self.assertEqual(len(posts),1)
        self.assertEqual(posts[0]['results'],receipt['results'])
        self.assertGreaterEqual(elapsed,110);self.assertLess(elapsed,111)
        self.assertTrue(receipt['result_submitted']);self.assertEqual(receipt['model_calls'],1)
        self.assertLessEqual(client.checkpoint_wait,600)

    def test_saved_claim_expiry_bounds_wait_and_keeps_paid_result_without_submission(self):
        receipt,posts,calls,elapsed,error,_=self.exercise(expiry=50)
        self.assertIsInstance(error,TimeoutError);self.assertEqual(posts,[]);self.assertEqual(calls,1)
        self.assertLessEqual(elapsed,50);self.assertEqual(receipt['failure_stage'],'paid_result_settlement')
        self.assertEqual(receipt['failure_type'],'TimeoutError');self.assertEqual(receipt['failure']['results_preserved'],1)

    def test_settlement_allowance_is_finite_even_when_claim_lives_longer(self):
        receipt,posts,calls,elapsed,error,_=self.exercise(busy_until=1000)
        self.assertIsInstance(error,TimeoutError);self.assertEqual(posts,[]);self.assertEqual(calls,1)
        self.assertLessEqual(elapsed,601);self.assertEqual(receipt['settlement_wait_budget_seconds'],600)

    def test_session_change_does_not_reinfer_or_submit_stored_result(self):
        receipt,posts,calls,_,error,_=self.exercise(change_session_at=50)
        self.assertIsInstance(error,ValueError);self.assertEqual(posts,[]);self.assertEqual(calls,1)
        self.assertEqual(receipt['status'],'held');self.assertEqual(receipt['failure_stage'],'paid_result_settlement')

    def test_uncertain_or_rejected_submission_retains_stage_and_never_retries(self):
        for error in (TimeoutError('private transport text'),urllib.error.HTTPError('url',400,'private text',{},io.BytesIO(b'private'))):
            with self.subTest(error=type(error).__name__):
                receipt,posts,calls,_,caught,_=self.exercise(post_error=error)
                self.assertIs(caught,error);self.assertEqual(len(posts),1);self.assertEqual(calls,1)
                self.assertEqual(receipt['failure_stage'],'result_submission')
                self.assertEqual(receipt['failure']['results_preserved'],1)
                self.assertNotIn('private',json.dumps(receipt))

    def test_preclaim_wait_remains_40_seconds(self):
        clock=[0.0]
        state={'bridge':{'session':'a','last_seen':1000,'command':{'kind':'rest'}},
               'society':{'error':None,'transition':None,'unsettled_effect':None}}
        with patch('tools.run_resident_goals.time.monotonic',side_effect=lambda:clock[0]),\
             patch('tools.run_resident_goals.time.time',return_value=1000),\
             patch('tools.run_resident_goals.time.sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)):
            with self.assertRaises(TimeoutError):wait_settled(lambda _:state)
        self.assertEqual(clock[0],40)


if __name__=='__main__':unittest.main()
