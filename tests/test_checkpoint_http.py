import io
import json
import unittest
import urllib.error
from unittest.mock import patch
from tools.checkpoint_http import CheckpointHTTP,checkpoint_rejection


def response(value):return io.BytesIO(json.dumps(value).encode())
def conflict(code='checkpoint_busy',session='a',status=409):
    return urllib.error.HTTPError('http://127.0.0.1/state',status,'conflict',{},response({'code':code,'session':session,'error':'Rejected before mutation'}))


class CheckpointHTTPTests(unittest.TestCase):
    def client(self):return CheckpointHTTP('http://127.0.0.1:1234','test-token')

    def test_busy_checkpoint_retries_identical_payload_with_bound_session(self):
        calls=[]
        results=[response({'bridge':{'session':'a'}}),conflict(),response({'checkpoint':7})]
        def open_(request,**kwargs):
            calls.append(request)
            result=results.pop(0)
            if isinstance(result,Exception):raise result
            return result
        with patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=open_),patch('tools.checkpoint_http.time.sleep'):
            result=self.client()('/goals/result',{'claim_id':'one','results':[]})
        self.assertEqual(result,{'checkpoint':7});self.assertEqual(len(calls),3)
        self.assertEqual(calls[1].data,calls[2].data)
        self.assertEqual(calls[1].get_header('X-society-session'),'a')
        self.assertEqual(calls[2].get_header('X-society-session'),'a')

    def test_changed_session_on_conflict_never_retries(self):
        client=self.client();client.session='a'
        with patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=conflict(session='b')) as opened:
            with self.assertRaisesRegex(ValueError,'session changed'):client('/agency/decision',{})
        self.assertEqual(opened.call_count,1)

    def test_other_http_status_or_timeout_is_never_retried(self):
        for error in (conflict(status=500),TimeoutError('unknown delivery outcome')):
            client=self.client();client.session='a'
            with patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=error) as opened:
                with self.assertRaises(type(error)):client('/conversation/result',{})
            self.assertEqual(opened.call_count,1)

    def test_other_409_and_malformed_409_are_not_retry_authority(self):
        for error in (conflict(code='session_changed'),urllib.error.HTTPError('url',409,'',{},io.BytesIO(b'not json'))):
            client=self.client();client.session='a'
            with patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=error) as opened:
                with self.assertRaises(ValueError):client('/routines/start',{})
            self.assertEqual(opened.call_count,1)

    def test_conflict_wait_is_finite(self):
        client=self.client();client.session='a';client.checkpoint_wait=0
        with patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=conflict()) as opened:
            with self.assertRaises(TimeoutError):client('/town/review',{})
        self.assertEqual(opened.call_count,1)

    def test_later_state_read_cannot_rebind_worker_to_another_save(self):
        client=self.client();client.session='a'
        with patch('tools.checkpoint_http.urllib.request.urlopen',return_value=response({'bridge':{'session':'b'}})):
            with self.assertRaisesRegex(ValueError,'session changed'):client('/state')
        self.assertEqual(client.session,'a')

    def test_missing_native_session_cannot_issue_mutation(self):
        with patch('tools.checkpoint_http.urllib.request.urlopen',return_value=response({'bridge':{'session':None}})) as opened:
            with self.assertRaisesRegex(ValueError,'No game session'):self.client()('/goals/claim',{})
        self.assertEqual(opened.call_count,1)

    def test_server_checks_session_before_checkpoint_and_exempts_heartbeat(self):
        self.assertEqual(checkpoint_rejection('/agency/decision','old','new',True)['code'],'session_changed')
        self.assertEqual(checkpoint_rejection('/goals/result','same','same',True)['code'],'checkpoint_busy')
        self.assertIsNone(checkpoint_rejection('/agency/decision','same','same',False))
        self.assertIsNone(checkpoint_rejection('/heartbeat','old','new',True))
        self.assertIsNone(checkpoint_rejection('/command',None,'same',True))


if __name__=='__main__':unittest.main()
