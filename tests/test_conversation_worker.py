"""Faster polling cannot bypass persisted claims or replay paid inference."""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from tools.run_conversation import main
from language import LanguageOutputError


class ConversationWorkerTests(unittest.TestCase):
    def run_worker(self, changed_claim=False, rejected=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';runtime.mkdir()
            (runtime/'bridge-config.json').write_text(json.dumps({'port':12345,'token':'test-only'}))
            config=runtime/'model.json';config.write_text(json.dumps({'model':'test','key_env':'TEST_VOICE_KEY'}))
            scene={'id':'worker-test','phase':'propose' if rejected else 'choose_partner','turn':0,'turn_limit':6,'reply_policy':'combined_choice'}
            state={'bridge':{'session':'s','last_seen':time.time(),'observation':{'residents':[]}},
                   'society':{'error':None,'transition':None,'conversation':scene}}
            pending=0;started=False;routes=[]
            def request(req,timeout):
                nonlocal pending,started
                route=req.full_url.split('12345')[-1];routes.append(route)
                data=json.loads(req.data) if req.data else None
                if route=='/conversation/start':
                    self.assertEqual(data['reply_policy'],'combined_choice');started=True;pending=2;result={}
                elif route=='/conversation/claim':
                    claim={'id':'claim','session':'s','context':{'actor_id':1,'options':[{'id':'defer'}]}}
                    scene.update(phase='thinking_choose_partner',claim=claim);pending=2;result={'claim':copy.deepcopy(claim)}
                elif route=='/conversation/result':
                    self.assertEqual(data['claim_id'],'claim');scene.update(phase='complete',outcome='continued_quietly');pending=2;result={}
                elif route=='/conversation/hold':
                    if rejected:
                        self.assertEqual(data['inference_failure']['claim_id'],'claim')
                        self.assertEqual(data['inference_failure']['receipt']['validation_failure'],'candidate_count')
                    result={} 
                else:
                    self.assertEqual(route,'/state');result=copy.deepcopy(state)
                    if started and pending:
                        pending-=1;result['society']['transition']={'next':2}
                    elif changed_claim and scene.get('claim'):
                        result['society']['conversation']['claim']['id']='another-worker'
                return io.BytesIO(json.dumps(result).encode())
            argv=['worker','--root',str(root),'--id','worker-test','--decision-config',str(config),'--language-config',str(config)]
            with patch('sys.argv',argv),patch.dict(os.environ,{'TEST_VOICE_KEY':'test-placeholder'}),\
                 patch('tools.run_conversation.urllib.request.urlopen',side_effect=request),\
                 patch('tools.run_conversation.VoiceWorker') as voice,\
                 patch('tools.run_conversation.time.sleep') as sleep,patch('builtins.print'),\
                 patch('tools.run_conversation.propose',side_effect=LanguageOutputError('Invalid language candidates',{
                     'model':'test-language','elapsed_seconds':1,'usage':{'cost':.001},
                     'finish_reason':'stop','validation_failure':'candidate_count'})) as language,\
                 patch('tools.run_conversation.infer',return_value={'model':'test','decision':{'action_id':'defer'}}) as inference:
                if rejected:
                    with self.assertRaises(LanguageOutputError):main()
                elif changed_claim:
                    with self.assertRaisesRegex(ValueError,'changed before inference'):main()
                else:main()
                self.assertEqual(inference.call_count,0 if changed_claim or rejected else 1)
                self.assertEqual(language.call_count,int(rejected))
                self.assertTrue(sleep.call_count)
                self.assertTrue(all(call.args==(.1,) for call in sleep.call_args_list))
                voice.return_value.close.assert_called_once()
            receipt=json.loads(next(runtime.glob('conversation-*.json')).read_text())
            return receipt,routes

    def test_every_claim_and_result_settles_without_an_extra_post_mutation_sleep(self):
        receipt,routes=self.run_worker()
        self.assertEqual(receipt['status'],'complete')
        self.assertEqual(receipt['calls'],{'propose':0,'select':0,'social':1})
        self.assertEqual(routes.count('/conversation/claim'),1)
        self.assertNotIn('/conversation/hold',routes)

    def test_changed_claim_stops_before_any_model_call(self):
        receipt,routes=self.run_worker(changed_claim=True)
        self.assertEqual(receipt['status'],'held')
        self.assertEqual(sum(receipt['calls'].values()),0)
        self.assertEqual(routes.count('/conversation/claim'),1)
        self.assertEqual(routes.count('/conversation/hold'),1)

    def test_language_rejection_forwards_billed_receipt_bound_to_original_claim(self):
        receipt,routes=self.run_worker(rejected=True)
        self.assertEqual(receipt['calls'],{'propose':1,'select':0,'social':0})
        self.assertEqual(receipt['rejected_language']['usage']['cost'],.001)
        self.assertEqual(routes.count('/conversation/hold'),1)
        self.assertNotIn('/conversation/result',routes)


if __name__=='__main__':unittest.main()
