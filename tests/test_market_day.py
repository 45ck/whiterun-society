import copy
import unittest
import test_food


class MarketDayTests(unittest.TestCase):
    def setUp(self):
        test_food.FoodTests.setUp(self)
        for actor in self.obs['residents']:actor['inventory']['grain']=2
    tearDown=test_food.FoodTests.tearDown
    sync=test_food.FoodTests.sync
    decide=test_food.FoodTests.decide

    def start(self,name='day'):
        self.world.start_market_day(name,self.obs);self.sync()

    def test_uninitialized_participants_cannot_create_a_running_scenario(self):
        for people in ({},{'108186':copy.deepcopy(self.world.active['people']['108186'])}):
            with self.subTest(people=list(people)):
                self.world.active['people']=people
                before=copy.deepcopy(self.world.active)
                count=self.world.db.execute('SELECT COUNT(*) FROM checkpoints').fetchone()[0]
                with self.assertRaisesRegex(ValueError,'Initialize every authored'):
                    self.world.start_market_day('missing-people',self.obs)
                self.assertEqual(self.world.active,before)
                self.assertIsNone(self.world.transition)
                self.assertEqual(self.world.db.execute('SELECT COUNT(*) FROM checkpoints').fetchone()[0],count)

    def stage(self):
        event=self.world.scenario_status()['next_event']
        self.world.begin_plan(event['id'],self.obs,event['actor'],event['kind']);self.sync()
        self.decide('reserve_one' if event['kind']=='stock_review' else 'defer',event['id'])
        self.world.advance_market_day(self.world.scenario_status()['id'],event['id'],self.obs);self.sync()
        return event

    def test_finite_sequence_allows_refusals_and_completes_without_forcing_trade(self):
        self.start()
        for _ in range(4):self.stage()
        scenario=self.world.scenario_status()
        self.assertEqual(scenario['status'],'complete')
        self.assertIsNone(scenario['next_event'])
        self.assertEqual(scenario['calls_observed'],4)
        self.assertEqual(scenario['metrics']['gold_before'],scenario['metrics']['gold_after'])
        self.assertEqual(scenario['metrics']['trades'],0)
        self.assertTrue(self.world.start_market_day('day',self.obs)['duplicate'])

    def test_duplicate_stage_advance_does_not_increment_or_retrigger_meal(self):
        self.start();first=self.stage();before=copy.deepcopy(self.world.active)
        self.assertTrue(self.world.advance_market_day('day',first['id'],self.obs)['duplicate'])
        self.assertEqual(self.world.active,before)

    def test_loading_previous_save_restores_queue_and_blocks_future_stage(self):
        self.start();old=copy.deepcopy(self.obs);self.stage()
        future=self.world.scenario_status()['next_event']
        self.world.observe({**old,'session':'old-day-save'})
        self.obs={**old,'session':'old-day-save'}
        self.assertEqual(self.world.scenario_status()['cursor'],0)
        with self.assertRaisesRegex(ValueError,'owns'):
            self.world.begin_plan(future['id'],self.obs,future['actor'],future['kind'])

    def test_stage_must_settle_and_unrelated_events_are_rejected(self):
        self.start()
        with self.assertRaisesRegex(ValueError,'owns'):self.world.begin_plan('unrelated',self.obs, 108186)
        with self.assertRaisesRegex(ValueError,'settled'):self.world.advance_market_day('day','day-work',self.obs)

    def test_completed_day_cannot_be_replayed_after_starting_another_day(self):
        self.start()
        for _ in range(4):self.stage()
        self.start('another')
        result=self.world.start_market_day('day',self.obs)
        self.assertTrue(result['duplicate']);self.assertEqual(result['scenario']['status'],'complete')
        self.assertEqual(self.world.scenario_status()['id'],'another')

    def test_employer_deferral_is_not_false_worker_memory(self):
        self.start();self.stage()
        people=self.world.status()['people']
        self.assertEqual(people['108186']['memories'],[])
        self.assertEqual(people['108149']['memories'][-1]['kind'],'deferred')

    def test_held_decision_stops_the_sequence_without_repeating_inference(self):
        self.start()
        self.world.begin_plan('day-work',self.obs,108186,'work_shift');self.sync()
        self.world.hold_plan('day-work','fixture unavailable',self.obs);self.sync()
        self.world.advance_market_day('day','day-work',self.obs);self.sync()
        self.assertEqual(self.world.scenario_status()['status'],'held')
        self.assertIsNone(self.world.scenario_status()['next_event'])
