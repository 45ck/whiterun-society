"""Review game-clock needs and optionally run a finite number of queued decisions.

No wall-clock simulation while the game is disconnected. Inference is delegated
to persisted-claim workers: at most five calls per economic event, eight per
social encounter when an explicit language configuration is supplied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from social import social_candidates
from parallel_routines import select_routine_events


def event_available(state,event):
    """Recheck queued work after every previous resident's consequences."""
    society=state['society'];observation=state['bridge']['observation']
    current=next((e for e in society['town']['daily']['queue'] if e['id']==event['id']),None)
    if not current or current['status']!='pending':return False
    if not any(r['id']==event['actor'] and r.get('isPerson') is True for r in observation['residents']):return False
    return event['kind']!='social_review' or bool(social_candidates(society,observation,event['actor']))


def isolated_before_action(state, event):
    """A failed inference may finish without blocking unrelated residents.

    The service must have certified no accepted decision or native effect.
    Never infer this from a worker exit code, exception text or timeout.
    """
    society=state['society'];plan=society.get('plan') or {}
    return (event['kind']!='social_review' and plan.get('id')==event['id']
            and plan.get('phase')=='held' and plan.get('effect_free_hold') is True
            and plan.get('remembered') is True and not plan.get('decisions')
            and not plan.get('travel') and not plan.get('release_required')
            and not society.get('error') and not society.get('transition')
            and not state['bridge'].get('command'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--max-events',type=int,default=0)
    parser.add_argument('--watch-seconds',type=int,default=0)
    parser.add_argument('--model-config',type=Path)
    parser.add_argument('--language-config',type=Path,help='Enables scheduled social encounters with at most eight model calls each')
    parser.add_argument('--parallel-journeys',action='store_true',help='Group up to eight eligible food-search journeys within the event budget')
    args=parser.parse_args()
    if not 0<=args.max_events<=24 or not 0<=args.watch_seconds<=600:
        raise ValueError('Use 0–24 resident events and 0–600 seconds of observation')
    if args.max_events and not args.model_config:raise ValueError('An explicit decision model configuration is required')
    runtime=args.root/'runtime'
    config=json.loads((runtime/'bridge-config.json').read_text())
    def request(route,data=None):
        req=urllib.request.Request(f"http://127.0.0.1:{config['port']}"+route,
            None if data is None else json.dumps(data).encode(),
            headers={'Authorization':'Bearer '+config['token'],'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
        except urllib.error.HTTPError as error:raise ValueError(json.load(error).get('error','Request rejected')) from None
    def fresh():
        state=request('/state')
        if not state['bridge']['last_seen'] or time.time()-state['bridge']['last_seen']>10:
            raise ValueError('Game observation is stale; no offline progression')
        if state['society']['error']:raise ValueError(state['society']['error'])
        return state
    before=fresh();session=before['bridge']['session']
    evidence={'before':before,'started_at':time.time(),'reviews':[],'events':[],
              'maximum_model_calls':(8 if args.language_config else 5)*args.max_events,'status':'running'}
    output=runtime/('daily-life-'+str(time.time_ns())+'.json')
    def record():output.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    record();deadline=time.monotonic()+args.watch_seconds;first=True
    try:
        while first or time.monotonic()<deadline:
            first=False;state=fresh()
            if state['bridge']['session']!=session:raise ValueError('Save/session changed; director stopped')
            if state['society']['transition'] or state['bridge']['command']:
                raise ValueError('Finish the pending native/checkpoint command before running the director')
            result=request('/town/review',{'source':'bounded_director'})
            if not result.get('duplicate'):evidence['reviews'].append(result);record()
            bind_deadline=time.monotonic()+30
            while True:
                state=fresh()
                if state['bridge']['session']!=session:raise ValueError('Save/session changed while binding review')
                if not state['society']['transition']:break
                if time.monotonic()>bind_deadline:raise TimeoutError('Daily review did not bind')
                time.sleep(.4)
            loaded={a['id'] for a in state['bridge']['observation']['residents'] if a.get('isPerson') is True}
            queue=(state['society']['town'].get('daily') or {}).get('queue',[])
            pending=sorted((e for e in queue if e['status']=='pending' and e['actor'] in loaded
                            and (e['kind']!='social_review' or args.language_config)),
                           key=lambda e:(-e['priority'],e.get('created_day',0),e['id']))
            if args.parallel_journeys:
                selected=select_routine_events(state['society'],state['bridge']['observation'],pending,min(8,args.max_events-len(evidence['events'])))
                if len(selected)>=2:
                    ids=[e['id'] for e in selected];batch_id='daily-routes-'+hashlib.sha256('|'.join(ids).encode()).hexdigest()[:16]
                    result=subprocess.run([sys.executable,str(Path(__file__).with_name('run_parallel_routines.py')),
                        '--root',str(args.root),'--id',batch_id,'--events',*ids,'--model-config',str(args.model_config)],check=False)
                    current=fresh();batch=current['society'].get('routine_batch')
                    if current['bridge']['session']!=session or result.returncode or not batch or batch['id']!=batch_id:
                        raise ValueError('Independent-journey cohort did not finish cleanly')
                    for member in batch['members']:
                        evidence['events'].append({'id':member['event_id'],'actor':member['actor'],'status':member['phase'],
                            'outcome':member.get('outcome'),'model_calls':int(bool(member.get('result'))),'cohort':batch_id})
                    record()
                    if batch['phase']=='held':raise ValueError('Independent journey held; no automatic repeat')
            for event in pending:
                if len(evidence['events'])>=args.max_events:break
                current=fresh()
                if current['bridge']['session']!=session:raise ValueError('Game session changed before resident decision')
                if not event_available(current,event):continue
                evidence['events'].append({'id':event['id'],'actor':event['actor'],'status':'started'});record()
                if event['kind']=='social_review':
                    command=[sys.executable,str(Path(__file__).with_name('run_conversation.py')),'--root',str(args.root),
                        '--id',event['id'],'--actor',str(event['actor']),'--decision-config',str(args.model_config),'--language-config',str(args.language_config)]
                else:command=[sys.executable,str(Path(__file__).with_name('run_resident_event.py')),
                    '--runtime',str(runtime),'--event-id',event['id'],'--actor',str(event['actor']),
                    '--kind',event['kind'],'--model-config',str(args.model_config)]
                result=subprocess.run(command,check=False)
                current=fresh()
                if current['bridge']['session']!=session:raise ValueError('Game session changed during resident decision')
                plan=current['society']['conversation'] if event['kind']=='social_review' else current['society']['plan']
                if event['kind']!='social_review' and plan and plan.get('effect_free_hold'):
                    settle_until=time.monotonic()+30
                    while not isolated_before_action(current,event) and time.monotonic()<settle_until:
                        time.sleep(.5);current=fresh()
                        if current['bridge']['session']!=session:raise ValueError('Session changed while settling an interrupted decision')
                    if isolated_before_action(current,event):
                        worker_file=runtime/('resident-event-'+hashlib.sha256(event['id'].encode()).hexdigest()[:12]+'.json')
                        worker=json.loads(worker_file.read_text(encoding='utf-8'))
                        if worker.get('event_id')!=event['id']:raise ValueError('Worker receipt belongs to a different event')
                        evidence['events'][-1].update(status='held',outcome='interrupted_before_action',
                            model_calls=worker['model_calls'],continued_other_residents=True)
                        record();continue
                if result.returncode or not plan or plan['id']!=event['id']:raise ValueError('Scheduled resident event did not finish cleanly')
                calls=(len(plan.get('social_decisions',[]))+2*len(plan.get('turns',[]))) if event['kind']=='social_review' else len(plan['decisions'])
                evidence['events'][-1].update(status=plan['phase'],outcome=plan.get('outcome'),model_calls=calls)
                record()
                if plan['phase']=='held':raise ValueError('Scheduled resident event held; no automatic retry')
            if args.max_events and len(evidence['events'])>=args.max_events:break
            if time.monotonic()<deadline:time.sleep(min(2,max(.01,deadline-time.monotonic())))
        evidence.update(status='complete',after=fresh());record()
        print(json.dumps({'status':'complete','reviews':len(evidence['reviews']),'events':evidence['events'],'evidence':str(output)}))
    except Exception as error:
        evidence.update(status='held',error=str(error));record();raise


if __name__=='__main__':main()
