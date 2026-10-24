import copy
import unittest
import test_daily_life
import test_food
from rest import rest_opportunities


class RestTests(unittest.TestCase):
    tearDown=test_daily_life.DailyLifeTests.tearDown
    sync=test_daily_life.DailyLifeTests.sync
    census=test_daily_life.DailyLifeTests.census
    review=test_daily_life.DailyLifeTests.review
    decide=test_food.FoodTests.decide

    def setUp(self):
        test_daily_life.DailyLifeTests.setUp(self)
        self.actor=self.obs['residents'][2];self.actor.update(x=100,y=0,z=0)
        self.world.active['people']['99']['needs'].update(hunger=.2,fatigue=.9)
        self.obs['rest']={'available':True,'sites':[{'id':0x8f15b,'position':[200,0,0],'loaded':True,'occupancy_known':True,'occupied':False}],
            'sensors':{'99':{'sit_available':True,'furniture_reference_available':True,'sit_state':0,'furniture':0}}}

    def start(self):
        self.review();event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.world.begin_plan(event['id'],self.obs,99,'need_review');self.sync();self.decide('rest_at_bench',event['id'])
        self.command=self.world.pending(self.obs['session']);return event

    def ack(self,**changes):
        rest={'actor':99,'target':0x8f15b,'rested_minutes':30,'seated_samples':100,'release_verified':True,'exact_furniture_verified':True}
        rest.update(changes);self.obs['ack']={'id':self.command['id'],'status':'applied','rest':rest}
        self.world.observe(self.obs);self.sync()

    def test_available_nearest_bench_requires_classification_occupancy_and_exact_sensor(self):
        self.assertEqual(len(rest_opportunities(self.world.active,self.obs,99)),1)
        self.obs['rest']['sites'][0]['occupied']=True
        self.assertEqual(rest_opportunities(self.world.active,self.obs,99),[])
        self.obs['rest']['sensors']['99'].update(sit_state=3,furniture=0x8f15b)
        self.assertEqual(len(rest_opportunities(self.world.active,self.obs,99)),1)
        self.world.active['people']['99']['commitments']=[{'kind':'duty'}]
        self.assertEqual(rest_opportunities(self.world.active,self.obs,99),[])

    def test_preparation_does_not_recover_and_verified_rest_changes_no_inventory(self):
        before=copy.deepcopy(self.obs['residents']);event=self.start()
        self.assertEqual(self.world.active['people']['99']['needs']['fatigue'],.9)
        self.assertEqual(self.command['kind'],'rest_at_bench')
        self.obs['gameDays']+=.5/24;self.ack()
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['fatigue'],.5625)
        self.assertEqual(self.obs['residents'],before)
        self.assertEqual(self.world.agency_plan()['outcome'],'rested_at_bench')
        self.assertEqual(len(self.world.status()['rests']),1)
        queued=next(e for e in self.world.active['town']['daily']['queue'] if e['id']==event['id'])
        self.assertEqual(queued['status'],'complete')
        self.world.observe(self.obs);self.sync();self.assertEqual(len(self.world.status()['rests']),1)

    def test_invalid_attendance_cannot_change_fatigue(self):
        for change in ({'rested_minutes':29.9},{'rested_minutes':float('inf')},{'seated_samples':0},
                       {'release_verified':False},{'exact_furniture_verified':False},{'target':123}):
            with self.subTest(change=change):
                # Separate saved lineages prevent one failed operation contaminating another.
                self.tearDown();self.setUp();self.start();self.ack(**change)
                self.assertEqual(self.world.active['people']['99']['needs']['fatigue'],.9)
                self.assertEqual(self.world.status()['rests'],[])
                self.assertEqual(self.world.agency_plan()['phase'],'held')

    def test_loading_pre_rest_save_removes_recovery_and_future_memory(self):
        self.review();old=copy.deepcopy(self.obs)
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.world.begin_plan(event['id'],self.obs,99,'need_review');self.sync();self.decide('rest_at_bench',event['id'])
        self.command=self.world.pending(self.obs['session']);self.ack()
        self.world.observe({**old,'session':'older-rest-save'})
        self.assertEqual(self.world.active['people']['99']['needs']['fatigue'],.9)
        self.assertEqual(self.world.status()['rests'],[])
        self.assertNotIn('fatigue_clock',self.world.active['people']['99'])

    def test_next_review_ages_only_time_after_recovery(self):
        self.start();self.obs['gameDays']+=2/24;self.ack()
        fatigue=self.world.active['people']['99']['needs']['fatigue'];self.review(1)
        self.assertAlmostEqual(self.world.active['people']['99']['needs']['fatigue'],fatigue+.025)

    def test_bench_becoming_occupied_before_preparation_holds_without_recovery(self):
        self.review();event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.world.begin_plan(event['id'],self.obs,99,'need_review');self.sync()
        claim=self.world.claim_plan_decision(event['id'],self.obs)['claim'];self.sync()
        self.obs['rest']['sites'][0]['occupied']=True
        with self.assertRaisesRegex(ValueError,'not currently allowed'):
            self.world.finish_plan_decision(event['id'],claim['id'],{'decision':{'action_id':'rest_at_bench','reason':'test','emotion':'calm'}},self.obs)


if __name__=='__main__':unittest.main()
