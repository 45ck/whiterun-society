"""Offline-first qualification of two real owner jobs and optional local speech.

Default usage requires --state-file and performs no HTTP or native actions.
--inspect-live only reads loopback metadata. --execute-authorized-trial is for
an operator who has separately obtained permission to run the native trial.
This harness never seeds stock, edits charters, loads saves, calls cloud models,
replays uncertain mutations, or cancels/releases work after a timeout.
"""
import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_production import owner_work_opportunities
from owner_work_jobs import IDENTITY
from economy_catalog import catalog_hash, commodity_ids, native_catalog_matches, recipe_hash, recipe_spec
from social import social_candidates, SOCIAL_STAGES
from conversation import validate_candidates
from dialogue_context import validate_situated_candidates
from decisions import validate_decision
from tools.checkpoint_http import CheckpointHTTP
from tools.run_resident_event import owner_work_job_records, delegated_activity_admission
from tools.run_conversation import stock_voice
from tools.voice_worker import VoiceWorker

MODEL = 'authored-owner-work-qualification-v1'
ITEMS = commodity_ids()
KEYS = (*IDENTITY, 'actor_base_id')
LINES = (
    'Hello there. It is good to exchange a few words. A brief pause and a little conversation can be pleasant, without any business to settle.',
    'Yes, a friendly word can be welcome. I appreciate a moment to listen without needing to make a promise or settle a bargain.',
    'I understand. Sometimes a simple greeting and a little patience are enough. Thank you for taking the time to exchange a few words with me.',
    'You are welcome. I have enjoyed this brief conversation, and I appreciate your courtesy. Take care, and may the rest of your day go well.',
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def exact_identity(row, job):
    return (isinstance(row, dict) and row.get('job_id', row.get('id')) == job['job_id']
            and all(k in job and type(row.get(k)) is type(job[k]) and row.get(k) == job[k] for k in KEYS))


def resident(observation, actor):
    return next((r for r in observation.get('residents', []) if r.get('id') == actor and r.get('isPerson') is True), None)


def disjoint_pair(state, excluded):
    society, obs = state['society'], state['bridge']['observation']
    for actor in sorted(int(k) for k in society.get('people', {})):
        if actor in excluded:continue
        for other in social_candidates(society, obs, actor):
            if other['id'] not in excluded:return [actor, other['id']]
    return None


def preflight(state, director_running=False, now=None):
    """Pure selection: observe existing opportunities; never create prerequisites."""
    society, obs = state['society'], state['bridge']['observation']
    capability = obs.get('owner_work_jobs') or {}
    candidates, eligible, gaps = [], [], []
    if not native_catalog_matches(obs, 'bread_recipe'):gaps.append('Current verified native bread catalog and recipe hashes are required.')
    recipe = recipe_spec('bread_recipe')
    if recipe['inputs'] != {'grain': 1} or recipe['outputs'] != {'bread': 2}:
        gaps.append('This acceptance case requires the existing one-grain two-bread recipe; use a separate case for other conversions.')
    if now is not None:
        seen = state['bridge'].get('last_seen')
        if type(seen) not in (int, float) or not 0 <= now - seen <= 10 or obs.get('ready') is not True:
            gaps.append('Fresh ready native observation required; metadata is stale or not ready.')
    if director_running:gaps.append('Director is running; controlled qualification requires it stopped.')
    if society.get('error') or society.get('transition') or society.get('unsettled_effect') or state['bridge'].get('command'):
        gaps.append('Checkpoint or inventory writer is unsettled.')
    if capability.get('available') is not True or type(capability.get('capacity')) is not int or capability['capacity'] - len(capability.get('jobs', [])) < 2:
        gaps.append('At least two free native owner-work slots are required.')
    plan = society.get('plan') or {};chat = society.get('conversation') or {}
    if plan and plan.get('phase') not in ('held', 'complete', 'delegated'):gaps.append('A foreground resident plan is active.')
    if chat and chat.get('phase') not in ('held', 'complete'):gaps.append('A conversation is active.')
    queue = society.get('town', {}).get('daily', {}).get('queue', [])
    for person in sorted(obs.get('residents', []), key=lambda r:r.get('id', 0)):
        actor = person.get('id')
        if person.get('isPerson') is not True or type(person.get('baseId')) is not int:continue
        for opportunity in owner_work_opportunities(society, obs, actor):
            if opportunity['recipe_id'] != 'bread_recipe':continue
            control = next((r for r in obs.get('resident_control', {}).get('activities', []) if r.get('actor') == actor), {})
            slot = control.get('slot')
            if type(slot) is not int or not 0 <= slot < 128:continue
            entry = {'actor': actor, 'actor_base_id': person['baseId'], 'slot': slot,
                     'business_id': opportunity['business_id'], 'business_revision': opportunity['revision'],
                     'recipe_id': opportunity['recipe_id'], 'catalog_hash': opportunity['catalog_hash'], 'recipe_hash': opportunity['recipe_hash'],
                     'policy': opportunity['policy'], 'expected_package': opportunity['expected_package'],
                     'inventory_before': {k:person['inventory'][k] for k in ITEMS}, 'account_actor': actor}
            eligible.append(entry)
            event = next((e for e in queue if e.get('actor') == actor and e.get('kind') == 'need_review' and e.get('status') == 'pending'), None)
            if event:candidates.append({**entry, 'source_plan': event['id']})
    pairs = [(a, b) for i, a in enumerate(candidates) for b in candidates[i + 1:]
             if a['actor'] != b['actor'] and a['slot'] != b['slot'] and a['business_id'] != b['business_id']]
    selected = list(min(pairs, key=lambda pair:(-min(p['policy']['work_minutes'] for p in pair), pair[0]['actor'], pair[1]['actor']))) if pairs else []
    if not selected:gaps.append(f'Two disjoint eligible owners with pending need reviews required; found {len({p["actor"] for p in eligible})} eligible owners and {len({p["actor"] for p in candidates})} pending eligible owners. No stock or charters will be created.')
    pair = disjoint_pair(state, {p['actor'] for p in selected}) if selected else None
    charters = [{'business_id': key, 'owner': b.get('owner'), 'custodian': b.get('custodian'), 'capabilities': b.get('capabilities', [])}
                for key, b in sorted(society.get('town', {}).get('businesses', {}).items()) if b.get('active', True)]
    return {'ready': not gaps, 'gaps': gaps, 'selected_owners': selected, 'eligible_owners': eligible,
            'observed_charters': charters, 'social_pair': pair, 'cloud_model_calls': 0,
            'checkpoint': society.get('checkpoint'), 'native_received_at': state['bridge'].get('last_seen'),
            'owner_work_capability': {k:capability.get(k) for k in ('available', 'capacity')},
            'freshness_checked': now is not None,
            'scope': 'Existing loaded state only; no seeded stock, new charter, need review or authored completion.'}


def native_working(observation, job):
    native = next((r for r in (observation.get('owner_work_jobs') or {}).get('jobs', []) if exact_identity(r, job)), None)
    actor = resident(observation, job['actor'])
    control = next((r for r in (observation.get('resident_control') or {}).get('activities', []) if r.get('actor') == job['actor']), {})
    return bool(native and native.get('phase') == 'working' and type(native.get('samples')) is int and native['samples'] >= 2
                and type(native.get('worked_minutes')) in (int, float) and math.isfinite(native['worked_minutes']) and native['worked_minutes'] >= 0
                and actor and actor.get('baseId') == job['actor_base_id'] and control.get('slot') == job['slot']
                and control.get('mode') == 'await_decision' and control.get('target') == job['actor']
                and control.get('phase') == 'work_holding' and control.get('ownedPackage') is True
                and control.get('work_hold_id') == 'owner-work-' + job['job_id'] and control.get('goal_id') == control['work_hold_id']
                and type(control.get('serial')) is int and 1 <= control['serial'] <= 16777215
                and type(control.get('expectedPackage')) is int
                and (actor.get('activity') or {}).get('package_id') == control['expectedPackage'])


def overlap_metrics(samples, verified_delivery_ids=()):
    work = voice = longest = longest_voice = current = current_voice = 0.
    verified = set(verified_delivery_ids)
    for a, b in zip(samples, samples[1:]):
        delta = b['elapsed_seconds'] - a['elapsed_seconds']
        same_jobs = a.get('working_job_ids') == b.get('working_job_ids') and len(b.get('working_job_ids', [])) == len(set(b.get('working_job_ids', []))) == 2
        observed_delta = b.get('native_received_at', 0) - a.get('native_received_at', 0)
        left = {r['job_id']: r for r in a.get('work_observations', [])}
        right = {r['job_id']: r for r in b.get('work_observations', [])}
        progressed = same_jobs and all(j in left and j in right and exact_identity(left[j], right[j])
            and left[j]['serial'] == right[j]['serial'] and right[j]['samples'] > left[j]['samples']
            and right[j]['worked_minutes'] > left[j]['worked_minutes'] for j in b['working_job_ids'])
        qualifies = 0 < delta <= 1.75 and 0 < observed_delta <= 1.75 and progressed
        delta = min(delta, observed_delta) if qualifies else 0.
        current = current + delta if qualifies else 0.;work += delta if qualifies else 0.;longest = max(longest, current)
        delivery = b.get('playing_delivery_id')
        spoken = qualifies and delivery in verified and delivery == a.get('playing_delivery_id')
        current_voice = current_voice + delta if spoken else 0.;voice += delta if spoken else 0.;longest_voice = max(longest_voice, current_voice)
    return {'two_qualified_work_seconds': round(work, 3), 'longest_continuous_work_seconds': round(longest, 3),
            'verified_voice_and_two_work_seconds': round(voice, 3), 'longest_continuous_voice_overlap_seconds': round(longest_voice, 3),
            'method': 'Adjacent samples at most 1.75 seconds apart with advancing heartbeat timestamps and two identical jobs, serials, increasing native samples and attended minutes; duration is the smaller observed or polling interval. Speech requires same delivery and subsequently completed unmuted nearby playback. Cached state and gaps add no time.'}


def qualification_summary(results, samples, verified, conversation_id, conversation, minimum_overlap_seconds):
    metrics = overlap_metrics(samples, verified)
    work = len(results) == 2 and all(r['qualified'] for r in results) and metrics['two_qualified_work_seconds'] >= minimum_overlap_seconds
    voice = bool(conversation_id and conversation.get('id') == conversation_id and conversation.get('phase') == 'complete'
        and len(set(verified)) == 4 and metrics['verified_voice_and_two_work_seconds'] >= minimum_overlap_seconds)
    return {'work_qualified': work, 'voice_overlap_qualified': voice, 'qualified': bool(work and voice),
            'status': 'qualified' if work and voice else 'work_only' if work else 'not_qualified'}


def read_plan_proofs(database, checkpoint, plan_ids):
    """Read the exact immutable bound checkpoint; never attach to the latest row."""
    if type(checkpoint) is not int or checkpoint < 1:raise ValueError('Bound checkpoint required for source-plan proof')
    uri = Path(database).resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True, timeout=2)) as db:
        row = db.execute('SELECT payload,sha256 FROM checkpoints WHERE id=?', (checkpoint,)).fetchone()
    if not row or hashlib.sha256(row[0].encode()).hexdigest() != row[1]:raise ValueError('Exact source-plan checkpoint missing or hash mismatch')
    payload = json.loads(row[0])
    return {'checkpoint': checkpoint, 'checkpoint_sha256': row[1], 'plans': [
        {k:p.get(k) for k in ('id', 'actor', 'kind', 'phase', 'outcome', 'work_job')}
        for p in payload.get('plans', []) if p.get('id') in plan_ids]}


