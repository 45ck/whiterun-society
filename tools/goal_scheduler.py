"""Share one bounded subprocess and call budget between goals and due reviews."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from resident_goals import occupied
from routing import activity_blocker
from goal_opportunities import pending_goal_review


def active_decision_wave(snapshot):
    society=snapshot['society']
    return any(w.get('phase')=='thinking' for w in [
        *(society.get('town') or {}).get('goal_waves',[]),*society.get('independent_review_waves',[])])


def due_independent_reviews(snapshot):
    society=snapshot['society'];bridge=snapshot['bridge'];obs=bridge.get('observation') or {}
    if (society.get('error') or society.get('transition') or society.get('unsettled_effect')
            or bridge.get('command') or active_decision_wave(snapshot)):return []
    if not ((society.get('town') or {}).get('daily') or {}).get('queue'):return []
    from independent_reviews import independent_review_candidates
    return independent_review_candidates({**society,
        'plans':[society['plan']] if society.get('plan') else [],
        'routine_batches':[society['routine_batch']] if society.get('routine_batch') else []},obs)


def due_residents(snapshot):
    society=snapshot['society'];bridge=snapshot['bridge'];obs=bridge.get('observation') or {}
    town=society.get('town') or {};control=town.get('resident_control') or {}
    if (society.get('error') or society.get('transition') or society.get('unsettled_effect') or bridge.get('command')
            or not control.get('enabled') or (obs.get('resident_control') or {}).get('goal_destinations') is not True
            or active_decision_wave(snapshot)):return []
    day=obs.get('gameDays')
    if type(day) not in (int,float) or not math.isfinite(day):return []
    busy=occupied({**society,'plans':[society['plan']] if society.get('plan') else [],
                   'routine_batches':[society['routine_batch']] if society.get('routine_batch') else []},obs)
    people=society.get('people',{});due=[]
    for row in obs.get('residents',[]):
        actor=row['id'];key=str(actor);person=people.get(key)
        if (key not in control.get('assignments',{}) or not person or row.get('isPerson') is not True
                or actor in busy or activity_blocker(row) or pending_goal_review(society,actor)):continue
        goal=person.get('standing_goal') or {}
        if goal.get('phase')!='travelling' and day>=goal.get('next_review_day',0):due.append(actor)
    return sorted(set(due))


class GoalScheduler:
    """No background thread: the director owns and drains every subprocess."""
    def __init__(self,root,model_config,session,evidence,record,budget=64,interval=5):
        self.root=Path(root);self.model_config=model_config;self.session=session;self.evidence=evidence;self.record=record
        self.budget=budget;self.interval=interval;self.budget_used=0;self.last_sample=-math.inf
        self.process=None;self.wave=None;self.disabled=False
        self.last_lane=None
        evidence.setdefault('goal_waves',[]);evidence.setdefault('goal_model_calls',0)
        evidence.setdefault('independent_review_waves',[]);evidence.setdefault('independent_review_model_calls',0)
        evidence.setdefault('background_model_calls',0)
        evidence['goal_scheduler']={'budget':budget,'budget_committed':0,'interval_seconds':interval,'status':'idle',
            'scope':'One subprocess shared by alternating due goals and independent reviews; maximum four concurrent inferences. Budget counts call attempts, including attempts without reported cost. Unknown attempts retain their reservation; no constant inference.'}

    def hold(self,reason):
        if not self.disabled:
            self.disabled=True;self.evidence['goal_scheduler'].update(status='held',error=reason);self.record()

    def _finish(self):
        if self.process is None or self.process.poll() is None:return
        code=self.process.returncode;wave=self.wave;self.process=None;self.wave=None
        lane=wave.get('lane','goals');review=lane=='independent_reviews'
        summary={'id':wave['id'],'lane':lane,'status':'held','model_calls':None,'reserved_limit':wave['limit'],'exit_code':code}
        try:
            receipt=json.loads(wave['path'].read_text(encoding='utf-8'))
            if receipt.get('id')!=wave['id']:raise ValueError('Goal receipt identity mismatch')
            calls=receipt.get('model_calls')
            if type(calls) is not int or not 0<=calls<=wave['limit']:raise ValueError('Goal receipt call count invalid')
            if receipt.get('before',{}).get('bridge',{}).get('session')!=self.session:raise ValueError('Goal receipt session mismatch')
            self.evidence['independent_review_model_calls' if review else 'goal_model_calls']+=calls
            self.evidence['background_model_calls']+=calls;summary['model_calls']=calls
            status=receipt.get('status')
            if code!=0 or status not in ('complete','empty'):raise ValueError('Goal worker did not settle; lane held without replay')
            if status=='empty' and calls!=0:raise ValueError('Empty decision wave reported inference')
            if status=='complete':
                after=receipt.get('after') or {};society=after.get('society',{})
                waves=society.get('independent_review_waves',[]) if review else (society.get('town') or {}).get('goal_waves',[])
                saved=next((w for w in waves if w['id']==wave['id']),None)
                if (after.get('bridge',{}).get('session')!=self.session or not saved or saved.get('phase')!='complete'
                        or saved.get('claim_id')!=receipt.get('claim_id')):raise ValueError('Goal completion lacks matching saved claim')
            self.budget_used-=wave['limit']-calls
            summary.update(status=status,reported_cost=receipt.get('reported_cost'),cost_reports=receipt.get('cost_reports'),
                           failed_results=sum(bool(r.get('result',{}).get('failure')) for r in receipt.get('results',[])))
            self.evidence['goal_scheduler']['status']='held' if self.disabled else 'budget_exhausted' if self.budget_used>=self.budget else 'idle'
        except (OSError,ValueError,KeyError,TypeError) as error:
            summary['reserved_unconfirmed_calls']=wave['limit']-(summary['model_calls'] or 0)
            summary['error']=str(error)[:180];self.hold(summary['error'])
        self.evidence['independent_review_waves' if review else 'goal_waves'].append(summary)
        self.evidence['goal_scheduler'].update(budget_committed=self.budget_used,active_wave=None,active_lane=None)
        self.record()

    def tick(self,snapshot=None,allow_launch=True):
        self._finish()
        if self.process is not None or self.disabled or not allow_launch or self.budget_used>=self.budget:return False
        now=time.monotonic()
        if now-self.last_sample<self.interval:return False
        self.last_sample=now
        if not snapshot:return False
        bridge=snapshot['bridge']
        if bridge.get('session')!=self.session:self.hold('Game session changed; personal-goal lane stopped');return False
        if not bridge.get('last_seen') or time.time()-bridge['last_seen']>10:return False
        goals=due_residents(snapshot);reviews=due_independent_reviews(snapshot)
        if not goals and not reviews:return False
        # Alternate eligible lanes, so a stream of review events cannot starve
        # resident goals (or consume the shared budget without giving them a turn).
        lane='independent_reviews' if reviews and (not goals or self.last_lane=='goals') else 'goals'
        review=lane=='independent_reviews';due=reviews if review else goals
        limit=min(32,self.budget-self.budget_used,len(due));wave_id=('reviews-' if review else 'goals-')+uuid.uuid4().hex[:20]
        prefix='independent-reviews-' if review else 'resident-goals-'
        path=self.root/'runtime'/(prefix+hashlib.sha256(wave_id.encode()).hexdigest()[:12]+'.json')
        worker='run_independent_reviews.py' if review else 'run_resident_goals.py'
        command=[sys.executable,str(Path(__file__).with_name(worker)),'--root',str(self.root),
                 '--id',wave_id,'--limit',str(limit),'--model-config',str(self.model_config)]
        self.wave={'id':wave_id,'limit':limit,'path':path,'lane':lane};self.budget_used+=limit
        self.evidence['goal_scheduler'].update(status='running',active_wave=wave_id,active_lane=lane,budget_committed=self.budget_used)
        self.record()
        try:self.process=subprocess.Popen(command,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except OSError:
            self.budget_used-=limit;self.wave=None
            self.evidence['goal_scheduler'].update(active_wave=None,active_lane=None,budget_committed=self.budget_used)
            self.hold('Personal-goal worker could not start');return False
        self.last_lane=lane
        return True

    def drain(self):
        """Never launch, cancel or abandon an already-started goal worker."""
        while self.process is not None:
            self._finish()
            if self.process is not None:time.sleep(.2)

    def run_foreground(self,command,snapshot,stopping,deadline):
        process=subprocess.Popen(command,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        last_snapshot=-math.inf
        try:
            while process.poll() is None:
                self._finish()
                if time.monotonic()-last_snapshot>=self.interval:
                    last_snapshot=time.monotonic()
                    try:self.tick(snapshot(),allow_launch=not stopping() and time.monotonic()<deadline)
                    except (OSError,ValueError,KeyError,TypeError):self.hold('Observation unavailable; personal-goal lane stopped')
                time.sleep(.2)
            return subprocess.CompletedProcess(command,process.returncode)
        finally:
            # A sampling error must not orphan speech synthesis or a claimed wave.
            process.wait()
            self.drain()
