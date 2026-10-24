"""Authoritative prototype economy. Integer units, atomic trades, replay protection."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path


class Society:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path), timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS people(id TEXT PRIMARY KEY, gold INTEGER NOT NULL CHECK(gold>=0));
            CREATE TABLE IF NOT EXISTS inventory(owner TEXT REFERENCES people(id), item TEXT,
                quantity INTEGER NOT NULL CHECK(quantity>=0), PRIMARY KEY(owner,item));
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, kind TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS beliefs(person TEXT, topic TEXT, stance TEXT, cause TEXT,
                PRIMARY KEY(person,topic));
        ''')

    def seed(self):
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO people VALUES (?,?)',
                                [('player', 100), ('baker', 60), ('farmer', 40)])
            self.db.executemany('INSERT OR IGNORE INTO inventory VALUES (?,?,?)',
                                [('player', 'bread', 0), ('baker', 'bread', 12), ('farmer', 'grain', 30)])

    def trade(self, event_id, buyer, seller, item, quantity, unit_price):
        if type(quantity) is not int or type(unit_price) is not int or quantity <= 0 or unit_price <= 0:
            raise ValueError('Positive integer quantity and price required')
        if buyer == seller or not event_id or len(event_id) > 128:
            raise ValueError('Invalid trade identity')
        payload = dict(buyer=buyer, seller=seller, item=item, quantity=quantity, unit_price=unit_price)
        encoded = json.dumps(payload, sort_keys=True)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            existing = self.db.execute('SELECT kind,payload FROM events WHERE id=?', (event_id,)).fetchone()
            if existing:
                if existing['kind'] != 'trade' or existing['payload'] != encoded:
                    raise ValueError('Event ID reused with different trade')
                return {'duplicate': True, **payload}
            balance = self.db.execute('SELECT gold FROM people WHERE id=?', (buyer,)).fetchone()
            stock = self.db.execute('SELECT quantity FROM inventory WHERE owner=? AND item=?', (seller,item)).fetchone()
            if not balance or not stock or balance['gold'] < quantity*unit_price or stock['quantity'] < quantity:
                raise ValueError('Insufficient funds or stock')
            self.db.execute('UPDATE people SET gold=gold-? WHERE id=?', (quantity*unit_price,buyer))
            self.db.execute('UPDATE people SET gold=gold+? WHERE id=?', (quantity*unit_price,seller))
            self.db.execute('UPDATE inventory SET quantity=quantity-? WHERE owner=? AND item=?', (quantity,seller,item))
            self.db.execute('INSERT INTO inventory VALUES (?,?,?) ON CONFLICT(owner,item) DO UPDATE SET quantity=quantity+excluded.quantity', (buyer,item,quantity))
            self.db.execute('INSERT INTO events VALUES (?,?,?)', (event_id,'trade',encoded))
        return {'duplicate': False, **payload}

    def shortage(self, event_id):
        """Explicit scenario event; policy baseline, not a generated human response."""
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            existing = self.db.execute('SELECT kind FROM events WHERE id=?', (event_id,)).fetchone()
            if existing:
                if existing['kind'] != 'shortage':
                    raise ValueError('Event ID collision')
                return
            self.db.execute('INSERT INTO events VALUES (?,?,?)', (event_id, 'shortage', '{}'))
            self.db.executemany('INSERT INTO beliefs VALUES (?,?,?,?) ON CONFLICT(person,topic) DO UPDATE SET stance=excluded.stance,cause=excluded.cause', [
                ('baker','grain shortage','Support grain imports to keep the bakery open',event_id),
                ('farmer','grain shortage','Prefer mill repairs over competing imports',event_id)])

    def state(self):
        return {table: [dict(row) for row in self.db.execute('SELECT * FROM ' + table)]
                for table in ('people','inventory','events','beliefs')}

    def checkpoint(self, target):
        """Standalone checkpoint only; binding to Skyrim save lineage remains to implement."""
        target = Path(target)
        if target.exists():
            raise FileExistsError(target)
        with closing(sqlite3.connect(target)) as output:
            self.db.backup(output)

