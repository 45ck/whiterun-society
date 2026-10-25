"""Exercise handoff -> committed release -> current-state resident worker order."""
import copy
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
from tools.run_daily_life import main


class SceneDirectorTests(unittest.TestCase):
    def test_no_worker_before_release_and_checkpoint_settlement(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';runtime.mkdir()
            (runtime/'bridge-config.json').write_text(json.dumps({'port':12345,'token':'test'}))
            event={'id':'need-1','actor':7,'kind':'need_review','status':'pending','priority':1}
            row={'id':7,'isPerson':True,'activity':{'scene_id':888,'in_combat':False,'sleep_state':0,'package_id':42}}
            state={'bridge':{'session':'test','last_seen':time.time(),'command':None,'observation':{'residents':[row]}},
                'society':{'error':None,'transition':None,'scene_handoffs':[],
                    'town':{'residents':{'7':{}},'daily':{'queue':[event]}}}}
            order=[];reads=0;clock=[0.0]
            def request(req,**kwargs):
                nonlocal reads
                path=req.full_url.split(':12345')[-1]
                if path=='/town/scene-handoff':
                    data=json.loads(req.data);order.append('requested')
                    state['society']['scene_handoffs']=[{**data,'status':'pending'}]
                    return io.BytesIO(b'{}')
                if path=='/town/review':
                    self.assertEqual(state['society']['scene_handoffs'][0]['status'],'released')
                    self.assertIsNone(state['society']['transition']);order.append('review')
                    return io.BytesIO(b'{"duplicate":true}')
                self.assertEqual(path,'/state')
                if state['society']['scene_handoffs']:
                    reads+=1
                    if reads==1:state['society']['transition']={'next':2}
                    elif reads==2:
                        state['society']['scene_handoffs'][0]['status']='released';row['activity']['scene_id']=0
                    else:state['society']['transition']=None
                return io.BytesIO(json.dumps(copy.deepcopy(state)).encode())
            def worker(*args,**kwargs):
                self.assertGreaterEqual(reads,3);self.assertEqual(order,['requested','review']);order.append('worker')
                state['society']['plan']={'id':event['id'],'phase':'complete','outcome':'deferred','decisions':[{'decision':{'action_id':'defer'}}]}
                return Mock(returncode=0)
            output=runtime/'receipt.json'
            with patch('sys.argv',['director','--root',str(root),'--max-events','1','--watch-seconds','30','--model-config','fixture.json','--scene-handoffs','--receipt',str(output)]),\
                 patch('tools.run_daily_life.urllib.request.urlopen',side_effect=request),\
                 patch('tools.run_daily_life.subprocess.run',side_effect=worker) as call,\
                 patch('tools.run_daily_life.time.monotonic',side_effect=lambda:clock[0]),\
                 patch('tools.run_daily_life.time.sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)),patch('builtins.print'):
                main()
            receipt=json.loads(output.read_text());self.assertEqual(call.call_count,1)
            self.assertEqual(receipt['status'],'complete');self.assertEqual(len(receipt['scene_handoffs']),1)
            self.assertEqual(receipt['events'][0]['outcome'],'deferred')


if __name__=='__main__':unittest.main()
