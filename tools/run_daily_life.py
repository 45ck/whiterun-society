"""Review game-clock needs and optionally run a finite number of queued decisions.

No wall-clock simulation while the game is disconnected. Inference is delegated
to persisted-claim workers: at most six calls per economic event, 16 per
social encounter when an explicit language configuration is supplied.
The watch duration is a scheduling horizon: an already claimed event is settled
before exit. It is not a hard cancellation deadline for network operations.
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
from scene_handoffs import scene_candidates
from dialogue_policy import recorded_model_results,MAX_COMBINED_CALLS
from bargaining import MAX_ECONOMIC_CALLS
from tools.checkpoint_http import CheckpointHTTP
from tools.goal_scheduler import GoalScheduler
from director_policy import load_run_policy, resolve_run_policy
from dispatch_policy import fair_pending, can_insert_social, dispatch_metrics
from tools.run_resident_event import delegated_activity_admission,activity_job_records,owner_work_job_records,delegated_job_completed
from activity_leases import reserved_activity_actors


def routine_dispatch_prefix(state,observation,events):
    """Batch only the consecutive journeys at the front of the fair queue."""
    result=[];leased=reserved_activity_actors(state,observation)
    for event in events:
        if event.get('actor') in leased or event.get('goal_followups') or not select_routine_events(state,observation,[event],1):break
        result.append(event)
    return result


def event_available(state,event):
    """Recheck queued work after every previous resident's consequences."""
    society=state['society'];observation=state['bridge']['observation']
    leased=reserved_activity_actors(society,observation)
    if event['kind']=='social_opportunity':
        return any(any(candidate['id'] not in leased for candidate in social_candidates(society,observation,int(key)))
                   for key in society['town']['residents'] if int(key) not in leased)
    if event.get('actor') in leased:return False
    current=next((e for e in society['town']['daily']['queue'] if e['id']==event['id']),None)
    if not current or current['status']!='pending':return False
    if not any(r['id']==event['actor'] and r.get('isPerson') is True and not activity_blocker(r) for r in observation['residents']):return False
    return event['kind']!='social_review' or any(candidate['id'] not in leased for candidate in social_candidates(society,observation,event['actor']))


def observe_delegated_completions(evidence,state):
    """Record later verified receipts without relabelling an admission as work."""
    jobs={'rest':activity_job_records(state['society']),'owner_production':owner_work_job_records(state['society'])}
    session=state['bridge'].get('session')
    for event in evidence.get('events',[]):
        kind=event.get('activity_kind','owner_production' if event.get('work_job_id') else 'rest')
        job=jobs.get(kind,{}).get(event.get('work_job_id') or event.get('activity_job_id'))
        if not job or job.get('source_plan')!=event['id'] or job.get('actor')!=event.get('actor') or job.get('session')!=session:continue
        event['activity_observed_phase']=job.get('phase')
        if job.get('phase')=='held':event['activity_outcome']=job.get('outcome','independent_activity_held')
        if delegated_job_completed(job,kind):
            event.update(completion_confirmed=True,activity_outcome=job.get('outcome'))


