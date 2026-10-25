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
from dashboard import town_dashboard
from spatial_telemetry import SpatialTelemetry
from employment_concurrency_metrics import EmploymentConcurrencyTelemetry
from tools.checkpoint_http import checkpoint_rejection
from routing import route_available
from livelihood_backgrounds import preview_livelihood_background
from population import eligible_actors


def validate_startup_checkpoint(world, observation, data, *, required=False, require_session=False):
    """Pin a reviewed startup change before the single writer can mutate it."""
    if required or 'expected_checkpoint' in data:
        marker=data.get('expected_checkpoint')
        if (type(marker) is not int or marker!=world.marker or world.transition
                or not isinstance(observation,dict) or observation.get('checkpoint')!=marker):
            raise ValueError('Startup checkpoint changed; preview again before applying')
    if require_session or 'expected_session' in data:
        session=data.get('expected_session')
        if (not isinstance(session,str) or not session or session!=world.session
                or not isinstance(observation,dict) or observation.get('session')!=session):
            raise ValueError('Startup session changed; preview again before applying')


def begin_livelihood_background(world, observation, data, *, preview=False, observer=False):
    fields={'id','seed','scenario_id','scenario_hash','actor_ids','expected_checkpoint'}
    if (not isinstance(data,dict) or not fields<=set(data)
            or set(data)-fields-{'expected_session'}):
        raise ValueError('Explicit livelihood scenario, cohort and checkpoint are required')
    validate_startup_checkpoint(world,observation,data,required=True,require_session=observer)
    world._agency_guard(observation)
    args=(data['id'],data['seed'],data['scenario_id'],data['scenario_hash'],data['actor_ids'])
    if preview:
        return preview_livelihood_background(world.active,observation,*args)
    return world.establish_livelihood_background(*args,observation)


def validate_census_cohort(observation, data):
    """Optional exact roster pin for previewed startup tools, checked atomically."""
    if 'expected_cohort' not in data:return
    cohort=data['expected_cohort']
    if (not isinstance(cohort,list) or not 1<=len(cohort)<=128
            or any(not isinstance(row,dict) or set(row)!={'actor','base_id'}
                   or any(type(row[key]) is not int or not 0<row[key]<=0xffffffff
                          for key in ('actor','base_id')) for row in cohort)
            or len({row['actor'] for row in cohort})!=len(cohort)):
        raise ValueError('An exact bounded actor/base census cohort is required')
    actual=[{'actor':row['id'],'base_id':row.get('baseId')} for row in eligible_actors(observation)]
    if sorted(cohort,key=lambda row:row['actor'])!=sorted(actual,key=lambda row:row['actor']):
        raise ValueError('Census cohort changed; preview again before applying')


def begin_agency_event(world, observation, data):
    """Dispatch an event without selecting a resident on the caller's behalf."""
    return world.begin_plan(data['id'], observation, data.get('actor'),
        data.get('kind', 'meal_time'), data.get('voiced_trade', False), data.get('natural_trade', False))


def begin_trade_event(world, observation, data):
    """Forward explicit public trade terms without silently changing the good."""
    allowed={'id','buyer','seller','quantity','unit_price','commodity'}
    if not isinstance(data,dict) or set(data)-allowed or not {'id','buyer','seller'}<=set(data):
        raise ValueError('Invalid trade request fields')
    commodity=data.get('commodity','bread')
    if not isinstance(commodity,str) or not commodity:
        raise ValueError('Trade commodity must be a nonempty catalog ID')
    return world.plan_trade(data['id'],observation,data['buyer'],data['seller'],
        data.get('quantity',1),data.get('unit_price',3),commodity=commodity)


