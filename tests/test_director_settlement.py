"""The director must wait for native binding before isolating a failed worker."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
from tools.run_daily_life import main


class SettlementTests(unittest.TestCase):
    def test_delayed_effect_free_hold_settles_without_repeating_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';runtime.mkdir()
            (runtime/'bridge-config.json').write_text(json.dumps({'port':12345,'token':'test-only'}))
            event={'id':'need-1','actor':7,'kind':'need_review','status':'pending','priority':1}
            state={'bridge':{'session':'test-session','last_seen':time.time(),'command':None,
                    'observation':{'residents':[{'id':7,'isPerson':True}]}},
                   'society':{'error':None,'transition':None,'town':{'daily':{'queue':[event]}}}}
            failed=False;reads_after_worker=0
            def request(req,timeout):
                nonlocal reads_after_worker
                if req.full_url.endswith('/town/review'):result={'duplicate':True}
                else:
                    result=copy.deepcopy(state)
                    if failed:
                        reads_after_worker+=1
                        if reads_after_worker==1:
                            result['society'].update(transition={'checkpoint':2},plan={'id':'need-1','phase':'thinking'})
                        else:
                            result['society']['plan']={'id':'need-1','phase':'held','effect_free_hold':True,
                                'remembered':True,'decisions':[],'outcome':'interrupted_before_action'}
                return io.BytesIO(json.dumps(result).encode())
            def worker(*args,**kwargs):
                nonlocal failed
                failed=True
                name='resident-event-'+hashlib.sha256(b'need-1').hexdigest()[:12]+'.json'
                (runtime/name).write_text(json.dumps({'event_id':'need-1','model_calls':1}))
                return Mock(returncode=1)
            output=runtime/'receipt.json'
            argv=['director','--root',str(root),'--max-events','1','--model-config','fixture.json','--receipt',str(output)]
            with patch('sys.argv',argv),patch('tools.run_daily_life.urllib.request.urlopen',side_effect=request),\
                 patch('tools.run_daily_life.subprocess.run',side_effect=worker) as call,\
                 patch('tools.run_daily_life.time.sleep'),patch('builtins.print'):
                main()
            receipt=json.loads(output.read_text())
            self.assertEqual(call.call_count,1)
            self.assertGreaterEqual(reads_after_worker,2)
            self.assertEqual(receipt['status'],'complete')
            self.assertTrue(receipt['events'][0]['continued_other_residents'])
            self.assertEqual(receipt['events'][0]['model_calls'],1)
