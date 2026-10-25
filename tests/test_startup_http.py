"""Real local HTTP handler over in-memory sockets; no game or listener."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import server
from lineage import TimelineEconomy
from livelihood_backgrounds import load_livelihood_manifest, livelihood_manifest_hash
from test_world_trade_http import MemorySocket, FinishedRequests
from catalog_fixture import native_catalog


class StartupHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.world=TimelineEconomy(Path(self.temp.name)/'timeline.sqlite')
        self.obs={'session':'startup','checkpoint':0,'ready':True,'gameDays':12,
                  'economy_catalog':native_catalog(),'residents':[
                      {'id':7,'baseId':70,'isPerson':True,'name':'Resident A',
                       'inventory':{'gold':2,'grain':0,'bread':0}},
                      {'id':8,'baseId':80,'isPerson':True,'name':'Resident B',
                       'inventory':{'gold':2,'grain':0,'bread':0}}]}
        self.world.observe(self.obs);self.world.bootstrap(self.obs);self.bind()
        self.world.initialize_population('census','seed',self.obs);self.bind()
        manifest=load_livelihood_manifest()
        self.request={'id':'background','seed':'seed','scenario_id':manifest['id'],
                      'scenario_hash':livelihood_manifest_hash(manifest),'actor_ids':[7,8],
                      'expected_checkpoint':self.world.marker}

    def tearDown(self):
        self.world.db.close();self.temp.cleanup()

    def bind(self):
        command=self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'],'bind_checkpoint')
        self.obs['checkpoint']=command['next'];self.obs.pop('ack',None)
        self.world.observe(self.obs)

    def post(self,path,payload,*,observer=False,session='startup'):
        requests=[('/heartbeat',self.obs), (path,payload)];responses=[]
        class MemoryServer:
            def __init__(inner,address,handler):inner.handler=handler
            def handle_request(inner):
                if not requests:raise FinishedRequests()
                route,body=requests.pop(0);encoded=json.dumps(body).encode()
                headers=(f'POST {route} HTTP/1.0\r\nHost: 127.0.0.1:17899\r\n'
                         f'Authorization: Bearer fixture-token\r\nX-Society-Session: {session}\r\n'
                         'Origin: http://127.0.0.1:17899\r\n'
                         f'X-Observer-Token: {"fixture-token" if observer else "none"}\r\n'
                         f'Content-Type: application/json\r\nContent-Length: {len(encoded)}\r\n\r\n').encode()
                connection=MemorySocket(headers+encoded);inner.handler(connection,('127.0.0.1',1),inner)
                header,body=connection.output.getvalue().split(b'\r\n\r\n',1)
                responses.append((int(header.split(b' ',2)[1]),json.loads(body)))
            def server_close(inner):pass
        runtime=Path(self.temp.name)/'http'
        world=self.world
        class ServerWorld:
            # Each request harness closes its server; the test owns the real DB.
            db=SimpleNamespace(close=lambda:None)
            def __getattr__(inner,key):return getattr(world,key)
        with patch.object(server,'LocalServer',MemoryServer),patch.object(server,'TimelineEconomy',return_value=ServerWorld()),\
             patch.object(server.secrets,'token_hex',return_value='fixture-token'),patch('builtins.print'),\
             patch('sys.argv',['server','--runtime',str(runtime),'--port','17899']):
            with self.assertRaises(FinishedRequests):server.main()
        self.assertEqual(responses[0][0],200,responses)
        return responses[-1]

    def test_preview_has_no_checkpoint_or_assets_and_apply_binds_same_assignment(self):
        before=copy.deepcopy(self.world.active)
        status,proposal=self.post('/town/livelihood-background/preview',self.request)
        self.assertEqual(status,200,proposal);self.assertEqual(self.world.active,before)
        self.assertIsNone(self.world.transition)
        status,result=self.post('/town/livelihood-background',self.request)
        self.assertEqual(status,202,result)
        self.assertEqual(result['background']['assignments'],proposal['background']['assignments'])
        self.assertEqual(self.world.active,before)
        self.bind()
        self.assertEqual(self.world.active['town']['businesses'],before['town']['businesses'])
        self.assertEqual(self.world.active['trades'],[])
        self.assertFalse(self.world.active.get('production'))
        self.assertTrue(all(not p['memories'] for p in self.world.active['people'].values()))

    def test_stale_checkpoint_rejected_before_any_write(self):
        status,result=self.post('/town/livelihood-background',{**self.request,'expected_checkpoint':0})
        self.assertEqual(status,400,result);self.assertIn('checkpoint',result['error'])
        self.assertIsNone(self.world.transition)

    def test_same_marker_new_session_rejected_before_write(self):
        status,result=self.post('/town/livelihood-background',self.request,session='old')
        self.assertEqual(status,409,result);self.assertEqual(result['code'],'session_changed')
        self.assertIsNone(self.world.transition)

    def test_missing_checkpoint_and_unknown_fields_rejected(self):
        for payload in ({k:v for k,v in self.request.items() if k!='expected_checkpoint'},
                        {**self.request,'give_gold':100}):
            status,result=self.post('/town/livelihood-background',payload)
            self.assertEqual(status,400,result);self.assertIsNone(self.world.transition)

    def test_replaced_identity_rejects_apply(self):
        self.obs['residents'][0]['baseId']=71
        status,result=self.post('/town/livelihood-background',self.request)
        self.assertEqual(status,400,result);self.assertIn('identity',result['error'])
        self.assertIsNone(self.world.transition)

    def test_observer_preview_requires_token_and_session_and_returns_real_proposal(self):
        payload={**self.request,'expected_session':'startup'}
        status,_=self.post('/observer/livelihood-background/preview',payload)
        self.assertEqual(status,403)
        status,result=self.post('/observer/livelihood-background/preview',payload,observer=True)
        self.assertEqual(status,200,result);self.assertEqual(len(result['background']['assignments']),1)
        status,result=self.post('/observer/livelihood-background',self.request,observer=True)
        self.assertEqual(status,400,result);self.assertIn('session',result['error'])
        self.assertIsNone(self.world.transition)

    def test_boolean_checkpoint_is_not_integer_marker(self):
        status,result=self.post('/town/livelihood-background',{**self.request,'expected_checkpoint':True})
        self.assertEqual(status,400,result);self.assertIsNone(self.world.transition)

    def test_existing_initialization_route_honours_optional_marker(self):
        status,result=self.post('/town/initialize',{'id':'second','seed':'seed','expected_checkpoint':0})
        self.assertEqual(status,400,result);self.assertIn('checkpoint',result['error'])
        self.assertIsNone(self.world.transition)

    def test_census_rejects_same_checkpoint_roster_change(self):
        cohort=[{'actor':row['id'],'base_id':row['baseId']} for row in self.obs['residents']]
        self.obs['residents'][0]['baseId']=71
        status,result=self.post('/town/initialize',{'id':'second','seed':'seed',
            'expected_checkpoint':self.world.marker,'expected_cohort':cohort})
        self.assertEqual(status,400,result);self.assertIn('cohort changed',result['error'])
        self.assertIsNone(self.world.transition)

    def test_census_rejects_boolean_or_duplicate_identity_pin(self):
        for cohort in ([{'actor':True,'base_id':70}],
                       [{'actor':7,'base_id':70},{'actor':7,'base_id':70}]):
            status,result=self.post('/town/initialize',{'id':'second','seed':'seed',
                'expected_checkpoint':self.world.marker,'expected_cohort':cohort})
            self.assertEqual(status,400,result);self.assertIsNone(self.world.transition)
