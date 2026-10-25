import subprocess
import unittest
from unittest.mock import Mock
from tools.run_parallel_routines import settle_social_child


class BackgroundWorkerTests(unittest.TestCase):
    def test_failure_holds_only_owned_encounter_then_awaits_voice_cleanup(self):
        process=Mock(pid=123,returncode=1);process.poll.return_value=None
        request=Mock()
        result=settle_social_child(process,'owned-encounter',request,'Lost game connection')
        request.assert_called_once_with('/conversation/hold',{'id':'owned-encounter','reason':'Lost game connection'})
        process.wait.assert_called_once_with(timeout=660)
        self.assertEqual(result['status'],'child_exited')
        process.kill.assert_not_called();process.terminate.assert_not_called()

    def test_unreachable_service_and_late_child_are_reported_without_retry(self):
        process=Mock(pid=123);process.poll.return_value=None
        process.wait.side_effect=subprocess.TimeoutExpired('worker',660)
        request=Mock(side_effect=OSError('Disconnected'))
        result=settle_social_child(process,'owned-encounter',request,'Disconnected')
        self.assertEqual(result['status'],'child_still_running')
        self.assertTrue(result['hold_not_confirmed']);self.assertEqual(request.call_count,1)

    def test_finished_or_absent_child_needs_no_native_mutation(self):
        request=Mock();process=Mock(pid=123,returncode=0);process.poll.return_value=0
        self.assertEqual(settle_social_child(process,'done',request,'failure')['exit_code'],0)
        self.assertIsNone(settle_social_child(None,None,request,'failure'))
        request.assert_not_called();process.wait.assert_not_called()