def begin_endowment_event(world, observation, data):
    """An operator explicitly selects a reviewed finite scenario; no default."""
    if not isinstance(data,dict) or set(data)!={'actor','scenario_id','scenario_hash'}:
        raise ValueError('Endowment requires exactly actor, scenario_id and scenario_hash')
    if type(data['actor']) is not int or not 0<data['actor']<=0xffffffff:
        raise ValueError('Endowment actor must be a positive integer')
    if not isinstance(data['scenario_id'],str) or not data['scenario_id']:
        raise ValueError('An explicit resource scenario ID is required')
    if not isinstance(data['scenario_hash'],str) or not re.fullmatch('[0-9a-f]{64}',data['scenario_hash']):
        raise ValueError('An exact resource scenario hash is required')
    return world.plan_endowment(data['actor'],observation,data['scenario_id'],data['scenario_hash'])


def begin_conversation_event(world, observation, data, *, scenario=False):
    """Authored demonstrations have a separate explicit admission boundary."""
    allowed={'id','scenario','reply_policy'} if scenario else {'id','actor','max_turns','opportunity_batch','reply_policy'}
    if not isinstance(data,dict) or set(data)-allowed or 'id' not in data:
        raise ValueError('Invalid scenario request fields' if scenario else 'Invalid ordinary conversation request fields')
    if scenario:
        if 'scenario' not in data:raise ValueError('An explicit scenario definition is required')
        return world.start_scenario_conversation(data['id'],observation,data['scenario'],
            reply_policy=data.get('reply_policy','separate_choice'))
    return world.start_conversation(data['id'],observation,data.get('actor'),data.get('max_turns'),
        data.get('opportunity_batch'),data.get('reply_policy','combined_choice'))


