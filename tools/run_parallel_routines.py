"""Claim a finite cohort, decide independently, then observe concurrent journeys."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path
import sys
import time
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from decisions import infer
from social import social_candidates,valid_social_notice
from dialogue_policy import MAX_COMBINED_CALLS
from tools.checkpoint_http import CheckpointHTTP


def settle_social_child(process, encounter_id, request, reason):
    """Hold this worker's encounter, then let its voice-worker finally block run."""
    if process is None:return None
    result={'id':encounter_id,'pid':process.pid,'status':'child_cleanup'}
    if process.poll() is None:
        try:
            request('/conversation/hold',{'id':encounter_id,'reason':reason})
            result['hold_requested']=True
        except (OSError,ValueError):result['hold_not_confirmed']=True
        try:process.wait(timeout=660)
        except subprocess.TimeoutExpired:
            result['status']='child_still_running'
            return result
    result.update(status='child_exited',exit_code=process.returncode)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--id',required=True)
    parser.add_argument('--events',nargs='+',required=True)
    parser.add_argument('--model-config',type=Path,required=True)
    parser.add_argument('--background',action='store_true')
    parser.add_argument('--social-during-travel',action='store_true',help=f'Offer one disjoint conversation during background travel; at most {MAX_COMBINED_CALLS} extra model calls')
    parser.add_argument('--language-config',type=Path)
    args=parser.parse_args()
    background=args.background or args.social_during_travel
    if args.social_during_travel and not args.language_config:raise ValueError('Concurrent social activity requires a language configuration')
    if background and len(args.events)>6:raise ValueError('Background journeys reserve two of eight slots for conversation')
    if not 1<=len(args.events)<=8:raise ValueError('One to eight resident events per bounded run')
    runtime=args.root/'runtime';config=json.loads((runtime/'bridge-config.json').read_text())
    model=json.loads(args.model_config.read_text());key=os.environ[model['key_env']] if model.get('key_env') else Path(model['key_file']).read_text().strip()
    client=CheckpointHTTP(f"http://127.0.0.1:{config['port']}",config['token'])
    def request(path,data=None):
        try:
            return client(path,data)
        except urllib.error.HTTPError as e:raise ValueError(json.load(e).get('error','Request rejected')) from None
    def state():
        result=request('/state')
        if not result['bridge']['last_seen'] or time.time()-result['bridge']['last_seen']>10:raise ValueError('Stale game observation')
        if result['society']['error']:raise ValueError(result['society']['error'])
        return result
    evidence={'started_at':time.time(),'before':state(),'id':args.id,'model_calls':0,'samples':[]}
    path=runtime/('parallel-routines-'+hashlib.sha256(args.id.encode()).hexdigest()[:12]+'.json')
    def record():path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    result=request('/routines/start',{'id':args.id,'event_ids':args.events,'background':background})
    if result.get('duplicate'):print(json.dumps({'duplicate':True,'model_calls':0}));return
    batch=result['batch'];deadline=time.monotonic()+240;record();social_process=None;social_id=None
    def settled():
        while time.monotonic()<deadline:
            s=state()
            if s['bridge']['session']!=batch['session']:raise ValueError('Game session changed; do not repeat inference')
            if not s['society']['transition']:return s
            time.sleep(.3)
        raise TimeoutError('Cohort checkpoint did not bind')
    try:
        current=settled()['society']['routine_batch']
        if current['claim_id']!=batch['claim_id'] or current['phase']!='thinking':raise ValueError('Claim changed before inference')
        evidence['model_calls']=len(batch['members']);record()
        def decide(member):return {'event_id':member['event_id'],'result':infer(member['context'],model,key)}
        with ThreadPoolExecutor(max_workers=min(4,len(batch['members']))) as executor:results=list(executor.map(decide,batch['members']))
        evidence['results']=results;record()
        settled();request('/routines/decisions',{'id':args.id,'claim_id':batch['claim_id'],'results':results})
        while time.monotonic()<deadline:
            s=settled();current=s['society']['routine_batch'];native=s['bridge']['observation'].get('parallel_routines',{})
            if not current or current['id']!=args.id:raise ValueError('Background cohort changed; retain only this worker receipt')
            evidence['samples'].append({'at':time.time(),'native':native});record()
            notice=current.get('social_notice')
            recent=valid_social_notice(notice,s['bridge']['observation']) and not notice.get('consumed_by')
            if (args.social_during_travel and social_id is None and current.get('launched') and current['phase']=='travelling'
                    and any(social_candidates(s['society'],s['bridge']['observation'],int(a),notice if recent else None) for a in s['society']['town']['residents'])):
                social_id='overlap-'+uuid.uuid4().hex[:20]
                command=[sys.executable,str(Path(__file__).with_name('run_conversation.py')),
                    '--root',str(args.root),'--id',social_id,'--decision-config',str(args.model_config),'--language-config',str(args.language_config)]
                if recent:command+=['--opportunity-batch',args.id]
                social_process=subprocess.Popen(command,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                evidence['social_event']={'id':social_id,'pid':social_process.pid,'status':'started','maximum_model_calls':MAX_COMBINED_CALLS,
                    'recent_notice_used':recent,'notice_to_dispatch_seconds':round(time.time()-notice['captured_at'],3) if recent else None};record()
                deadline=max(deadline,time.monotonic()+660)
            if social_process and social_process.poll() is not None and evidence['social_event']['status']=='started':
                c=s['society'].get('conversation') or {}
                social_receipt=runtime/('conversation-'+hashlib.sha256(social_id.encode()).hexdigest()[:12]+'.json')
                evidence_calls=None
                if social_receipt.is_file():
                    social_worker=json.loads(social_receipt.read_text(encoding='utf-8'))
                    if social_worker.get('id')==social_id:evidence_calls=sum(social_worker['calls'].values())
                evidence['social_event'].update(status=c.get('phase','held') if c.get('id')==social_id else 'held',outcome=c.get('outcome'),exit_code=social_process.returncode,
                    actor=c.get('initiator'),model_calls=evidence_calls,
                    matching_encounter=c.get('id')==social_id)
                record()
            if current['phase'] in ('complete','held'):
                if social_process and social_process.poll() is None:
                    time.sleep(.5);continue
                evidence.update(after=s,status=current['phase'],finished_at=time.time());record()
                if social_process and (social_process.returncode or not evidence['social_event'].get('matching_encounter')):
                    raise ValueError('Concurrent social event held; background receipts retained')
                print(json.dumps({'phase':current['phase'],'choices':[(m['actor'],m.get('result',{}).get('decision',{}).get('action_id'),m.get('outcome')) for m in current['members']],
                    'concurrency':current.get('concurrency'),'model_calls':evidence['model_calls'],'evidence':str(path)}),flush=True);return
            print(json.dumps({'phase':current['phase'],'peak_owned':native.get('peak_owned'),'activities':len(native.get('activities',[]))}),flush=True)
            time.sleep(2)
        raise TimeoutError('Cohort exceeded its execution bound; native leases remain time bounded')
    except Exception as error:
        evidence.update(status='held',error=str(error));record()
        try:request('/routines/hold',{'id':args.id,'reason':str(error)})
        except (OSError,ValueError):pass
        evidence['social_cleanup']=settle_social_child(social_process,social_id,request,str(error));record()
        raise


if __name__=='__main__':main()
