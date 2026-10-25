"""A failed chat stays failed while other residents continue after release."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from tools.run_daily_life import isolated_released_conversation, main


def released_state():
    c={'id':'chat-1','phase':'held','mode':'autonomous_social','social_settled':True,
       'initiator':1,'speakers':[1,2],'paired_attendance':True,'error':'Invalid language candidates',
       'release_evidence':{'id':'release-chat-chat-1','released':True,'status':'applied',
           'attendance':{'id':'attend-chat-1','phase':'released','participants':[
               {'actor':i,'released':True,'ownedPackage':False} for i in (1,2)]}}}
    return {'bridge':{'session':'s','last_seen':time.time(),'command':None,
                     'observation':{'residents':[{'id':i,'isPerson':True} for i in (1,2,3)]}},
            'society':{'error':None,'transition':None,'unsettled_effect':None,'conversation':c,
                       'town':{'daily':{'queue':[
                           {'id':'chat-1','actor':1,'kind':'social_review','priority':1,'status':'held'},
                           {'id':'meal-3','actor':3,'kind':'need_review','priority':1,'status':'pending'}]}}}}


class ConversationIsolationTests(unittest.TestCase):
    def test_cleanup_must_be_complete_before_any_continuation(self):
        baseline=released_state()
        self.assertTrue(isolated_released_conversation(baseline,'chat-1','s'))
        cases=[(('bridge','session'),'new'),(('bridge','command'),{'kind':'release'}),
               (('society','transition'),{'next':8}), (('society','error'),'native error'),
               (('society','unsettled_effect'),{'kind':'trade'}),
               (('society','conversation','social_settled'),False),
               (('society','conversation','interruption'),{'kind':'observer'}),
               (('society','conversation','release_evidence','released'),False),
               (('society','conversation','release_evidence','id'),'another-release'),
               (('society','conversation','release_evidence','attendance','participants'),[]),
               (('society','conversation','current'),{'delivery_id':'unconfirmed-speech'}),
               (('society','plan'),{'phase':'travelling'}),
               (('society','routine_batch'),{'phase':'complete','settled':True,'release_verified':False})]
        for path,value in cases:
            with self.subTest(path=path):
                state=copy.deepcopy(baseline);target=state
                for key in path[:-1]:target=target[key]
                target[path[-1]]=value
                self.assertFalse(isolated_released_conversation(state,'chat-1','s'))
        baseline['society']['town']['daily']['queue'][0]['status']='pending'
        self.assertFalse(isolated_released_conversation(baseline,'chat-1','s'))

    def run_director(self, released):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';runtime.mkdir()
            (runtime/'bridge-config.json').write_text(json.dumps({'port':12345,'token':'test-only'}))
            state=released_state();state['society']['conversation']=None
            state['society']['town']['daily']['queue'][0]['status']='pending'
            calls=[]
            def request(req,timeout):
                result={'duplicate':True} if req.full_url.endswith('/town/review') else state
                return io.BytesIO(json.dumps(result).encode())
            def worker(command,check):
                calls.append(command)
                if 'run_conversation.py' in command[1]:
                    state['society']['conversation']=released_state()['society']['conversation']
                    state['society']['conversation']['release_evidence']['released']=released
                    state['society']['town']['daily']['queue'][0]['status']='held'
                    path=runtime/('conversation-'+hashlib.sha256(b'chat-1').hexdigest()[:12]+'.json')
                    path.write_text(json.dumps({'id':'chat-1','status':'held','calls':{'propose':1,'select':0,'social':2}}))
                    return Mock(returncode=1)
                self.assertEqual(command[command.index('--event-id')+1],'meal-3')
                state['society']['plan']={'id':'meal-3','phase':'complete','outcome':'ate_bread','decisions':[{}]}
                state['society']['town']['daily']['queue'][1]['status']='complete'
                return Mock(returncode=0)
            output=runtime/'receipt.json'
            argv=['director','--root',str(root),'--max-events','2','--model-config','fixture.json',
                  '--language-config','fixture.json','--receipt',str(output)]
            with patch('sys.argv',argv),patch('tools.run_daily_life.urllib.request.urlopen',side_effect=request),\
                 patch('tools.run_daily_life.social_candidates',return_value=[{'id':2}]),\
                 patch('tools.run_daily_life.subprocess.run',side_effect=worker),patch('builtins.print'):
                if released:main()
                else:
                    with self.assertRaisesRegex(ValueError,'Invalid language candidates'):main()
            return json.loads(output.read_text()),calls

    def test_failed_chat_does_not_starve_meal_or_repeat_inference(self):
        receipt,calls=self.run_director(True)
        self.assertEqual(len(calls),2)
        self.assertEqual(receipt['status'],'complete')
        self.assertEqual([e['status'] for e in receipt['events']],['held','complete'])
        self.assertEqual(receipt['events'][0]['model_calls'],3)
        self.assertTrue(receipt['events'][0]['continued_other_residents'])
        self.assertEqual(receipt['events'][1]['outcome'],'ate_bread')

    def test_missing_release_stops_without_touching_another_resident(self):
        receipt,calls=self.run_director(False)
        self.assertEqual(len(calls),1)
        self.assertEqual(receipt['status'],'held')
        self.assertNotIn('continued_other_residents',receipt['events'][0])
