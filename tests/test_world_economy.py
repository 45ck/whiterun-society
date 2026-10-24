import copy
import json
import unittest
from world_economy import WorldEconomy


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.world=WorldEconomy(':memory:')
        self.observation={'session':'game-a','ready':True,'residents':[
            {'id':100,'inventory':{'gold':9,'bread':0}},
            {'id':200,'inventory':{'gold':10,'bread':1}}]}
    def tearDown(self): self.world.db.close()
    def plan(self): return self.world.plan_trade('purchase-1',self.observation,100,200)

    def test_quote_conserves_gold_and_bread_and_retry_keeps_same_command(self):
        command=json.loads(self.plan()['command'])
        for item in ('gold','bread'):
            self.assertEqual(sum(v[item] for v in command['before'].values()),sum(v[item] for v in command['after'].values()))
        self.assertEqual(self.plan()['command'],json.dumps(command,sort_keys=True))
        self.assertEqual(len(self.world.state()),1)

    def test_acknowledgement_without_matching_inventory_cannot_commit(self):
        self.plan();self.observation['ack']={'id':'purchase-1','status':'applied'}
        self.world.observe(self.observation)
        self.assertEqual(self.world.get('purchase-1')['status'],'held')

    def test_final_observation_and_acknowledgement_commit_exactly_once(self):
        command=json.loads(self.plan()['command'])
        for role,row in zip(('buyer','seller'),self.observation['residents']): row['inventory']=command['after'][role]
        self.world.observe(self.observation)
        self.assertEqual(self.world.get('purchase-1')['status'],'pending')
        self.observation['ack']={'id':'purchase-1','status':'applied'}
        self.world.observe(self.observation);self.world.observe(self.observation)
        self.assertEqual(self.world.get('purchase-1')['status'],'committed')
        self.assertIsNone(self.world.pending('game-a'))

    def test_new_session_holds_unsettled_effects_and_blocks_further_trades(self):
        self.plan();new=copy.deepcopy(self.observation);new['session']='older-save'
        self.world.observe(new)
        self.assertEqual(self.world.get('purchase-1')['status'],'held')
        with self.assertRaises(ValueError): self.world.plan_trade('purchase-2',new,100,200)

    def test_insufficient_resources_and_conflicting_ids_do_not_mutate_ledger(self):
        self.plan()
        with self.assertRaises(ValueError): self.world.plan_trade('purchase-1',self.observation,100,200,2)
        self.assertEqual(len(self.world.state()),1)
        other=WorldEconomy(':memory:')
        try:
            with self.assertRaises(ValueError): other.plan_trade('large',self.observation,100,200,2)
            self.assertEqual(other.state(),[])
        finally: other.db.close()

    def test_unloaded_counterparty_cannot_be_assumed_available(self):
        self.observation['residents'].pop()
        with self.assertRaises(ValueError): self.plan()
        self.assertEqual(self.world.state(),[])


if __name__=='__main__': unittest.main()
