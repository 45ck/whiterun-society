"""A released route failure must not starve the rest of the daily queue."""
import copy
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from tools.run_daily_life import isolated_released_cohort, main


def settled_state():
    events=[{'id':f'need-{i}','actor':i,'kind':'need_review','status':'pending','priority':4-i} for i in (1,2,3)]
    members=[{'event_id':'need-1','actor':1,'phase':'held','outcome':'journey_held','command':{'id':'route-1'},
              'receipt':{'release_verified':True}},
             {'event_id':'need-2','actor':2,'phase':'complete','outcome':'deferred'}]
    for e,m in zip(events,members):e['status']=m['phase']
    return {'bridge':{'session':'test-session','last_seen':time.time(),'command':None,
                     'observation':{'residents':[{'id':i,'isPerson':True} for i in (1,2,3)]}},
            'society':{'error':None,'transition':None,'unsettled_effect':None,'plan':None,'conversation':None,
                       'town':{'daily':{'queue':events}},
                       'routine_batch':{'id':'batch','session':'test-session','phase':'held','settled':True,
                                        'release_verified':True,'members':members}}}


class CohortIsolationTests(unittest.TestCase):
    def test_each_unresolved_effect_or_missing_receipt_blocks_continuation(self):
        baseline=settled_state()
        self.assertTrue(isolated_released_cohort(baseline,'batch'))
        cases=[(('society','routine_batch','release_verified'),False),
               (('society','routine_batch','unverified_release'),True),
               (('society','routine_batch','settled'),False),
               (('society','routine_batch','session'),'other-session'),
               (('society','routine_batch','members'),[]),
               (('society','transition'),{'next':10}),
               (('society','error'),'native error'),
               (('society','unsettled_effect'),{'kind':'inventory_trade'}),
               (('society','conversation'),{'phase':'held'}),
               (('society','conversation'),{'phase':'speaking'}),
               (('society','plan'),{'phase':'complete','release_required':True}),
               (('bridge','command'),{'kind':'release'})]
        for path,value in cases:
            with self.subTest(path=path):
                state=copy.deepcopy(baseline);target=state
                for part in path[:-1]:target=target[part]
                target[path[-1]]=value
                self.assertFalse(isolated_released_cohort(state,'batch'))
        for mutation in ('receipt','queue','travelling'):
            state=copy.deepcopy(baseline)
            if mutation=='receipt':state['society']['routine_batch']['members'][0]['receipt']={}
            if mutation=='queue':state['society']['town']['daily']['queue'][0]['status']='pending'
            if mutation=='travelling':state['society']['routine_batch']['members'][0]['phase']='travelling'
            self.assertFalse(isolated_released_cohort(state,'batch'))
        baseline['society']['conversation']={'phase':'complete'}
        self.assertTrue(isolated_released_cohort(baseline,'batch'))

    def run_director(self, released):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';runtime.mkdir()
            (runtime/'bridge-config.json').write_text(json.dumps({'port':12345,'token':'test-only'}))
            state=settled_state();state['society']['routine_batch']=None
            for event in state['society']['town']['daily']['queue']:event['status']='pending'
            calls=[];clock=[0.0]
            def request(req,timeout):
                result={'duplicate':True} if req.full_url.endswith('/town/review') else state
                return io.BytesIO(json.dumps(result).encode())
            def worker(command,check):
                calls.append(command)
                if 'run_parallel_routines.py' in command[1]:
                    batch=settled_state()['society']['routine_batch']
                    batch['id']=command[command.index('--id')+1];batch['release_verified']=released
                    state['society']['routine_batch']=batch
                    for e,m in zip(state['society']['town']['daily']['queue'],batch['members']):e['status']=m['phase']
                else:
                    self.assertEqual(command[command.index('--event-id')+1],'need-3')
                    state['society']['plan']={'id':'need-3','phase':'complete','outcome':'deferred','decisions':[{}]}
                    state['society']['town']['daily']['queue'][2]['status']='complete'
                return Mock(returncode=0)
            output=runtime/'receipt.json'
            argv=['director','--root',str(root),'--max-events','3','--watch-seconds','30','--parallel-journeys',
                  '--model-config','fixture.json','--receipt',str(output)]
            with patch('sys.argv',argv),patch('tools.run_daily_life.urllib.request.urlopen',side_effect=request),\
                 patch('tools.run_daily_life.select_routine_events',side_effect=lambda s,o,events,limit:events[:2]),\
                 patch('tools.run_daily_life.subprocess.run',side_effect=worker),\
                 patch('tools.run_daily_life.time.monotonic',side_effect=lambda:clock[0]),\
                 patch('tools.run_daily_life.time.sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)),patch('builtins.print'):
                if released:main()
                else:
                    with self.assertRaisesRegex(ValueError,'unresolved effects'):main()
            return json.loads(output.read_text()),calls

    def test_other_resident_acts_after_held_cohort_without_retrying_failed_member(self):
        receipt,calls=self.run_director(True)
        self.assertEqual(len(calls),2)
        self.assertEqual(receipt['status'],'complete')
        self.assertEqual([e['id'] for e in receipt['events']],['need-1','need-2','need-3'])
        self.assertEqual([e['status'] for e in receipt['events']],['held','complete','complete'])
        self.assertTrue(receipt['events'][0]['continued_other_residents'])

    def test_uncertain_release_stops_before_another_resident_or_inference(self):
        receipt,calls=self.run_director(False)
        self.assertEqual(len(calls),1)
        self.assertEqual(receipt['status'],'held')
        self.assertNotIn('continued_other_residents',receipt['events'][0])


if __name__=='__main__':unittest.main()
