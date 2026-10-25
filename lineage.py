"""Immutable society checkpoints selected by a save-persistent Skyrim global.

Persist intent before asking the game to bind its marker. Inventory mutations
only run after the prepared marker is observed. Thus an intermediate game save
retains enough information to reconcile either transfer leg after loading.
"""
import copy
import hashlib
import json
import sqlite3
import time
from trade_execution import TradeExecution
from agency import Agency
from food import FoodEconomy, allocation
from production import Production
from market_day import MarketDay
from conversation import Conversation
from population import Population
from livelihood_backgrounds import LivelihoodBackgrounds
from paid_work_policy import paid_work_capability
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
from owner_production import OwnerProduction
from resident_goals import ResidentGoals
from independent_reviews import IndependentReviews
from activity_jobs import ActivityJobs
from owner_work_jobs import OwnerWorkJobs
from paid_employment import PaidEmployment
from paid_employment_metrics import paid_employment_metrics
from independent_review_metrics import independent_review_metrics
from activity_leases import activity_conflict,identity_quarantine_actors
from resident_identity import valid_actor_id
from economy_catalog import require_native_catalog, native_catalog_matches, catalog_hash, MAX_STOCK

MAX_MARKER = 2**24 - 1


class TimelineEconomy(TradeExecution, Agency, FoodEconomy, Production, MarketDay, Conversation, Population, LivelihoodBackgrounds, DailyLife, Endowments, Rest, ParallelRoutines, Enterprises, EconomicSpeech, SceneHandoffs, ResidentControl, OwnerProduction, ResidentGoals, IndependentReviews, ActivityJobs, OwnerWorkJobs, PaidEmployment):
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
        self.latest_observation = None
        self.latest_observation_at = None

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
        # Bootstrap binds observational history only. An explicit census applies
        # the same initialization policy to every currently observed adult.
        state = {'trades': [], 'pending': None, 'people': {},
                 'starting_inventory': copy.deepcopy(observation.get('residents', [])),
                 'starting_inventory_provenance': {
                     'source': 'Observed snapshot at explicit fresh-world bootstrap',
                     'session': self.session, 'checkpoint': 0,
                     'scope': 'Historical observation only; not a spendable account, endowment, or population census'}}
        self.error = None
        return {'checkpoint': self._write(state, 'explicit new-world bootstrap')}

    def observe(self, observation):
        self.latest_observation = None
        self.latest_observation_at = None
        session, marker = observation.get('session'), observation.get('checkpoint')
        if not isinstance(session, str) or not session or type(marker) is not int or not 0 <= marker <= MAX_MARKER:
            self.error = 'Missing or invalid game checkpoint'
            return
        self.latest_observation = copy.deepcopy(observation)
        self.latest_observation_at = time.monotonic()
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
        # A prepared recipe owns the writer until its exact receipt settles.
        # Do not hide its acknowledgement behind an unrelated conversation.
        effect = self.active.get('pending')
        if effect and effect.get('command',{}).get('kind')=='inventory_paid_work_commit':
            self.observe_paid_production(observation)
            return
        if effect and effect.get('command',{}).get('kind')=='inventory_produce':
            self.observe_production(observation)
            return
        if effect and effect.get('command',{}).get('kind')=='inventory_trade':
            self.observe_trade(observation)
            return
        if effect and effect.get('command',{}).get('kind')=='inventory_endowment':
            self.observe_endowment(observation)
            return
        if (effect and effect.get('status')=='pending' and effect.get('command',{}).get('kind','').startswith('inventory_')
            and (effect['command'].get('catalog_hash')!=catalog_hash() or not native_catalog_matches(observation))):
            state=copy.deepcopy(self.active);record=state['pending']
            record.update(status='held',error='Inventory intent has no matching resolved catalog proof; do not replay or stamp a new identity')
            job=state.get('work_jobs',{}).get(record.get('work_job'))
            if job:
                job['settlement']['phase']='held';job['catalog_held']=True
                self._hold_owner_job(state,job,record['error'],unreconciled=True)
            elif state.get('plans'):
                state['plans'][-1].update(phase='held',error=record['error'])
            self._write(state,'unbound inventory intent held before execution or settlement');return
        if effect and effect.get('command', {}).get('kind') == 'inventory_self_produce_commit':
            self.observe_owner_work_recipe(observation)
            return
        # Long activities tick independently in the bridge. Persist their receipts
        # only between foreground inventory effects; these remain serialized.
        foreground_command = self.speech_command(self.session) or self.agency_command(self.session)
        if not self.active['pending'] and not foreground_command and self.observe_activity_jobs(observation):
            return
        if not self.active['pending'] and not foreground_command:
            if self.observe_paid_employment(observation):
                return
            if self.observe_owner_work_jobs(observation):
                return
            if not self.conversation_busy() and not self.agency_busy() and self.prepare_paid_work_commit(observation):
                return
            if not self.conversation_busy() and not self.agency_busy() and self.prepare_owner_work_recipe(observation):
                return
        if self.observe_routines(observation):
            return
        if self.conversation_busy():
            self.observe_conversation(observation)
            if not self.transition and not self.active['pending']:
                self.observe_resident_goals(observation)
                self._observe_independent_followthrough(observation)
            return
        if not self.active['pending']:
            self._agency_observe(observation)
            if not self.transition and not self.active['pending']:
                self.observe_resident_goals(observation)
                self._observe_independent_followthrough(observation)
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
        if pending['command']['kind']=='inventory_self_produce':
            self.observe_owner_production(observation)
            return
    def _observe_independent_followthrough(self, observation):
        # Admission can progress beside an unrelated foreground plan, but every
        # saved change still binds through the single checkpoint writer.
        if self.error or self.transition or not self.active or self.active.get('pending'):return
        if self.observe_independent_reviews(observation):return
        self.prepare_independent_review_jobs(observation)

    def pending(self, session):
        if session != self.session or self.error:
            return None
        if self.transition:
            return {'id': 'checkpoint-' + str(self.transition['next']), 'kind': 'bind_checkpoint',
                    'session': session, **self.transition}
        if self.active and self.active['pending'] and self.active['pending']['status'] == 'pending':
            command=self.active['pending']['command']
            if command.get('kind')=='inventory_produce':return None
            if command.get('kind')=='inventory_paid_work_commit':
                paid_command=self.paid_work_commit_command(session)
                return {**paid_command,'checkpoint':self.marker} if paid_command else None
            if command.get('kind') in ('parallel_routines','background_routines'):
                observation=self.latest_observation or {}
                jobs=command.get('jobs')
                if (command.get('origin_session')!=session or observation.get('session')!=session
                        or observation.get('checkpoint')!=self.marker or not isinstance(jobs,list) or not jobs):return None
                quarantined=identity_quarantine_actors(self.active,observation)
                for job in jobs:
                    if not isinstance(job,dict) or not valid_actor_id(job.get('actor_base_id')):return None
                    matches=[row for row in observation.get('residents',[]) if row.get('id')==job.get('actor')]
                    if len(matches)!=1 or matches[0].get('baseId')!=job['actor_base_id'] or job.get('actor') in quarantined:return None
            if command.get('kind')=='inventory_trade':return self.trade_pending_command(session)
            if command.get('kind')=='inventory_endowment':return self.endowment_pending_command(session)
            if command.get('kind','').startswith('inventory_') and command.get('catalog_hash')!=catalog_hash():return None
            return {**self.active['pending']['command'], 'session': session, 'checkpoint': self.marker}
        foreground_command = self.speech_command(session) or self.agency_command(session)
        if foreground_command:return foreground_command
        paid_command = self.paid_work_pending_command()
        if paid_command:
            return {**paid_command, 'checkpoint': self.marker}
        activity_command = self.activity_pending_command()
        if activity_command:
            return {**activity_command, 'checkpoint': self.marker}
        work_command = self.owner_work_pending_command()
        if work_command:
            return {**work_command, 'checkpoint': self.marker}
        return None

    def state(self):
        if not self.active:
            return []
        pending = self.active['pending']
        records = self.active['trades'] + ([pending] if pending and pending['command']['kind']=='inventory_trade' else [])
        return [{**r, 'command': json.dumps(r['command'])} for r in records]

    def status(self):
        observation=self.latest_observation
        if observation and (observation.get('session')!=self.session or observation.get('checkpoint')!=self.marker):
            observation=None
        return {'checkpoint': self.marker, 'transition': self.transition, 'error': self.error,
                **self.independent_reviews_status(),
                'independent_review_metrics':independent_review_metrics(
                    {**(self.active or {}),'checkpoint':self.marker,'transition':self.transition,'error':self.error},observation,
                    fresh=observation is not None and self.latest_observation_at is not None and 0<=time.monotonic()-self.latest_observation_at<=10),
                'paid_work_capability':paid_work_capability(),
                'paid_employment':self.paid_employment_status(),
                'paid_employment_metrics':paid_employment_metrics(self.active, observation,
                    fresh=observation is not None and self.latest_observation_at is not None and 0<=time.monotonic()-self.latest_observation_at<=10),
                'activity_jobs': self.activity_status(),
                'owner_work_jobs': self.owner_work_status(),
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
                'town':self.population_status(observation)}
