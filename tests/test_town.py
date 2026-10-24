import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from town import Town

class TownTests(unittest.TestCase):
    def setUp(self):
        self.town=Town(':memory:'); self.town.seed()
    def tearDown(self): self.town.db.close()
    def test_autonomous_economy_conserves_money_for_thirty_days(self):
        for day in range(1,31):
            state=self.town.advance_day(day)
            self.assertEqual(sum(p['gold'] for p in state['people']),490)
            self.assertTrue(all(i['quantity']>=0 for i in state['inventory']))
        kinds={e['kind'] for e in state['events']}
        self.assertTrue({'wage','trade','production','consumption'}<=kinds)
        self.assertTrue(all(p['gold']>0 for p in state['people']))
        self.assertLessEqual(next(i['quantity'] for i in state['inventory'] if i['owner']=='bakery' and i['item']=='grain'),6)
    def test_duplicate_day_cannot_pay_twice(self):
        self.town.advance_day(1)
        before=self.town.state()
        with self.assertRaises(ValueError): self.town.advance_day(1)
        self.assertEqual(before,self.town.state())
    def test_shortage_eventually_causes_unmet_food_need(self):
        import json
        for day in range(1,15): self.town.advance_day(day,harvest=0)
        meals=[json.loads(e['payload']) for e in self.town.state()['events'] if e['kind']=='consumption']
        self.assertTrue(any(m['unmet_need']>0 for m in meals))
    def test_failed_day_is_atomic(self):
        # Inject a ledger conflict after wages and production would have run.
        self.town.db.execute("INSERT INTO events VALUES ('day-1-meal-baker','probe','{}')")
        self.town.db.commit()
        before=self.town.state()
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError): self.town.advance_day(1)
        self.assertEqual(before,self.town.state())
        self.assertEqual(self.town.db.execute('SELECT day FROM clock').fetchone()[0],0)

if __name__=='__main__': unittest.main()
