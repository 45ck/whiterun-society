import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from tools.voice_worker import VoiceWorker


class VoiceWorkerTests(unittest.TestCase):
    def test_warm_child_is_bounded_and_does_not_inherit_model_credential(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'runtime').mkdir()
            process=Mock();process.stdin=io.BytesIO();process.stdout=io.BytesIO(b'{"ready":true,"load_seconds":2}\n{"id":"voice-1","audio":{"file":"fixture"},"synthesis_seconds":1}\n')
            with patch.dict(os.environ,{'TEST_MODEL_KEY':'never-pass'}),patch('tools.voice_worker.subprocess.Popen',return_value=process) as spawn:
                worker=VoiceWorker(root,1,['TEST_MODEL_KEY'])
                try:
                    result=worker.synthesize('Hello there.','bm_lewis')
                    self.assertEqual(result['audio']['file'],'fixture')
                    self.assertNotIn('TEST_MODEL_KEY',spawn.call_args.kwargs['env'])
                    self.assertEqual(json.loads(process.stdin.getvalue())['id'],'voice-1')
                    with self.assertRaises(ValueError):worker.synthesize('Another line.','bm_lewis')
                finally:worker.close()
                process.terminate.assert_not_called()

    def test_wrong_response_identity_does_not_retry_speech(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'runtime').mkdir()
            process=Mock();process.stdin=io.BytesIO();process.stdout=io.BytesIO(b'{"ready":true}\n{"id":"wrong","audio":{}}\n')
            with patch('tools.voice_worker.subprocess.Popen',return_value=process):
                worker=VoiceWorker(root)
                try:
                    with self.assertRaisesRegex(ValueError,'identity'):worker.synthesize('Hello there.','bm_lewis')
                    self.assertEqual(len(process.stdin.getvalue().splitlines()),1)
                finally:worker.close()
