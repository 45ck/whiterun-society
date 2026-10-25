"""Review game-clock needs and optionally run a finite number of queued decisions.

No wall-clock simulation while the game is disconnected. Inference is delegated
to persisted-claim workers: at most five calls per economic event, 16 per
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
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from social import social_candidates
from parallel_routines import select_routine_events
from routing import activity_blocker
from dialogue_policy import recorded_model_results,MAX_COMBINED_CALLS


def fair_pending(events, social_first=True):
    """Keep hunger backlogs from starving social life, without inventing events."""
    ordered = sorted(events, key=lambda e: (-e['priority'], e.get('created_day', 0), e['id']))
    social = [e for e in ordered if e['kind'] == 'social_review']
    economic = [e for e in ordered if e['kind'] != 'social_review']
    result = []
    while social or economic:
        lane = social if social_first else economic
        if not lane: lane = economic if social_first else social
        result.append(lane.pop(0))
        social_first = not social_first
    return result


def event_available(state,event):
    """Recheck queued work after every previous resident's consequences."""
    society=state['society'];observation=state['bridge']['observation']
    if event['kind']=='social_opportunity':
        return any(social_candidates(society,observation,int(key)) for key in society['town']['residents'])
    current=next((e for e in society['town']['daily']['queue'] if e['id']==event['id']),None)
    if not current or current['status']!='pending':return False
    if not any(r['id']==event['actor'] and r.get('isPerson') is True and not activity_blocker(r) for r in observation['residents']):return False
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


def isolated_released_cohort(state, batch_id):
    """Continue other people only after committed receipts prove lease release.

    A terminal worker or a held phase alone never proves that native actions
    stopped. A concurrent conversation must also have completed successfully.
    """
    society=state['society'];batch=society.get('routine_batch') or {}
    if (batch.get('id')!=batch_id or batch.get('session')!=state['bridge'].get('session')
            or batch.get('phase')!='held' or batch.get('settled') is not True
            or batch.get('release_verified') is not True or batch.get('unverified_release')
            or society.get('error') or society.get('transition') or society.get('unsettled_effect')
            or state['bridge'].get('command')):return False
    conversation=society.get('conversation') or {};plan=society.get('plan') or {}
    if conversation and conversation.get('phase')!='complete':return False
    if plan and (plan.get('phase') not in ('complete','held') or plan.get('release_required')):return False
    members=batch.get('members') or []
    queue={e['id']:e for e in society['town']['daily']['queue']}
    return bool(members) and all(
        m.get('phase') in ('complete','held')
        and queue.get(m.get('event_id'),{}).get('status')==m['phase']
        and (not m.get('command') or m.get('receipt',{}).get('release_verified') is True)
        for m in members)


