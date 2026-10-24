import copy
import tempfile
import unittest
from pathlib import Path
from lineage import TimelineEconomy


class AgencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.world = TimelineEconomy(Path(self.temp.name)/'timeline.sqlite')
        self.obs = {'session': 'a', 'checkpoint': 0, 'ready': True, 'residents': [
            {'id': 108186, 'x': 1000, 'y': 0, 'z': 0, 'inventory': {'gold': 9, 'bread': 0}},
            {'id': 108149, 'x': 0, 'y': 0, 'z': 0, 'inventory': {'gold': 10, 'bread': 3}},
            {'id': 108156, 'x': -1000, 'y': 0, 'z': 0, 'inventory': {'gold': 12, 'bread': 0}}]}
        self.world.observe(self.obs)
        self.world.bootstrap(self.obs)
        self.sync()

    def tearDown(self):
        self.world.db.close()
        self.temp.cleanup()

    def sync(self):
        for _ in range(8):
            if not self.world.transition:
                return
            self.obs['checkpoint'] = self.world.transition['next']
            self.obs.pop('ack', None)
            self.world.observe(self.obs)
        self.fail('Checkpoint loop did not settle')

    def start(self):
        self.world.begin_plan('meal-1', self.obs)
        self.sync()

    def decide(self, action):
        claim = self.world.claim_plan_decision('meal-1', self.obs)['claim']
        self.assertEqual(self.world.pending('a')['kind'], 'bind_checkpoint')
        self.sync()
        result = {'decision': {'action_id': action, 'reason': 'An authored test decision.', 'emotion': 'calm'},
                  'model': 'unit-test', 'elapsed_seconds': 0}
        self.world.finish_plan_decision('meal-1', claim['id'], result, self.obs)
        self.sync()

    def arrive(self, owned=True):
        self.obs['residents'][0]['x'] = 200
        self.obs['ack'] = {'id': 'travel-meal-1', 'status': 'applied', 'movement': {'hasOwnedPackage': owned}}
        self.world.observe(self.obs)
        self.sync()

    def test_choice_travel_consent_trade_memory_and_release(self):
        self.start()
        self.decide('seek_bread')
        command = self.world.pending('a')
        self.assertEqual((command['kind'], command['target'], command['retain']), ('walk_to',108149,True))
        self.arrive()
        self.assertEqual(self.world.agency_plan()['phase'], 'consent')
        self.assertIsNone(self.world.pending('a'))
        self.decide('sell_bread')
        command = self.world.pending('a')
        self.assertEqual(command['kind'], 'inventory_trade')
        for index, role in [(0, 'buyer'), (1, 'seller')]:
            self.obs['residents'][index]['inventory'] = command['after'][role]
        self.obs['ack'] = {'id': 'meal-meal-1', 'status': 'applied'}
        self.world.observe(self.obs)
        self.sync()
        self.assertEqual(self.world.agency_plan()['outcome'], 'bought_bread')
        self.assertEqual(len(self.world.status()['people']['108186']['memories']), 1)
        self.assertEqual(self.world.pending('a')['kind'], 'release_routine')
        self.obs['ack'] = {'id': 'release-meal-1', 'status': 'applied'}
        self.world.observe(self.obs)
        self.sync()
        self.assertFalse(self.world.agency_busy())
        self.assertIsNone(self.world.pending('a'))
        # A second event receives the actual earlier trade memory.
        self.world.begin_plan('meal-2', self.obs)
        self.sync()
        claim = self.world.claim_plan_decision('meal-2', self.obs)['claim']
        self.assertEqual(claim['context']['memories'][0]['event_id'], 'meal-meal-1')
        self.assertNotIn('seek_bread', [o['id'] for o in claim['context']['options']])

    def test_seller_can_refuse_without_mutating_inventory(self):
        self.start(); self.decide('seek_bread'); self.arrive()
        before = copy.deepcopy(self.obs['residents'])
        self.decide('decline')
        self.assertEqual(self.world.agency_plan()['outcome'], 'seller_declined')
        self.assertEqual(self.obs['residents'], before)
        self.assertEqual(self.world.state(), [])
        self.obs['ack']={'id':'release-meal-1','status':'applied'}
        self.world.observe(self.obs);self.sync()
        memory=self.world.status()['people']['108186']['memories'][-1]
        self.assertEqual(memory['kind'],'trade_offer_declined')
        self.assertEqual(self.world.status()['people']['108186']['trust'],{})

    def test_private_seller_stock_is_not_revealed_by_buyers_options(self):
        self.obs['residents'][1]['inventory']['bread']=0
        self.start()
        context=self.world.claim_plan_decision('meal-1',self.obs)['claim']['context']
        self.assertIn('seek_bread',[o['id'] for o in context['options']])
        self.assertNotIn('residents',context)

    def test_vanilla_proximity_cannot_advance_to_consent(self):
        self.start(); self.decide('seek_bread'); self.arrive(False)
        self.assertEqual(self.world.agency_plan()['phase'], 'held')
        self.assertEqual(self.world.pending('a')['kind'], 'release_routine')

    def test_unqualified_vision_does_not_leak_sensor_diagnostics_or_hidden_people(self):
        self.obs['perception']={'108186':{'available':False,'visible':[{'id':108149}],
                                        'diagnostics':{'nearby':7}}}
        self.start()
        context=self.world.claim_plan_decision('meal-1',self.obs)['claim']['context']
        self.assertFalse(context['perception']['available'])
        self.assertNotIn('diagnostics',context['perception'])
        self.assertNotIn('visible',context['perception'])

    def test_claim_is_not_reissued_and_old_save_restores_old_plan(self):
        before = copy.deepcopy(self.obs)
        self.start()
        self.world.claim_plan_decision('meal-1', self.obs)
        self.sync()
        with self.assertRaises(ValueError):
            self.world.claim_plan_decision('meal-1', self.obs)
        thinking = copy.deepcopy(self.obs)
        self.world.observe({**before, 'session': 'old-save'})
        self.assertIsNone(self.world.agency_plan())
        self.world.observe({**thinking, 'session': 'thinking-save'})
        self.obs = {**thinking, 'session': 'thinking-save'}
        self.sync()
        self.assertEqual(self.world.agency_plan()['phase'], 'held')

    def test_replayed_event_does_not_repeat_hunger_or_model_claim(self):
        self.start(); self.decide('defer')
        hunger = self.world.status()['people']['108186']['needs']['hunger']
        result = self.world.begin_plan('meal-1', self.obs)
        self.assertTrue(result['duplicate'])
        self.assertEqual(self.world.status()['people']['108186']['needs']['hunger'], hunger)
        self.assertIsNone(self.world.transition)
