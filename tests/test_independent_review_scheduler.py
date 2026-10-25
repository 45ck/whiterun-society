import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from tools.goal_scheduler import GoalScheduler,due_residents,due_independent_reviews
from test_goal_scheduler import snapshot,Process


class SharedReviewSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'runtime').mkdir();self.evidence={}
        self.scheduler=GoalScheduler(self.root,'frozen-model.json','a',self.evidence,lambda:None,budget=8,interval=0)

    def settle(self,process,calls=None,status='complete'):
        wave=self.scheduler.wave;calls=wave['limit'] if calls is None else calls
        saved={'id':wave['id'],'phase':'complete','claim_id':'claimed'}
        society={'independent_review_waves':[saved]} if wave['lane']=='independent_reviews' else {'town':{'goal_waves':[saved]}}
        wave['path'].write_text(json.dumps({'id':wave['id'],'status':status,'model_calls':calls,'claim_id':'claimed',
            'before':{'bridge':{'session':'a'}},'after':{'bridge':{'session':'a'},'society':society}}))
        process.returncode=0;self.scheduler.tick(allow_launch=False)

    def test_both_due_lanes_alternate_one_subprocess_and_one_budget(self):
        processes=[]
        def spawn(*args,**kwargs):
            process=Process();processes.append(process);return process
        with patch('tools.goal_scheduler.due_independent_reviews',return_value=[{'actor':9}]),\
                patch('tools.goal_scheduler.subprocess.Popen',side_effect=spawn) as opened:
            lanes=[]
            for _ in range(4):
                self.assertTrue(self.scheduler.tick(snapshot(1)));lanes.append(self.scheduler.wave['lane'])
                self.assertFalse(self.scheduler.tick(snapshot(1)))
                self.settle(processes[-1])
        self.assertEqual(lanes,['goals','independent_reviews','goals','independent_reviews'])
        self.assertEqual(opened.call_count,4);self.assertEqual(self.scheduler.budget_used,4)
        self.assertEqual(self.evidence['goal_model_calls'],2)
        self.assertEqual(self.evidence['independent_review_model_calls'],2)
        self.assertEqual(self.evidence['background_model_calls'],4)
        self.assertTrue(all('frozen-model.json' in call.args[0] for call in opened.call_args_list))

    def test_reviews_alone_use_remaining_cap_and_unknown_cost_still_consumes_attempt(self):
        process=Process();self.scheduler.budget=2
        with patch('tools.goal_scheduler.due_residents',return_value=[]),\
                patch('tools.goal_scheduler.due_independent_reviews',return_value=[{'actor':i} for i in range(5)]),\
                patch('tools.goal_scheduler.subprocess.Popen',return_value=process) as opened:
            self.assertTrue(self.scheduler.tick(snapshot()));self.assertEqual(self.scheduler.wave['limit'],2)
            self.settle(process)
            self.assertFalse(self.scheduler.tick(snapshot()));self.assertEqual(opened.call_count,1)
        self.assertEqual(self.scheduler.budget_used,2)
        self.assertEqual(self.evidence['independent_review_model_calls'],2)
        self.assertEqual(self.evidence['goal_model_calls'],0)

    def test_unknown_review_receipt_retains_full_reservation_and_is_not_replayed(self):
        process=Process()
        with patch('tools.goal_scheduler.due_residents',return_value=[]),\
                patch('tools.goal_scheduler.due_independent_reviews',return_value=[{'actor':7},{'actor':8}]),\
                patch('tools.goal_scheduler.subprocess.Popen',return_value=process) as opened:
            self.scheduler.tick(snapshot());process.returncode=1;self.scheduler.drain()
            self.assertFalse(self.scheduler.tick(snapshot()));self.assertEqual(opened.call_count,1)
        self.assertEqual(self.scheduler.budget_used,2);self.assertTrue(self.scheduler.disabled)
        self.assertEqual(self.evidence['independent_review_waves'][0]['reserved_unconfirmed_calls'],2)

    def test_foreground_drain_never_orphans_started_review_or_starts_after_stop(self):
        foreground=Process([None,None,0]);review=Process([None,0]);current=snapshot()
        def spawn(command,**kwargs):
            if command[1].endswith('run_independent_reviews.py'):
                wave=self.scheduler.wave;saved={'id':wave['id'],'phase':'complete','claim_id':'claimed'}
                wave['path'].write_text(json.dumps({'id':wave['id'],'status':'complete','model_calls':1,'claim_id':'claimed',
                    'before':{'bridge':{'session':'a'}},'after':{'bridge':{'session':'a'},'society':{'independent_review_waves':[saved]}}}))
                return review
            return foreground
        with patch('tools.goal_scheduler.due_residents',return_value=[]),\
                patch('tools.goal_scheduler.due_independent_reviews',side_effect=[[{'actor':7}],[]]),\
                patch('tools.goal_scheduler.subprocess.Popen',side_effect=spawn) as opened,patch('tools.goal_scheduler.time.sleep'):
            result=self.scheduler.run_foreground(['python','foreground.py'],lambda:current,lambda:False,time.monotonic()+60)
            self.assertEqual(result.returncode,0);self.assertTrue(foreground.waited)
            self.assertIsNone(self.scheduler.process);self.assertEqual(opened.call_count,2)
            self.assertFalse(self.scheduler.tick(current,allow_launch=False))

    def test_pending_review_claim_blocks_both_lanes_before_launch(self):
        current=snapshot();current['society']['independent_review_waves']=[{'phase':'thinking'}]
        self.assertEqual(due_residents(current),[]);self.assertEqual(due_independent_reviews(current),[])

    def test_real_candidate_filter_uses_current_foreground_plan_from_public_snapshot(self):
        current=snapshot(3)
        current['society']['plan']={'id':'foreground','phase':'travelling','actor':1,'target':3}
        current['society']['town']['daily']={'queue':[
            {'id':'review-'+str(actor),'actor':actor,'kind':'need_review','status':'pending',
             'goal_followups':[{'focus':'rest'}]} for actor in (1,2,3)]}
        self.assertEqual([event['actor'] for event in due_independent_reviews(current)],[2])


if __name__=='__main__':unittest.main()
