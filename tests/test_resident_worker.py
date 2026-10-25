"""Faster polling must retain the persisted inference and session boundaries."""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from tools.run_resident_event import main


class ResidentWorkerTests(unittest.TestCase):
    def run_worker(self,mode='normal'):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder)
            (runtime/'bridge-config.json').write_text(json.dumps({'port':12345,'token':'test'}))
            model=runtime/'model.json';model.write_text(json.dumps({'key_env':'WORKER_TEST_KEY'}))
            plan={'id':'event','phase':'choose','claim':None,'decisions':[]}
            state={'bridge':{'session':'native','last_seen':time.time(),'observation':{}},
                   'society':{'transition':None,'error':None,'plan':plan}}
            claim={'id':'claim-1','context':{'session':'native'}};claimed=False;claim_reads=0;calls=[]
            def request(req,**kwargs):
                nonlocal claimed,claim_reads
                route=req.full_url.split(':12345')[-1];calls.append(route)
                if route=='/state':
                    result=copy.deepcopy(state)
                    if claimed:
                        claim_reads+=1
                        if claim_reads==1:result['society']['transition']={'next':2}
                        if mode=='changed':result['bridge']['session']='new-save'
                    return io.BytesIO(json.dumps(result).encode())
                if route=='/agency/event':
                    if mode=='already-thinking':plan['phase']='thinking'
                    return io.BytesIO(b'{}')
                if route=='/agency/claim':
                    claimed=True;plan.update(phase='thinking',claim=claim)
                    return io.BytesIO(json.dumps({'claim':claim}).encode())
                if route=='/agency/decision':
                    plan.update(phase='complete',remembered=True,outcome='deferred')
                    return io.BytesIO(b'{}')
                if route=='/agency/hold':return io.BytesIO(b'{}')
                raise AssertionError(route)
            def infer(*args):
                self.assertGreaterEqual(claim_reads,2)
                self.assertEqual(plan['claim']['id'],'claim-1')
                return {'decision':{'action_id':'defer'}}
            with patch('sys.argv',['worker','--runtime',str(runtime),'--event-id','event','--actor','108186','--model-config',str(model)]),\
                 patch.dict(os.environ,{'WORKER_TEST_KEY':'test'}),\
                 patch('tools.run_resident_event.urllib.request.urlopen',side_effect=request),\
                 patch('tools.run_resident_event.infer',side_effect=infer) as model_call,\
                 patch('tools.run_resident_event.time.sleep') as sleep,patch('builtins.print'):
                if mode=='normal':main()
                else:
                    with self.assertRaises(ValueError):main()
            return calls,model_call.call_count,[c.args[0] for c in sleep.call_args_list]

    def test_inference_waits_for_bound_claim_and_has_no_fixed_post_mutation_pause(self):
        calls,count,pauses=self.run_worker()
        self.assertEqual(count,1);self.assertEqual(calls.count('/agency/decision'),1)
        self.assertEqual(pauses,[.1]);self.assertNotIn('/agency/hold',calls)

    def test_changed_session_before_inference_cannot_spend_or_apply_result(self):
        calls,count,_=self.run_worker('changed')
        self.assertEqual(count,0);self.assertNotIn('/agency/decision',calls)
        self.assertIn('/agency/hold',calls)

    def test_existing_claim_is_not_repeated(self):
        calls,count,_=self.run_worker('already-thinking')
        self.assertEqual(count,0);self.assertNotIn('/agency/claim',calls)


if __name__=='__main__':unittest.main()
