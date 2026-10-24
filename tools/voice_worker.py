"""Bounded local voice child, warmed during approach; no TCP service or retries."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time


class VoiceWorker:
    def __init__(self, root, limit=6, credential_names=()):
        self.responses=queue.Queue();self.sequence=0;self.limit=limit;self.ready=None
        self.log=(root/'runtime/voice-worker.log').open('a',encoding='utf-8')
        environment={k:v for k,v in os.environ.items() if k not in credential_names}
        try:
            self.process=subprocess.Popen([str(root/'voice-venv/Scripts/python.exe'),
                str(Path(__file__).with_name('synthesize_voice.py')),'--root',str(root),'--serve','--max-requests',str(limit)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except Exception:
            self.log.close();raise
        threading.Thread(target=self._read,daemon=True).start()

    def _read(self):
        try:
            while True:
                line=self.process.stdout.readline(65537)
                if not line:break
                if len(line)>65536:raise ValueError('Oversized voice response')
                self.responses.put(json.loads(line))
        except (OSError,ValueError):pass
        finally:self.responses.put({'error':'Voice worker closed its output'})

    def synthesize(self,text,voice,timeout=90):
        if self.sequence>=self.limit:raise ValueError('Voice request budget exhausted')
        deadline=time.monotonic()+timeout
        def receive():
            try:return self.responses.get(timeout=max(.001,deadline-time.monotonic()))
            except queue.Empty:raise TimeoutError('Voice worker timed out') from None
        if self.ready is None:
            self.ready=receive()
            if self.ready.get('ready') is not True:raise ValueError(self.ready.get('error','Voice worker did not become ready'))
        self.sequence+=1;request_id='voice-'+str(self.sequence)
        self.process.stdin.write((json.dumps({'id':request_id,'text':text,'voice':voice})+'\n').encode())
        self.process.stdin.flush();result=receive()
        if result.get('id')!=request_id or result.get('error'):
            raise ValueError(result.get('error','Voice response identity mismatch'))
        return result

    def close(self):
        try:
            try:self.process.stdin.close()
            except OSError:pass
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
        finally:
            self.process.stdout.close();self.log.close()
