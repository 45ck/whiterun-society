import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
from director_control import DirectorControl
from director_policy import load_run_policy


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
        result=self.control.start({'max_events':2,'scene_handoffs':True},self.bridge,self.society)
        self.assertTrue(result['running']);self.assertEqual(result['maximum_model_calls'],224)
        self.assertNotIn('receipt',result);self.assertNotIn('stop_file',result)
        argv=popen.call_args.args[0];self.assertNotIn('test-placeholder',' '.join(argv))
        self.assertIn('--social-opportunities',argv)
        self.assertIn('--parallel-journeys',argv)
        self.assertIn('--resident-goals',argv)
        self.assertIn('--scene-handoffs',argv)
        policy_path=Path(argv[argv.index('--run-policy')+1])
        policy=load_run_policy(policy_path,expected_max_events=2,expected_watch_seconds=600)
        self.assertEqual(policy['goal_budget'],192);self.assertEqual(policy['goal_review_seconds'],5)
        self.assertEqual(result['run_policy'],policy)
        self.assertNotIn('test-placeholder',policy_path.read_text())
        self.assertTrue(result['scene_handoffs_enabled'])
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
        for key in ('plan','conversation','routine_batch'):
            with self.assertRaises(ValueError):self.control.start({},self.bridge,{**self.society,key:{'phase':'speaking'}})
        for extra in ({'unsettled_effect':True},{'routine_batch':{'phase':'held','unverified_release':True}}):
            with self.assertRaisesRegex(ValueError,'unverified'):self.control.start({},self.bridge,{**self.society,**extra})
        with self.assertRaises(ValueError):self.control.start({}, {'last_seen':0},self.society)
        popen.assert_not_called()

    @patch.dict(os.environ,{},clear=True)
    @patch('director_control.subprocess.Popen')
    def test_missing_credentials_fails_without_call_or_secret_lookup(self,popen):
        with self.assertRaisesRegex(ValueError,'credential'):self.control.start({},self.bridge,self.society)
        popen.assert_not_called()

    @patch.dict(os.environ,{'TEST_SOCIETY_KEY':'test-placeholder'})
    @patch('director_control.subprocess.Popen')
    def test_play_has_explicit_session_limits_and_pause_settles_current_event(self,popen):
        process=Mock();process.poll.return_value=None;popen.return_value=process
        result=self.control.control({'action':'play'},self.bridge,self.society)
        self.assertEqual((result['mode'],result['max_events'],result['session_limit_seconds']),('play',96,3600))
        self.assertEqual(result['run_policy']['goal_budget'],768)
        self.assertEqual(result['maximum_model_calls'],2304)
        self.assertTrue(result['scene_handoffs_enabled'])
        argv=popen.call_args.args[0]
        self.assertEqual(argv[argv.index('--watch-seconds')+1],'3600')
        self.assertEqual(self.control.control({'action':'pause'},self.bridge,self.society)['status'],'stopping')
        process.kill.assert_not_called()
        process.terminate.assert_not_called()

    def test_play_rejects_unsupported_limits(self):
        for value in (97,0,True):
            with self.assertRaises(ValueError):self.control.control({'action':'play','max_events':value},self.bridge,self.society)

    @patch.dict(os.environ,{'TEST_SOCIETY_KEY':'test-placeholder'})
    @patch('director_control.subprocess.Popen')
    def test_policy_is_frozen_before_process_starts_and_cannot_change_with_source(self,popen):
        from director_policy import load_director_policy
        config=load_director_policy();config['modes']['sample'].update(default_events=3,goal_budget=111,goal_review_seconds=7)
        source=self.runtime/'source-policy.json';source.write_text(json.dumps(config))
        def launch(argv,**kwargs):
            path=Path(argv[argv.index('--run-policy')+1])
            self.assertEqual(load_run_policy(path)['goal_budget'],111)
            source.write_text('{}')
            process=Mock();process.poll.return_value=None;return process
        popen.side_effect=launch
        with patch('director_policy.DEFAULT_PATH',source):
            result=self.control.start({},self.bridge,self.society)
        self.assertEqual(result['max_events'],3)
        self.assertEqual(result['run_policy']['goal_review_seconds'],7)
        path=Path(popen.call_args.args[0][popen.call_args.args[0].index('--run-policy')+1])
        self.assertEqual(load_run_policy(path)['goal_budget'],111)

    @patch.dict(os.environ,{'TEST_SOCIETY_KEY':'test-placeholder'})
    @patch('director_control.subprocess.Popen')
    def test_invalid_policy_never_starts_or_creates_run_files(self,popen):
        source=self.runtime/'bad-policy.json';source.write_text('{}')
        with patch('director_policy.DEFAULT_PATH',source),self.assertRaises(ValueError):
            self.control.start({},self.bridge,self.society)
        popen.assert_not_called();self.assertEqual(list(self.runtime.glob('society-*')),[])