def verify_result(state, admission, source_plans):
    society = state['society'];job = owner_work_job_records(society).get(admission['job_id'], {})
    settlement = job.get('settlement') or {};commit_id = settlement.get('commit_id')
    records = [r for r in society.get('production', []) if r.get('id') == commit_id and r.get('work_job') == admission['job_id']]
    record = records[0] if len(records) == 1 else {};command = record.get('command') or {};evidence = record.get('evidence') or {};ack = evidence.get('ack') or {}
    before, after = command.get('before'), command.get('after');inventory_valid = False;delta = None
    if isinstance(before, dict) and isinstance(after, dict) and set(before) == set(after) == {'owner'}:
        if all(isinstance(v, dict) and set(v) == set(ITEMS) and all(type(v[k]) is int and v[k] >= 0 for k in ITEMS) for v in (before['owner'], after['owner'])):
            delta = {k:after['owner'][k] - before['owner'][k] for k in ITEMS}
            inventory_valid = delta == {**{k:0 for k in ITEMS}, 'bread': 2, 'grain': -1} and before['owner'] == admission['inventory_before']
    actual = resident(state['bridge']['observation'], admission['actor'])
    attendance = job.get('attendance') or {};minutes = attendance.get('worked_minutes');anchor = attendance.get('anchor')
    attendance_verified = bool(job.get('attendance_receipt_hash') and attendance.get('token') == command.get('attendance_token')
        and type(attendance.get('samples')) is int and attendance['samples'] >= 2
        and type(minutes) in (int, float) and math.isfinite(minutes) and admission['work_minutes'] <= minutes <= admission['work_minutes'] + 1
        and attendance.get('slot') == admission['slot'] and attendance.get('expected_package') == admission['expected_package']
        and type(attendance.get('serial')) is int and 1 <= attendance['serial'] <= 16777215
        and isinstance(anchor, list) and len(anchor) == 3 and all(type(x) in (int, float) and math.isfinite(x) for x in anchor))
    output_verified = bool(exact_identity(job, admission) and exact_identity(command, admission) and exact_identity(ack, admission)
        and admission['recipe_id'] == 'bread_recipe' and admission['catalog_hash'] == catalog_hash() and admission['recipe_hash'] == recipe_hash('bread_recipe')
        and native_catalog_matches(state['bridge']['observation'], 'bread_recipe')
        and record.get('status') == 'committed' and command.get('kind') == 'inventory_self_produce_commit' and command.get('id') == commit_id
        and ack.get('id') == commit_id and ack.get('commit_id') == commit_id and ack.get('status') == 'applied'
        and ack.get('effects_issued') is True and ack.get('committed_inventory_verified') is True and ack.get('mechanism') == 'native_owner_recipe'
        and bool(command.get('attendance_token')) and ack.get('attendance_token') == command['attendance_token']
        and attendance_verified and inventory_valid and ack.get('inventory') == evidence.get('actual') == after and evidence.get('session') == admission['session']
        and actual and actual.get('baseId') == admission['actor_base_id'] and actual.get('inventory') == after['owner']
        and state['bridge']['session'] == admission['session'] and settlement.get('phase') == 'committed'
        and settlement.get('production_record_id') == commit_id and settlement.get('committed_inventory_verified') is True)
    source = next((p for p in source_plans if p.get('id') == admission['source_plan']), {})
    source_verified = source.get('actor') == admission['actor'] and source.get('work_job') == admission['job_id'] and source.get('phase') == 'complete' and source.get('outcome') == 'owner_work_completed'
    cleanup = job.get('phase') == 'complete' and job.get('release_verified') is True and job.get('receipt_acknowledged') is True and bool(job.get('receipt_hash')) and job.get('effect_unreconciled') is not True
    return {'job_id': admission['job_id'], 'actor': admission['actor'], 'commit_id': commit_id, 'source_plan': admission['source_plan'],
            'output_verified': output_verified, 'attendance_verified': attendance_verified, 'source_plan_verified': source_verified, 'release_acknowledged': cleanup,
            'qualified': bool(output_verified and source_verified and cleanup), 'inventory_delta': delta,
            'production_record_sha256': digest(record) if record else None, 'native_receipt_hash': job.get('receipt_hash'),
            'productive_animation_verified': False}