def isolated_released_conversation(state, event_id, session):
    """An individual failed chat cannot freeze a town after verified cleanup."""
    society=state['society'];c=society.get('conversation') or {}
    if (state['bridge'].get('session')!=session or c.get('id')!=event_id
            or c.get('phase')!='held' or c.get('social_settled') is not True
            or c.get('mode')!='autonomous_social' or c.get('interruption')
            or society.get('error') or society.get('transition') or society.get('unsettled_effect')
            or state['bridge'].get('command')):return False
    release=c.get('release_evidence') or {}
    if (release.get('id')!='release-chat-'+event_id or release.get('released') is not True
            or release.get('status')!='applied'):return False
    if c.get('paired_attendance'):
        attendance=release.get('attendance') or {};participants=attendance.get('participants') or []
        if (attendance.get('id')!='attend-'+event_id or attendance.get('phase')!='released'
                or sorted(p.get('actor',-1) for p in participants)!=sorted(c.get('speakers',[]))
                or not participants or not all(p.get('released') is True and p.get('ownedPackage') is False for p in participants)):
            return False
    if c.get('current',{}).get('delivery_id') and release.get('speechStop',{}).get('acknowledged') is not True:
        return False
    batch=society.get('routine_batch') or {};plan=society.get('plan') or {}
    if batch and (batch.get('phase') not in ('complete','held') or batch.get('settled') is not True
                  or batch.get('release_verified') is not True):return False
    if plan and (plan.get('phase') not in ('complete','held') or plan.get('release_required')):return False
    queued=next((e for e in society['town']['daily']['queue'] if e['id']==event_id),None)
    return queued is None or queued.get('status')=='held'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--max-events',type=int,default=0)
    parser.add_argument('--watch-seconds',type=int,default=0)
    parser.add_argument('--model-config',type=Path)
    parser.add_argument('--language-config',type=Path,help=f'Enables scheduled social encounters with at most {MAX_COMBINED_CALLS} model calls each')
    parser.add_argument('--parallel-journeys',action='store_true',help='Group up to eight eligible food-search journeys within the event budget')
    parser.add_argument('--receipt',type=Path)
    parser.add_argument('--stop-file',type=Path,help='Stop between settled events; never interrupt a native effect')
    parser.add_argument('--social-opportunities',action='store_true',help='Offer nearby encounters between economic events; participation remains a resident choice')
    args=parser.parse_args()
    if not 0<=args.max_events<=24 or not 0<=args.watch_seconds<=600:
        raise ValueError('Use 0–24 resident events and 0–600 seconds of observation')
    if args.max_events and not args.model_config:raise ValueError('An explicit decision model configuration is required')
    if args.social_opportunities and not args.language_config:raise ValueError('Social opportunities require a language configuration')
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
              'maximum_model_calls':(MAX_COMBINED_CALLS if args.language_config else 5)*args.max_events,'status':'running'}
    output=args.receipt or runtime/('daily-life-'+str(time.time_ns())+'.json')
    def stopping():return args.stop_file is not None and args.stop_file.exists()
    def record():output.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    record();deadline=time.monotonic()+args.watch_seconds;first=True
    try:
        while first or time.monotonic()<deadline:
            if stopping():break
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
            pending=fair_pending((e for e in queue if e['status']=='pending' and e['actor'] in loaded
                            and (e['kind']!='social_review' or args.language_config)),
                           social_first=len(evidence['events'])%2==0)
            if args.social_opportunities and len(evidence['events'])%2==0 and not any(e['kind']=='social_review' and event_available(state,e) for e in pending):
                opportunity={'id':'encounter-'+uuid.uuid4().hex[:20],'kind':'social_opportunity','actor':None,
                             'source':'director nearby opportunity; not a claimed urgent need'}
                if event_available(state,opportunity):pending.insert(0,opportunity)
            if args.parallel_journeys:
                remaining=args.max_events-len(evidence['events'])
                overlap=bool(args.language_config and remaining>=3)
                selected=select_routine_events(state['society'],state['bridge']['observation'],pending,min(6 if overlap else 8,remaining-int(overlap)))
                if len(selected)>=2:
                    ids=[e['id'] for e in selected];batch_id='daily-routes-'+hashlib.sha256('|'.join(ids).encode()).hexdigest()[:16]
                    command=[sys.executable,str(Path(__file__).with_name('run_parallel_routines.py')),
                        '--root',str(args.root),'--id',batch_id,'--events',*ids,'--model-config',str(args.model_config)]
                    if overlap:command+=['--social-during-travel','--language-config',str(args.language_config)]
                    result=subprocess.run(command,check=False)
                    current=fresh();batch=current['society'].get('routine_batch')
                    if current['bridge']['session']!=session or not batch or batch['id']!=batch_id:
                        raise ValueError('Independent-journey cohort did not finish cleanly')
                    for member in batch['members']:
                        evidence['events'].append({'id':member['event_id'],'actor':member['actor'],'status':member['phase'],
                            'outcome':member.get('outcome'),'model_calls':int(bool(member.get('result'))),'cohort':batch_id})
                    if overlap:
                        receipt_path=runtime/('parallel-routines-'+hashlib.sha256(batch_id.encode()).hexdigest()[:12]+'.json')
                        receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
                        if receipt.get('id')!=batch_id:raise ValueError('Concurrent worker receipt mismatch')
                        if receipt.get('social_event'):evidence['events'].append({**receipt['social_event'],'cohort':batch_id})
                    record()
                    if result.returncode:raise ValueError('Concurrent resident activity held; completed receipts retained')
                    if batch['phase']=='held':
                        if not isolated_released_cohort(current,batch_id):
                            raise ValueError('Independent journey has unresolved effects; director stopped')
                        for item in evidence['events']:
                            if item.get('cohort')==batch_id and item['status']=='held':
                                item['continued_other_residents']=True
                        record()
                    # Never repeat a cohort member from this cached queue,
                    # even if another service revision later changes its status.
                    pending=[e for e in pending if e['id'] not in ids]
            for event in pending:
                if stopping() or len(evidence['events'])>=args.max_events:break
                current=fresh()
                if current['bridge']['session']!=session:raise ValueError('Game session changed before resident decision')
                if not event_available(current,event):continue
                evidence['events'].append({'id':event['id'],'actor':event['actor'],'status':'started'});record()
                social=event['kind'] in ('social_review','social_opportunity')
                if social:
                    command=[sys.executable,str(Path(__file__).with_name('run_conversation.py')),'--root',str(args.root),
                        '--id',event['id'],'--decision-config',str(args.model_config),'--language-config',str(args.language_config)]
                    if event['actor'] is not None:command+=['--actor',str(event['actor'])]
                else:command=[sys.executable,str(Path(__file__).with_name('run_resident_event.py')),
                    '--runtime',str(runtime),'--event-id',event['id'],'--actor',str(event['actor']),
                    '--kind',event['kind'],'--model-config',str(args.model_config)]
                if not social and args.language_config:command+=['--voice-trade']
                result=subprocess.run(command,check=False)
                current=fresh()
                if current['bridge']['session']!=session:raise ValueError('Game session changed during resident decision')
                # A worker's hold/finish response can precede the engine's
                # checkpoint acknowledgement. Inspect the committed plan only.
                settle_until=time.monotonic()+30
                while current['society']['transition'] and time.monotonic()<settle_until:
                    time.sleep(.4);current=fresh()
                    if current['bridge']['session']!=session:raise ValueError('Session changed while settling worker checkpoint')
                if current['society']['transition']:raise TimeoutError('Resident worker checkpoint did not settle')
                plan=current['society']['conversation'] if social else current['society']['plan']
                if not social and plan and plan.get('effect_free_hold'):
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
                if social and plan and plan.get('id')==event['id'] and plan.get('phase') in ('releasing','held'):
                    release_until=time.monotonic()+30
                    while not isolated_released_conversation(current,event['id'],session) and time.monotonic()<release_until:
                        # A terminal failure without a releasable route cannot be certified here.
                        if (current['society'].get('conversation') or {}).get('phase')=='held' and not current['society']['transition']:
                            break
                        time.sleep(.2);current=fresh()
                        if current['bridge']['session']!=session:raise ValueError('Session changed while releasing failed encounter')
                    if isolated_released_conversation(current,event['id'],session):
                        worker_file=runtime/('conversation-'+hashlib.sha256(event['id'].encode()).hexdigest()[:12]+'.json')
                        worker=json.loads(worker_file.read_text(encoding='utf-8'))
                        if worker.get('id')!=event['id'] or worker.get('status')!='held':raise ValueError('Failed conversation receipt mismatch')
                        plan=current['society']['conversation']
                        evidence['events'][-1].update(actor=plan.get('initiator'),status='held',outcome='failed_encounter_released',
                            error=plan.get('error'),model_calls=sum(worker['calls'].values()),continued_other_residents=True)
                        record();continue
                if result.returncode or not plan or plan['id']!=event['id']:
                    evidence['events'][-1].update(status='held',error=(plan or {}).get('error','Resident worker did not finish cleanly'))
                    record();raise ValueError(evidence['events'][-1]['error'])
                calls=len(recorded_model_results(plan)) if social else len(plan['decisions'])
                if social:evidence['events'][-1]['actor']=plan.get('initiator')
                evidence['events'][-1].update(status=plan['phase'],outcome=plan.get('outcome'),model_calls=calls)
                record()
                if plan['phase']=='held':raise ValueError('Scheduled resident event held; no automatic retry')
                # Re-observe the town after each event. This also gives the
                # director a chance to offer the next social opportunity.
                if args.social_opportunities:break
            if args.max_events and len(evidence['events'])>=args.max_events:break
            if time.monotonic()<deadline:time.sleep(min(2,max(.01,deadline-time.monotonic())))
        evidence.update(status='stopped' if stopping() else 'complete',after=fresh());record()
        print(json.dumps({'status':'complete','reviews':len(evidence['reviews']),'events':evidence['events'],'evidence':str(output)}))
    except Exception as error:
        evidence.update(status='held',error=str(error));record();raise


if __name__=='__main__':main()
