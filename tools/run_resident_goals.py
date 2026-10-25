"""Bounded concurrent personal decisions; native destinations progress independently."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from threading import Lock
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from decisions import infer
from inference_receipts import usage_receipt
from tools.checkpoint_http import CheckpointHTTP


PAID_SETTLEMENT_SECONDS=600


def settlement_deadline(wave,maximum=PAID_SETTLEMENT_SECONDS):
    """Bound settlement of existing results by the persisted claim expiry."""
    expires=wave.get('deadline_at')
    if type(expires) not in (int,float) or not math.isfinite(expires):
        raise ValueError('Goal claim has no valid settlement deadline')
    remaining=expires-time.time()
    if remaining<=0:raise TimeoutError('Goal claim expired before result settlement')
    return time.monotonic()+min(maximum,remaining)


def wait_settled(request,session=None,*,deadline=None,wave=None,require_idle=True,expected_phase=None):
    """Observe only; never replay inference or a mutation to make progress."""
    deadline=time.monotonic()+40 if deadline is None else deadline
    while time.monotonic()<deadline:
        state=request('/state');world=state['society']
        if not state['bridge']['last_seen'] or time.time()-state['bridge']['last_seen']>10:
            raise ValueError('Stale native observation')
        if session and state['bridge']['session']!=session:raise ValueError('Session changed; do not replay inference')
        if world['error']:raise ValueError('Society has an unresolved error')
        current=None
        # A binding checkpoint exposes the previous committed snapshot. The
        # claimed wave can legitimately be absent or still thinking there.
        # Session and global errors above remain authoritative while binding.
        if wave and not world['transition']:
            current=next((w for w in (world.get('town') or {}).get('goal_waves',[]) if w['id']==wave['id']),{})
            if current.get('claim_id')!=wave['claim_id'] or current.get('session')!=wave['session']:
                raise ValueError('Goal claim changed while awaiting settlement')
            if current.get('phase')=='held':raise ValueError('Goal claim held while awaiting settlement')
        ready=not world['transition'] and (not require_idle or not state['bridge']['command'] and not world.get('unsettled_effect'))
        if ready and (expected_phase is None or current.get('phase')==expected_phase):return state
        time.sleep(min(.2,max(0,deadline-time.monotonic())))
    raise TimeoutError('Goal settlement wait exhausted its bounded deadline')


def run_decisions(members,model,key,wave_seconds=120,on_update=None,clock=None):
    """Bound queued starts and socket waits; drain launched calls before returning.

    The deadline is a scheduling deadline, not a process kill timer. A peer
    trickling bytes can outlive a socket timeout. No future is detached.
    """
    if type(wave_seconds) not in (int,float) or not math.isfinite(wave_seconds) or not 1<=wave_seconds<=300:
        raise ValueError('Wave duration must be 1 to 300 seconds')
    now=clock or time.monotonic;started=now();deadline=started+wave_seconds;lock=Lock()
    stats={'reserved_model_calls':len(members),'model_calls':0,'concurrency':min(4,len(members)),
           'attempted_actors':[],'results':[],'reported_cost':0,'cost_reports':0,
           'deadline_seconds':wave_seconds,'attempt_scope':'Calls entering infer, not provider billing confirmation'}
    def update():
        if on_update:on_update({**stats,'attempted_actors':list(stats['attempted_actors']),'results':list(stats['results'])})
    def decide(member):
        actor=member['actor'];attempted=False
        with lock:
            remaining=deadline-now()
            if remaining<=0:
                result={'failure':'wave_deadline_before_inference','model':model['model'],'elapsed_seconds':0}
            else:
                stats['model_calls']+=1;stats['attempted_actors'].append(actor);update();result=None
        if result is None:
            began=now()
            try:
                # Receipt persistence may consume part of the remaining budget.
                remaining=deadline-now()
                if remaining<=0:
                    with lock:stats['model_calls']-=1;stats['attempted_actors'].remove(actor)
                    result={'failure':'wave_deadline_before_inference','model':model['model'],'elapsed_seconds':0}
                else:
                    attempted=True
                    result=infer(member['context'],model,key,timeout=max(.001,min(30,remaining)))
                    if not isinstance(result,dict):raise ValueError('Invalid inference result')
                    if now()>deadline:result={**result,'failure':'wave_deadline_after_inference'}
            except Exception:
                result={'failure':'inference_failed','model':model['model'],'elapsed_seconds':round(max(0,now()-began),3)}
        result={**result,'attempted':attempted}
        item={'actor':actor,'result':result}
        with lock:
            stats['results'].append(item)
            usage=usage_receipt(result.get('usage'));cost=usage.get('cost')
            if type(cost) in (int,float) and math.isfinite(cost) and cost>=0:stats['reported_cost']+=cost;stats['cost_reports']+=1
            update()
        return item
    if members:
        with ThreadPoolExecutor(max_workers=stats['concurrency']) as executor:results=list(executor.map(decide,members))
    else:results=[]
    return {**stats,'results':results,'inference_wall_seconds':round(max(0,now()-started),3),
            'unreported_cost_calls':stats['model_calls']-stats['cost_reports']}


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--id',required=True)
    p.add_argument('--model-config',type=Path,required=True);p.add_argument('--limit',type=int,default=32)
    p.add_argument('--wave-seconds',type=float,default=120,help='Queued-call scheduling deadline; launched socket waits are bounded and drained')
    a=p.parse_args()
    if not math.isfinite(a.wave_seconds) or not 1<=a.wave_seconds<=300:raise ValueError('Wave duration must be 1 to 300 seconds')
    runtime=a.root/'runtime';config=json.loads((runtime/'bridge-config.json').read_text());model=json.loads(a.model_config.read_text())
    key=os.environ[model['key_env']]
    request=CheckpointHTTP(f"http://127.0.0.1:{config['port']}",config['token'])
    path=runtime/('resident-goals-'+hashlib.sha256(a.id.encode()).hexdigest()[:12]+'.json')
    receipt={'id':a.id,'started_at':time.time(),'model_calls':0,'status':'starting'}
    def record():path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    owned_receipt=False;stage='preclaim_wait'
    try:
        receipt['before']=wait_settled(request);stage='claim_request'
        result=request('/goals/claim',{'id':a.id,'limit':a.limit})
        if result.get('duplicate') or result.get('empty'):
            receipt.update(status='duplicate' if result.get('duplicate') else 'empty')
            # Duplicate inspection must not erase paid results or original evidence.
            if not path.exists():record()
            print(json.dumps({'status':receipt['status'],'model_calls':0}));return
        wave=result['wave'];owned_receipt=True
        receipt.update(claim_id=wave['claim_id'],status='claimed',claim_deadline_at=wave.get('deadline_at'));record()
        stage='claim_binding'
        wait_settled(request,wave['session'],deadline=settlement_deadline(wave,maximum=40),wave=wave,expected_phase='thinking')
        stage='inference'
        def progress(stats):receipt.update(stats);record()
        receipt.update(run_decisions(wave['members'],model,key,a.wave_seconds,progress));record();results=receipt['results']
        stage='paid_result_settlement'
        deadline=settlement_deadline(wave)
        receipt.update(status='awaiting_settlement',settlement_wait_started_at=time.time(),
                       settlement_wait_budget_seconds=round(deadline-time.monotonic(),3));record()
        wait_settled(request,wave['session'],deadline=deadline,wave=wave,expected_phase='thinking')
        remaining=min(deadline-time.monotonic(),wave['deadline_at']-time.time())
        if remaining<=0:raise TimeoutError('Goal claim expired before result submission')
        # Only certified pre-mutation conflicts may retry, using this same
        # finite remaining window. A timeout or uncertain POST is never replayed.
        request.checkpoint_wait=remaining;request.timeout=min(30,remaining)
        stage='result_submission'
        request('/goals/result',{'id':a.id,'claim_id':wave['claim_id'],'results':results})
        receipt.update(result_submitted=True,status='awaiting_result_binding');record()
        stage='result_binding'
        # Once accepted, unrelated native work need not become idle again.
        after=wait_settled(request,wave['session'],wave=wave,require_idle=False,expected_phase='complete')
        receipt.update(status='complete',after=after);record()
    except Exception as error:
        receipt.update(status='held',failure_stage=stage,failure_type=type(error).__name__,
            error='Goal worker failed during '+stage+'; persisted results must not be re-inferred',
            failure={'stage':stage,'type':type(error).__name__,
                'category':'http_rejection' if isinstance(error,urllib.error.HTTPError) else 'deadline' if isinstance(error,TimeoutError) else 'transport' if isinstance(error,OSError) else 'state_or_contract',
                'http_status':error.code if isinstance(error,urllib.error.HTTPError) else None,
                'results_preserved':len(receipt.get('results',[])),'result_submitted':receipt.get('result_submitted',False)})
        if owned_receipt or not path.exists():record()
        raise
    print(json.dumps({'status':'complete','model_calls':receipt['model_calls'],'concurrency':receipt['concurrency'],'evidence':str(path)}))

if __name__=='__main__':main()
