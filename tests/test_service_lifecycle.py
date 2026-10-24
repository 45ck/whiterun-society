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
                authority=config.read_text()
                collision=start(first_port)
                self.assertNotEqual(collision.wait(timeout=20),0)
                self.assertEqual(config.read_text(),authority)
                self.assertIsNone(first.poll())
                second_port=free_port();second=start(second_port);ready(second_port)
                self.assertEqual(first.wait(timeout=10),0)
                self.assertEqual(json.loads(config.read_text())['port'],second_port)
                self.assertIsNone(second.poll())
            finally:
                # These are this test's subprocess handles only, never live lab services.
                config.write_text(json.dumps({'port':0,'token':'test-finished'}))
                for p in processes:
                    try:p.wait(timeout=10)
                    except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
                    p.stdout.close();p.stderr.close()
