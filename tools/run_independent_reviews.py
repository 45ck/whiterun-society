"""One claimed review wave, bounded inference, and no native action authority."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.error

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.checkpoint_http import CheckpointHTTP
from tools.run_resident_goals import run_decisions, settlement_deadline


def wait_review_settled(request,session=None,*,deadline=None,wave=None,require_idle=True,expected_phase=None):
    deadline=time.monotonic()+40 if deadline is None else deadline
    while time.monotonic()<deadline:
        state=request('/state');world=state['society'];bridge=state['bridge']
        if not bridge.get('last_seen') or time.time()-bridge['last_seen']>10:raise ValueError('Stale native observation')
        if session and bridge.get('session')!=session:raise ValueError('Session changed; review must not replay')
        if world.get('error'):raise ValueError('Society has an unresolved error')
        current={}
        if wave and not world.get('transition'):
            current=next((row for row in world.get('independent_review_waves',[]) if row.get('id')==wave['id']),{})
            if current.get('claim_id')!=wave['claim_id'] or current.get('session')!=wave['session']:
                raise ValueError('Independent review claim changed')
            if current.get('phase')=='held':raise ValueError('Independent review claim held')
        if (not world.get('transition') and (not require_idle or not bridge.get('command') and not world.get('unsettled_effect'))
                and (expected_phase is None or current.get('phase')==expected_phase)):return state
        time.sleep(min(.2,max(0,deadline-time.monotonic())))
    raise TimeoutError('Independent review settlement deadline exhausted')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--id',required=True)
    parser.add_argument('--model-config',type=Path,required=True);parser.add_argument('--limit',type=int,default=32)
    parser.add_argument('--wave-seconds',type=float,default=120)
    args=parser.parse_args()
    if not 1<=args.limit<=32:raise ValueError('Review limit must be 1 to 32')
    if not math.isfinite(args.wave_seconds) or not 1<=args.wave_seconds<=300:raise ValueError('Review wave duration must be 1 to 300 seconds')
    runtime=args.root/'runtime';config=json.loads((runtime/'bridge-config.json').read_text())
    model=json.loads(args.model_config.read_text())
    request=CheckpointHTTP(f"http://127.0.0.1:{config['port']}",config['token'])
    path=runtime/('independent-reviews-'+hashlib.sha256(args.id.encode()).hexdigest()[:12]+'.json')
    receipt={'id':args.id,'lane':'independent_reviews','started_at':time.time(),'model_calls':0,'status':'starting'}
    def record():path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    owned=False;stage='preclaim_wait'
    try:
        receipt['before']=wait_review_settled(request);stage='claim_request'
        result=request('/independent-reviews/claim',{'id':args.id,'limit':args.limit})
        if result.get('duplicate') or result.get('empty'):
            receipt['status']='duplicate' if result.get('duplicate') else 'empty'
            if not path.exists():record()
            print(json.dumps({'status':receipt['status'],'model_calls':0}));return
        wave=result['wave'];owned=True
        receipt.update(claim_id=wave['claim_id'],claim_deadline_at=wave.get('deadline_at'),status='claimed');record()
        members=wave['members']
        if (wave.get('id')!=args.id or wave.get('session')!=receipt['before']['bridge']['session']
                or not isinstance(members,list) or not 1<=len(members)<=args.limit
                or any(type(m.get('actor')) is not int or not isinstance(m.get('context'),dict)
                       or not isinstance(m.get('source_event'),str) or not m['source_event'] for m in members)
                or len({m['actor'] for m in members})!=len(members)):
            raise ValueError('Independent review wave identity or members invalid')
        receipt['source_events']={str(m['actor']):m['source_event'] for m in members};record()
        stage='claim_binding'
        wait_review_settled(request,wave['session'],deadline=settlement_deadline(wave,maximum=40),wave=wave,expected_phase='thinking')
        stage='inference'
        key=os.environ[model['key_env']]
        def progress(stats):receipt.update(stats);record()
        receipt.update(run_decisions(members,model,key,args.wave_seconds,progress));record()
        stage='paid_result_settlement';deadline=settlement_deadline(wave)
        receipt.update(status='awaiting_settlement',settlement_wait_started_at=time.time(),
            settlement_wait_budget_seconds=round(deadline-time.monotonic(),3));record()
        wait_review_settled(request,wave['session'],deadline=deadline,wave=wave,expected_phase='thinking')
        remaining=min(deadline-time.monotonic(),wave['deadline_at']-time.time())
        if remaining<=0:raise TimeoutError('Independent review claim expired before result submission')
        request.checkpoint_wait=remaining;request.timeout=min(30,remaining);stage='result_submission'
        request('/independent-reviews/result',{'id':args.id,'claim_id':wave['claim_id'],'results':receipt['results']})
        receipt.update(result_submitted=True,status='awaiting_result_binding');record();stage='result_binding'
        after=wait_review_settled(request,wave['session'],wave=wave,require_idle=False,expected_phase='complete')
        receipt.update(status='complete',after=after);record()
    except Exception as error:
        receipt.update(status='held',failure_stage=stage,failure_type=type(error).__name__,
            error='Independent review failed during '+stage+'; retained results must not be re-inferred',
            failure={'stage':stage,'type':type(error).__name__,
                'category':'http_rejection' if isinstance(error,urllib.error.HTTPError) else 'deadline' if isinstance(error,TimeoutError) else 'transport' if isinstance(error,OSError) else 'state_or_contract',
                'http_status':error.code if isinstance(error,urllib.error.HTTPError) else None,
                'results_preserved':len(receipt.get('results',[])),'result_submitted':receipt.get('result_submitted',False)})
        if owned or not path.exists():record()
        raise
    print(json.dumps({'status':'complete','model_calls':receipt['model_calls'],'concurrency':receipt['concurrency'],'evidence':str(path)}))


if __name__=='__main__':main()
