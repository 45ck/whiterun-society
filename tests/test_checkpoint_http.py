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

    def test_native_effect_conflict_is_certified_only_for_goal_result(self):
        self.assertEqual(checkpoint_rejection('/goals/result','a','a',False,True)['code'],'goal_effect_busy')
        self.assertEqual(checkpoint_rejection('/goals/result','old','a',False,True)['code'],'session_changed')
        for route in ('/goals/claim','/agency/decision','/conversation/result','/heartbeat'):
            self.assertIsNone(checkpoint_rejection(route,'a','a',False,True))

    def test_goal_effect_retry_preserves_exact_results_and_session(self):
        client=self.client();client.session='a'
        replies=[conflict(code='goal_effect_busy'),response({'checkpoint':8})]
        with patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=replies) as call,patch('tools.checkpoint_http.time.sleep'):
            self.assertEqual(client('/goals/result',{'claim_id':'paid','results':[{'actor':7}]}),{'checkpoint':8})
        self.assertEqual(call.call_count,2)
        self.assertEqual(call.call_args_list[0].args[0].data,call.call_args_list[1].args[0].data)
        self.assertEqual(call.call_args_list[1].args[0].get_header('X-society-session'),'a')

    def test_goal_effect_code_cannot_retry_another_route_or_session(self):
        for route,session in (('/goals/claim','a'),('/agency/decision','a'),('/goals/result','b')):
            client=self.client();client.session='a'
            with self.subTest(route=route,session=session),patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=conflict(code='goal_effect_busy',session=session)) as call:
                with self.assertRaises(ValueError):client(route,{})
                self.assertEqual(call.call_count,1)

    def test_goal_result_never_retries_400_500_transport_or_expired_conflict(self):
        for error in (conflict(code='goal_effect_busy',status=400),conflict(code='goal_effect_busy',status=500),TimeoutError(),OSError()):
            client=self.client();client.session='a'
            with self.subTest(error=type(error).__name__),patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=error) as call:
                with self.assertRaises(type(error)):client('/goals/result',{})
                self.assertEqual(call.call_count,1)
        client=self.client();client.session='a';client.checkpoint_wait=.5;clock=[0.0]
        with patch('tools.checkpoint_http.time.monotonic',side_effect=lambda:clock[0]),\
             patch('tools.checkpoint_http.time.sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)),\
             patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=lambda *a,**k:(_ for _ in ()).throw(conflict(code='goal_effect_busy'))) as call:
            with self.assertRaises(TimeoutError):client('/goals/result',{})
        self.assertLessEqual(clock[0],.5)
        self.assertLessEqual(call.call_count,6)

    def test_independent_result_retries_only_exact_certified_conflict_and_pins_session(self):
        code='independent_review_effect_busy'
        self.assertEqual(checkpoint_rejection('/independent-reviews/result','a','a',False,True)['code'],code)
        self.assertEqual(checkpoint_rejection('/independent-reviews/claim','old','a',False)['code'],'session_changed')
        self.assertIsNone(checkpoint_rejection('/independent-reviews/claim','a','a',False,True))
        client=self.client();client.session='a'
        with patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=[conflict(code=code),response({'checkpoint':9})]) as call,\
                patch('tools.checkpoint_http.time.sleep'):
            self.assertEqual(client('/independent-reviews/result',{'claim_id':'one','results':[{'actor':7}]}),{'checkpoint':9})
        self.assertEqual(call.call_args_list[0].args[0].data,call.call_args_list[1].args[0].data)
        self.assertEqual(call.call_args_list[1].args[0].get_header('X-society-session'),'a')
        for route,session in (('/independent-reviews/claim','a'),('/goals/result','a'),('/independent-reviews/result','b')):
            client=self.client();client.session='a'
            with patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=conflict(code=code,session=session)) as call:
                with self.assertRaises(ValueError):client(route,{})
                self.assertEqual(call.call_count,1)

    def test_independent_result_never_retries_uncertain_failure_or_expired_window(self):
        code='independent_review_effect_busy'
        for error in (conflict(code=code,status=400),conflict(code=code,status=500),TimeoutError(),OSError()):
            client=self.client();client.session='a'
            with patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=error) as call:
                with self.assertRaises(type(error)):client('/independent-reviews/result',{})
                self.assertEqual(call.call_count,1)
        client=self.client();client.session='a';client.checkpoint_wait=0
        with patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=conflict(code=code)) as call:
            with self.assertRaises(TimeoutError):client('/independent-reviews/result',{})
            self.assertEqual(call.call_count,1)


if __name__=='__main__':unittest.main()
