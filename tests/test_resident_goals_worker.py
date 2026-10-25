import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from threading import Barrier,Lock
import unittest
from unittest.mock import patch
from tools.run_resident_goals import run_decisions,main
from decisions import infer


class ResidentGoalWorkerTests(unittest.TestCase):
    def members(self,n):return [{'actor':i,'context':{'id':i}} for i in range(n)]

    def test_four_concurrent_inferences_have_exact_attempt_and_cost_counts(self):
        barrier=Barrier(4);guard=Lock();active=0;peak=0
        def decision(context,model,key,timeout):
            nonlocal active,peak
            self.assertGreater(timeout,0);self.assertLessEqual(timeout,30)
            with guard:active+=1;peak=max(peak,active)
            barrier.wait(timeout=2)
            with guard:active-=1
            return {'model':'test','usage':{'cost':.001}}
        with patch('tools.run_resident_goals.infer',side_effect=decision) as call:
            stats=run_decisions(self.members(8),{'model':'test'},'placeholder')
        self.assertEqual(peak,4);self.assertEqual(call.call_count,8);self.assertEqual(stats['model_calls'],8)
        self.assertEqual(stats['reserved_model_calls'],8);self.assertEqual(stats['cost_reports'],8)
        self.assertAlmostEqual(stats['reported_cost'],.008);self.assertEqual(stats['unreported_cost_calls'],0)
        self.assertEqual([r['actor'] for r in stats['results']],list(range(8)))

    def test_deadline_stops_queued_starts_and_discards_late_choices_without_retry(self):
        elapsed=[0]
        def late(*args,**kwargs):elapsed[0]=2;return {'model':'test','usage':{'cost':.001}}
        with patch('tools.run_resident_goals.infer',side_effect=late) as call:
            stats=run_decisions(self.members(8),{'model':'test'},'placeholder',wave_seconds=1,clock=lambda:elapsed[0])
        self.assertEqual(call.call_count,1);self.assertEqual(stats['model_calls'],1);self.assertEqual(stats['reserved_model_calls'],8)
        self.assertEqual(stats['results'][0]['result']['failure'],'wave_deadline_after_inference')
        self.assertTrue(stats['results'][0]['result']['attempted'])
        self.assertTrue(all(r['result']['failure']=='wave_deadline_before_inference' for r in stats['results'][1:]))
        self.assertTrue(all(r['result']['attempted'] is False for r in stats['results'][1:]))
        self.assertEqual(stats['cost_reports'],1)

    def test_individual_failure_does_not_cancel_other_claimed_residents(self):
        def decision(context,*args,**kwargs):
            if context['id']==2:raise TimeoutError('private provider failure')
            return {'model':'test'}
        with patch('tools.run_resident_goals.infer',side_effect=decision) as call:
            stats=run_decisions(self.members(6),{'model':'test'},'placeholder')
        self.assertEqual(call.call_count,6);self.assertEqual(len(stats['results']),6)
        self.assertEqual(sum('failure' in r['result'] for r in stats['results']),1)
        self.assertNotIn('private provider failure',str(stats));self.assertEqual(stats['unreported_cost_calls'],6)

    def test_duplicate_inspection_preserves_original_paid_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';runtime.mkdir()
            (runtime/'bridge-config.json').write_text(json.dumps({'port':1234,'token':'test'}))
            model=root/'model.json';model.write_text(json.dumps({'key_env':'TEST_GOAL_KEY','model':'test'}))
            path=runtime/('resident-goals-'+hashlib.sha256(b'reused').hexdigest()[:12]+'.json')
            original='{"status":"complete","model_calls":3,"results":[1,2,3]}'
            path.write_text(original)
            state={'bridge':{'last_seen':10**12,'session':'a','command':None},'society':{'error':None,'transition':None}}
            with patch.dict(os.environ,{'TEST_GOAL_KEY':'placeholder'}),patch('sys.argv',['worker','--root',folder,'--id','reused','--model-config',str(model)]),\
                 patch('tools.run_resident_goals.CheckpointHTTP') as client,patch('tools.run_resident_goals.infer') as call,patch('builtins.print'):
                client.return_value.side_effect=[state,{'duplicate':True}];main()
            self.assertEqual(path.read_text(),original);call.assert_not_called()

    def test_timeout_validation_and_jev_override_are_backward_compatible(self):
        context={'options':[{'id':'wait','effect':'Wait'}]}
        config={'provider':'openrouter_decisions','url':'https://openrouter.ai/api/alpha/decisions','model':'test'}
        payload={'answers':{'action':{'choice':'wait','probabilities':{'wait':1}}}}
        with patch('decision_provider.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())) as call:
            infer(context,config,'placeholder',timeout=2.5)
        self.assertEqual(call.call_args.kwargs['timeout'],2.5)
        for value in (0,-1,float('nan'),True,181):
            with self.assertRaises(ValueError):infer(context,config,'placeholder',timeout=value)


if __name__=='__main__':unittest.main()
