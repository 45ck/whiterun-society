import copy
import json
import unittest
from world_economy import WorldEconomy
from catalog_fixture import native_catalog, native_ack


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.world=WorldEconomy(':memory:')
        self.observation={'session':'game-a','ready':True,'economy_catalog':native_catalog(),'residents':[
            {'id':100,'inventory':{'gold':9,'bread':0,'grain':0}},
            {'id':200,'inventory':{'gold':10,'bread':1,'grain':0}}]}
    def tearDown(self): self.world.db.close()
    def plan(self): return self.world.plan_trade('purchase-1',self.observation,100,200)

    def test_quote_conserves_gold_and_bread_and_retry_keeps_same_command(self):
        self.observation['residents'][0]['inventory']['grain']=3
        self.observation['residents'][1]['inventory']['grain']=7
        command=json.loads(self.plan()['command'])
        self.assertEqual(command['catalog_hash'],native_catalog()['catalog_hash'])
        for item in ('gold','bread','grain'):
            self.assertEqual(sum(v[item] for v in command['before'].values()),sum(v[item] for v in command['after'].values()))
        self.assertEqual((command['after']['buyer']['grain'],command['after']['seller']['grain']),(3,7))
        self.assertEqual(self.plan()['command'],json.dumps(command,sort_keys=True))
        self.assertEqual(len(self.world.state()),1)

    def test_acknowledgement_without_matching_inventory_cannot_commit(self):
        self.plan();self.observation['ack']=native_ack(json.loads(self.world.get('purchase-1')['command']))
        self.world.observe(self.observation)
        self.assertEqual(self.world.get('purchase-1')['status'],'held')

    def test_final_observation_and_acknowledgement_commit_exactly_once(self):
        command=json.loads(self.plan()['command'])
        for role,row in zip(('buyer','seller'),self.observation['residents']): row['inventory']=command['after'][role]
        self.world.observe(self.observation)
        self.assertEqual(self.world.get('purchase-1')['status'],'pending')
        self.observation['ack']=native_ack(json.loads(self.world.get('purchase-1')['command']))
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

    def test_fresh_trade_requires_matching_resolved_native_catalog(self):
        for catalog in (None, {**native_catalog(),'catalog_hash':'other'}, {**native_catalog(),'type_verified':False}):
            obs=copy.deepcopy(self.observation)
            if catalog is None:obs.pop('economy_catalog')
            else:obs['economy_catalog']=catalog
            with self.assertRaisesRegex(ValueError,'catalog'):self.world.plan_trade('unverified',obs,100,200)
            self.assertEqual(self.world.state(),[])

    def test_hashless_legacy_pending_is_held_without_stamping_or_dispatch(self):
        command=json.loads(self.plan()['command']);command.pop('catalog_hash')
        self.world.db.execute('UPDATE world_commands SET command=? WHERE id=?',(json.dumps(command),'purchase-1'))
        self.world.db.commit()
        self.assertIsNone(self.world.pending('game-a'))
        self.world.observe(self.observation)
        record=self.world.get('purchase-1')
        self.assertEqual(record['status'],'held');self.assertNotIn('catalog_hash',json.loads(record['command']))
        self.assertIn('catalog',record['evidence'])

    def reject_unbound_ack(self, pin):
        command=json.loads(self.plan()['command'])
        for role,row in zip(('buyer','seller'),self.observation['residents']):row['inventory']=command['after'][role]
        self.observation['ack']={'id':command['id'],'status':'applied'}
        if pin is not None:self.observation['ack']['catalog_hash']=pin
        self.world.observe(self.observation)
        self.assertEqual(self.world.get(command['id'])['status'],'held')
        self.assertIsNone(self.world.pending('game-a'))

    def test_matching_inventory_without_ack_catalog_proof_does_not_settle(self):
        self.reject_unbound_ack(None)

    def test_matching_inventory_with_other_ack_catalog_does_not_settle(self):
        self.reject_unbound_ack('unrelated-catalog')


if __name__=='__main__': unittest.main()
