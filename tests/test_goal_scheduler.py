import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from tools.goal_scheduler import GoalScheduler,due_residents


def snapshot(n=3):
    return {'bridge':{'session':'a','last_seen':time.time(),'command':None,'observation':{'gameDays':1,
                'resident_control':{'goal_destinations':True},'residents':[{'id':i,'isPerson':True} for i in range(1,n+1)]}},
            'society':{'error':None,'transition':None,'unsettled_effect':None,'people':{str(i):{'standing_goal':{'phase':'arrived','next_review_day':.5}} for i in range(1,n+1)},
                'town':{'goal_waves':[],'resident_control':{'enabled':True,'assignments':{str(i):{'actor':i} for i in range(1,n+1)}}}}}


class Process:
    def __init__(self,polls=None):self.returncode=None;self.polls=list(polls or []);self.waited=False
    def poll(self):
        if self.polls:self.returncode=self.polls.pop(0)
        return self.returncode
    def wait(self):self.waited=True;self.returncode=0;return 0


class GoalSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'runtime').mkdir()
        self.evidence={};self.records=0
    def tearDown(self):self.temp.cleanup()
    def scheduler(self,**kwargs):
        def record():self.records+=1
        return GoalScheduler(self.root,'model.json','a',self.evidence,record,**kwargs)
    def receipt(self,scheduler,calls=None,status='complete'):
        wave=scheduler.wave;calls=wave['limit'] if calls is None else calls
        data={'id':wave['id'],'before':{'bridge':{'session':'a'}},'model_calls':calls,'status':status,'claim_id':'claim',
            'after':{'bridge':{'session':'a'},'society':{'town':{'goal_waves':[{'id':wave['id'],'phase':'complete','claim_id':'claim'}]}}}}
        wave['path'].write_text(json.dumps(data));return wave['path']

    def test_due_eligibility_excludes_foreground_travel_and_future_review(self):
        state=snapshot(5);state['society']['conversation']={'phase':'speaking','speakers':[1,2]}
        state['society']['people']['3']['standing_goal']['phase']='travelling'
        state['society']['people']['4']['standing_goal']['next_review_day']=2
        self.assertEqual(due_residents(state),[5])
        state['society']['town']['goal_waves']=[{'phase':'thinking'}];self.assertEqual(due_residents(state),[])
        state['society']['town']['goal_waves']=[];state['society']['unsettled_effect']={'kind':'trade'};self.assertEqual(due_residents(state),[])

    def test_budget_reservation_prevents_overlap_and_never_exceeds_cap(self):
        scheduler=self.scheduler(budget=4,interval=0);process=Process()
        with patch('tools.goal_scheduler.subprocess.Popen',return_value=process) as opened:
            self.assertTrue(scheduler.tick(snapshot(3)));self.assertEqual(scheduler.budget_used,3)
            self.assertFalse(scheduler.tick(snapshot(3)));self.assertEqual(opened.call_count,1)
            self.receipt(scheduler);process.returncode=0;scheduler.tick(allow_launch=False)
            process.returncode=None;self.assertTrue(scheduler.tick(snapshot(3)))
            self.assertEqual(scheduler.wave['limit'],1);self.receipt(scheduler);process.returncode=0;scheduler.tick(allow_launch=False)
            self.assertEqual(scheduler.budget_used,4);self.assertEqual(self.evidence['goal_model_calls'],4)
            self.assertFalse(scheduler.tick(snapshot(3)));self.assertEqual(opened.call_count,2)

    def test_exact_receipt_identity_is_required_and_failure_isolated_to_lane(self):
        scheduler=self.scheduler(interval=0);process=Process()
        with patch('tools.goal_scheduler.subprocess.Popen',return_value=process):
            scheduler.tick(snapshot());path=self.receipt(scheduler)
            data=json.loads(path.read_text());data['id']='another-wave';path.write_text(json.dumps(data))
            process.returncode=0;scheduler.tick(allow_launch=False)
        self.assertTrue(scheduler.disabled);self.assertIsNone(scheduler.process)
        self.assertEqual(self.evidence['goal_scheduler']['status'],'held');self.assertEqual(scheduler.budget_used,3)
        self.assertFalse(scheduler.tick(snapshot()));self.assertEqual(self.evidence['goal_model_calls'],0)

    def test_failed_partial_worker_does_not_refund_uncertain_attempts(self):
        scheduler=self.scheduler(interval=0);process=Process()
        with patch('tools.goal_scheduler.subprocess.Popen',return_value=process):
            scheduler.tick(snapshot());self.receipt(scheduler,calls=1,status='claimed');process.returncode=1;scheduler.drain()
        self.assertEqual(self.evidence['goal_model_calls'],1);self.assertEqual(scheduler.budget_used,3);self.assertTrue(scheduler.disabled)

    def test_verified_unused_budget_refunded_and_no_launch_after_stop(self):
        scheduler=self.scheduler(interval=0);process=Process()
        with patch('tools.goal_scheduler.subprocess.Popen',return_value=process) as opened:
            scheduler.tick(snapshot());self.receipt(scheduler,calls=1);process.returncode=0
            scheduler.tick(snapshot(),allow_launch=False)
            self.assertEqual(scheduler.budget_used,1);self.assertEqual(opened.call_count,1)
            self.assertIsNone(scheduler.process)

    def test_foreground_continues_and_all_owned_children_are_drained(self):
        scheduler=self.scheduler(interval=0);foreground=Process([None,None,0]);goal=Process([None,0]);calls=[]
        current=snapshot()
        def spawn(command,**kwargs):
            calls.append(command)
            if 'run_resident_goals.py' in command[1]:
                self.receipt(scheduler)
                for p in current['society']['people'].values():p['standing_goal']['next_review_day']=2
                return goal
            return foreground
        with patch('tools.goal_scheduler.subprocess.Popen',side_effect=spawn),patch('tools.goal_scheduler.time.sleep'):
            result=scheduler.run_foreground(['python','foreground.py'],lambda:current,lambda:False,time.monotonic()+60)
        self.assertEqual(result.returncode,0);self.assertTrue(foreground.waited);self.assertIsNone(scheduler.process)
        self.assertEqual(len(calls),2);self.assertEqual(self.evidence['goal_model_calls'],3)

    def test_observation_failure_holds_goal_lane_without_abandoning_foreground(self):
        scheduler=self.scheduler(interval=0);foreground=Process([None,0])
        def unavailable():raise ValueError('stale observation')
        with patch('tools.goal_scheduler.subprocess.Popen',return_value=foreground) as opened,patch('tools.goal_scheduler.time.sleep'):
            result=scheduler.run_foreground(['python','foreground.py'],unavailable,lambda:False,time.monotonic()+60)
        self.assertEqual(result.returncode,0);self.assertTrue(foreground.waited);self.assertTrue(scheduler.disabled)
        self.assertEqual(opened.call_count,1)

    def test_changed_session_or_stale_bridge_never_launches(self):
        for change in ('session','last_seen'):
            scheduler=self.scheduler(interval=0);state=snapshot();state['bridge'][change]='b' if change=='session' else 0
            with patch('tools.goal_scheduler.subprocess.Popen') as opened:self.assertFalse(scheduler.tick(state))
            opened.assert_not_called()


if __name__=='__main__':unittest.main()