def authored_dialogue(stage, context, turn, partner):
    metadata = {'model': MODEL, 'attempted': False, 'model_generated': False, 'authored_test_fixture': True}
    if stage == 'propose':
        if not 0 <= turn < 4:raise ValueError('Authored four-turn limit reached')
        proposal = {'candidates': [{'id': 'option_1', 'intention': 'Close politely' if turn == 3 else 'Exchange a courteous remark', 'line': LINES[turn], 'tone': 'calm'},
                                   {'id': 'option_2', 'intention': 'Be courteous', 'line': 'Thank you for taking the time. Goodbye.' if turn == 3 else 'A friendly word can be welcome.', 'tone': 'calm'}]}
        validate_candidates(proposal)
        if context.get('interaction'):validate_situated_candidates(proposal['candidates'], context['interaction'], closing=turn == 3)
        return {**metadata, 'proposal': proposal}
    action = {'choose_partner': 'approach_' + str(partner), 'respond': 'chat', 'select': 'option_1',
              'continue_dialogue': 'close_politely' if turn == 3 else 'reply', 'reflect_first': 'neutral', 'reflect_second': 'neutral'}.get(stage)
    if not action:raise ValueError('Unsupported authored conversation stage')
    decision = {'action_id': action, 'reason': 'Authored native protocol qualification; not autonomous reasoning', 'emotion': 'calm'}
    validate_decision(decision, context)
    return {**metadata, 'decision': decision}


