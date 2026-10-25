import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request


class ServiceLifecycleTests(unittest.TestCase):
    def test_replacement_exits_old_instance_and_failed_bind_preserves_authority(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder)
            config=runtime/'bridge-config.json'
            processes=[]

            def free_port():
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1',0))
                    return sock.getsockname()[1]

            def start(port):
                p=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'server.py'),
                    '--runtime',folder,'--port',str(port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                processes.append(p)
                return p

            def ready(port):
                deadline=time.monotonic()+20
                while time.monotonic()<deadline:
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=1) as response:
                            if json.load(response)['service']=='whiterun-society':return
                    except OSError:
                        time.sleep(.1)
                self.fail('Test service did not become ready')

            try:
                first_port=free_port();first=start(first_port);ready(first_port)
                origin=f'http://127.0.0.1:{first_port}'
                with urllib.request.urlopen(origin+'/observer') as response:
                    page=response.read().decode()
                    self.assertIn('Society control room',page)
                    self.assertEqual(response.headers['X-Frame-Options'],'DENY')
                import re
                observer_token=re.search("const token='([^']+)'",page).group(1)
                with urllib.request.urlopen(origin+'/observer/state') as response:
                    self.assertFalse(json.load(response)['connected'])
                with urllib.request.urlopen(origin+'/docs') as response:
                    self.assertEqual(response.url,origin+'/docs/')
                    self.assertIn('Whiterun',response.read().decode())
                for route in ('/observer/camera','/observer/enterprise','/observer/director','/observer/conversation'):
                    for headers in ({},{'Origin':'https://unrelated.example','X-Observer-Token':observer_token},
                                    {'Origin':origin,'X-Observer-Token':'wrong'}):
                        req=urllib.request.Request(origin+route,data=b'{"mode":"market"}',headers=headers)
                        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
                        self.assertEqual(error.exception.code,403)
                auth={'Authorization':'Bearer '+json.loads(config.read_text())['token'],'Content-Type':'application/json'}
                def post(route,data,headers=auth):
                    with urllib.request.urlopen(urllib.request.Request(origin+route,data=json.dumps(data).encode(),headers=headers)) as response:
                        return json.load(response)
                observation={'session':'test-session','ready':True,'checkpoint':0,'gameDays':1,
                    'residents':[{'id':7,'baseId':100007,'name':'New founder','isPerson':True,'isGuard':False,'inventory':{'gold':12,'bread':0,'grain':2}}]}
                post('/heartbeat',observation)
                observation['checkpoint']=post('/world/bootstrap',{})['checkpoint']
                with self.assertRaises(urllib.error.HTTPError) as unsettled:
                    post('/service/shutdown',{})
                self.assertEqual(unsettled.exception.code,400)
                self.assertIsNone(first.poll())
                post('/heartbeat',observation)
                observation['checkpoint']=post('/town/initialize',{'id':'census','seed':'test'})['checkpoint'];post('/heartbeat',observation)
                observation['director_control']={'id':'pause-from-game','action':'pause'}
                control_reply=post('/heartbeat',observation)
                self.assertEqual(control_reply['director_control_receipt']['status'],'accepted')
                observation['director_control']['action']='play'
                self.assertEqual(post('/heartbeat',observation)['director_control_receipt']['action'],'pause')
                observation['director_control']={'id':'play-without-configuration','action':'play'}
                self.assertEqual(post('/heartbeat',observation)['director_control_receipt']['status'],'rejected')
                observation.pop('director_control')
                self.assertEqual(control_reply['presentation']['dashboard']['population'],1)
                for invalid in (None,True,'',' '*5,'x'*161):
                    with self.assertRaises(urllib.error.HTTPError) as invalid_output:
                        post('/command',{'kind':'select_voice_output','output':invalid})
                    self.assertEqual(invalid_output.exception.code,400)
                output_command=post('/command',{'kind':'select_voice_output','output':' Realtek '})
                self.assertEqual(output_command['output'],'Realtek')
                observation['ack']={'id':output_command['id'],'status':'applied'}
                post('/heartbeat',observation);observation.pop('ack')
                specification={'id':'new-bakery','expected_revision':0,'name':'New bakery','custodian':7,
                    'active':True,'capabilities':['bread_recipe','retail_food'],'production_policy':{'wage_gold':4}}
                observer_headers={'Origin':origin,'X-Observer-Token':observer_token,'Content-Type':'application/json'}
                self.assertEqual(post('/observer/director',{'action':'stop'},observer_headers)['status'],'idle')
                with self.assertRaises(urllib.error.HTTPError) as missing_config:
                    post('/observer/director',{'action':'start','max_events':2},observer_headers)
                self.assertEqual(missing_config.exception.code,400)
                result=post('/observer/enterprise',{'id':'charter','enterprise':specification},observer_headers)
                observation['checkpoint']=result['checkpoint'];post('/heartbeat',observation)
                with urllib.request.urlopen(origin+'/observer/state') as response:projection=json.load(response)
                self.assertEqual(projection['businesses'][0]['production_policy']['wage_gold'],4)
                self.assertEqual(projection['businesses'][0]['observed_inventory'],{'gold':12,'bread':0,'grain':2})
                self.assertTrue(post('/observer/enterprise',{'id':'charter','enterprise':specification},observer_headers)['duplicate'])
                with self.assertRaises(urllib.error.HTTPError) as error:
                    post('/observer/enterprise',{'id':'stale-edit','enterprise':specification},observer_headers)
                self.assertEqual(error.exception.code,400)
                authority=config.read_text()
                collision=start(first_port)
                self.assertNotEqual(collision.wait(timeout=20),0)
                self.assertEqual(config.read_text(),authority)
                self.assertIsNone(first.poll())
                second_port=free_port();second=start(second_port);ready(second_port)
                self.assertEqual(first.wait(timeout=10),0)
                self.assertEqual(json.loads(config.read_text())['port'],second_port)
                self.assertIsNone(second.poll())
                second_auth={'Authorization':'Bearer '+json.loads(config.read_text())['token'],'Content-Type':'application/json'}
                request=urllib.request.Request(f'http://127.0.0.1:{second_port}/service/shutdown',data=b'{}',headers=second_auth)
                with urllib.request.urlopen(request) as response:self.assertEqual(json.load(response)['status'],'stopping')
                self.assertEqual(second.wait(timeout=10),0)
            finally:
                # These are this test's subprocess handles only, never live lab services.
                config.write_text(json.dumps({'port':0,'token':'test-finished'}))
                for p in processes:
                    try:p.wait(timeout=10)
                    except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
                    p.stdout.close();p.stderr.close()
