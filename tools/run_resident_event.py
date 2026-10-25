"""Run a bounded meal-time event through decisions, owned travel and consent.

The local service persists each claim before inference and owns all game effects.
This worker never writes the timeline database or sends native commands.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decisions import infer
from bargaining import MAX_ECONOMIC_CALLS
from context_window import check_purchase_decision_budget, purchase_decision_counts, MAX_PURCHASE_NAVIGATION_CALLS
from tools.voice_worker import VoiceWorker
from tools.run_conversation import stock_voice
from language import propose, LanguageOutputError
from economic_language import MAX_ECONOMIC_LANGUAGE_CALLS
from tools.prepared_speech import PreparedSpeech
from tools.checkpoint_http import CheckpointHTTP


def _job_records(status):
    if isinstance(status.get('jobs'),list):
        return {job['id']:job for job in [*status.get('history',[]),*status['jobs']] if isinstance(job,dict) and isinstance(job.get('id'),str)}
    return {key:job for key,job in status.items() if isinstance(job,dict) and job.get('id')==key}

def activity_job_records(society):
    """Read public rest status, including fast acknowledged results."""
    return _job_records(society.get('activity_jobs') or {})

def owner_work_job_records(society):
    return _job_records(society.get('owner_work_jobs',society.get('work_jobs')) or {})

def paid_work_job_records(society):
    return _job_records(society.get('paid_employment') or {})


def has_delegated_job(plan):
    return any(plan.get(key) for key in ('activity_job','work_job','paid_work_job'))


def delegated_job_completed(job,kind):
    if job.get('phase')!='complete' or job.get('release_verified') is not True or not job.get('receipt_hash'):return False
    if kind=='rest':return True
    settlement=job.get('settlement') or {}
    if kind=='paid_employment':
        return (type(job.get('protocol')) is int and job['protocol']==2 and not job.get('orphan')
            and job.get('effect_unreconciled') is False and bool(job.get('effect_receipt_hash'))
            and settlement.get('phase')=='committed'
            and all(settlement.get(key) is True for key in ('output_verified','wage_debit_verified','wages_verified','inventory_verified'))
            and isinstance(settlement.get('commit_id'),str) and bool(settlement['commit_id'])
            and settlement.get('production_record_id')==settlement['commit_id'])
    return (kind=='owner_production' and not job.get('orphan') and settlement.get('phase')=='committed'
            and settlement.get('committed_inventory_verified') is True
            and isinstance(settlement.get('commit_id'),str) and bool(settlement['commit_id'])
            and settlement.get('production_record_id')==settlement['commit_id'])


def delegated_activity_admission(state,event_id,actor,session):
    """A persisted exact native acceptance frees this worker, never proves output."""
    society=state['society'];plan=society.get('plan') or {}
    if state['bridge'].get('session')!=session:raise ValueError('Delegated activity belongs to another game session')
    if society.get('transition'):return None
    if plan.get('id')!=event_id or plan.get('actor')!=actor or plan.get('phase') not in ('delegated','complete'):
        raise ValueError('Delegated activity does not match the current resident plan')
    protocols=[(key,kind,records) for key,kind,records in (
        ('activity_job','rest',activity_job_records),('work_job','owner_production',owner_work_job_records),
        ('paid_work_job','paid_employment',paid_work_job_records)) if plan.get(key)]
    if len(protocols)!=1:raise ValueError('Delegated activity requires one unambiguous job protocol')
    field,kind,records=protocols[0];job_id=plan[field];job=records(society).get(job_id)
    work=kind=='owner_production';paid=kind=='paid_employment'
    actor_field='worker' if paid else 'actor'
    if (not isinstance(job,dict) or job.get('id')!=job_id or job.get('source_plan')!=event_id
            or type(job.get(actor_field)) is not int or job[actor_field]!=actor or job.get('session')!=session
            or job.get('orphan')):
        raise ValueError('Delegated activity lacks a matching saved job')
    if paid:
        terms=plan.get('work_terms') or {};status=society.get('paid_employment') or {}
        native=(state['bridge'].get('observation') or {}).get('paid_employment') or {}
        if (type(job.get('protocol')) is not int or job['protocol']!=2
                or job.get('job_id')!=job_id or job.get('employer')!=plan.get('target')
                or job.get('epoch')!=status.get('epoch') or not job.get('epoch')
                or native.get('available') is not True or type(native.get('protocol')) is not int or native['protocol']!=2
                or native.get('epoch')!=job['epoch']
                or any(job.get(key)!=terms.get(key) for key in ('worker','worker_base_id','employer','employer_base_id',
                    'recipe_id','catalog_hash','recipe_hash','terms_hash','business_id'))
                or job.get('business_revision')!=terms.get('revision')
                or not isinstance(job.get('consent_hash'),str) or not job['consent_hash']):
            raise ValueError('Delegated paid employment identity or terms do not match')
    if job.get('phase')=='prepared':return None
    result={'activity_job_id':job_id,'activity_phase':job['phase'],'activity_kind':kind,
            'admission_verified':True,'completion_confirmed':False}
    if work:result['work_job_id']=job_id
    if paid:
        result['paid_work_job_id']=job_id
        result['paid_identity']={key:job[key] for key in ('worker','worker_base_id','employer','employer_base_id',
            'session','epoch','business_id','business_revision','recipe_id','catalog_hash','recipe_hash','terms_hash','consent_hash')}
    if delegated_job_completed(job,kind):return {**result,'completion_confirmed':True}
    accepted=job.get('phase')=='running'
    if work and job.get('phase') in ('attendance_verified','recipe_prepared','recipe_committed'):
        accepted=bool(job.get('attendance_receipt_hash'))
        if job['phase']=='recipe_committed':
            settlement=job.get('settlement') or {}
            accepted=accepted and settlement.get('phase')=='committed' and settlement.get('committed_inventory_verified') is True
    if paid:
        accepted=(job.get('phase')=='working' and type(job.get('accepted_at')) in (int,float)
            and math.isfinite(job['accepted_at']) and job['accepted_at']>=0)
        if job.get('phase') in ('attendance_verified','commit_prepared','effects_verified'):
            accepted=bool(job.get('attendance_receipt_hash'))
            if job['phase']=='effects_verified':
                settlement=job.get('settlement') or {}
                accepted=accepted and settlement.get('phase')=='committed' and all(settlement.get(key) is True
                    for key in ('output_verified','wage_debit_verified','wages_verified','inventory_verified'))
    if not accepted or job.get('receipt_acknowledged'):
        raise ValueError('Independent activity has no current accepted native admission')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--event-id', required=True)
    parser.add_argument('--model-config', type=Path)
    parser.add_argument('--language-config', type=Path,help='Generate and select contextual phrasing around exact economic terms')
    parser.add_argument('--actor', type=int, required=True)
    parser.add_argument('--voice-trade',action='store_true',help='Speak grounded offers and outcomes before continuing the trade')
    parser.add_argument('--kind', choices=('meal_time','stock_review','work_shift','need_review'), default='meal_time')
    args = parser.parse_args()
    if args.language_config and not args.voice_trade:raise ValueError('Economic language requires voiced trade')
    config = json.loads((args.runtime/'bridge-config.json').read_text())
    model = json.loads((args.model_config or args.runtime/'model-config.json').read_text())
    key = os.environ[model['key_env']] if model.get('key_env') else Path(model['key_file']).read_text().strip()
    wording=json.loads(args.language_config.read_text()) if args.language_config else None
    wording_key=(os.environ[wording['key_env']] if wording.get('key_env') else Path(wording['key_file']).read_text().strip()) if wording else None

    client=CheckpointHTTP(f"http://127.0.0.1:{config['port']}",config['token'])
    def request(route, data=None):
        try:
            result=client(route,data)
        except urllib.error.HTTPError as error:
            raise ValueError(json.load(error).get('error', 'Request rejected')) from None
        if route == '/state' and (not result['bridge']['last_seen'] or time.time()-result['bridge']['last_seen'] > 10):
            raise ValueError('Game observation is stale')
        return result

    evidence = {'event_id': args.event_id, 'started_at': time.time(), 'model_calls': 0,'wording_calls':0,
                'before': request('/state'), 'stages': [],
                'polling':{'checkpoint_seconds':.1,'native_wait_seconds':.2,'sleep_after_mutation':False}}
    path = args.runtime/('resident-event-'+hashlib.sha256(args.event_id.encode()).hexdigest()[:12]+'.json')
    def record(stage, state):
        evidence['stages'].append({'at': time.time(), 'phase': stage, 'plan': state['society'].get('plan')})
        path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(json.dumps({'phase': stage, 'model_calls': evidence['model_calls']}), flush=True)

    started = request('/agency/event', {'id': args.event_id, 'actor':args.actor, 'kind':args.kind,'voiced_trade':args.voice_trade,'natural_trade':bool(wording)})
    if started.get('duplicate'):
        print(json.dumps({'duplicate': True, 'model_calls': 0, 'phase': started['plan']['phase']}), flush=True)
        return
    previous = None;voice_worker=None;prepared=PreparedSpeech();independent_owner=False
    deadline = time.monotonic()+480
    try:
        while time.monotonic() < deadline:
            state = request('/state')
            society = state['society']
            if state['bridge']['session']!=evidence['before']['bridge']['session']:
                raise ValueError('Game session changed during the resident event')
            if society['transition']:
                time.sleep(.1)
                continue
            if society['error']:
                raise ValueError(society['error'])
            plan = society.get('plan')
            if not plan or plan['id'] != args.event_id:
                raise ValueError('Active plan changed, possibly after loading another save')
            phase = plan['phase']
            independent_owner=independent_owner or has_delegated_job(plan)
            if previous != phase:
                record(phase, state)
                previous = phase
            if phase=='delegated':
                independent_owner=True
                admission=delegated_activity_admission(state,args.event_id,args.actor,evidence['before']['bridge']['session'])
                if admission:
                    evidence.update(after=state,status='delegated',outcome='independent_activity_admitted',**admission)
                    path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
                    print(json.dumps({'status':'delegated','outcome':evidence['outcome'],**admission,'evidence':str(path)}),flush=True)
                    return
                time.sleep(.2);continue
            if args.voice_trade and phase in ('travelling','economic_attending','economic_propose','economic_synthesize') and voice_worker is None:
                # At most five spoken turns: two silent options plus a possible
                # original-terms fallback each. Preparation never plays audio.
                voice_worker=VoiceWorker(args.runtime.parent,15 if wording else 5,[model.get('key_env'),(wording or {}).get('key_env')])
            if phase in ('complete', 'held') and not plan.get('release_required') and not plan.get('activity_release_required') and plan.get('remembered'):
                if phase=='complete' and has_delegated_job(plan):
                    admission=delegated_activity_admission(state,args.event_id,args.actor,evidence['before']['bridge']['session'])
                    if not admission or not admission['completion_confirmed']:raise ValueError('Completed independent activity lacks a verified receipt')
                    evidence.update(admission)
                evidence['after'] = state
                evidence['status'] = phase
                evidence['outcome'] = plan.get('outcome')
                path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
                print(json.dumps({'status': phase, 'outcome': plan.get('outcome'), 'evidence': str(path)}), flush=True)
                return
            if phase in ('economic_propose','economic_select'):
                if not wording:raise ValueError('This event requires its language configuration')
                if evidence['wording_calls']>=MAX_ECONOMIC_LANGUAGE_CALLS:raise ValueError('Economic wording budget exhausted')
                claim=request('/agency/wording-claim',{'id':args.event_id})['claim']
                confirmed=request('/state')
                while confirmed['society']['transition']:
                    if time.monotonic()>deadline:raise TimeoutError('Wording checkpoint did not bind')
                    time.sleep(.1);confirmed=request('/state')
                current=confirmed['society'].get('plan') or {}
                if (confirmed['bridge']['session']!=claim['session'] or current.get('id')!=args.event_id
                        or (current.get('economic_speech',{}).get('claim') or {}).get('id')!=claim['id']):
                    raise ValueError('Wording claim changed before inference')
                if claim['stage']=='select':
                    count=prepared.prepare(voice_worker,current,claim['session'],
                        stock_voice(current['economic_speech']['actor'],confirmed['bridge']['observation']))
                    evidence['prepared_voice_requests']=evidence.get('prepared_voice_requests',0)+count
                evidence['wording_calls']+=1
                path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
                start=time.monotonic();used=wording if claim['stage']=='propose' else model
                try:
                    result=propose(claim['context'],wording,wording_key) if claim['stage']=='propose' else infer(claim['context'],model,key)
                except LanguageOutputError as error:
                    result={**error.receipt,'failure':'invalid_output'}
                except urllib.error.HTTPError:
                    result={'model':used['model'],'elapsed_seconds':time.monotonic()-start,'failure':'provider_error'}
                except (OSError,TimeoutError):
                    result={'model':used['model'],'elapsed_seconds':time.monotonic()-start,'failure':'transport_error'}
                except ValueError:
                    result={'model':used['model'],'elapsed_seconds':time.monotonic()-start,'failure':'invalid_output'}
                request('/agency/wording-result',{'id':args.event_id,'claim_id':claim['id'],'result':result})
                continue
            if phase.startswith('economic_thinking_'):
                raise ValueError('Economic wording inference already claimed; refusing automatic repetition')
            if phase=='economic_synthesize':
                turn=plan['economic_speech'];began=time.monotonic()
                voice=stock_voice(turn['actor'],state['bridge']['observation'])
                cached=prepared.selected(voice_worker,plan,state['bridge']['session'],voice)
                if cached:audio,timing=cached
                else:
                    audio=voice_worker.synthesize(turn['line'],voice)
                    timing={'mode':'on_demand','wait_seconds':round(time.monotonic()-began,3),'lead_seconds':0}
                evidence.setdefault('synthesis_timings',[]).append({'act':turn['act'],'seconds':round(time.monotonic()-began,3),'engine_seconds':audio['synthesis_seconds'],**timing})
                request('/agency/audio',{'id':args.event_id,'audio':audio['audio']})
                continue  # Observe the persisted audio checkpoint without an extra fixed pause.
            elif phase in ('choose', 'purchase_select', 'quote', 'consent', 'reconsider', 'allocate', 'after_purchase', 'job_offer', 'job_accept'):
                check_purchase_decision_budget(plan)
                evidence['decision_calls']=purchase_decision_counts(plan)
                evidence['maximum_decision_calls']=MAX_ECONOMIC_CALLS+MAX_PURCHASE_NAVIGATION_CALLS
                claim = request('/agency/claim', {'id': args.event_id})['claim']
                # Wait for the persisted claim's game marker before making the call.
                confirmed=request('/state')
                while confirmed['society']['transition']:
                    if time.monotonic() > deadline:
                        raise TimeoutError('Claim checkpoint did not bind')
                    time.sleep(.1)
                    confirmed=request('/state')
                current=confirmed['society'].get('plan')
                if confirmed['bridge']['session']!=claim['context']['session'] or not current or (current.get('claim') or {}).get('id')!=claim['id']:
                    raise ValueError('Claim or game session changed before inference')
                evidence['model_calls'] += 1
                result = infer(claim['context'], model, key)
                request('/agency/decision', {'id': args.event_id, 'claim_id': claim['id'], 'result': result})
                continue  # The next iteration still waits for native checkpoint binding.
            elif phase == 'thinking':
                raise ValueError('An inference claim already exists; it must not be automatically repeated')
            time.sleep(.2)
        raise TimeoutError('Resident event exceeded its bounded execution time')
    except Exception as error:
        evidence['status'] = 'held'
        evidence['error'] = type(error).__name__+': '+str(error)
        if independent_owner:
            # The saved job owns actor/seat leases and terminal receipt handling.
            # A worker observation failure is not authority to cancel that job.
            evidence['independent_job_owns_cleanup']=True
        else:
            try:
                request('/agency/hold', {'id': args.event_id, 'reason': evidence['error']})
            except (OSError, ValueError):
                evidence['hold_not_confirmed'] = True
        path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        raise
    finally:
        if voice_worker:voice_worker.close()


if __name__ == '__main__':
    main()
