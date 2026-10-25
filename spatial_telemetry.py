"""Bounded, sampled native geometry. Displacement is not intent or a navmesh path.

No inference, inventory edits, inferred psychology, or offline progression.
The optional append log contains only observation-derived numeric evidence.
"""
from collections import Counter, deque
import copy
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median
import time


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def space_key(space):
    if not isinstance(space, dict):
        return None
    if space.get('interior') is False and type(space.get('world')) is int and space['world'] > 0:
        return ('world', space['world'])
    if type(space.get('cell')) is int and space['cell'] > 0 and type(space.get('interior')) is bool:
        return ('cell', space['cell'])
    return None


def ratio(numerator, denominator):
    return round(100 * numerator / denominator, 3) if denominator else None


def distribution(values):
    ordered = sorted(v for v in values if finite(v) and v >= 0)
    return {'n': len(ordered), 'median': round(median(ordered), 3) if ordered else None,
            'p95': round(ordered[max(0, math.ceil(.95 * len(ordered)) - 1)], 3) if ordered else None}


class SpatialTelemetry:
    def __init__(self, path=None, config=None):
        self.config = copy.deepcopy(config) if config is not None else json.loads(
            (Path(__file__).parent / 'config/spatial-metrics.json').read_text(encoding='utf-8'))
        c = self.config
        if not isinstance(c, dict) or type(c.get('version')) is not int or c['version'] < 1:
            raise ValueError('Spatial configuration needs a positive integer version')
        for key in ('sample_seconds', 'maximum_gap_seconds', 'window_seconds', 'maximum_samples',
                    'chart_points', 'position_jitter_units', 'maximum_speed_units_per_second',
                    'nearby_radius_units', 'log_rotation_bytes'):
            if not finite(c.get(key)) or c[key] <= 0:
                raise ValueError('Invalid spatial metric configuration: ' + key)
        if c['sample_seconds'] < 5 or c['maximum_gap_seconds'] < c['sample_seconds']:
            raise ValueError('Spatial sampling requires at least five seconds and a compatible gap')
        if any(type(c[key]) is not int for key in ('maximum_samples', 'chart_points', 'log_rotation_bytes')):
            raise ValueError('Spatial bounds must be integers')
        if c['maximum_samples'] > 10000 or c['chart_points'] > c['maximum_samples']:
            raise ValueError('Spatial sample bounds exceeded')
        targets = c.get('targets')
        if not isinstance(targets, list):
            raise ValueError('Spatial targets must be a list')
        ids = set()
        for goal in targets:
            if not isinstance(goal, dict):
                raise ValueError('Spatial target must be an object')
            identifier = goal.get('id')
            if (not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', identifier)
                    or identifier in ids):
                raise ValueError('Spatial target IDs must be valid unique strings')
            ids.add(identifier)
            if goal.get('direction') not in ('gte', 'lte'):
                raise ValueError('Spatial target direction must be gte or lte')
            if not finite(goal.get('target')) or not finite(goal.get('minimum_sample')) or goal['minimum_sample'] < 0:
                raise ValueError('Spatial target and nonnegative sample minimum must be finite numbers')
            for key in ('objective', 'measure', 'unit', 'scope'):
                if not isinstance(goal.get(key), str) or not goal[key].strip():
                    raise ValueError('Spatial target requires text: ' + key)
            for key in ('field', 'sample_field'):
                value = goal.get(key)
                if value is not None and (not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*', value)):
                    raise ValueError('Spatial target needs a valid metric path: ' + key)
            if 'field' not in goal or (goal['field'] is not None and goal['minimum_sample'] > 0 and goal.get('sample_field') is None):
                raise ValueError('Measured spatial target requires its field and sample denominator')
        # Canonical JSON binds reported measurements to startup thresholds and targets.
        self.config_sha256 = hashlib.sha256(json.dumps(c, sort_keys=True, separators=(',', ':'),
                                                      allow_nan=False).encode('utf-8')).hexdigest()
        self.path = Path(path) if path is not None else None
        self.frames = deque(maxlen=c['maximum_samples'])
        self.previous = None
        self.session = None
        self.segment = 0
        self.segment_reason = 'not_started'
        self.sequence = 0
        self.write_failures = 0
        self.stationary = {}
        self._cached = None

    def _new_segment(self, session, reason):
        self.session = session
        self.segment += 1
        self.segment_reason = reason
        self.frames.clear()
        self.previous = None
        self.stationary.clear()
        self._cached = None

    def observe(self, observation, society, now=None):
        """Accept at most one sample per configured interval; return new frame or None."""
        now = time.time() if now is None else now
        if not finite(now):
            raise ValueError('Finite observation time required')
        session = observation.get('session')
        if not isinstance(session, str) or not session or len(session) > 128:
            return None
        day, checkpoint = observation.get('gameDays'), observation.get('checkpoint')
        if session != self.session:
            self._new_segment(session, 'native_session_changed')
        p = self.previous
        if p and (now < p['at'] or (finite(day) and finite(p['game_day']) and day < p['game_day']) or
                  (type(checkpoint) is int and type(p['checkpoint']) is int and checkpoint < p['checkpoint'])):
            self._new_segment(session, 'clock_or_checkpoint_reversed')
            p = None
        if p and now - p['at'] < self.config['sample_seconds']:
            return None

        managed = (society.get('town') or {}).get('residents', {})
        people = society.get('people') or {}
        native = {a.get('actor'): a for a in (observation.get('resident_control') or {}).get('activities', [])}
        rows = {}
        for r in observation.get('residents', []):
            actor = r.get('id')
            if type(actor) is not int or str(actor) not in managed or r.get('isPerson') is not True:
                continue
            coords = [r.get(k) for k in ('x', 'y', 'z')]
            coords = coords if all(finite(v) for v in coords) else None
            a, person = native.get(actor, {}), people.get(str(actor), {})
            goal = person.get('standing_goal') or {}
            package = a.get('expectedPackage')
            owned = (a.get('ownedPackage') is True and type(package) is int and package > 0 and
                     (r.get('activity') or {}).get('package_id') == package)
            rows[actor] = {'position': coords, 'space': space_key(r.get('space')),
                'goal': goal.get('phase') in ('travelling', 'quiet', 'arrived'),
                'target': (goal.get('target') or {}).get('id'),
                'travel_intent': owned and a.get('mode') == 'go_to' and a.get('phase') == 'travelling'}

        dt = now - p['at'] if p else 0
        advancing = p is not None and finite(day) and finite(p['game_day']) and day > p['game_day']
        interval_ok = bool(p and advancing and dt <= self.config['maximum_gap_seconds'] and
                           observation.get('paused') is not True and observation.get('ready') is True and p['ready'])
        reasons = Counter()
        intervals = []
        # Previous/current union exposes unloads and incomplete geometry rather than calling them idle.
        candidates = set(rows) | set(p['rows'] if p else {})
        for actor in candidates:
            row, previous = rows.get(actor), (p['rows'].get(actor) if p else None)
            reason = ('initial_sample' if p is None else 'observation_gap' if dt > self.config['maximum_gap_seconds'] else
                      'paused_or_unobserved_clock' if not interval_ok else 'not_loaded_both_samples' if not row or not previous else
                      'invalid_geometry' if row['position'] is None or previous['position'] is None or row['space'] is None or previous['space'] is None else
                      'space_changed' if row['space'] != previous['space'] else None)
            if reason:
                reasons[reason] += 1
                self.stationary.pop(actor, None)
                continue
            distance = math.dist(row['position'], previous['position'])
            speed = distance / dt
            if speed > self.config['maximum_speed_units_per_second']:
                reasons['discontinuity_or_teleport'] += 1
                self.stationary.pop(actor, None)
                continue
            moving = distance > self.config['position_jitter_units']
            self.stationary[actor] = 0 if moving else self.stationary.get(actor, 0) + dt
            intervals.append({'actor': actor, 'seconds': dt, 'distance': round(distance, 3),
                'speed': round(speed, 3), 'moving': moving, 'travel_intent': row['travel_intent'],
                'stationary_seconds': self.stationary[actor]})

        valid = {a: r for a, r in rows.items() if r['position'] is not None and r['space'] is not None}
        pair_distances = [math.dist(a['position'], b['position']) for i, a in enumerate(valid.values())
                          for b in list(valid.values())[i + 1:] if a['space'] == b['space']]
        proximity = self._access(rows, society)
        targets = Counter(str(r['target']) for r in rows.values() if type(r['target']) is int and r['goal'])
        self.sequence += 1
        frame = {'at': now, 'session': session, 'segment': self.segment, 'sequence': self.sequence,
            'config_sha256': self.config_sha256,
            'checkpoint': checkpoint, 'game_day': day if finite(day) else None,
            'loaded': len(rows), 'with_goal': sum(r['goal'] for r in rows.values()),
            'observed_moving': sum(i['moving'] for i in intervals),
            'observed_stationary': sum(not i['moving'] for i in intervals),
            'travel_intentions': sum(r['travel_intent'] for r in rows.values()),
            'unmeasured_intervals': sum(reasons.values()), 'excluded': dict(reasons),
            'candidate_actor_seconds': dt * len(candidates) if p else 0,
            'intervals': intervals, 'rows': rows, 'targets': dict(targets),
            'close_pairs': sum(d <= self.config['nearby_radius_units'] for d in pair_distances),
            'comparable_pairs': len(pair_distances), 'proximity': proximity,
            'ready': observation.get('ready') is True and observation.get('paused') is not True}
        self.frames.append(frame)
        self._cached = None
        self.previous = frame
        while self.frames and now - self.frames[0]['at'] > self.config['window_seconds']:
            self.frames.popleft()
        self._write(frame)
        return copy.deepcopy(frame)

    def _access(self, rows, society):
        result = {}
        businesses = (society.get('town') or {}).get('businesses', {}).values()
        for label, capability in [('food_supplier', 'retail_food'), ('productive_enterprise', 'bread_recipe')]:
            suppliers = {b.get('custodian') for b in businesses if b.get('active', True) and capability in b.get('capabilities', [])}
            distances = []
            for actor, row in rows.items():
                if row['position'] is None or row['space'] is None:
                    continue
                choices = [math.dist(row['position'], rows[s]['position']) for s in suppliers if s != actor and s in rows and
                           rows[s]['position'] is not None and rows[s]['space'] == row['space']]
                if choices:
                    distances.append(min(choices))
            result[label] = {**distribution(distances), 'loaded_residents': len(rows), 'public_custodians': len(suppliers)}
        result['scope'] = '3D straight-line proximity to currently observed enterprise custodians, not fixed premises, reachable paths, stocked offers, affordability or available jobs.'
        return result

    def _write(self, frame):
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size >= self.config['log_rotation_bytes']:
                self.path.replace(self.path.with_suffix(self.path.suffix + '.previous'))
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(frame, allow_nan=False, separators=(',', ':')) + '\n')
        except (OSError, ValueError):
            self.write_failures += 1

    def status(self, session, now=None):
        now = time.time() if now is None else now
        if not finite(now):
            raise ValueError('Finite observation time required')
        frames = [f for f in self.frames if session == self.session and now - f['at'] <= self.config['window_seconds']]
        latest = frames[-1] if frames else None
        cache_key = (session, frames[0]['sequence'] if frames else None, latest['sequence'] if latest else None)
        if self._cached and self._cached[0] == cache_key:
            result = copy.deepcopy(self._cached[1])
            result['fresh'] = bool(latest and 0 <= now - latest['at'] <= self.config['maximum_gap_seconds'])
            return result
        intervals = [i for f in frames for i in f['intervals']]
        usable = sum(i['seconds'] for i in intervals)
        moving = sum(i['seconds'] for i in intervals if i['moving'])
        candidate = sum(f['candidate_actor_seconds'] for f in frames)
        loaded = sum(f['loaded'] for f in frames)
        by_actor = {}
        for i in intervals:
            row = by_actor.setdefault(i['actor'], {'actor': i['actor'], 'observed_seconds': 0, 'moving_seconds': 0, 'sampled_distance': 0})
            row['observed_seconds'] += i['seconds']
            row['moving_seconds'] += i['seconds'] if i['moving'] else 0
            row['sampled_distance'] += i['distance']
        for row in by_actor.values():
            row['moving_percent'] = ratio(row['moving_seconds'], row['observed_seconds'])
            row['sampled_distance'] = round(row['sampled_distance'], 3)
        excluded = Counter()
        for frame in frames:
            excluded.update(frame['excluded'])
        targets = latest['targets'] if latest else {}
        total_targets = sum(targets.values())
        result = {'version': self.config['version'], 'config_sha256': self.config_sha256,
            'session': session, 'segment': self.segment if frames else None,
            'segment_reason': self.segment_reason if frames else 'no_samples_for_session',
            'fresh': bool(latest and 0 <= now - latest['at'] <= self.config['maximum_gap_seconds']),
            'last_sample_at': latest['at'] if latest else None, 'sample_seconds': self.config['sample_seconds'],
            'samples': len(frames), 'window_seconds': self.config['window_seconds'],
            'observed_span_seconds': round(frames[-1]['at'] - frames[0]['at'], 3) if frames else 0,
            'coverage': {'candidate_actor_seconds': round(candidate, 3), 'usable_actor_seconds': round(usable, 3),
                'usable_percent': ratio(usable, candidate), 'loaded_resident_samples': loaded,
                'goal_percent': ratio(sum(f['with_goal'] for f in frames), loaded), 'excluded_intervals': dict(excluded)},
            'current': {k: latest[k] if latest else None for k in ('loaded', 'with_goal', 'observed_moving', 'observed_stationary', 'travel_intentions', 'unmeasured_intervals', 'close_pairs', 'comparable_pairs')},
            'movement': {'moving_actor_seconds': round(moving, 3), 'stationary_actor_seconds': round(usable - moving, 3),
                'moving_percent': ratio(moving, usable), 'sampled_distance_units': round(sum(i['distance'] for i in intervals), 3),
                'speed_units_per_second': distribution(i['speed'] for i in intervals),
                'current_stationary_seconds': distribution(i['stationary_seconds'] for i in (latest['intervals'] if latest else [])),
                'per_resident': list(by_actor.values())},
            'destinations': {'assigned_residents': total_targets, 'distinct_assigned_targets': len(targets),
                'assignment_histogram': targets, 'largest_target_share_percent': ratio(max(targets.values(), default=0), total_targets),
                'scope': 'Current personal target assignments; not visits, independent behavioural mechanisms or demand.'},
            'proximity': latest['proximity'] if latest else {},
            'chart': [{k: f[k] for k in ('at', 'loaded', 'with_goal', 'observed_moving', 'observed_stationary', 'travel_intentions', 'unmeasured_intervals')} for f in frames[-self.config['chart_points']:]],
            'write_failures': self.write_failures,
            'scope': 'Current native session and monotonic save segment only. Sampled 3D displacement in game units; no offline, paused-clock, cross-space or teleport time counted as stationary. Stationary includes legitimate conversation, work and rest. Travel intention is not observed movement; neither proves human realism.'}
        result['quality_goals'] = self._goals(result)
        self._cached = (cache_key, copy.deepcopy(result))
        return result

    def _goals(self, result):
        def get(path):
            value = result
            for key in (path or '').split('.'):
                value = value.get(key) if isinstance(value, dict) else None
            return value
        items = []
        for goal in self.config.get('targets', []):
            value = get(goal.get('field'))
            n = get(goal.get('sample_field'))
            value = value if finite(value) else None
            n = n if finite(n) and n >= 0 else None
            status = ('unmeasured' if value is None else 'insufficient_sample' if (n or 0) < goal['minimum_sample'] else
                      'met' if (value >= goal['target'] if goal['direction'] == 'gte' else value <= goal['target']) else 'below_target')
            items.append({**goal, 'current': value, 'n': n, 'status': status})
        return {'version': self.config['version'], 'config_sha256': self.config_sha256,
                'source': 'Authored engineering targets, not validated human or city norms', 'items': items}