def authored_walk_command(world, observation, data, session, command_id):
    """A new operator request uses the same current route evidence as agents."""
    world._agency_guard(observation)
    if session != world.session:
        raise ValueError('Travel belongs to another game session')
    if data.get('method', 'package') != 'package' or data.get('dynamic', True) is not True:
        raise ValueError('Travel requires the dynamic mailbox package protocol')
    for key in ('actor', 'target'):
        value=data.get(key)
        if type(value) is not int or not 0 < value <= 0xffffffff or str(value) not in world.active['people']:
            raise ValueError('Explicit initialized resident actor and target are required')
    if not route_available(observation,data['actor'],data['target'],world.active):
        raise ValueError('Two available observed residents and current mailbox capability are required')
    return {'id':command_id,'kind':'walk_to','actor':data['actor'],'target':data['target'],
        'method':'package','dynamic':True,'origin':'operator_request',
        'session':session,'checkpoint':world.marker}


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
    spatial=SpatialTelemetry(args.runtime/'spatial-telemetry.jsonl')
    employment_concurrency=EmploymentConcurrencyTelemetry()

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
                self.send_header('Content-Security-Policy',"default-src 'none'; img-src 'self'; media-src 'self'; style-src 'unsafe-inline'; base-uri 'none'")
                self.send_header('X-Frame-Options','DENY');self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body);return
            if self.path=='/' or self.path.startswith('/observer'):
                if self.headers.get('Host')!=f'127.0.0.1:{args.port}':return self.reply(403,{'error':'Loopback host required'})
                if self.path=='/observer/state':return self.reply(200,{**observer_state({**bridge,'spatial':spatial.status(bridge['session']),
                    'employment_concurrency':employment_concurrency.status(bridge['session'])},world.status()),'director':director.status()})
                if self.path not in ('/','/observer','/observer/'):return self.reply(404,{'error':'not found'})
                page=(Path(__file__).parent/'ui'/'observer.html').read_text(encoding='utf-8').replace('__OBSERVER_TOKEN__',observer_token)
                page=page.replace('<script>','<script>\n'+(Path(__file__).parent/'ui/resident-media-data.js').read_text(encoding='utf-8')+"\nwindow.RESIDENT_MEDIA_BASE='/docs/images/';\n"+(Path(__file__).parent/'ui/resident-media.js').read_text(encoding='utf-8')+'\n'+(Path(__file__).parent/'ui/society-dashboard.js').read_text(encoding='utf-8')+'\n',1).encode()
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
            if self.path in ('/observer/camera', '/observer/enterprise', '/observer/director','/observer/conversation','/observer/scene-handoff','/observer/livelihood-background','/observer/livelihood-background/preview'):
                origin=f'http://127.0.0.1:{args.port}'
                if self.headers.get('Host')!=f'127.0.0.1:{args.port}' or self.headers.get('Origin')!=origin or self.headers.get('X-Observer-Token')!=observer_token:
                    return self.reply(403,{'error':'Same-origin observer control required'})
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=8192:raise ValueError('Invalid observer request size')
                    data=json.loads(self.rfile.read(length))
                    if not isinstance(data,dict):raise ValueError('Expected control object')
                    if self.path=='/observer/director':
                        return self.reply(202,director.control(data,bridge,world.status()))
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:raise ValueError('Game bridge unavailable')
                    if self.path.startswith('/observer/livelihood-background'):
                        preview=self.path.endswith('/preview')
                        if not preview and director.status()['running']:raise ValueError('Pause the director before applying starting backgrounds')
                        if bridge['command']:raise ValueError('Another command is pending')
                        return self.reply(200 if preview else 202,begin_livelihood_background(world,bridge['observation'],data,preview=preview,observer=True))
                    if self.path=='/observer/scene-handoff':
                        if director.status()['running']:raise ValueError('Stop the society director before a manual scene handoff')
                        if bridge['command']:raise ValueError('Another command is pending')
                        return self.reply(202,world.request_scene_handoff(data['id'],data['actor'],data['scene_id'],bridge['observation']))
                    if self.path=='/observer/conversation':
                        if data.get('action')!='interrupt':raise ValueError('Unknown conversation control')
                        return self.reply(202,world.interrupt_conversation(data['id'],bridge['observation']))
                    if self.path=='/observer/enterprise':
                        if bridge['command']:raise ValueError('Another command is pending')
                        validate_startup_checkpoint(world,bridge['observation'],data)
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
                rejected=checkpoint_rejection(self.path,self.headers.get('X-Society-Session'),bridge['session'],world.transition,
                    native_effect=bool(bridge['command'] or world.active and world.active.get('pending')))
                if rejected:return self.reply(409,rejected)
                if self.path=='/service/shutdown':
                    if director.status()['running'] or world.transition or bridge['command'] or world.agency_busy() or world.conversation_busy() or world.routines_busy() or (world.active and world.active.get('pending')) or world.activity_status()['jobs'] or world.owner_work_status()['jobs'] or world.paid_employment_status()['jobs']:
                        raise ValueError('Settle active society work before restarting the service')
                    bridge['shutdown_requested']=True
                    return self.reply(202,{'status':'stopping','effects_in_flight':False})
                if self.path=='/heartbeat':
                    session=data.get('session')
                    if not isinstance(session,str) or len(session)>128: raise ValueError('invalid session')
                    if bridge['session']!=session:
                        bridge['command']=None  # Never replay actions across a game load.
                        bridge['observer_camera']=None
                        bridge['director_control_receipt']=None
                    ack=data.get('ack')
                    if ack is not None and not isinstance(ack,dict): raise ValueError('invalid acknowledgement')
                    if not isinstance(data.get('residents',[]),list): raise ValueError('invalid residents')
                    assets=data.get('inventory_observations',[])
                    if not isinstance(assets,list) or len(assets)>128:raise ValueError('invalid bounded inventory observations')
                    bridge.update(last_seen=time.time(),observation=data,session=session)
                    if bridge.get('observer_camera') and (data.get('camera') or {}).get('request_id')==bridge['observer_camera']['request_id']:
                        bridge['observer_camera']=None
                    world.observe(data)
                    control=data.get('director_control')
                    if control is not None and not isinstance(control,dict):raise ValueError('Invalid in-game society control')
                    if control and control.get('id')!=(bridge.get('director_control_receipt') or {}).get('id'):
                        if not isinstance(control.get('id'),str) or not 1<=len(control['id'])<=128 or control.get('action') not in ('play','pause'):
                            raise ValueError('Invalid in-game society control')
                        receipt={'id':control['id'],'action':control['action']}
                        try:
                            director.control({'action':control['action']},bridge,world.status())
                            receipt['status']='accepted'
                        except ValueError as error:receipt.update(status='rejected',error=str(error))
                        bridge['director_control_receipt']=receipt
                    if ack:
                        bridge['last_ack']=ack
                        if bridge['command'] and ack.get('id')==bridge['command']['id']:
                            bridge['command']=None
                    with (args.runtime/'bridge-events.jsonl').open('a',encoding='utf-8') as log:
                        log.write(json.dumps({'at':time.time(),'observation':data})+'\n')
                    journal=world.state()
                    society_status=world.status()
                    spatial.observe(data,society_status)
                    bridge['spatial']=spatial.status(session)
                    bridge['employment_concurrency']=employment_concurrency.observe(society_status,data)
                    presentation={'committedCount':sum(row['status']=='committed' for row in journal),
                        'trades':[{**json.loads(row['command']),'status':row['status']} for row in journal[-5:]],
                        'society':society_status,'director':director.status(),'director_control_receipt':bridge.get('director_control_receipt'),
                        'dashboard':{**town_dashboard(society_status,data,bridge['spatial']),
                                     'paid_employment_metrics':society_status['paid_employment_metrics'],
                                     'employment_concurrency_metrics':bridge['employment_concurrency']}}
                    try:
                        proposals=json.loads((args.runtime/'decision-proposals.json').read_text(encoding='utf-8'))
                        if proposals.get('session')==session and proposals.get('status') in ('running','complete'):
                            presentation['decisions']=[{'actor_id':item['actor_id'],'name':item['name'],
                                'decision':item['decision'],'elapsed_seconds':item['elapsed_seconds']}
                                for item in proposals.get('results',[])]
                    except (OSError,ValueError,KeyError,TypeError):
                        pass
                    self.reply(200,{'command':world.pending(session) or bridge['command'],'presentation':presentation,'observer_camera':bridge.get('observer_camera'),'director_control_receipt':bridge.get('director_control_receipt')})
                elif self.path in ('/goals/claim','/goals/result'):
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:raise ValueError('Game bridge unavailable')
                    if bridge['command']:raise ValueError('Another native command is pending')
                    if self.path=='/goals/claim':result=world.claim_resident_goals(data['id'],bridge['observation'],data.get('limit',32))
                    else:result=world.finish_resident_goals(data['id'],data['claim_id'],data['results'],bridge['observation'])
                    self.reply(202,result)
                elif self.path=='/town/resident-control':
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:raise ValueError('Game bridge unavailable')
                    if director.status()['running']:raise ValueError('Pause the director before changing resident control')
                    result=world.configure_resident_control(data.get('id'),data.get('enabled'),bridge['observation'])
                    self.reply(202,result)
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
                    result=begin_trade_event(world,bridge['observation'],data)
                    self.reply(202,result)
                elif self.path in ('/town/initialize','/town/review','/town/endow','/town/enterprise','/town/social-background','/town/scene-handoff','/town/livelihood-background','/town/livelihood-background/preview'):
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command']:raise ValueError('another command is pending')
                    if self.path.startswith('/town/livelihood-background'):
                        preview=self.path.endswith('/preview')
                        if not preview and director.status()['running']:raise ValueError('Pause the director before applying starting backgrounds')
                        return self.reply(200 if preview else 202,begin_livelihood_background(world,bridge['observation'],data,preview=preview))
                    if self.path in ('/town/initialize','/town/enterprise','/town/social-background'):
                        validate_startup_checkpoint(world,bridge['observation'],data)
                    if self.path=='/town/scene-handoff':result=world.request_scene_handoff(data['id'],data['actor'],data['scene_id'],bridge['observation'])
                    elif self.path=='/town/endow':result=begin_endowment_event(world,bridge['observation'],data)
                    elif self.path=='/town/social-background':result=world.establish_social_background(data['id'],data['cohort'],bridge['observation'])
                    elif self.path=='/town/enterprise':result=world.configure_enterprise(data['id'],data['enterprise'],bridge['observation'])
                    elif self.path=='/town/initialize':
                        validate_census_cohort(bridge['observation'],data)
                        result=world.initialize_population(data['id'],data['seed'],bridge['observation'])
                    else:result=world.review_population(bridge['observation'])
                    self.reply(202,result)
                elif self.path.startswith('/conversation/'):
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command']: raise ValueError('another command is pending')
                    observation=bridge['observation']
                    if self.path=='/conversation/start': result=begin_conversation_event(world,observation,data)
                    elif self.path=='/conversation/scenario': result=begin_conversation_event(world,observation,data,scenario=True)
                    elif self.path=='/conversation/claim': result=world.claim_conversation(data['id'],observation)
                    elif self.path=='/conversation/result': result=world.finish_conversation_inference(data['id'],data['claim_id'],data['result'],observation)
                    elif self.path=='/conversation/audio':
                        result=world.prepare_speech(data['id'],self.checked_audio(data),observation)
                    elif self.path=='/conversation/hold':result=world.hold_conversation(data['id'],data['reason'],observation,inference_failure=data.get('inference_failure'))
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
                elif self.path in ('/agency/event','/agency/claim','/agency/decision','/agency/hold','/agency/audio','/agency/wording-claim','/agency/wording-result'):
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command']: raise ValueError('another command is pending')
                    observation=bridge['observation']
                    if self.path=='/agency/event': result=begin_agency_event(world,observation,data)
                    elif self.path=='/agency/wording-claim':result=world.claim_economic_wording(data['id'],observation)
                    elif self.path=='/agency/wording-result':result=world.finish_economic_wording(data['id'],data['claim_id'],data['result'],observation)
                    elif self.path=='/agency/audio':result=world.prepare_trade_speech(data['id'],self.checked_audio(data),observation)
                    elif self.path=='/agency/claim': result=world.claim_plan_decision(data['id'],observation)
                    elif self.path=='/agency/decision': result=world.finish_plan_decision(data['id'],data['claim_id'],data['result'],observation)
                    else: result=world.hold_plan(data['id'],data['reason'],observation)
                    self.reply(202,result)
                elif self.path=='/command':
                    if bridge['last_seen'] is None or time.time()-bridge['last_seen']>10:
                        raise ValueError('game bridge unavailable')
                    if bridge['command'] or world.pending(bridge['session']): raise ValueError('command pending')
                    if data.get('kind') not in ('notify','look_at_player','save_game','load_game','prepare_market','walk_to','test_voice_output','select_voice_output'): raise ValueError('unknown command')
                    if data['kind']=='select_voice_output' and (not isinstance(data.get('output'),str) or not 1<=len(data['output'].strip())<=160):
                        raise ValueError('Choose a permitted audio output label or default')
                    if (world.agency_busy() or world.conversation_busy() or world.routines_busy()) and data['kind'] in ('prepare_market','walk_to'):
                        raise ValueError('A resident currently owns the task')
                    if data['kind']=='test_voice_output' and (director.status()['running'] or world.agency_busy() or world.conversation_busy() or world.routines_busy()):
                        raise ValueError('Pause society and finish the current interaction before the audio check')
                    if data['kind']=='walk_to':
                        walk=authored_walk_command(world,bridge['observation'],data,bridge['session'],secrets.token_hex(8))
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
                    if data['kind']=='select_voice_output': command['output']=data['output'].strip()
                    if data['kind']=='walk_to': command=walk
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
