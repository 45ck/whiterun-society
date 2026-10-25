"""Bounded social choice and three-layer speech with confirmed overlay playback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from language import LanguageOutputError, propose
from decisions import infer
from social import SOCIAL_STAGES
from tools.voice_worker import VoiceWorker
from dialogue_policy import POLICIES
from tools.checkpoint_http import CheckpointHTTP
from conversation_scenarios import validate_scenario


def load_scenario(path):
    """An explicitly supplied, bounded definition; never discover a default file."""
    with Path(path).open('rb') as handle:raw=handle.read(16385)
    if len(raw)>16384:raise ValueError('Conversation scenario exceeds 16 KiB')
    def unique_fields(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate scenario JSON field')
            result[key]=value
        return result
    try:definition=json.loads(raw.decode('utf-8'),object_pairs_hook=unique_fields)
    except (UnicodeError,json.JSONDecodeError) as error:raise ValueError('Scenario must be valid UTF-8 JSON') from error
    return validate_scenario(definition)


def stock_voice(actor, observation):
    row=next((r for r in observation.get('residents',[]) if r['id']==actor),{})
    if row.get('voiceSex')==0:return 'bm_george' if actor%2 else 'bm_lewis'
    return 'bf_emma' if actor%2==0 else 'bf_alice'


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--id',required=True)
    p.add_argument('--language-config',type=Path,required=True);p.add_argument('--decision-config',type=Path,required=True)
    p.add_argument('--actor',type=int,help='Run an existing scheduled social opportunity for this resident')
    p.add_argument('--max-turns',type=int,choices=range(2,7))
    p.add_argument('--opportunity-batch',help='Consume a recent proximity notice from this background cohort')
    p.add_argument('--scenario',type=Path,help='Explicit authored scenario JSON; separate from ordinary census conversations')
    p.add_argument('--reply-policy',choices=POLICIES,default='combined_choice')
    args=p.parse_args()
    if args.scenario is not None and (args.actor is not None or args.opportunity_batch is not None or args.max_turns is not None):
        p.error('--scenario cannot be combined with --actor, --opportunity-batch, or --max-turns; the definition owns its participants and turn limit')
    scenario=load_scenario(args.scenario) if args.scenario is not None else None
    max_turns=scenario['max_turns'] if scenario is not None else (args.max_turns or 6)
    runtime=args.root/'runtime';bridge=json.loads((runtime/'bridge-config.json').read_text())
    models={stage:json.loads(path.read_text()) for stage,path in [('propose',args.language_config),('select',args.decision_config)]}
    evidence={'id':args.id,'calls':{'propose':0,'select':0,'social':0},'started_at':time.time(),'stages':[],'synthesis_timings':[],
              'polling':{'checkpoint_seconds':.1,'native_wait_seconds':.2,'sleep_after_mutation':False}}
    path=runtime/('conversation-'+hashlib.sha256(args.id.encode()).hexdigest()[:12]+'.json')
    client=CheckpointHTTP(f"http://127.0.0.1:{bridge['port']}",bridge['token'],timeout=10)
    def req(route,data=None):
        try:
            result=client(route,data)
        except urllib.error.HTTPError as e:raise ValueError(json.load(e).get('error','Request rejected')) from None
        if route=='/state' and time.time()-(result['bridge']['last_seen'] or 0)>10:raise ValueError('Game disconnected')
        return result
    deadline=time.monotonic()+600
    def stable():
        while time.monotonic()<deadline:
            s=req('/state')
            if s['society']['error']:raise ValueError(s['society']['error'])
            if not s['society']['transition']:return s
            time.sleep(.1)
        raise TimeoutError('Checkpoint did not settle')
    def record():path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    evidence['before']=stable()
    if scenario is not None:
        started=req('/conversation/scenario',{'id':args.id,'scenario':scenario,'reply_policy':args.reply_policy})
    else:
        started=req('/conversation/start',{'id':args.id,'max_turns':max_turns,'reply_policy':args.reply_policy,**({'actor':args.actor} if args.actor is not None else {}),
                    **({'opportunity_batch':args.opportunity_batch} if args.opportunity_batch else {})})
    if started.get('duplicate'):
        print(json.dumps({'duplicate':True,'phase':started['conversation']['phase'],'model_calls':0}));return
    previous=None;voice_worker=None;claim=None
    try:
        # Admission (including the census boundary and exact duplicate check)
        # precedes credential resolution, model inference and speech startup.
        keys={stage:os.environ[c['key_env']] if c.get('key_env') else Path(c['key_file']).read_text().strip() for stage,c in models.items()}
        voice_worker=VoiceWorker(args.root,max_turns,[c.get('key_env') for c in models.values()])
        while time.monotonic()<deadline:
            s=stable();c=s['society']['conversation']
            if not c or c['id']!=args.id:raise ValueError('Conversation changed after save/load')
            phase=c['phase']
            if phase!=previous:
                evidence['stages'].append({'phase':phase,'turn':c['turn'],'at':time.time()});record()
                print(json.dumps({'phase':phase,'turn':c['turn'],'calls':evidence['calls']}),flush=True);previous=phase
            if phase in ('complete','held'):
                evidence.update(status=phase,after=s,elapsed_seconds=round(time.time()-evidence['started_at'],3));record()
                if phase=='held':raise ValueError(c.get('error','Conversation held'))
                print(json.dumps({'complete':True,'evidence':str(path)}),flush=True);return
            if phase in ('propose','select')+SOCIAL_STAGES:
                bucket='social' if phase in SOCIAL_STAGES else phase
                model_stage='propose' if phase=='propose' else 'select'
                limit=c.get('turn_limit',2)
                cap=4+(limit-1 if limit>2 and c.get('reply_policy','separate_choice')=='separate_choice' else 0) if bucket=='social' else limit
                if evidence['calls'][bucket]>=cap:raise ValueError('Inference cap exceeded')
                claim=req('/conversation/claim',{'id':args.id})['claim'];confirmed=stable()
                confirmed_conversation=confirmed['society'].get('conversation') or {}
                if (confirmed['bridge']['session']!=claim['session'] or confirmed_conversation.get('id')!=args.id
                        or (confirmed_conversation.get('claim') or {}).get('id')!=claim['id']):
                    raise ValueError('Save/session changed before inference; no model call made')
                evidence['calls'][bucket]+=1;record()
                result=(propose if phase=='propose' else infer)(claim['context'],models[model_stage],keys[model_stage])
                req('/conversation/result',{'id':args.id,'claim_id':claim['id'],'result':result})
                continue  # stable() waits for this result's native checkpoint.
            elif phase=='synthesize':
                turn=c['current'];input_path=runtime/('speech-'+hashlib.sha256((args.id+str(c['turn'])).encode()).hexdigest()[:16]+'.json')
                input_path.write_text(json.dumps({'text':turn['selected']['line'],'voice':stock_voice(turn['speaker'],s['bridge']['observation'])}),encoding='utf-8')
                synthesis_start=time.monotonic()
                voice_result=voice_worker.synthesize(turn['selected']['line'],stock_voice(turn['speaker'],s['bridge']['observation']))
                audio=voice_result['audio'];input_path.with_suffix('.audio.json').write_text(json.dumps(audio),encoding='utf-8')
                evidence['voice_load_seconds']=voice_worker.ready['load_seconds']
                evidence['synthesis_timings'].append({'turn':c['turn'],'seconds':round(time.monotonic()-synthesis_start,3),'engine_seconds':voice_result['synthesis_seconds']});record()
                req('/conversation/audio',{'id':args.id,'audio':audio})
                continue  # Do not add a fixed pause before observing playback.
            elif phase.startswith('thinking_'):
                raise ValueError('Unsettled inference claim; refusing automatic repetition')
            time.sleep(.2)
        raise TimeoutError('Conversation execution cap reached')
    except Exception as e:
        evidence.update(status='held',error=type(e).__name__+': '+str(e)[:200])
        failure={}
        if isinstance(e, LanguageOutputError):
            evidence['rejected_language']=e.receipt
            if claim:failure={'inference_failure':{'claim_id':claim['id'],'receipt':e.receipt}}
        try:req('/conversation/hold',{'id':args.id,'reason':evidence['error'],**failure})
        except (OSError,ValueError):evidence['hold_not_confirmed']=True
        record();raise
    finally:
        if voice_worker:voice_worker.close()


if __name__=='__main__':main()
