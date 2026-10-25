"""Local development bridge. No hosted services, telemetry uploads or model calls."""
import argparse
import json
import secrets
import re
import time
import os
import socket
import hashlib
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from society import Society
from lineage import TimelineEconomy
from observer import observer_state, camera_request
from director_control import DirectorControl
from doc_assets import documentation_asset


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
    observer_token=secrets.token_hex(24)
    config_path=args.runtime/'bridge-config.json'
    sim=Society(args.runtime/'society.sqlite')
    sim.seed()
    world=TimelineEconomy(args.runtime/'timeline.sqlite')
    bridge={'last_seen':None,'observation':None,'session':None,'command':None,'last_ack':None}
    director=DirectorControl(args.runtime)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass

        def checked_audio(self,data):
            audio=data['audio'];world.validate_audio_metadata(audio)
            asset=args.runtime.parent/'game/Data/Platform/UI/audio'/audio['file']
            if not asset.is_file() or asset.stat().st_size>2000000:raise ValueError('Missing or oversized speech asset')
            if hashlib.sha256(asset.read_bytes()).hexdigest()!=audio['sha256']:raise ValueError('Speech hash mismatch')
            with wave.open(str(asset),'rb') as wav:
                seconds=wav.getnframes()/wav.getframerate()
                if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or abs(seconds-audio['seconds'])>.01:raise ValueError('Speech format mismatch')
            return audio

        def reply(self,status,payload):
            encoded=json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path=='/docs' or self.path.startswith('/docs/'):
                if self.headers.get('Host')!=f'127.0.0.1:{args.port}':return self.reply(403,{'error':'Loopback host required'})
                if self.path=='/docs':
                    self.send_response(308);self.send_header('Location','/docs/');self.send_header('Content-Length','0');self.end_headers();return
                asset=documentation_asset(Path(__file__).parent,self.path)
                if asset is None:return self.reply(404,{'error':'not found'})
                kind,body=asset;self.send_response(200);self.send_header('Content-Type',kind)
                self.send_header('Content-Security-Policy',"default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'")
                self.send_header('X-Frame-Options','DENY');self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body);return
            if self.path=='/' or self.path.startswith('/observer'):
                if self.headers.get('Host')!=f'127.0.0.1:{args.port}':return self.reply(403,{'error':'Loopback host required'})
                if self.path=='/observer/state':return self.reply(200,{**observer_state(bridge,world.status()),'director':director.status()})
                if self.path not in ('/','/observer','/observer/'):return self.reply(404,{'error':'not found'})
                page=(Path(__file__).parent/'ui'/'observer.html').read_text(encoding='utf-8').replace('__OBSERVER_TOKEN__',observer_token).encode()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Options','DENY')
                self.send_header('Content-Length',str(len(page)));self.end_headers();self.wfile.write(page)
            elif self.path=='/health':
                connected=bridge['last_seen'] is not None and time.time()-bridge['last_seen']<10
                observation=bridge['observation'] or {}
                self.reply(200,{'service':'whiterun-society','protocol':1,'status':'running',
                    'bridge_connected':connected,'observer_ready':connected and observation.get('ready') is True,
                    'residents_loaded':len(observation.get('residents',[])) if connected else 0})
            elif self.path=='/state' and self.headers.get('Authorization')=='Bearer '+token:
                self.reply(200,{'bridge':bridge,'simulation':sim.state(),'world':world.state(),'society':world.status()})
            else: self.reply(404,{'error':'not found'})

        def do_POST(self):
            if self.path in ('/observer/camera', '/observer/enterprise', '/observer/director','/observer/conversation'):
                origin=f'http://127.0.0.1:{args.port}'
                if self.headers.get('Host')!=f'127.0.0.1:{args.port}' or self.headers.get('Origin')!=origin or self.headers.get('X-Observer-Token')!=observer_token:
                    return self.reply(403,{'error':'Same-origin observer control required'})
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=2048:raise ValueError('Invalid observer request size')
                    data=json.loads(self.rfile.read(length))
                    if not isinstance(data,dict):raise ValueError('Expected control object')
                    if self.path=='/observer/director':
                        if data.get('action')=='stop':return self.reply(202,director.stop())
                        if data.get('action')!='start':raise ValueError('Unknown society control')
                        return self.reply(202,director.start(data,bridge,world.status()))
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:raise ValueError('Game bridge unavailable')
                    if self.path=='/observer/conversation':
                        if data.get('action')!='interrupt':raise ValueError('Unknown conversation control')
                        return self.reply(202,world.interrupt_conversation(data['id'],bridge['observation']))
                    if self.path=='/observer/enterprise':
                        if bridge['command']:raise ValueError('Another command is pending')
                        return self.reply(202,world.configure_enterprise(data['id'],data['enterprise'],bridge['observation']))
                    request=camera_request(data,bridge['observation'],world.status())
                    request['request_id']=secrets.token_hex(8);bridge['observer_camera']=request
                    return self.reply(202,request)
                except (ValueError,TypeError,KeyError) as error:return self.reply(400,{'error':str(error)})
            if self.headers.get('Authorization')!='Bearer '+token:
                return self.reply(401,{'error':'unauthorized'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=65536: raise ValueError('invalid body size')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict): raise ValueError('expected object')
                if self.path=='/service/shutdown':
                    if director.status()['running'] or world.transition or bridge['command'] or world.agency_busy() or world.conversation_busy() or world.routines_busy() or (world.active and world.active.get('pending')):
                        raise ValueError('Settle active society work before restarting the service')
                    bridge['shutdown_requested']=True
                    return self.reply(202,{'status':'stopping','effects_in_flight':False})
                if self.path=='/heartbeat':
                    session=data.get('session')
                    if not isinstance(session,str) or len(session)>128: raise ValueError('invalid session')
                    if bridge['session']!=session:
                        bridge['command']=None  # Never replay actions across a game load.
                        bridge['observer_camera']=None
                    ack=data.get('ack')
                    if ack is not None and not isinstance(ack,dict): raise ValueError('invalid acknowledgement')
                    if not isinstance(data.get('residents',[]),list): raise ValueError('invalid residents')
                    assets=data.get('inventory_observations',[])
                    if not isinstance(assets,list) or len(assets)>128:raise ValueError('invalid bounded inventory observations')
                    bridge.update(last_seen=time.time(),observation=data,session=session)
                    if bridge.get('observer_camera') and (data.get('camera') or {}).get('request_id')==bridge['observer_camera']['request_id']:
                        bridge['observer_camera']=None
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
                        'society':world.status(),'director':director.status()}
                    try:
                        proposals=json.loads((args.runtime/'decision-proposals.json').read_text(encoding='utf-8'))
                        if proposals.get('session')==session and proposals.get('status') in ('running','complete'):
                            presentation['decisions']=[{'actor_id':item['actor_id'],'name':item['name'],
                                'decision':item['decision'],'elapsed_seconds':item['elapsed_seconds']}
                                for item in proposals.get('results',[])]
                    except (OSError,ValueError,KeyError,TypeError):
                        pass
                    self.reply(200,{'command':world.pending(session) or bridge['command'],'presentation':presentation,'observer_camera':bridge.get('observer_camera')})
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
                elif self.path in ('/town/initialize','/town/review','/town/endow','/town/enterprise','/town/social-background'):
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command']:raise ValueError('another command is pending')
                    if self.path=='/town/endow':result=world.plan_endowment(data['actor'],bridge['observation'])
                    elif self.path=='/town/social-background':result=world.establish_social_background(data['id'],data['cohort'],bridge['observation'])
                    elif self.path=='/town/enterprise':result=world.configure_enterprise(data['id'],data['enterprise'],bridge['observation'])
                    elif self.path=='/town/initialize':result=world.initialize_population(data['id'],data['seed'],bridge['observation'])
                    else:result=world.review_population(bridge['observation'])
                    self.reply(202,result)
                elif self.path.startswith('/conversation/'):
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command']: raise ValueError('another command is pending')
                    observation=bridge['observation']
                    if self.path=='/conversation/start': result=world.start_conversation(data['id'],observation,data.get('actor'),data.get('max_turns'))
                    elif self.path=='/conversation/claim': result=world.claim_conversation(data['id'],observation)
                    elif self.path=='/conversation/result': result=world.finish_conversation_inference(data['id'],data['claim_id'],data['result'],observation)
                    elif self.path=='/conversation/audio':
                        result=world.prepare_speech(data['id'],self.checked_audio(data),observation)
                    elif self.path=='/conversation/hold':result=world.hold_conversation(data['id'],data['reason'],observation)
                    else:raise ValueError('Unknown conversation operation')
                    self.reply(202,result)
                elif self.path in ('/market-day/start','/market-day/advance'):
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command']: raise ValueError('another command is pending')
                    if self.path=='/market-day/start':result=world.start_market_day(data['id'],bridge['observation'])
                    else:result=world.advance_market_day(data['id'],data['event_id'],bridge['observation'])
                    self.reply(202,result)
                elif self.path in ('/routines/start','/routines/decisions','/routines/hold'):
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:raise ValueError('game bridge unavailable')
                    if bridge['command']:raise ValueError('another command is pending')
                    observation=bridge['observation']
                    if self.path=='/routines/start':result=world.begin_routines(data['id'],data['event_ids'],observation,data.get('background',False))
                    elif self.path=='/routines/decisions':result=world.finish_routines(data['id'],data['claim_id'],data['results'],observation)
                    else:result=world.hold_routines(data['id'],data['reason'],observation)
                    self.reply(202,result)
                elif self.path in ('/agency/event','/agency/claim','/agency/decision','/agency/hold','/agency/audio'):
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command']: raise ValueError('another command is pending')
                    observation=bridge['observation']
                    if self.path=='/agency/event': result=world.begin_plan(data['id'],observation,data.get('actor',108186),data.get('kind','meal_time'),data.get('voiced_trade',False))
                    elif self.path=='/agency/audio':result=world.prepare_trade_speech(data['id'],self.checked_audio(data),observation)
                    elif self.path=='/agency/claim': result=world.claim_plan_decision(data['id'],observation)
                    elif self.path=='/agency/decision': result=world.finish_plan_decision(data['id'],data['claim_id'],data['result'],observation)
                    else: result=world.hold_plan(data['id'],data['reason'],observation)
                    self.reply(202,result)
                elif self.path=='/command':
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command'] or world.pending(bridge['session']): raise ValueError('command pending')
                    if data.get('kind') not in ('notify','look_at_player','save_game','load_game','prepare_market','walk_to'): raise ValueError('unknown command')
                    if (world.agency_busy() or world.conversation_busy() or world.routines_busy()) and data['kind'] in ('prepare_market','walk_to'):
                        raise ValueError('A resident currently owns the task')
                    if data['kind']=='walk_to':
                        if data.get('method','path') not in ('path','offset','package'): raise ValueError('Unsupported movement method')
                        if data.get('dynamic') is True:
                            observed={a['id'] for a in bridge['observation']['residents'] if a.get('isPerson') is True}
                            managed=set((world.status().get('town') or {}).get('residents',{}))
                            if data.get('method')!='package' or any(type(data.get(k)) is not int or data[k] not in observed or str(data[k]) not in managed for k in ('actor','target')) or data['actor']==data['target']:
                                raise ValueError('Dynamic travel requires two observed, initialized adult residents')
                        elif data.get('actor') not in (108149,108186,108156) or data.get('target') not in (108149,108186,108156) or data['actor']==data['target']:
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
                    if data['kind']=='walk_to': command.update(actor=data['actor'],target=data['target'],method=data.get('method','path'),dynamic=data.get('dynamic') is True)
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
            if bridge.get('shutdown_requested'):break
            current=json.loads(config_path.read_text())
            if current.get('port')!=args.port or current.get('token')!=token:
                print('Development service superseded; exiting this instance',flush=True)
                break
    finally:
        director.stop()
        http.server_close()
        sim.db.close()
        world.db.close()

if __name__=='__main__': main()
