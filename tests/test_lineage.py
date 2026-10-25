import copy
import tempfile
import unittest
from pathlib import Path
from lineage import TimelineEconomy
from legacy_fixture import install_legacy_people
from catalog_fixture import native_catalog, native_ack
from trade_execution_fixture import qualify_trade_observation, trade_ack, arm_trade


class LineageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'timeline.sqlite'
        self.world = TimelineEconomy(self.path)
        self.obs = {'session': 'a', 'checkpoint': 0, 'ready': True, 'economy_catalog': native_catalog(), 'residents': [
            {'id': 108186, 'inventory': {'gold': 9, 'bread': 0, 'grain': 0}},
            {'id': 108149, 'inventory': {'gold': 10, 'bread': 1, 'grain': 0}}]}
        qualify_trade_observation(self.obs)
        self.world.observe(self.obs)
        self.world.bootstrap(self.obs)
        self.bind()
        self.initial = install_legacy_people(self.world)
        self.bind()

    def tearDown(self):
        self.world.db.close()
        self.temp.cleanup()

    def bind(self):
        command = self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'], 'bind_checkpoint')
        self.obs['checkpoint'] = command['next']
        self.obs.pop('ack', None)
        self.world.observe(self.obs)
        return command['next']

    def prepare(self):
        self.world.plan_trade('bread-1', self.obs, 108186, 108149)
        return self.bind()

    def finish(self):
        command = arm_trade(self.world,self.obs,self.bind)
        for role, actor in [('buyer', 108186), ('seller', 108149)]:
            next(a for a in self.obs['residents'] if a['id'] == actor)['inventory'] = command['after'][role].copy()
        self.obs['ack'] = trade_ack(command)
        self.world.observe(self.obs)
        return self.bind()

    def test_no_inventory_command_before_prepared_checkpoint_is_observed(self):
        self.world.plan_trade('bread-1', self.obs, 108186, 108149)
        self.assertEqual(self.world.pending('a')['kind'], 'bind_checkpoint')
        self.world.observe(self.obs)
        self.assertEqual(self.world.pending('a')['kind'], 'bind_checkpoint')
        prepared = self.bind()
        self.assertEqual(self.world.pending('a')['checkpoint'], prepared)
        self.assertEqual(self.world.pending('a')['catalog_hash'],native_catalog()['catalog_hash'])

    def test_fresh_trade_requires_catalog_proof_before_persisting_intent(self):
        before=copy.deepcopy(self.world.active)
        for catalog in (None, {**native_catalog(),'catalog_hash':'other'}, {**native_catalog(),'type_verified':False}):
            obs=copy.deepcopy(self.obs)
            if catalog is None:obs.pop('economy_catalog')
            else:obs['economy_catalog']=catalog
            with self.assertRaisesRegex(ValueError,'catalog'):self.world.plan_trade('unverified',obs,108186,108149)
            self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_hashless_pending_is_not_rebound_and_completed_legacy_history_remains_readable(self):
        self.prepare()
        self.world.active['pending']['command'].pop('catalog_hash')
        self.assertIsNone(self.world.pending('a'))
        self.world.observe(self.obs);self.bind()
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertNotIn('catalog_hash',self.world.active['pending']['command'])
        self.assertIn('catalog',self.world.active['pending']['error'])
        # A historical receipt is readable evidence, never an invitation to dispatch.
        legacy=copy.deepcopy(self.world.active['pending']);legacy['status']='committed'
        self.world.active.update(pending=None,trades=[legacy])
        self.assertEqual(self.world.status()['trades'][0]['status'],'committed')
        self.assertNotIn('catalog_hash',self.world.status()['trades'][0]['command'])
        self.assertIsNone(self.world.pending('a'))

    def reject_unbound_ack(self, pin):
        self.prepare();command=self.world.pending('a')
        for role,actor in [('buyer',108186),('seller',108149)]:
            next(a for a in self.obs['residents'] if a['id']==actor)['inventory']=command['after'][role].copy()
        self.obs['ack']={'id':command['id'],'status':'applied'}
        if pin is not None:self.obs['ack']['catalog_hash']=pin
        self.world.observe(self.obs);self.bind()
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(self.world.active['trades'],[])
        self.assertEqual(self.world.active['people']['108186']['memories'],[])

    def test_matching_inventory_without_ack_catalog_proof_does_not_settle(self):
        self.reject_unbound_ack(None)

    def test_matching_inventory_with_other_ack_catalog_does_not_settle(self):
        self.reject_unbound_ack('unrelated-catalog')

    def test_older_save_restores_old_memories_and_trade_history(self):
        before = copy.deepcopy(self.obs)
        self.prepare()
        committed = self.finish()
        self.assertEqual(len(self.world.status()['people']['108186']['memories']), 1)
        self.assertEqual(self.world.status()['people']['108186']['trust']['108149'], 1)
        self.world.observe({**before, 'session': 'loaded-old'})
        self.assertEqual(self.world.status()['checkpoint'], self.initial)
        self.assertEqual(self.world.state(), [])
        self.assertEqual(self.world.status()['people']['108186']['memories'], [])
        self.world.observe({**self.obs, 'session': 'loaded-new', 'checkpoint': committed})
        self.assertEqual(len(self.world.state()), 1)
        self.assertEqual(len(self.world.status()['people']['108186']['memories']), 1)

    def test_restart_at_prepared_checkpoint_holds_without_rebinding_or_replay(self):
        self.prepare();command=arm_trade(self.world,self.obs,self.bind)
        self.obs['residents'][0]['inventory']['bread']=1
        self.obs['residents'][1]['inventory']['bread']=0
        self.world.db.close();self.world=TimelineEconomy(self.path)
        self.obs['session']='restarted';self.world.observe(self.obs);self.bind()
        self.assertIsNone(self.world.pending('restarted'))
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(self.world.active['pending']['command'],{k:v for k,v in command.items() if k not in ('session','checkpoint')})
        self.assertEqual(self.world.active['trades'],[])
        self.assertEqual(self.world.active['people']['108149']['memories'],[])

    def test_unknown_marker_never_adopts_latest_checkpoint(self):
        self.world.observe({**self.obs, 'checkpoint': 99999})
        self.assertIsNone(self.world.pending('a'))
        self.assertEqual(self.world.state(), [])
        self.assertIn('Unknown', self.world.status()['error'])
        with self.assertRaises(ValueError):
            self.world.bootstrap({**self.obs, 'checkpoint': 99999})

    def test_loading_old_save_discards_unbound_new_transition_and_holds_old_trade(self):
        self.prepare();old=copy.deepcopy(self.obs)
        command=self.world.pending('a');self.obs['ack']=trade_ack(command);self.world.observe(self.obs)
        self.assertIsNotNone(self.world.transition)
        self.world.observe({**old,'session':'loaded'})
        self.assertIsNotNone(self.world.transition)
        self.obs={**old,'session':'loaded'};self.bind()
        self.assertIsNone(self.world.pending('loaded'))
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(self.world.status()['people']['108149']['memories'],[])

    def test_duplicate_completion_cannot_duplicate_memories(self):
        self.prepare()
        self.finish()
        self.obs['ack'] = trade_ack(self.world.active['trades'][-1]['command'])
        self.world.observe(self.obs)
        self.world.plan_trade('bread-1', self.obs, 108186, 108149)
        self.assertEqual(len(self.world.state()), 1)
        self.assertEqual(len(self.world.status()['people']['108186']['memories']), 1)

    def test_corrupt_checkpoint_is_rejected(self):
        self.world.db.execute('UPDATE checkpoints SET payload=? WHERE id=?', ('{}', self.initial))
        self.world.db.commit()
        self.world.observe({**self.obs, 'session': 'reload'})
        self.assertIsNone(self.world.pending('reload'))
        self.assertIn('corrupt', self.world.status()['error'])
