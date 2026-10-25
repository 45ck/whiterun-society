import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error

from tools.run_independent_reviews import main,wait_review_settled


class IndependentReviewWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'runtime').mkdir()
        (self.root/'runtime'/'bridge-config.json').write_text(json.dumps({'port':1234,'token':'fixture'}))
        self.model=self.root/'model.json';self.model.write_text(json.dumps({'model':'fixture','key_env':'INDEPENDENT_FIXTURE_KEY'}))
        self.path=self.root/'runtime'/('independent-reviews-'+hashlib.sha256(b'review-test').hexdigest()[:12]+'.json')
        self.wave={'id':'review-test','claim_id':'claim','session':'session','deadline_at':time.time()+1000,
            'phase':'thinking','members':[{'actor':7,'source_event':'rest-followup','context':{'options':[{'id':'rest'}]}}]}
        self.before={'bridge':{'session':'session','last_seen':time.time(),'command':None},
            'society':{'error':None,'transition':None,'independent_review_waves':[]}}
        self.thinking=copy.deepcopy(self.before);self.thinking['society']['independent_review_waves']=[self.wave]
        self.complete=copy.deepcopy(self.thinking);self.complete['society']['independent_review_waves'][0]['phase']='complete'
        self.binding=copy.deepcopy(self.before);self.binding['society']['transition']={'next':2}
        self.argv=['worker','--root',str(self.root),'--id','review-test','--model-config',str(self.model)]

    def invoke(self,responses):
        with patch('sys.argv',self.argv),patch.dict(os.environ,{'INDEPENDENT_FIXTURE_KEY':'fixture'}),\
                patch('tools.run_independent_reviews.CheckpointHTTP') as client,\
                patch('tools.run_independent_reviews.time.sleep'),patch('builtins.print'),\
                patch('tools.run_resident_goals.infer',return_value={'model':'fixture','decision':{'action_id':'rest'}}) as infer:
            client.return_value.side_effect=responses
            main()
            return client.return_value,infer

    def test_actual_main_waits_for_binding_then_infers_once_and_submits_same_results(self):
        self.complete['society']['unsettled_effect']={'kind':'unrelated_native_work'}
        request,infer=self.invoke([self.before,{'wave':self.wave},self.binding,self.thinking,
                                  self.thinking,{},self.binding,self.complete])
        self.assertEqual(infer.call_count,1)
        posts=[call.args for call in request.call_args_list if len(call.args)>1]
        self.assertEqual([route for route,_ in posts],['/independent-reviews/claim','/independent-reviews/result'])
        receipt=json.loads(self.path.read_text())
        self.assertEqual(receipt['status'],'complete');self.assertEqual(receipt['model_calls'],1)
        self.assertEqual(receipt['source_events'],{'7':'rest-followup'})
        self.assertEqual(posts[1][1]['results'],receipt['results'])
        self.assertEqual(receipt['unreported_cost_calls'],1)

    def test_duplicate_keeps_original_evidence_and_never_requires_provider_key(self):
        original='{"status":"complete","model_calls":2,"results":["paid-evidence"]}'
        self.path.write_text(original)
        with patch('sys.argv',self.argv),patch.dict(os.environ,{},clear=True),\
                patch('tools.run_independent_reviews.CheckpointHTTP') as client,patch('builtins.print'),\
                patch('tools.run_resident_goals.infer') as infer:
            client.return_value.side_effect=[self.before,{'duplicate':True}];main()
        self.assertEqual(self.path.read_text(),original);infer.assert_not_called()

    def test_uncertain_result_submission_keeps_paid_result_without_reinference(self):
        failure=urllib.error.HTTPError('fixture',500,'fixture',{},None)
        with self.assertRaises(urllib.error.HTTPError):
            self.invoke([self.before,{'wave':self.wave},self.thinking,self.thinking,failure])
        receipt=json.loads(self.path.read_text())
        self.assertEqual(receipt['model_calls'],1);self.assertEqual(len(receipt['results']),1)
        self.assertEqual(receipt['failure_stage'],'result_submission')
        self.assertFalse(receipt['failure']['result_submitted'])

    def test_claim_change_after_binding_prevents_any_model_call(self):
        wrong=copy.deepcopy(self.thinking);wrong['society']['independent_review_waves'][0]['claim_id']='different'
        with self.assertRaisesRegex(ValueError,'claim changed'):
            self.invoke([self.before,{'wave':self.wave},self.binding,wrong])
        receipt=json.loads(self.path.read_text())
        self.assertEqual(receipt['model_calls'],0);self.assertEqual(receipt['failure_stage'],'claim_binding')

    def test_session_change_during_transition_still_stops_worker(self):
        changed=copy.deepcopy(self.binding);changed['bridge']['session']='loaded-save'
        with self.assertRaisesRegex(ValueError,'Session changed'):
            self.invoke([self.before,{'wave':self.wave},changed])
        self.assertEqual(json.loads(self.path.read_text())['model_calls'],0)

    def test_invalid_duplicate_actor_members_fail_before_inference(self):
        self.wave['members'].append(copy.deepcopy(self.wave['members'][0]))
        with self.assertRaisesRegex(ValueError,'members invalid'):
            self.invoke([self.before,{'wave':self.wave}])
        self.assertEqual(json.loads(self.path.read_text())['model_calls'],0)


if __name__=='__main__':unittest.main()