def event_counts(events):
    return {'attempted_events':len(events),
            'independent_activity_admissions':sum(e.get('admission_verified') is True for e in events),
            'confirmed_completions':sum(e.get('status')=='complete' or e.get('completion_confirmed') is True for e in events),
            'admitted_activities_without_confirmed_completion':sum(e.get('admission_verified') is True and e.get('completion_confirmed') is not True for e in events),
            'held_workers':sum(e.get('status')=='held' for e in events)}


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
    parser.add_argument('--resident-goals',action='store_true',help='Give residents bounded personal decisions under the recorded run policy')
    parser.add_argument('--run-policy',type=Path,help='Frozen validated director policy; its event and scheduling limits must match the CLI')
    parser.add_argument('--receipt',type=Path)
    parser.add_argument('--stop-file',type=Path,help='Stop between settled events; never interrupt a native effect')
    parser.add_argument('--social-opportunities',action='store_true',help='Offer nearby encounters between economic events; participation remains a resident choice')
    parser.add_argument('--scene-handoffs',action='store_true',help='Request bounded native scene interruption before resident decisions; scene scripts may run')
    args=parser.parse_args()
    if not 0<=args.max_events<=96 or not 0<=args.watch_seconds<=3600:
        raise ValueError('Use 0–96 resident events and 0–3600 seconds of observation')
    if args.max_events and not args.model_config:raise ValueError('An explicit decision model configuration is required')
    if args.resident_goals and not args.model_config:raise ValueError('Personal goals require a decision model configuration')
    if args.social_opportunities and not args.language_config:raise ValueError('Social opportunities require a language configuration')
    run_policy=(load_run_policy(args.run_policy,expected_max_events=args.max_events,expected_watch_seconds=args.watch_seconds)
                if args.run_policy else resolve_run_policy('play' if args.max_events>12 or args.watch_seconds>600 else 'sample',
                                                          max_events=args.max_events,watch_seconds=args.watch_seconds))
    runtime=args.root/'runtime'
    config=json.loads((runtime/'bridge-config.json').read_text())
    client=CheckpointHTTP(f"http://127.0.0.1:{config['port']}",config['token'])
    def request(route,data=None):
        try:
            return client(route,data)
        except urllib.error.HTTPError as error:raise ValueError(json.load(error).get('error','Request rejected')) from None
    def fresh():
        state=request('/state')
        if not state['bridge']['last_seen'] or time.time()-state['bridge']['last_seen']>10:
            raise ValueError('Game observation is stale; no offline progression')
        if state['society']['error']:raise ValueError(state['society']['error'])
        return state
    before=fresh();session=before['bridge']['session']
    evidence={'before':before,'started_at':time.time(),'reviews':[],'events':[],'scene_handoffs':[],'goal_waves':[],'goal_model_calls':0,
              'run_policy':run_policy,
              'maximum_model_calls':(MAX_COMBINED_CALLS if args.language_config else MAX_ECONOMIC_CALLS)*args.max_events+(run_policy['goal_budget'] if args.resident_goals else 0),'status':'running'}
    output=args.receipt or runtime/('daily-life-'+str(time.time_ns())+'.json')
    def stopping():return args.stop_file is not None and args.stop_file.exists()
    def record():
        evidence['event_counts']=event_counts(evidence['events'])
        output.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    record();deadline=time.monotonic()+args.watch_seconds;first=True
    goals=GoalScheduler(args.root,args.model_config,session,evidence,record,budget=run_policy['goal_budget'],
                        interval=run_policy['goal_review_seconds']) if args.resident_goals else None
    initial_goals=False
    def scheduling_open():return not stopping() and time.monotonic()<deadline
    def run_worker(command):
        # Recheck at launch, after any observation or receipt-writing latency.
        # Returning None means no claim, subprocess or model call was started.
        if not scheduling_open():return None
        return goals.run_foreground(command,fresh,stopping,deadline) if goals else subprocess.run(command,check=False)
    try:
        while first or time.monotonic()<deadline:
            if stopping():break
            first=False;state=fresh()
            if state['bridge']['session']!=session:raise ValueError('Save/session changed; director stopped')
            settle_deadline=time.monotonic()+40
            while state['society']['transition'] or state['bridge']['command']:
                if time.monotonic()>settle_deadline:raise TimeoutError('Native/checkpoint command did not settle before director review')
                time.sleep(.2);state=fresh()
                if state['bridge']['session']!=session:raise ValueError('Save/session changed while waiting for director review')
            candidates=scene_candidates(state['society'],state['bridge']['observation']) if args.scene_handoffs else []
            if candidates and len(evidence['scene_handoffs'])<args.max_events and scheduling_open():
                resident=candidates[0];handoff_id='scene-'+uuid.uuid4().hex[:20]
                request('/town/scene-handoff',{'id':handoff_id,'actor':resident['id'],'scene_id':resident['activity']['scene_id']})
                handoff_deadline=time.monotonic()+45
                while True:
                    state=fresh()
                    if state['bridge']['session']!=session:raise ValueError('Save/session changed during scene handoff')
                    handoff=next((h for h in state['society'].get('scene_handoffs',[]) if h['id']==handoff_id),None)
                    if handoff and handoff['status']!='pending' and not state['society']['transition']:
                        evidence['scene_handoffs'].append(handoff);record();break
                    if time.monotonic()>handoff_deadline:raise TimeoutError('Scene handoff did not settle; no automatic retry')
                    time.sleep(.2)
            if goals:
                goals.tick(state,allow_launch=scheduling_open())
                if not initial_goals:goals.drain();initial_goals=True
                state=fresh()
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
            game_day=state['bridge']['observation'].get('gameDays')
            pending=fair_pending((e for e in queue if e['status']=='pending' and e['actor'] in loaded
                            and (e['kind']!='social_review' or args.language_config)),
                           social_first=len(evidence['events'])%2==0,game_day=game_day)
            evidence['dispatch']=dispatch_metrics(pending,game_day=game_day);record()
            if args.social_opportunities and scheduling_open() and can_insert_social(pending,game_day=game_day) and len(evidence['events'])%2==0 and not any(e['kind']=='social_review' and event_available(state,e) for e in pending):
                opportunity={'id':'encounter-'+uuid.uuid4().hex[:20],'kind':'social_opportunity','actor':None,
                             'source':'director nearby opportunity; not a claimed urgent need'}
                if event_available(state,opportunity):pending.insert(0,opportunity)
            if args.parallel_journeys and scheduling_open():
                remaining=args.max_events-len(evidence['events'])
                overlap=bool(args.language_config and remaining>=3)
                # A travel batch may not jump over an older resident's self-care.
                # Goal reviews retain their full action menu in the normal worker.
                travel_pending=routine_dispatch_prefix(state['society'],state['bridge']['observation'],pending)
                selected=select_routine_events(state['society'],state['bridge']['observation'],travel_pending,min(6 if overlap else 8,remaining-int(overlap)))
                if len(selected)>=2:
                    ids=[e['id'] for e in selected];batch_id='daily-routes-'+hashlib.sha256('|'.join(ids).encode()).hexdigest()[:16]
                    command=[sys.executable,str(Path(__file__).with_name('run_parallel_routines.py')),
                        '--root',str(args.root),'--id',batch_id,'--events',*ids,'--model-config',str(args.model_config)]
                    if overlap:command+=['--social-during-travel','--language-config',str(args.language_config)]
                    result=run_worker(command)
                    if result is None:break
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
                if not scheduling_open() or len(evidence['events'])>=args.max_events:break
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
                if not social and args.language_config:command+=['--voice-trade','--language-config',str(args.language_config)]
                result=run_worker(command)
                if result is None:
                    evidence['events'].pop();record();break
                current=fresh()
                if current['bridge']['session']!=session:raise ValueError('Game session changed during resident decision')
                # A worker's hold/finish response can precede the engine's
                # checkpoint acknowledgement. Inspect the committed plan only.
                settle_until=time.monotonic()+30
                while current['society']['transition'] and time.monotonic()<settle_until:
                    time.sleep(.4);current=fresh()
                    if current['bridge']['session']!=session:raise ValueError('Session changed while settling worker checkpoint')
                if current['society']['transition']:raise TimeoutError('Resident worker checkpoint did not settle')
                observe_delegated_completions(evidence,current)
                plan=current['society']['conversation'] if social else current['society']['plan']
                if not social and plan and plan.get('id')==event['id'] and (plan.get('activity_job') or plan.get('work_job')) and plan.get('phase') in ('delegated','complete'):
                    admission=delegated_activity_admission(current,event['id'],event['actor'],session)
                    worker_file=runtime/('resident-event-'+hashlib.sha256(event['id'].encode()).hexdigest()[:12]+'.json')
                    worker=json.loads(worker_file.read_text(encoding='utf-8'))
                    if (result.returncode or not admission or worker.get('event_id')!=event['id'] or worker.get('status') not in ('delegated','complete')
                            or worker.get('activity_job_id')!=admission['activity_job_id'] or worker.get('admission_verified') is not True
                            or admission['activity_kind']=='owner_production' and (worker.get('activity_kind')!='owner_production' or worker.get('work_job_id')!=admission['work_job_id'])
                            or worker.get('status')=='complete' and admission['completion_confirmed'] is not True
                            or worker.get('before',{}).get('bridge',{}).get('session')!=session):
                        raise ValueError('Independent activity admission was not verified by the resident worker')
                    evidence['events'][-1].update(status=worker['status'],outcome='independent_activity_admitted' if worker['status']=='delegated' else plan.get('outcome'),
                        model_calls=worker['model_calls'],continued_other_residents=True,**admission)
                    record();continue
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
        if goals:goals.drain()
        after=fresh();observe_delegated_completions(evidence,after)
        evidence.update(status='stopped' if stopping() else 'complete',after=after);record()
        print(json.dumps({'status':'complete','reviews':len(evidence['reviews']),'events':evidence['events'],'evidence':str(output)}))
    except Exception as error:
        evidence.update(status='held',error=str(error));record();raise
    finally:
        if goals:goals.drain();record()


if __name__=='__main__':main()
