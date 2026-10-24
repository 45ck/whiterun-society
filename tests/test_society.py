import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from society import Society


class EconomyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'society.sqlite'
        self.sim = Society(self.path)
        self.sim.seed()

    def tearDown(self):
        self.sim.db.close()
        self.temp.cleanup()

    def test_trade_conserves_gold_and_stock(self):
        self.sim.trade('t1','player','baker','bread',2,3)
        state=self.sim.state()
        self.assertEqual(sum(p['gold'] for p in state['people']),200)
        self.assertEqual(sum(i['quantity'] for i in state['inventory'] if i['item']=='bread'),12)
        self.assertEqual(next(p['gold'] for p in state['people'] if p['id']=='player'),94)

    def test_retries_do_not_charge_again(self):
        self.sim.trade('t1','player','baker','bread',2,3)
        before=self.sim.state()
        self.assertTrue(self.sim.trade('t1','player','baker','bread',2,3)['duplicate'])
        self.assertEqual(before,self.sim.state())

    def test_reused_id_different_payload_rejected(self):
        self.sim.trade('t1','player','baker','bread',2,3)
        with self.assertRaises(ValueError):
            self.sim.trade('t1','player','baker','bread',3,3)

    def test_insufficient_stock_rolls_back(self):
        before=self.sim.state()
        with self.assertRaises(ValueError): self.sim.trade('t1','player','baker','bread',13,1)
        self.assertEqual(before,self.sim.state())

    def test_insufficient_gold_rolls_back(self):
        before=self.sim.state()
        with self.assertRaises(ValueError): self.sim.trade('t1','player','baker','bread',2,60)
        self.assertEqual(before,self.sim.state())

    def test_bad_quantities_rejected(self):
        for value in (-1,0,True,1.5):
            with self.assertRaises(ValueError): self.sim.trade('t1','player','baker','bread',value,3)

    def test_persistence_and_checkpoint(self):
        self.sim.trade('t1','player','baker','bread',2,3)
        self.sim.shortage('e1')
        expected=self.sim.state()
        self.sim.checkpoint(Path(self.temp.name)/'checkpoint.sqlite')
        self.sim.db.close()
        self.sim=Society(self.path)
        self.assertEqual(expected,self.sim.state())
        restored=Society(Path(self.temp.name)/'checkpoint.sqlite')
        self.assertEqual(expected,restored.state())
        restored.db.close()

    def test_event_causes_distinct_persistent_opinions(self):
        self.sim.shortage('e1')
        self.sim.shortage('e1')
        state=self.sim.state()
        self.assertEqual(len(state['events']),1)
        self.assertEqual(len({b['stance'] for b in state['beliefs']}),2)
        self.assertEqual({b['cause'] for b in state['beliefs']},{'e1'})

if __name__=='__main__': unittest.main()
