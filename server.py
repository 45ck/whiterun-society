"""Local development bridge. No hosted services, telemetry uploads or model calls."""
import argparse
import json
import secrets
import re
import time
import os
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from society import Society
from lineage import TimelineEconomy


class LocalServer(HTTPServer):
    # Windows SO_REUSEADDR can admit a second listener on the same endpoint.
    # Claim the socket exclusively before publishing runtime credentials.
    allow_reuse_address = os.name != 'nt'

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--port', type=int, default=17841)
    args=parser.parse_args()
    args.runtime.mkdir(parents=True, exist_ok=True)
    token=secrets.token_hex(32)
    config_path=args.runtime/'bridge-config.json'
    sim=Society(args.runtime/'society.sqlite')
    sim.seed()
    world=TimelineEconomy(args.runtime/'timeline.sqlite')
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
                connected=bridge['last_seen'] is not None and time.time()-bridge['last_seen']<10
                observation=bridge['observation'] or {}
                self.reply(200,{'service':'whiterun-society','protocol':1,'status':'running',
                    'bridge_connected':connected,'observer_ready':connected and observation.get('ready') is True,
                    'residents_loaded':len(observation.get('residents',[])) if connected else 0})
            elif self.path=='/state' and self.headers.get('Authorization')=='Bearer '+token:
                self.reply(200,{'bridge':bridge,'simulation':sim.state(),'world':world.state(),'society':world.status()})
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
                    ack=data.get('ack')
                    if ack is not None and not isinstance(ack,dict): raise ValueError('invalid acknowledgement')
                    if not isinstance(data.get('residents',[]),list): raise ValueError('invalid residents')
                    bridge.update(last_seen=time.time(),observation=data,session=session)
                    world.observe(data)
                    if ack:
                        bridge['last_ack']=ack
                        if bridge['command'] and ack.get('id')==bridge['command']['id']:
                            bridge['command']=None
                    with (args.runtime/'bridge-events.jsonl').open('a',encoding='utf-8') as log:
                        log.write(json.dumps({'at':time.time(),'observation':data})+'\n')
                    journal=world.state()
                    presentation={'committedCount':sum(row['status']=='committed' for row in journal),
                        'trades':[{**json.loads(row['command']),'status':row['status']} for row in journal[-5:]],
                        'society':world.status()}
                    try:
                        proposals=json.loads((args.runtime/'decision-proposals.json').read_text(encoding='utf-8'))
                        if proposals.get('session')==session and proposals.get('status') in ('running','complete'):
                            presentation['decisions']=[{'actor_id':item['actor_id'],'name':item['name'],
                                'decision':item['decision'],'elapsed_seconds':item['elapsed_seconds']}
                                for item in proposals.get('results',[])]
                    except (OSError,ValueError,KeyError,TypeError):
                        pass
                    self.reply(200,{'command':world.pending(session) or bridge['command'],'presentation':presentation})
                elif self.path=='/world/bootstrap':
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    self.reply(202,world.bootstrap(bridge['observation']))
                elif self.path=='/world/setup-production':
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command']: raise ValueError('another command is pending')
                    self.reply(202,world.setup_production(bridge['observation']))
                elif self.path=='/world/trade':
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command'] or world.agency_busy(): raise ValueError('another command or resident plan is pending')
                    result=world.plan_trade(data['id'],bridge['observation'],data['buyer'],data['seller'],
                        data.get('quantity',1),data.get('unit_price',3))
                    self.reply(202,result)
                elif self.path in ('/market-day/start','/market-day/advance'):
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command']: raise ValueError('another command is pending')
                    if self.path=='/market-day/start':result=world.start_market_day(data['id'],bridge['observation'])
                    else:result=world.advance_market_day(data['id'],data['event_id'],bridge['observation'])
                    self.reply(202,result)
                elif self.path in ('/agency/event','/agency/claim','/agency/decision','/agency/hold'):
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command']: raise ValueError('another command is pending')
                    observation=bridge['observation']
                    if self.path=='/agency/event': result=world.begin_plan(data['id'],observation,data.get('actor',108186),data.get('kind','meal_time'))
                    elif self.path=='/agency/claim': result=world.claim_plan_decision(data['id'],observation)
                    elif self.path=='/agency/decision': result=world.finish_plan_decision(data['id'],data['claim_id'],data['result'],observation)
                    else: result=world.hold_plan(data['id'],data['reason'],observation)
                    self.reply(202,result)
                elif self.path=='/command':
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command'] or world.pending(bridge['session']): raise ValueError('command pending')
                    if data.get('kind') not in ('notify','look_at_player','save_game','load_game','prepare_market','walk_to'): raise ValueError('unknown command')
                    if world.agency_busy() and data['kind'] in ('prepare_market','walk_to'):
                        raise ValueError('A resident currently owns the task')
                    if data['kind']=='walk_to':
                        if data.get('method','path') not in ('path','offset','package'): raise ValueError('Unsupported movement method')
                        if data.get('actor') not in (108149,108186,108156) or data.get('target') not in (108149,108186,108156) or data['actor']==data['target']:
                            raise ValueError('Choose two different demo residents')
                    if data['kind']=='prepare_market' and bridge['observation'].get('checkpoint')!=0:
                        raise ValueError('Demo stock is only added before a new-world bootstrap')
                    if data['kind'] in ('save_game','load_game'):
                        name=data.get('name','')
                        if not isinstance(name,str) or not re.fullmatch(r'WS-[A-Za-z0-9_-]{1,48}',name):
                            raise ValueError('Use an isolated WS- save name')
                        path=args.runtime.parent/'mod-organizer/profiles/Default/saves'/ (name+'.ess')
                        if data['kind']=='save_game' and (path.exists() or world.status()['error'] or world.transition):
                            raise ValueError('Save already exists or society is not synchronized')
                        if data['kind']=='load_game' and not path.is_file(): raise ValueError('Isolated save not found')
                    command={'id':secrets.token_hex(8),'kind':data['kind'],'session':bridge['session']}
                    if data['kind'] in ('save_game','load_game'): command['name']=data['name']
                    if data['kind']=='walk_to': command.update(actor=data['actor'],target=data['target'],method=data.get('method','path'))
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

    # Publish authority only after binding succeeds. A new development instance
    # atomically takes over the config; this instance then exits itself cleanly.
    http=LocalServer(('127.0.0.1',args.port),Handler)
    config_tmp=args.runtime/f'bridge-config-{args.port}.tmp'
    config_tmp.write_text(json.dumps({'port':args.port,'token':token}))
    config_tmp.replace(config_path)
    http.timeout=1
    print(json.dumps({'listening':f'http://127.0.0.1:{args.port}','runtime':str(args.runtime)}),flush=True)
    try:
        while True:
            http.handle_request()
            current=json.loads(config_path.read_text())
            if current.get('port')!=args.port or current.get('token')!=token:
                print('Development service superseded; exiting this instance',flush=True)
                break
    finally:
        http.server_close()
        sim.db.close()
        world.db.close()

if __name__=='__main__': main()
