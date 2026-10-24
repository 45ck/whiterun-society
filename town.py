"""Small autonomous economy: firms buy inputs, pay wages, produce, and sell food.

This runs independently of Skyrim until the game bridge is connected to the
clock. It is an explicit deterministic baseline, not a trained decision model.
"""
import argparse
import json
from society import Society


class Town(Society):
    def seed(self):
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO people VALUES (?,?)',
                                [('bakery',200),('farm',200),('baker',30),('farmer',30),('worker',30)])
            self.db.executemany('INSERT OR IGNORE INTO inventory VALUES (?,?,?)',
                                [('farm','grain',12),('bakery','grain',0),('bakery','bread',8)])
            self.db.execute('CREATE TABLE IF NOT EXISTS clock(singleton INTEGER PRIMARY KEY CHECK(singleton=1), day INTEGER)')
            self.db.execute('INSERT OR IGNORE INTO clock VALUES (1,0)')

    def advance_day(self, expected_day, harvest=6):
        if type(expected_day) is not int or expected_day<1 or type(harvest) is not int or not 0<=harvest<=6:
            raise ValueError('Invalid day or harvest capacity')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            day=self.db.execute('SELECT day FROM clock WHERE singleton=1').fetchone()[0]
            if day!=expected_day-1:
                raise ValueError('Stale or skipped day')
            prefix=f'day-{expected_day}'
            def emit(key,kind,payload):
                self.db.execute('INSERT INTO events VALUES (?,?,?)',(prefix+'-'+key,kind,json.dumps(payload,sort_keys=True)))
            def gold(owner):
                return self.db.execute('SELECT gold FROM people WHERE id=?',(owner,)).fetchone()[0]
            def stock(owner,item):
                row=self.db.execute('SELECT quantity FROM inventory WHERE owner=? AND item=?',(owner,item)).fetchone()
                return row[0] if row else 0
            def adjust(owner,item,delta):
                self.db.execute('INSERT OR IGNORE INTO inventory VALUES (?,?,0)',(owner,item))
                self.db.execute('UPDATE inventory SET quantity=quantity+? WHERE owner=? AND item=?',(delta,owner,item))
            def pay(key,buyer,seller,amount,kind):
                if gold(buyer)<amount:
                    emit(key,'unaffordable',{'payer':buyer,'amount':amount})
                    return False
                self.db.execute('UPDATE people SET gold=gold-? WHERE id=?',(amount,buyer))
                self.db.execute('UPDATE people SET gold=gold+? WHERE id=?',(amount,seller))
                emit(key,kind,{'payer':buyer,'payee':seller,'gold':amount})
                return True
            # One paid shift unlocks bounded farm output; harvest=0 is the shock.
            if pay('farm-wage','farm','farmer',6,'wage'):
                produced=min(harvest,max(0,12-stock('farm','grain')))
                adjust('farm','grain',produced)
                emit('harvest','production',{'producer':'farm','grain':produced,'capacity':6})
            needed=max(0,(12-stock('bakery','bread')+1)//2-stock('bakery','grain'))
            grain=min(needed,stock('farm','grain'),gold('bakery')//2)
            if grain and pay('grain-payment','bakery','farm',grain*2,'trade'):
                adjust('farm','grain',-grain); adjust('bakery','grain',grain)
                emit('grain-delivery','delivery',{'seller':'farm','buyer':'bakery','grain':grain})
            batches=min(6,stock('bakery','grain'),max(0,(12-stock('bakery','bread')+1)//2))
            if batches and pay('baker-wage','bakery','baker',6,'wage'):
                adjust('bakery','grain',-batches); adjust('bakery','bread',2*batches)
                emit('baking','production',{'grain_used':batches,'bread_produced':2*batches})
            if stock('bakery','bread'):
                pay('worker-wage','bakery','worker',6,'wage')
            price=5 if stock('bakery','bread')<6 else 3
            for resident in ('baker','farmer','worker'):
                bought=min(2,stock('bakery','bread'),gold(resident)//price)
                if bought and pay('food-'+resident,resident,'bakery',bought*price,'trade'):
                    adjust('bakery','bread',-bought); adjust(resident,'bread',bought)
                    emit('delivery-'+resident,'delivery',{'seller':'bakery','buyer':resident,'bread':bought,'unit_price':price})
                eaten=min(2,stock(resident,'bread'))
                adjust(resident,'bread',-eaten)
                emit('meal-'+resident,'consumption',{'resident':resident,'bread':eaten,'unmet_need':2-eaten})
            self.db.execute('UPDATE clock SET day=? WHERE singleton=1',(expected_day,))
            emit('close','day_close',{'gold_total':sum(p['gold'] for p in self.state()['people']),'bread_price':price})
        return self.state()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--days',type=int,default=10)
    parser.add_argument('--db',default=':memory:')
    args=parser.parse_args()
    town=Town(args.db); town.seed()
    try:
        for _ in range(args.days):
            next_day=town.db.execute('SELECT day FROM clock').fetchone()[0]+1
            town.advance_day(next_day)
        state=town.state()
        print(json.dumps({'days':args.days,'gold_total':sum(p['gold'] for p in state['people']),
                          'accounts':state['people'],'inventory':state['inventory'],
                          'event_count':len(state['events']),'evidence':'standalone simulation; not in-game'},indent=2))
    finally: town.db.close()
