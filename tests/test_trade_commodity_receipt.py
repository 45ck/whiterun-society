import copy
import unittest
import test_lineage as fixtures
from agency_metrics import economic_network
from trade_execution_fixture import arm_trade, trade_ack


class TradeCommodityReceiptTests(unittest.TestCase):
    setUp=fixtures.LineageTests.setUp
    tearDown=fixtures.LineageTests.tearDown
    bind=fixtures.LineageTests.bind
    prepare=fixtures.LineageTests.prepare
    finish=fixtures.LineageTests.finish

    def test_new_bread_receipt_has_explicit_commodity_and_keeps_legacy_request_identity(self):
        self.prepare();c=self.world.pending(self.obs['session'])
        self.assertEqual(c['commodity'],'bread')
        self.assertNotIn('commodity',self.world.active['pending']['request'])
        self.finish();m=economic_network(self.world.active)
        self.assertEqual(m['goods_receipts'],{'bread':1});self.assertEqual(m['goods_label_coverage']['percent'],100)
        again=self.world.plan_trade('bread-1',self.obs,108186,108149)
        self.assertEqual(again['status'],'committed');self.assertEqual(len(self.world.active['trades']),1)

    def test_legacy_unlabelled_trade_replay_preserves_old_command(self):
        self.prepare();self.world.active['pending']['command'].pop('commodity')
        old=copy.deepcopy(self.world.active['pending'])
        again=self.world.plan_trade('bread-1',self.obs,108186,108149)
        self.assertEqual(again,old);self.assertNotIn('commodity',again['command'])

    def test_new_bread_and_grain_commits_count_both_goods_but_no_held_sales(self):
        self.prepare();self.finish()
        for a in self.obs['residents']:a['inventory']['grain']=1 if a['id']==108149 else 0
        self.world.plan_trade('grain-1',self.obs,108186,108149,commodity='grain');self.bind()
        c=arm_trade(self.world,self.obs,self.bind);self.assertEqual(c['commodity'],'grain')
        self.assertEqual(c['phase'],'deliver')
        for role,actor in [('buyer',108186),('seller',108149)]:
            next(a for a in self.obs['residents'] if a['id']==actor)['inventory']=copy.deepcopy(c['after'][role])
        self.obs['ack']=trade_ack(c);self.world.observe(self.obs);self.bind()
        self.world.active['trades'].append({'id':'held','status':'held','command':{'commodity':'iron'}})
        m=economic_network(self.world.active)
        self.assertEqual(m['distinct_goods'],2);self.assertEqual(m['goods_receipts'],{'bread':1,'grain':1})
