import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
from director_control import DirectorControl


class DirectorControlTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.runtime=Path(self.folder.name);self.control=DirectorControl(self.runtime)
        self.addCleanup(lambda:self.control.log.close() if self.control.log else None)
        for name in ('jev','language'):
            (self.runtime/(name+'-config.json')).write_text(json.dumps({'key_env':'TEST_SOCIETY_KEY'}))
        self.bridge={'last_seen':time.time()};self.society={'town':{'residents':{'7':{}}}}

    @patch.dict(os.environ,{'TEST_SOCIETY_KEY':'test-placeholder'})
    @patch('director_control.subprocess.Popen')
    def test_single_owner_bounded_process_and_graceful_stop(self,popen):
        process=Mock();process.poll.return_value=None;popen.return_value=process
        result=self.control.start({'max_events':2},self.bridge,self.society)
        self.assertTrue(result['running']);self.assertEqual(result['maximum_model_calls'],16)
        self.assertNotIn('receipt',result);self.assertNotIn('stop_file',result)
        argv=popen.call_args.args[0];self.assertNotIn('test-placeholder',' '.join(argv))
        self.assertIn('--social-opportunities',argv)
        with self.assertRaises(ValueError):self.control.start({},self.bridge,self.society)
        self.control.stop();self.assertTrue(Path(self.control.run['stop_file']).exists())
        process.terminate.assert_not_called();process.kill.assert_not_called()
        self.assertEqual(self.control.status()['status'],'stopping')
        Path(self.control.run['receipt']).write_text(json.dumps({'status':'stopped','events':[{'status':'complete','outcome':'declined'}]}))
        process.poll.return_value=0
        self.assertEqual(self.control.status()['events_completed'],1)
        self.assertEqual(self.control.status()['outcome'],'stopped')

    @patch.dict(os.environ,{'TEST_SOCIETY_KEY':'test-placeholder'})
    @patch('director_control.subprocess.Popen')
    def test_invalid_budget_or_active_native_event_never_starts_worker(self,popen):
        for budget in (True,0,13,'2'):
            with self.assertRaises(ValueError):self.control.start({'max_events':budget},self.bridge,self.society)
        for key in ('plan','conversation'):
            with self.assertRaises(ValueError):self.control.start({},self.bridge,{**self.society,key:{'phase':'speaking'}})
        with self.assertRaises(ValueError):self.control.start({}, {'last_seen':0},self.society)
        popen.assert_not_called()

    @patch.dict(os.environ,{},clear=True)
    @patch('director_control.subprocess.Popen')
    def test_missing_credentials_fails_without_call_or_secret_lookup(self,popen):
        with self.assertRaisesRegex(ValueError,'credential'):self.control.start({},self.bridge,self.society)
        popen.assert_not_called()
