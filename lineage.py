"""Immutable society checkpoints selected by a save-persistent Skyrim global.

Persist intent before asking the game to bind its marker. Inventory mutations
only run after the prepared marker is observed. Thus an intermediate game save
retains enough information to reconcile either transfer leg after loading.
"""
import copy
import hashlib
import json
import sqlite3
from decisions import PROFILES
from world_economy import snapshot
from agency import Agency
from food import FoodEconomy, allocation
from production import Production
from market_day import MarketDay
from conversation import Conversation
from population import Population
from daily_life import DailyLife
from endowments import Endowments
from rest import Rest
from parallel_routines import ParallelRoutines
from metrics import simulation_metrics
from enterprises import Enterprises
from economic_speech import EconomicSpeech
from scene_handoffs import SceneHandoffs
from resident_control import ResidentControl
from trade_consent import reserved_sale_consent

MAX_MARKER = 2**24 - 1


class TimelineEconomy(Agency, FoodEconomy, Production, MarketDay, Conversation, Population, DailyLife, Endowments, Rest, ParallelRoutines, Enterprises, EconomicSpeech, SceneHandoffs, ResidentControl):
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS checkpoints(
            id INTEGER PRIMARY KEY AUTOINCREMENT, parent INTEGER,
            reason TEXT NOT NULL, payload TEXT NOT NULL, sha256 TEXT NOT NULL)''')
        self.db.commit()
        self.session = None
        self.marker = None
        self.active = None
        self.transition = None
        self.error = 'Waiting for game checkpoint'

    def _write(self, state, reason):
        encoded = json.dumps(state, sort_keys=True, separators=(',', ':'), allow_nan=False)
        with self.db:
            cursor = self.db.execute('INSERT INTO checkpoints(parent,reason,payload,sha256) VALUES (?,?,?,?)',
                (self.marker, reason, encoded, hashlib.sha256(encoded.encode()).hexdigest()))
            if cursor.lastrowid > MAX_MARKER:
                raise ValueError('Save marker range exhausted')
        self.transition = {'expected': self.marker, 'next': cursor.lastrowid}
        return cursor.lastrowid

    def _read(self, marker):
        row = self.db.execute('SELECT * FROM checkpoints WHERE id=?', (marker,)).fetchone()
        if not row or hashlib.sha256(row['payload'].encode()).hexdigest() != row['sha256']:
            raise ValueError('Unknown or corrupt save checkpoint; refusing to adopt latest state')
        return json.loads(row['payload'])

    def bootstrap(self, observation):
        if not observation.get('ready') or observation.get('checkpoint') != 0 or self.marker != 0:
            raise ValueError('Bootstrap requires a freshly observed zero-marker world')
        if observation.get('session') != self.session or self.transition:
            raise ValueError('Session changed or checkpoint transition pending')
        state = {'trades': [], 'pending': None, 'starting_inventory': observation.get('residents', []), 'people': {
            str(actor): {'profile': profile, 'memories': [], 'trust': {}, 'needs': {'hunger': .4}}
            for actor, profile in PROFILES.items()}}
        self.error = None
        return {'checkpoint': self._write(state, 'explicit new-world bootstrap')}

    def observe(self, observation):
        session, marker = observation.get('session'), observation.get('checkpoint')
        if not isinstance(session, str) or not session or type(marker) is not int or not 0 <= marker <= MAX_MARKER:
            self.error = 'Missing or invalid game checkpoint'
            return
        changed = session != self.session or marker != self.marker
        if session != self.session:
            self.transition = None
        if changed:
            expected_transition = self.transition and marker == self.transition['next']
            # Loading another save always follows its marker, never an in-flight newer one.
            if self.transition and not expected_transition:
                self.transition = None
            self.session, self.marker = session, marker
            self.active = None
            try:
                if marker == 0:
                    raise ValueError('New world: initialize society or load a managed save')
                self.active = self._read(marker)
                self.error = None
            except ValueError as error:
                self.error = str(error)
            if expected_transition:
                self.transition = None
        if self.transition:
            ack = observation.get('ack') or {}
            if ack.get('id') == 'checkpoint-' + str(self.transition['next']) and ack.get('status') != 'applied':
                self.error = 'Game could not bind the prepared checkpoint'
            return
        if self.error or not self.active:
            return
        if self.observe_routines(observation):
            return
        if self.conversation_busy():
            self.observe_conversation(observation)
            return
        if not self.active['pending']:
            self._agency_observe(observation)
            return
        pending = self.active['pending']
        if pending['status'] != 'pending':
            self._agency_observe(observation)
            return
        if pending['command']['kind'] == 'scene_handoff':
            self.observe_scene_handoff(observation)
            return
        if pending['command']['kind'] == 'inventory_consume':
            self.observe_consumption(observation)
            return
        if pending['command']['kind'] == 'rest_at_bench':
            self.observe_rest(observation)
            return
        if pending['command']['kind'] == 'inventory_endowment':
            self.observe_endowment(observation)
            return
        if pending['command']['kind'] in ('inventory_produce', 'inventory_supply'):
            self.observe_production(observation)
            return
        ack = observation.get('ack') or {}
        if ack.get('id') != pending['id']:
            return
        command = pending['command']
        try:
            actual = snapshot(observation, command['buyer'], command['seller'])
        except ValueError:
            return
        state = copy.deepcopy(self.active)
        if ack.get('status') == 'applied' and actual == command['after']:
            record = state['pending']
            record['status'] = 'committed'
            record['evidence'] = {'actual': actual, 'ack': ack, 'session': session}
            state['trades'].append(record)
            state['pending'] = None
            if state.get('plans') and state['plans'][-1]['trade_id'] == record['id']:
                if state['plans'][-1].get('food_actions'):
                    state['plans'][-1].update(phase='after_purchase', purchase_completed=True)
                    self.queue_trade_speech(state,state['plans'][-1],'receipt')
                else:
                    state['plans'][-1].update(phase='complete', outcome='bought_bread')
            for actor, other, role in [(command['buyer'], command['seller'], 'bought'),
                                        (command['seller'], command['buyer'], 'sold')]:
                person = state['people'].get(str(actor))
                if person is not None:
                    person['memories'].append({'event_id': record['id'], 'kind': 'completed_trade',
                        'role': role, 'other': other, 'bread': command['quantity'], 'gold': command['cost']})
                    person['memories'] = person['memories'][-32:]
                    person['trust'][str(other)] = min(10, person['trust'].get(str(other), 0) + 1)
            self._write(state, 'trade observed; memories and trust updated')
        else:
            state['pending']['status'] = 'held'
            state['pending']['evidence'] = {'actual': actual, 'ack': ack}
            if state.get('plans') and state['plans'][-1]['trade_id'] == pending['id']:
                state['plans'][-1].update(phase='held', error='Physical trade requires reconciliation')
            self._write(state, 'trade requires reconciliation')

    def plan_trade(self, event_id, observation, buyer, seller, quantity=1, unit_price=3, agency_plan=None):
        if self.routines_busy():raise ValueError('Independent journeys are still executing')
        if self.conversation_busy():
            raise ValueError('A conversation owns the participants')
        if self.error or not self.active or self.transition:
            raise ValueError('Society checkpoint is not synchronized')
        if observation.get('session') != self.session or observation.get('checkpoint') != self.marker:
            raise ValueError('Observation belongs to a different checkpoint')
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 128 or event_id.startswith('checkpoint-'):
            raise ValueError('Invalid trade event ID')
        if any(type(v) is not int or v <= 0 for v in (buyer, seller, quantity, unit_price)):
            raise ValueError('Positive integer trade values required')
        if buyer == seller or quantity > 10 or unit_price > 100:
            raise ValueError('Invalid or oversized trade')
        request = dict(buyer=buyer, seller=seller, quantity=quantity, unit_price=unit_price)
        for old in self.active['trades'] + ([self.active['pending']] if self.active['pending'] else []):
            if old['id'] == event_id:
                if old['request'] != request:
                    raise ValueError('Event ID reused with different trade')
                return old
        if self.active['pending']:
            raise ValueError('An unsettled trade must be reconciled first')
        before = snapshot(observation, buyer, seller)
        cost = quantity * unit_price
        if before['buyer']['gold'] < cost or before['seller']['bread'] < quantity:
            raise ValueError('Insufficient observed funds or bread')
        stock = allocation(self.active['people'].get(str(seller), {}), before['seller'])
        reserve_consent=reserved_sale_consent(self.active,event_id,buyer,seller,quantity,unit_price,agency_plan,before['seller'])
        if stock['allocated'] and stock['for_sale'] < quantity and not reserve_consent:
            raise ValueError('This trade would spend the resident\'s household reserve')
        after = {'buyer': {'gold': before['buyer']['gold']-cost, 'bread': before['buyer']['bread']+quantity},
                 'seller': {'gold': before['seller']['gold']+cost, 'bread': before['seller']['bread']-quantity}}
        command = dict(id=event_id, kind='inventory_trade', buyer=buyer, seller=seller,
                       quantity=quantity, cost=cost, before=before, after=after)
        record = dict(id=event_id, request=request, command=command, status='pending', evidence=None)
        if reserve_consent:record['reserve_release']=copy.deepcopy(reserve_consent)
        state = copy.deepcopy(self.active)
        state['pending'] = record
        if agency_plan:
            if not state.get('plans') or state['plans'][-1]['id'] != agency_plan:
                raise ValueError('Trade has no matching resident plan')
            state['plans'][-1]['phase'] = 'trading'
        checkpoint = self._write(state, 'trade intent persisted before physical action')
        return {**record, 'prepared_checkpoint': checkpoint}

    def pending(self, session):
        if session != self.session or self.error:
            return None
        if self.transition:
            return {'id': 'checkpoint-' + str(self.transition['next']), 'kind': 'bind_checkpoint',
                    'session': session, **self.transition}
        if self.active and self.active['pending'] and self.active['pending']['status'] == 'pending':
            return {**self.active['pending']['command'], 'session': session, 'checkpoint': self.marker}
        return self.speech_command(session) or self.agency_command(session)

    def state(self):
        if not self.active:
            return []
        pending = self.active['pending']
        records = self.active['trades'] + ([pending] if pending and pending['command']['kind']=='inventory_trade' else [])
        return [{**r, 'command': json.dumps(r['command'])} for r in records]

    def status(self):
        return {'checkpoint': self.marker, 'transition': self.transition, 'error': self.error,
                'scene_handoffs':self.active.get('scene_handoffs',[]) if self.active else [],
                'metrics':simulation_metrics(self.active),
                'people': self.active['people'] if self.active else {}, 'plan': self.agency_plan(),
                'routine_batch': self.routine_batch(),
                'trades':self.active.get('trades',[]) if self.active else [],
                'consumptions': self.active.get('consumptions', []) if self.active else [],
                'production': self.active.get('production', []) if self.active else [],
                'cancelled_production': self.active.get('cancelled_production', []) if self.active else [],
                'unsettled_effect': self.active.get('pending') if self.active else None,
                'rests': self.active.get('rests', []) if self.active else [],
                'imports': self.active.get('imports', []) if self.active else [],
                'resource_delivery': self.active['pending'] if self.active and self.active['pending'] and self.active['pending']['command']['kind']=='inventory_endowment' else None,
                'market_day': self.scenario_status(), 'conversation': self.conversation_status(),
                'town':self.population_status()}
