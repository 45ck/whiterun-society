"""Durable journal for observed Skyrim trades, separate from the toy economy.

The game owns physical inventory. A committed journal entry requires both the
game acknowledgement and an independent inventory observation. Unknown partial
effects are held for reconciliation, never silently retried on another save.
"""
import json
import sqlite3
import copy
from economy_catalog import commodity_ids, require_native_catalog, native_catalog_matches, catalog_hash, MAX_STOCK


def snapshot(observation,buyer,seller,commodity='bread'):
    items=commodity_ids()
    if commodity not in items or commodity=='gold':raise ValueError('Unsupported sale commodity')
    actors={row['id']:row for row in observation.get('residents',[])}
    result={}
    for role,actor_id in [('buyer',buyer),('seller',seller)]:
        if actor_id not in actors: raise ValueError('Both actors must be observed and loaded')
        inv=actors[actor_id].get('inventory',{})
        if any(type(inv.get(key)) is not int or not 0<=inv[key]<=MAX_STOCK for key in items):
            raise ValueError('Complete nonnegative inventory observation required')
        result[role]={key:inv[key] for key in items}
    return result


def qualified_snapshot(observation,buyer,seller,expected_bases=None):
    """Current loaded adults plus consistent checkpoint-pinned account evidence."""
    from endowments import observed_recipient, StaleAccountingObservation
    inventory={};bases={};stale=False
    for role,actor in (('buyer',buyer),('seller',seller)):
        visible=[r for r in observation.get('residents',[]) if isinstance(r,dict) and r.get('id')==actor]
        if len(visible)!=1 or visible[0].get('loaded') is False:
            raise ValueError('Both trade participants must be currently observed and loaded')
        try:
            base,stock=observed_recipient(observation,actor,(expected_bases or {}).get(role))
            inventory[role]=stock;bases[role]=base
        except StaleAccountingObservation:
            stale=True
    if stale:raise StaleAccountingObservation('Trade accounting inventory checkpoint is stale')
    return bases,inventory


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
            bound_catalog=require_native_catalog(observation)
            before=snapshot(observation,buyer,seller)
            cost=quantity*unit_price
            if before['buyer']['gold']<cost or before['seller']['bread']<quantity:
                raise ValueError('Insufficient observed funds or bread')
            after=copy.deepcopy(before)
            after['buyer']['gold']-=cost;after['buyer']['bread']+=quantity
            after['seller']['gold']+=cost;after['seller']['bread']-=quantity
            if any(n>MAX_STOCK for stock in after.values() for n in stock.values()):raise ValueError('Trade would overflow native inventory')
            command=dict(id=event_id,session=session,kind='inventory_trade',buyer=buyer,seller=seller,
                         catalog_hash=bound_catalog,quantity=quantity,cost=cost,before=before,after=after)
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
                if command.get('catalog_hash')!=catalog_hash() or not native_catalog_matches(observation):
                    status='held';reason='catalog proof missing or changed; no legacy replay'
                elif session!=row['session']:
                    status='held';reason='game session changed before settlement'
                elif ack.get('id')==row['id']:
                    if ack.get('status')=='applied' and ack.get('catalog_hash')==command['catalog_hash']:
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
        if not row:return None
        command=json.loads(row['command'])
        return command if command.get('catalog_hash')==catalog_hash() else None

    def get(self,event_id):
        row=self.db.execute('SELECT * FROM world_commands WHERE id=?',(event_id,)).fetchone()
        return dict(row) if row else None

    def state(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM world_commands ORDER BY rowid')]
