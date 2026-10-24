"""Bounded social choice and three-layer speech with confirmed overlay playback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from language import propose
from decisions import infer
from social import SOCIAL_STAGES


def stock_voice(actor, observation):
    row=next((r for r in observation.get('residents',[]) if r['id']==actor),{})
    if row.get('voiceSex')==0:return 'bm_george' if actor%2 else 'bm_lewis'
    return 'bf_emma' if actor%2==0 else 'bf_alice'


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--id',required=True)
    p.add_argument('--language-config',type=Path,required=True);p.add_argument('--decision-config',type=Path,required=True)
    p.add_argument('--actor',type=int,help='Run an existing scheduled social opportunity for this resident')
    args=p.parse_args();runtime=args.root/'runtime';bridge=json.loads((runtime/'bridge-config.json').read_text())
    models={stage:json.loads(path.read_text()) for stage,path in [('propose',args.language_config),('select',args.decision_config)]}
    keys={stage:os.environ[c['key_env']] if c.get('key_env') else Path(c['key_file']).read_text().strip() for stage,c in models.items()}
    evidence={'id':args.id,'calls':{'propose':0,'select':0,'social':0},'started_at':time.time(),'stages':[],'synthesis_timings':[]}
    path=runtime/('conversation-'+hashlib.sha256(args.id.encode()).hexdigest()[:12]+'.json')
    def req(route,data=None):
        request=urllib.request.Request(f"http://127.0.0.1:{bridge['port']}"+route,
            data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+bridge['token']})
        try:
            with urllib.request.urlopen(request,timeout=10) as r:result=json.load(r)
        except urllib.error.HTTPError as e:raise ValueError(json.load(e).get('error','Request rejected')) from None
        if route=='/state' and time.time()-(result['bridge']['last_seen'] or 0)>10:raise ValueError('Game disconnected')
        return result
    deadline=time.monotonic()+360
    def stable():
        while time.monotonic()<deadline:
            s=req('/state')
            if s['society']['error']:raise ValueError(s['society']['error'])
            if not s['society']['transition']:return s
            time.sleep(.4)
        raise TimeoutError('Checkpoint did not settle')
    def record():path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    evidence['before']=stable()
    started=req('/conversation/start',{'id':args.id,**({'actor':args.actor} if args.actor is not None else {})})
    if started.get('duplicate'):
        print(json.dumps({'duplicate':True,'phase':started['conversation']['phase'],'model_calls':0}));return
    previous=None
    try:
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
                if evidence['calls'][bucket]>=(4 if bucket=='social' else 2):raise ValueError('Inference cap exceeded')
                claim=req('/conversation/claim',{'id':args.id})['claim'];confirmed=stable()
                confirmed_conversation=confirmed['society'].get('conversation') or {}
                if (confirmed['bridge']['session']!=claim['session'] or confirmed_conversation.get('id')!=args.id
                        or (confirmed_conversation.get('claim') or {}).get('id')!=claim['id']):
                    raise ValueError('Save/session changed before inference; no model call made')
                evidence['calls'][bucket]+=1;record()
                result=(propose if phase=='propose' else infer)(claim['context'],models[model_stage],keys[model_stage])
                req('/conversation/result',{'id':args.id,'claim_id':claim['id'],'result':result})
            elif phase=='synthesize':
                turn=c['current'];input_path=runtime/('speech-'+hashlib.sha256((args.id+str(c['turn'])).encode()).hexdigest()[:16]+'.json')
                input_path.write_text(json.dumps({'text':turn['selected']['line'],'voice':stock_voice(turn['speaker'],s['bridge']['observation'])}),encoding='utf-8')
                synthesis_start=time.monotonic()
                subprocess.run([str(args.root/'voice-venv/Scripts/python.exe'),str(Path(__file__).with_name('synthesize_voice.py')),
                    '--root',str(args.root),'--input',str(input_path)],check=True,timeout=90)
                evidence['synthesis_timings'].append({'turn':c['turn'],'seconds':round(time.monotonic()-synthesis_start,3)});record()
                audio=json.loads(input_path.with_suffix('.audio.json').read_text())
                req('/conversation/audio',{'id':args.id,'audio':audio})
            elif phase.startswith('thinking_'):
                raise ValueError('Unsettled inference claim; refusing automatic repetition')
            time.sleep(.4)
        raise TimeoutError('Conversation execution cap reached')
    except Exception as e:
        evidence.update(status='held',error=type(e).__name__+': '+str(e)[:200])
        try:req('/conversation/hold',{'id':args.id,'reason':evidence['error']})
        except (OSError,ValueError):evidence['hold_not_confirmed']=True
        record();raise


if __name__=='__main__':main()
