"""Local development bridge. No hosted services, telemetry uploads or model calls."""
import argparse
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from society import Society


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--port', type=int, default=17841)
    args=parser.parse_args()
    args.runtime.mkdir(parents=True, exist_ok=True)
    token=secrets.token_hex(32)
    (args.runtime/'bridge-config.json').write_text(json.dumps({'port':args.port,'token':token}))
    sim=Society(args.runtime/'society.sqlite')
    sim.seed()
    bridge={'last_seen':None,'observation':None,'session':None,'command':None,'last_ack':None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass

        def reply(self,status,payload):
            encoded=json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path=='/health':
                self.reply(200,{'status':'running','bridge_connected':bridge['last_seen'] is not None and time.time()-bridge['last_seen']<10})
            elif self.path=='/state' and self.headers.get('Authorization')=='Bearer '+token:
                self.reply(200,{'bridge':bridge,'simulation':sim.state()})
            else: self.reply(404,{'error':'not found'})

        def do_POST(self):
            if self.headers.get('Authorization')!='Bearer '+token:
                return self.reply(401,{'error':'unauthorized'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16384: raise ValueError('invalid body size')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict): raise ValueError('expected object')
                if self.path=='/heartbeat':
                    session=data.get('session')
                    if not isinstance(session,str) or len(session)>128: raise ValueError('invalid session')
                    if bridge['session']!=session:
                        bridge['command']=None  # Never replay actions across a game load.
                    bridge.update(last_seen=time.time(),observation=data,session=session)
                    ack=data.get('ack')
                    if ack:
                        bridge['last_ack']=ack
                        if bridge['command'] and ack.get('id')==bridge['command']['id']:
                            bridge['command']=None
                    with (args.runtime/'bridge-events.jsonl').open('a',encoding='utf-8') as log:
                        log.write(json.dumps({'at':time.time(),'observation':data})+'\n')
                    self.reply(200,{'command':bridge['command']})
                elif self.path=='/command':
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command']: raise ValueError('command pending')
                    if data.get('kind') not in ('notify','look_at_player'): raise ValueError('unknown command')
                    command={'id':secrets.token_hex(8),'kind':data['kind'],'session':bridge['session']}
                    bridge['command']=command
                    self.reply(202,command)
                elif self.path=='/scenario/shortage':
                    sim.shortage(data['id'])
                    self.reply(200,sim.state())
                elif self.path=='/scenario/trade':
                    self.reply(200,sim.trade(**data))
                else: self.reply(404,{'error':'not found'})
            except (ValueError,KeyError,TypeError) as error:
                self.reply(400,{'error':str(error)})

    print(json.dumps({'listening':f'http://127.0.0.1:{args.port}','runtime':str(args.runtime)}),flush=True)
    try: HTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
    finally: sim.db.close()

if __name__=='__main__': main()
