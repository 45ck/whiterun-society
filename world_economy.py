"""Durable journal for observed Skyrim trades, separate from the toy economy.

The game owns physical inventory. A committed journal entry requires both the
game acknowledgement and an independent inventory observation. Unknown partial
effects are held for reconciliation, never silently retried on another save.
"""
import json
import sqlite3


def snapshot(observation,buyer,seller):
    actors={row['id']:row for row in observation.get('residents',[])}
    result={}
    for role,actor_id in [('buyer',buyer),('seller',seller)]:
        if actor_id not in actors: raise ValueError('Both actors must be observed and loaded')
        inv=actors[actor_id].get('inventory',{})
        if any(type(inv.get(key)) is not int or inv[key]<0 for key in ('gold','bread')):
            raise ValueError('Complete nonnegative inventory observation required')
        result[role]={'gold':inv['gold'],'bread':inv['bread']}
    return result


class WorldEconomy:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.row_factory=sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS world_commands(
            id TEXT PRIMARY KEY, session TEXT NOT NULL, request TEXT NOT NULL,
            command TEXT NOT NULL, status TEXT NOT NULL, evidence TEXT)''')
        self.db.commit()

    def plan_trade(self,event_id,observation,buyer,seller,quantity=1,unit_price=3):
        if not isinstance(event_id,str) or not 1<=len(event_id)<=128: raise ValueError('Invalid event ID')
        if any(type(v) is not int or v<=0 for v in (buyer,seller,quantity,unit_price)):
            raise ValueError('Positive integer IDs, quantity and price required')
        if buyer==seller or quantity>10 or unit_price>100: raise ValueError('Invalid or oversized trade')
        session=observation.get('session')
        if not isinstance(session,str) or not session or not observation.get('ready'):
            raise ValueError('Ready game session required')
        request=json.dumps(dict(session=session,buyer=buyer,seller=seller,quantity=quantity,unit_price=unit_price),sort_keys=True)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            old=self.db.execute('SELECT * FROM world_commands WHERE id=?',(event_id,)).fetchone()
            if old:
                if old['request']!=request: raise ValueError('Event ID already belongs to a different trade')
                return dict(old)
            if self.db.execute("SELECT 1 FROM world_commands WHERE status IN ('pending','held')").fetchone():
                raise ValueError('An unsettled world command must be reconciled first')
            before=snapshot(observation,buyer,seller)
            cost=quantity*unit_price
            if before['buyer']['gold']<cost or before['seller']['bread']<quantity:
                raise ValueError('Insufficient observed funds or bread')
            after={'buyer':{'gold':before['buyer']['gold']-cost,'bread':before['buyer']['bread']+quantity},
                   'seller':{'gold':before['seller']['gold']+cost,'bread':before['seller']['bread']-quantity}}
            command=dict(id=event_id,session=session,kind='inventory_trade',buyer=buyer,seller=seller,
                         quantity=quantity,cost=cost,before=before,after=after)
            self.db.execute('INSERT INTO world_commands VALUES (?,?,?,?,?,NULL)',
                (event_id,session,request,json.dumps(command,sort_keys=True),'pending'))
        return self.get(event_id)

    def observe(self,observation):
        session=observation.get('session')
        with self.db:
            rows=self.db.execute("SELECT * FROM world_commands WHERE status='pending'").fetchall()
            for row in rows:
                status=None
                reason=None
                command=json.loads(row['command'])
                ack=observation.get('ack') or {}
                if session!=row['session']:
                    status='held';reason='game session changed before settlement'
                elif ack.get('id')==row['id']:
                    if ack.get('status')=='applied':
                        try: actual=snapshot(observation,command['buyer'],command['seller'])
                        except ValueError: continue  # Wait for the next independent observation.
                        if actual==command['after']: status='committed';reason='acknowledged and observed'
                        else: status='held';reason='acknowledgement disagrees with inventory'
                    else:
                        status='held';reason='game could not confirm complete execution'
                if status:
                    evidence=json.dumps({'reason':reason,'observation':observation},sort_keys=True)
                    self.db.execute('UPDATE world_commands SET status=?,evidence=? WHERE id=?',(status,evidence,row['id']))

    def pending(self,session):
        row=self.db.execute("SELECT command FROM world_commands WHERE session=? AND status='pending' LIMIT 1",(session,)).fetchone()
        return json.loads(row['command']) if row else None

    def get(self,event_id):
        row=self.db.execute('SELECT * FROM world_commands WHERE id=?',(event_id,)).fetchone()
        return dict(row) if row else None

    def state(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM world_commands ORDER BY rowid')]
