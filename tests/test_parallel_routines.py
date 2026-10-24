import copy
import unittest
import test_daily_life
from places import MARKET
from tools.verify_plan_save import plugins_compatible
from parallel_routines import select_routine_events


class ParallelRoutineTests(unittest.TestCase):
    tearDown=test_daily_life.DailyLifeTests.tearDown
    sync=test_daily_life.DailyLifeTests.sync
    census=test_daily_life.DailyLifeTests.census
    review=test_daily_life.DailyLifeTests.review

    def setUp(self):
        test_daily_life.DailyLifeTests.setUp(self)
        self.ids=[108186,99]
        for actor in self.obs['residents']:
            if actor['id'] in self.ids:
                actor.update(isGuard=False,x=1000,y=0,z=0);actor['inventory'].update(bread=0,gold=9)
                self.world.active['people'][str(actor['id'])]['needs']['hunger']=.9
        self.obs['routing']={'available':True,'places':True}
        self.obs['parallel_routines']={'available':True}
        self.obs['places']=[{'id':MARKET,'available':True,'eligible_actors':self.ids,'position':[0,0,0]}]
        self.review()
        self.events=[e['id'] for e in self.world.active['town']['daily']['queue'] if e['actor'] in self.ids]
        self.assertEqual(len(self.events),2)

    def start(self):
        self.batch=self.world.begin_routines('cohort',self.events,self.obs)['batch'];self.sync()

    def choose(self,actions=('check_market','check_market')):
        results=[{'event_id':m['event_id'],'result':{'decision':{'action_id':action,'reason':'Authored unit test choice','emotion':'calm'},'model':'test'}}
                 for m,action in zip(self.batch['members'],actions)]
        self.world.finish_routines('cohort',self.batch['claim_id'],results,self.obs);self.sync()

    def complete(self,change=None):
        jobs=self.world.pending(self.obs['session'])['jobs'];receipts=[]
        for job in jobs:
            receipts.append({'id':job['id'],'slot':job['slot'],'status':'applied','release_verified':True,'seller_nearby':False,
                'movement':{'actor':job['actor'],'target':MARKET,'target_kind':'place','distance':200,'aliasesConfirmed':True,'hasOwnedPackage':True,'adapter':'papyrus-mailbox'}})
        if change:change(receipts)
        self.obs['ack']={'id':'cohort','status':'applied','routines':receipts,'concurrency':{'peak_owned':2,'overlap_samples':12}}
        self.world.observe(self.obs);self.sync()

    def test_two_claims_produce_distinct_slots_and_settle_without_inventory_or_need_changes(self):
        self.start();before=copy.deepcopy(self.obs['residents']);needs={i:copy.deepcopy(self.world.active['people'][str(i)]['needs']) for i in self.ids}
        self.choose();command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'parallel_routines')
        self.assertEqual({j['slot'] for j in command['jobs']},{0,1});self.complete()
        batch=self.world.routine_batch();self.assertEqual(batch['phase'],'complete');self.assertTrue(batch['release_verified'])
        self.assertEqual(before,self.obs['residents']);self.assertFalse(self.world.routines_busy())
        for i in self.ids:
            self.assertEqual(needs[i],self.world.active['people'][str(i)]['needs'])
            self.assertEqual(self.world.active['people'][str(i)]['memories'][-1]['kind'],'market_seller_not_observed')

    def test_one_resident_can_defer_without_blocking_the_other(self):
        self.start();self.choose(('defer','check_market'));self.assertEqual(len(self.world.pending(self.obs['session'])['jobs']),1);self.complete()
        self.assertEqual([m['outcome'] for m in self.world.routine_batch()['members']],['deferred','market_seller_not_observed'])

    def test_all_defer_has_no_native_command(self):
        self.start();self.choose(('defer','defer'));self.assertIsNone(self.world.pending(self.obs['session']));self.assertEqual(self.world.routine_batch()['phase'],'complete')

    def test_other_activity_cannot_steal_claimed_residents(self):
        self.start()
        with self.assertRaises(ValueError):self.world.review_population(self.obs)
        with self.assertRaises(ValueError):self.world.begin_plan('other',self.obs)
        with self.assertRaises(ValueError):self.world.start_conversation('other',self.obs)
        with self.assertRaises(ValueError):self.world.plan_trade('other',self.obs,108186,108149)

    def test_departed_resident_is_held_without_stopping_other_journey(self):
        self.start();self.obs['residents']=[r for r in self.obs['residents'] if r['id']!=108186];self.choose()
        self.assertEqual(len(self.world.pending(self.obs['session'])['jobs']),1);self.complete()
        self.assertEqual(self.world.routine_batch()['members'][0]['outcome'],'changed_before_departure')
        self.assertEqual(self.world.routine_batch()['members'][1]['phase'],'complete')

    def test_wrong_slot_or_missing_ownership_cannot_be_an_arrival(self):
        self.start();self.choose();self.complete(lambda rows:rows[0].update(slot=7))
        self.assertEqual(self.world.routine_batch()['members'][0]['phase'],'held')
        self.assertEqual(self.world.routine_batch()['members'][1]['phase'],'complete')

    def test_unverified_release_keeps_the_native_reconciliation_guard(self):
        self.start();self.choose();self.complete(lambda rows:rows[0].update(release_verified=False))
        self.assertEqual(self.world.active['pending']['status'],'held')
        with self.assertRaises(ValueError):self.world.begin_plan('other',self.obs)

    def test_loading_during_inference_or_execution_does_not_replay(self):
        self.start();old=copy.deepcopy(self.obs);self.choose()
        self.world.observe({**old,'session':'loaded'});self.obs.update(session='loaded');self.sync()
        self.assertEqual(self.world.routine_batch()['phase'],'held');self.assertIsNone(self.world.pending('loaded'))
        self.assertTrue(all(m['outcome']=='journey_interrupted_by_load' for m in self.world.routine_batch()['members']))

    def test_additive_plugin_migration_preserves_every_existing_byte_and_position(self):
        old=[{'name':'Old.esp','sha256':'first'}];new=old+[{'name':'WhiterunLanes.esp','sha256':'new'}]
        self.assertFalse(plugins_compatible(old,new));self.assertTrue(plugins_compatible(old,new,'WhiterunLanes.esp'))
        self.assertFalse(plugins_compatible(old,list(reversed(new)),'WhiterunLanes.esp'))
        self.assertFalse(plugins_compatible(old,[{'name':'Old.esp','sha256':'changed'},new[-1]],'WhiterunLanes.esp'))

    def test_director_selector_obeys_budget_eligibility_and_one_slot_per_resident(self):
        self.obs['residents']=[r for r in self.obs['residents'] if r['id']!=108149]
        queue=self.world.active['town']['daily']['queue']
        self.assertEqual(len(select_routine_events(self.world.active,self.obs,queue)),2)
        self.assertEqual(select_routine_events(self.world.active,self.obs,queue,0),[])
        self.assertEqual(len(select_routine_events(self.world.active,self.obs,queue,1)),1)
        self.assertEqual(len(select_routine_events(self.world.active,self.obs,queue+queue)),2)
        self.obs['residents'][0]['inventory']['bread']=1
        self.assertEqual(len(select_routine_events(self.world.active,self.obs,queue)),1)
        self.obs['parallel_routines']['available']=False
        self.assertEqual(select_routine_events(self.world.active,self.obs,queue),[])

    def test_director_keeps_full_decision_menu_when_seller_is_reachable(self):
        self.obs['routing'].update(adapter='papyrus-mailbox-v1')
        self.assertEqual(select_routine_events(self.world.active,self.obs,self.world.active['town']['daily']['queue']),[])