def authored_owner_choice(context, selected):
    choices = [key for key, terms in context.get('work_options', {}).items()
        if key in context.get('owner_work_actions', []) and isinstance(terms, dict)
        and all(terms.get(field) == selected[field] for field in ('business_id', 'recipe_id', 'catalog_hash', 'recipe_hash'))
        and terms.get('revision') == selected['business_revision']]
    if len(choices) != 1:raise ValueError('One exact current owner recipe choice is required; no inferred action ID')
    decision = {'action_id': choices[0], 'reason': 'Authored two-owner native qualification; use existing owned resources only', 'emotion': 'calm'}
    validate_decision(decision, context)
    return decision


class Qualification:
    def __init__(self, client, root, output, seconds=300, voice_factory=VoiceWorker, minimum_overlap_seconds=10):
        if not 30 <= seconds <= 600:raise ValueError('Trial bound must be30..600seconds')
        if not 1 <= minimum_overlap_seconds <= 120:raise ValueError('Overlap threshold must be 1..120 seconds')
        self.client, self.root, self.output, self.voice_factory = client, Path(root), Path(output), voice_factory
        self.began = time.monotonic();self.deadline = self.began + seconds;self.session = None;self.last_sample = -math.inf;self.last_state = None
        self.evidence = {'schema': 'owner-work-qualification-v1', 'id': 'owner-qualification-' + uuid.uuid4().hex[:16], 'status': 'preflight',
                         'authored_test_fixture': True, 'cloud_model_calls': 0, 'scope': 'Authored owner choices and optional four-line local speech. Native protocol qualification only; not autonomous choice, productive animation, natural conversation, lip sync or physical audibility.',
                         'limit_seconds': seconds, 'minimum_overlap_seconds': minimum_overlap_seconds, 'admissions': [], 'samples': [], 'qualified': False}
        self.verified = set();self.conversation_id = None;self.voice = None;self.clips = [];self.dialogue_calls = 0

    def save(self):
        self.evidence['overlap'] = overlap_metrics(self.evidence['samples'], self.verified)
        self.output.write_text(json.dumps(self.evidence, indent=2, allow_nan=False) + '\n', encoding='utf-8')

    def observe(self):
        state = self.client('/state');self.last_state = state;bridge = state['bridge'];society = state['society'];obs = bridge['observation']
        age = time.time() - (bridge.get('last_seen') or 0)
        if not 0 <= age <= 10 or obs.get('ready') is not True:raise ValueError('Fresh ready native observation required')
        if self.session is None:self.session = bridge['session'];self.evidence['session'] = self.session
        if not self.session or bridge['session'] != self.session:raise ValueError('Native session changed; trial will not replay')
        if society.get('error'):raise ValueError('Society reports an unresolved error')
        c = society.get('conversation') or {};speech = obs.get('speech') or {};current = c.get('current') or {}
        if c.get('id') == self.conversation_id:
            for turn in c.get('turns', []):
                playback = turn.get('playback') or {}
                if turn.get('delivered') is True and playback.get('status') == 'ended' and playback.get('nearbyThroughout') is True and playback.get('muted') is False and playback.get('volume') == 1:
                    self.verified.add(turn['delivery_id'])
        now = time.monotonic()
        if now - self.last_sample >= .5:
            self.last_sample = now;admissions = self.evidence['admissions'];excluded = {j['actor'] for j in admissions}
            participants = {current.get('speaker'), current.get('listener')} - {None}
            playing = c.get('id') == self.conversation_id and c.get('phase') == 'speaking' and speech.get('status') == 'playing' and speech.get('nearbyThroughout') is True and speech.get('id') == current.get('delivery_id') and len(participants) == 2 and not excluded.intersection(participants)
            working = []
            for job in admissions:
                if not native_working(obs, job):continue
                native = next(r for r in obs['owner_work_jobs']['jobs'] if exact_identity(r, job))
                control = next(r for r in obs['resident_control']['activities'] if r.get('actor') == job['actor'])
                working.append({'job_id': job['job_id'], **{k:job[k] for k in KEYS}, 'serial': control['serial'],
                    'samples': native['samples'], 'worked_minutes': native['worked_minutes'], 'expected_package': control['expectedPackage']})
            self.evidence['samples'].append({'elapsed_seconds': round(now - self.began, 3), 'checkpoint': society.get('checkpoint'),
                'native_received_at': bridge['last_seen'], 'game_days': obs.get('gameDays'), 'work_observations': working,
                'working_job_ids': sorted(j['job_id'] for j in working),
                'playing_delivery_id': speech.get('id') if playing else None})
            self.save()
        return state

    def stable(self, limit=40):
        until = min(self.deadline, time.monotonic() + limit)
        while time.monotonic() < until:
            state = self.observe()
            if not state['society'].get('transition') and not state['bridge'].get('command') and not state['society'].get('unsettled_effect'):return state
            time.sleep(.1)
        raise TimeoutError('Bounded checkpoint wait expired; no mutation replay')

    def mutate(self, route, data):
        if time.monotonic() >= self.deadline:raise TimeoutError('Trial deadline reached before mutation')
        return self.client(route, data)

    def admit(self, selected):
        state = self.stable();current = preflight(state)['eligible_owners']
        if not any(all(c.get(k) == selected[k] for k in ('actor', 'actor_base_id', 'slot', 'business_id', 'business_revision', 'recipe_id', 'catalog_hash', 'recipe_hash', 'policy', 'inventory_before')) for c in current):
            raise ValueError('Selected owner, charter or unseeded stock changed before admission')
        plan_id = selected['source_plan'];actor = selected['actor']
        started = self.mutate('/agency/event', {'id': plan_id, 'actor': actor, 'kind': 'need_review'})
        if started.get('duplicate'):raise ValueError('Existing source plan refused; no trial replay')
        self.stable();claim = self.mutate('/agency/claim', {'id': plan_id})['claim'];state = self.stable();plan = state['society'].get('plan') or {}
        if plan.get('id') != plan_id or (plan.get('claim') or {}).get('id') != claim['id']:raise ValueError('Owner decision claim identity changed')
        decision = authored_owner_choice(claim['context'], selected)
        self.mutate('/agency/decision', {'id': plan_id, 'claim_id': claim['id'], 'result': {'model': MODEL, 'attempted': False, 'authored_test_fixture': True, 'model_generated': False, 'decision': decision}})
        until = min(self.deadline, time.monotonic() + 60)
        while time.monotonic() < until:
            state = self.observe();plan = state['society'].get('plan') or {}
            if plan.get('id') != plan_id:raise ValueError('Owner source plan changed before verified delegation')
            if plan.get('phase') == 'held':raise ValueError('Native owner admission held; no retry')
            if plan.get('phase') in ('delegated', 'complete'):
                admission = delegated_activity_admission(state, plan_id, actor, self.session)
                if admission:
                    job = owner_work_job_records(state['society'])[admission['work_job_id']]
                    saved = {'job_id': job['id'], **{k:job[k] for k in KEYS}, 'source_plan': plan_id, 'inventory_before': selected['inventory_before'],
                             'expected_package': selected['expected_package'],
                             'admission_verified': True, 'admitted_checkpoint': state['society']['checkpoint'], 'admission_plan_phase': plan['phase']}
                    if any(saved[k] != selected[k] for k in ('actor', 'actor_base_id', 'slot', 'business_id', 'business_revision', 'recipe_id', 'catalog_hash', 'recipe_hash')):raise ValueError('Delegated owner identity differs from selection')
                    self.evidence['admissions'].append(saved);self.save();return
            time.sleep(.15)
        raise TimeoutError('Owner admission timeout; work remains governed by its saved lane')

    def drive_dialogue(self, state, pair):
        c = state['society'].get('conversation') or {}
        if c.get('id') != self.conversation_id:raise ValueError('Controlled conversation identity changed')
        if ({c.get('initiator'), c.get('partner')} - {None}) - set(pair):raise ValueError('Unexpected fixture conversation participant')
        phase, turn = c['phase'], c['turn']
        if phase in ('complete', 'held'):return
        if phase in ('propose', 'select') + SOCIAL_STAGES:
            if self.dialogue_calls >= 15:raise ValueError('Authored conversation claim budget exhausted')
            claim = self.mutate('/conversation/claim', {'id': self.conversation_id})['claim'];confirmed = self.stable()
            bound = confirmed['society'].get('conversation') or {}
            if claim.get('session') != self.session or bound.get('id') != self.conversation_id or (bound.get('claim') or {}).get('id') != claim['id']:raise ValueError('Conversation claim identity changed; no re-authoring')
            result = authored_dialogue(phase, claim['context'], turn, pair[1]);self.dialogue_calls += 1
            self.mutate('/conversation/result', {'id': self.conversation_id, 'claim_id': claim['id'], 'result': result})
        elif phase == 'synthesize':
            if not 0 <= turn < 4:raise ValueError('Four-turn local voice limit exceeded')
            current = c['current'];clip = self.clips[turn]
            if current.get('speaker') != pair[turn % 2] or current.get('selected', {}).get('line') != LINES[turn]:raise ValueError('Prepared speech identity or exact authored line changed')
            self.mutate('/conversation/audio', {'id': self.conversation_id, 'audio': clip['audio']})
        elif phase.startswith('thinking_'):raise ValueError('Unresolved authored claim; no automatic result replay')

    def run(self, authorized=False):
        if authorized is not True:raise PermissionError('Native trial requires separately granted operator authorization')
        if self.output.exists():raise FileExistsError('Evidence path already exists; choose a new path')
        with self.output.open('x', encoding='utf-8') as output:output.write('{}\n')
        try:
            state = self.stable();selection = preflight(state, self.client('/observer/state')['director']['running']);self.evidence['preflight'] = selection;self.save()
            if not selection['ready']:raise ValueError('Native prerequisites unavailable; inspect preflight gaps')
            pair = selection['social_pair'];self.evidence['social_pair'] = pair
            if pair:
                self.voice = self.voice_factory(self.root, 4, [])
                for turn, line in enumerate(LINES):
                    remaining = self.deadline - time.monotonic()
                    if remaining <= 0:raise TimeoutError('Local voice prewarming exceeded deadline')
                    self.clips.append(self.voice.synthesize(line, stock_voice(pair[turn % 2], state['bridge']['observation']), timeout=min(90, remaining)))
                self.evidence['prepared_audio'] = [{'sha256': c['audio']['sha256'], 'seconds': c['audio']['seconds']} for c in self.clips]
            for owner in selection['selected_owners']:self.admit(owner)
            until = min(self.deadline, time.monotonic() + 60)
            while time.monotonic() < until:
                state = self.observe()
                if all(native_working(state['bridge']['observation'], j) for j in self.evidence['admissions']):break
                if any(owner_work_job_records(state['society']).get(j['job_id'], {}).get('phase') in ('complete', 'held') for j in self.evidence['admissions']):raise ValueError('Work ended before simultaneous attendance was observed')
                time.sleep(.15)
            else:raise TimeoutError('No two simultaneously qualified owner jobs')
            self.evidence['both_working_before_dialogue'] = True
            if pair and pair[1] in {p['id'] for p in social_candidates(state['society'], state['bridge']['observation'], pair[0])}:
                self.conversation_id = self.evidence['id'] + '-dialogue';self.evidence['conversation_id'] = self.conversation_id
                response = self.mutate('/conversation/start', {'id': self.conversation_id, 'actor': pair[0], 'max_turns': 4, 'reply_policy': 'separate_choice'})
                if response.get('duplicate'):raise ValueError('Existing conversation refused; no replay')
            else:self.evidence['dialogue_unavailable'] = 'No currently qualified disjoint prepared social pair; work result measured separately.'
            self.evidence['status'] = 'observing'
            while time.monotonic() < self.deadline:
                state = self.observe()
                if not state['society'].get('transition') and self.conversation_id:self.drive_dialogue(state, pair)
                jobs = owner_work_job_records(state['society']);chat = state['society'].get('conversation') or {}
                if all(jobs.get(j['job_id'], {}).get('receipt_acknowledged') is True for j in self.evidence['admissions']) and (not self.conversation_id or chat.get('phase') in ('complete', 'held')):break
                time.sleep(.15)
            else:raise TimeoutError('Trial bound reached; no work cancellation or native effect replay')
            state = self.stable();proof = read_plan_proofs(self.root / 'runtime/timeline.sqlite', state['society']['checkpoint'], {j['source_plan'] for j in self.evidence['admissions']})
            self.evidence['source_plan_proof'] = proof
            self.evidence['results'] = [verify_result(state, j, proof['plans']) for j in self.evidence['admissions']]
            chat = state['society'].get('conversation') or {}
            self.evidence.update(qualification_summary(self.evidence['results'], self.evidence['samples'], self.verified,
                self.conversation_id, chat, self.evidence['minimum_overlap_seconds']), verified_delivery_ids=sorted(self.verified))
        except Exception as error:
            self.evidence.update(status='not_qualified', qualified=False, error_type=type(error).__name__, error=str(error)[:240],
                                 cleanup='No work cancellation, release, charter mutation or inventory retry attempted. Saved native/service lanes retain ownership.')
        finally:
            if self.voice:
                try:self.voice.close()
                except Exception as error:self.evidence['local_voice_cleanup_error'] = type(error).__name__
            self.evidence['authored_dialogue_results'] = self.dialogue_calls
            self.evidence['elapsed_seconds'] = round(time.monotonic() - self.began, 3);self.save()
        return self.evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('D:/WhiterunLab'))
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--state-file', type=Path, help='Offline JSON inspection; no HTTP, models or native actions')
    modes.add_argument('--inspect-live', action='store_true', help='Read-only loopback preflight')
    modes.add_argument('--execute-authorized-trial', action='store_true', help='Run only after separate human authorization; mutates native simulation through existing APIs')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--minimum-overlap-seconds', type=float, default=10)
    args = parser.parse_args(argv)
    if args.output.exists():raise FileExistsError('Evidence path already exists')
    if args.state_file:
        report = preflight(json.loads(args.state_file.read_text(encoding='utf-8')))
    else:
        bridge = json.loads((args.root / 'runtime/bridge-config.json').read_text(encoding='utf-8'))
        client = CheckpointHTTP('http://127.0.0.1:' + str(bridge['port']), bridge['token'], timeout=5, checkpoint_wait=10)
        if args.execute_authorized_trial:
            result = Qualification(client, args.root, args.output, args.seconds, minimum_overlap_seconds=args.minimum_overlap_seconds).run(authorized=True)
            print(json.dumps({k:result.get(k) for k in ('status', 'qualified', 'work_qualified', 'voice_overlap_qualified', 'overlap')}));return 0 if result.get('qualified') is True else 1
        state = client('/state');report = preflight(state, client('/observer/state')['director']['running'], now=time.time())
    report.update(executed=False, mode='read_only_live' if args.inspect_live else 'offline')
    with args.output.open('x', encoding='utf-8') as output:json.dump(report, output, indent=2, allow_nan=False);output.write('\n')
    print(json.dumps({'executed': False, 'ready': report['ready'], 'gaps': report['gaps']}))
    return 0


if __name__ == '__main__':sys.exit(main())
