import copy
import json
from pathlib import Path
import tempfile
import unittest

from spatial_telemetry import SpatialTelemetry, space_key


def resident(actor, x=0, **changes):
    return {'id': actor, 'isPerson': True, 'x': x, 'y': 0, 'z': 0,
            'space': {'cell': 100, 'interior': False, 'world': 1},
            'activity': {'package_id': 10}, **changes}


def observation(day=1, rows=None, **changes):
    return {'session': 'game-a', 'checkpoint': 10, 'gameDays': day, 'ready': True,
            'residents': rows if rows is not None else [resident(1), resident(2, 100)], **changes}


def society():
    return {'town': {'residents': {'1': {}, '2': {}}, 'businesses': {}},
            'people': {'1': {'standing_goal': {'phase': 'travelling', 'target': {'id': 500}}},
                       '2': {'standing_goal': {'phase': 'quiet'}}}}


class SpatialTelemetryTests(unittest.TestCase):
    def test_displacement_and_intention_are_separate(self):
        t = SpatialTelemetry(); s = society()
        t.observe(observation(), s, now=0)
        native = {'activities': [{'actor': 1, 'mode': 'go_to', 'phase': 'travelling', 'ownedPackage': True, 'expectedPackage': 10}]}
        t.observe(observation(1.001, [resident(1), resident(2, 200)], resident_control=native), s, now=5)
        m = t.status('game-a', now=5)
        self.assertEqual(m['current']['observed_moving'], 1)
        self.assertEqual(m['current']['travel_intentions'], 1)
        self.assertEqual(m['movement']['moving_percent'], 50)
        self.assertEqual(m['movement']['per_resident'][0]['moving_percent'], 0)
        self.assertEqual(m['coverage']['usable_actor_seconds'], 10)
        self.assertEqual(m['destinations']['distinct_assigned_targets'], 1)

    def test_paused_clock_and_long_gaps_never_become_idle_time(self):
        t = SpatialTelemetry(); s = society()
        t.observe(observation(), s, now=0)
        t.observe(observation(), s, now=5)
        t.observe(observation(1.001), s, now=30)
        m = t.status('game-a', now=30)
        self.assertIsNone(m['movement']['moving_percent'])
        self.assertEqual(m['movement']['stationary_actor_seconds'], 0)
        self.assertEqual(m['coverage']['excluded_intervals']['paused_or_unobserved_clock'], 2)
        self.assertEqual(m['coverage']['excluded_intervals']['observation_gap'], 2)

    def test_missing_actor_invalid_geometry_and_teleport_are_unknown(self):
        t = SpatialTelemetry(); s = society()
        t.observe(observation(), s, now=0)
        t.observe(observation(1.001, [resident(1, float('nan'))]), s, now=5)
        self.assertEqual(t.status('game-a', now=5)['current']['unmeasured_intervals'], 2)
        t.observe(observation(1.002), s, now=10)
        t.observe(observation(1.003, [resident(1, 100000), resident(2, 100)]), s, now=15)
        m = t.status('game-a', now=15)
        self.assertEqual(m['current']['observed_stationary'], 1)
        self.assertEqual(m['coverage']['excluded_intervals']['discontinuity_or_teleport'], 1)
        self.assertEqual(m['movement']['sampled_distance_units'], 0)

    def test_space_identity_requires_observed_world_or_cell(self):
        self.assertIsNone(space_key(None))
        self.assertIsNone(space_key({'cell': 1}))
        self.assertEqual(space_key({'cell': 5, 'interior': False, 'world': 1}), ('world', 1))
        t = SpatialTelemetry(); s = society()
        t.observe(observation(), s, now=0)
        changed = resident(1, 100, space={'cell': 7, 'interior': True, 'world': None})
        t.observe(observation(1.001, [changed, resident(2)]), s, now=5)
        m = t.status('game-a', now=5)
        self.assertEqual(m['coverage']['excluded_intervals']['space_changed'], 1)
        self.assertEqual(m['current']['comparable_pairs'], 0)

    def test_session_checkpoint_and_clock_reversals_reset_history(self):
        for change in ({'session': 'game-b'}, {'checkpoint': 9}, {'gameDays': .5}):
            with self.subTest(change=change):
                t = SpatialTelemetry(); s = society()
                t.observe(observation(), s, now=0)
                t.observe(observation(1.001), s, now=5)
                obs = observation(1.002, **change) if 'gameDays' not in change else observation(.5)
                t.observe(obs, s, now=10)
                m = t.status(obs['session'], now=10)
                self.assertEqual(m['samples'], 1)
                self.assertEqual(m['movement']['stationary_actor_seconds'], 0)
                self.assertEqual(m['segment'], 2)

    def test_sampling_and_retention_are_bounded(self):
        config = copy.deepcopy(SpatialTelemetry().config)
        config.update(maximum_samples=3, chart_points=2)
        t = SpatialTelemetry(config=config); s = society()
        for i in range(10):
            t.observe(observation(1 + i * .001), s, now=i * 5)
            self.assertIsNone(t.observe(observation(1 + i * .001), s, now=i * 5 + 1))
        m = t.status('game-a', now=45)
        self.assertEqual(m['samples'], 3)
        self.assertEqual(len(m['chart']), 2)
        self.assertFalse(t.status('game-a', now=61)['fresh'])
        self.assertEqual(t.status('other-game', now=45)['samples'], 0)
        config['sample_seconds'] = 1
        with self.assertRaises(ValueError):
            SpatialTelemetry(config=config)

    def test_proximity_is_not_path_access_and_uses_dynamic_enterprises(self):
        t = SpatialTelemetry(); s = society()
        s['town']['businesses'] = {'dynamic-shop': {'custodian': 2, 'capabilities': ['retail_food'], 'active': True}}
        t.observe(observation(), s, now=0)
        m = t.status('game-a', now=0)
        self.assertEqual(m['proximity']['food_supplier']['n'], 1)
        self.assertEqual(m['proximity']['food_supplier']['median'], 100)
        self.assertEqual(m['proximity']['productive_enterprise']['n'], 0)
        self.assertEqual(next(g for g in m['quality_goals']['items'] if g['id'] == 'SPA-03')['status'], 'unmeasured')
        s['town']['businesses']['dynamic-shop']['active'] = False
        t.observe(observation(1.001), s, now=5)
        self.assertEqual(t.status('game-a', now=5)['proximity']['food_supplier']['n'], 0)

    def test_local_log_is_numeric_evidence_without_personal_prompts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'spatial.jsonl'
            t = SpatialTelemetry(path=path); s = society()
            s['people']['1']['memories'] = [{'private': 'do not log this'}]
            obs = observation(); obs['token'] = 'do not log token'
            t.observe(obs, s, now=0)
            line = path.read_text()
            self.assertNotIn('do not log', line)
            self.assertEqual(json.loads(line)['rows']['1']['position'], [0, 0, 0])
            self.assertEqual(t.write_failures, 0)

    def test_rotation_and_write_failures_do_not_halt_simulation(self):
        with tempfile.TemporaryDirectory() as folder:
            config = copy.deepcopy(SpatialTelemetry().config)
            config['log_rotation_bytes'] = 1
            path = Path(folder) / 'spatial.jsonl'
            t = SpatialTelemetry(path=path, config=config)
            t.observe(observation(), society(), now=0)
            t.observe(observation(1.001), society(), now=5)
            self.assertTrue(path.with_suffix('.jsonl.previous').is_file())
            invalid = SpatialTelemetry(path=Path(folder))
            invalid.observe(observation(), society(), now=0)
            self.assertEqual(invalid.write_failures, 1)

    def test_current_stationary_timer_resets_on_unknown_interval(self):
        t = SpatialTelemetry(); s = society()
        for i in range(3):
            t.observe(observation(1 + i * .001), s, now=i * 5)
        self.assertEqual(t.status('game-a', now=10)['movement']['current_stationary_seconds']['median'], 10)
        t.observe(observation(1.002), s, now=15)
        t.observe(observation(1.003), s, now=20)
        self.assertEqual(t.status('game-a', now=20)['movement']['current_stationary_seconds']['median'], 5)

    def test_configured_targets_require_minimum_samples(self):
        t = SpatialTelemetry(); t.observe(observation(), society(), now=0)
        items = {g['id']: g for g in t.status('game-a', now=0)['quality_goals']['items']}
        self.assertEqual(items['SPA-01']['status'], 'unmeasured')
        self.assertEqual(items['SPA-02']['status'], 'insufficient_sample')

    def test_unmanaged_rows_and_stale_package_intentions_are_not_counted(self):
        t = SpatialTelemetry(); s = society()
        rows = [resident(1), resident(2), resident(999)]
        native = {'activities': [{'actor': 1, 'mode': 'go_to', 'phase': 'travelling',
                                 'ownedPackage': True, 'expectedPackage': 999}]}
        t.observe(observation(rows=rows, resident_control=native), s, now=0)
        m = t.status('game-a', now=0)
        self.assertEqual(m['current']['loaded'], 2)
        self.assertEqual(m['current']['travel_intentions'], 0)
        t.observe(observation(1.001, paused=True), s, now=5)
        self.assertEqual(t.status('game-a', now=5)['movement']['stationary_actor_seconds'], 0)

    def test_cached_status_does_not_share_mutable_results_and_expires(self):
        t = SpatialTelemetry(); t.observe(observation(), society(), now=0)
        first = t.status('game-a', now=0)
        first['chart'].clear()
        self.assertEqual(len(t.status('game-a', now=5)['chart']), 1)
        self.assertFalse(t.status('game-a', now=16)['fresh'])
        self.assertEqual(t.status('game-a', now=3601)['samples'], 0)

    def test_invalid_target_catalog_is_rejected_before_observation(self):
        base = SpatialTelemetry().config
        mutations = [
            {'target': float('nan')}, {'target': float('inf')}, {'target': True},
            {'minimum_sample': -1}, {'minimum_sample': float('inf')}, {'minimum_sample': False},
            {'direction': 'approximately'}, {'id': ''}, {'id': 4}, {'field': []},
            {'sample_field': None}, {'measure': ''}, {'unit': None}]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                config = copy.deepcopy(base); config['targets'][0].update(mutation)
                with self.assertRaises(ValueError):
                    SpatialTelemetry(config=config)
        for bad_targets in ([{}], [None], {}, [base['targets'][0], base['targets'][0]]):
            config = copy.deepcopy(base); config['targets'] = bad_targets
            with self.assertRaises(ValueError):
                SpatialTelemetry(config=config)

    def test_config_hash_binds_status_and_trace_to_thresholds(self):
        t = SpatialTelemetry(); config = copy.deepcopy(t.config)
        reordered = dict(reversed(list(config.items())))
        self.assertEqual(t.config_sha256, SpatialTelemetry(config=reordered).config_sha256)
        config['position_jitter_units'] += 1
        self.assertNotEqual(t.config_sha256, SpatialTelemetry(config=config).config_sha256)
        frame = t.observe(observation(), society(), now=0)
        status = t.status('game-a', now=0)
        self.assertRegex(status['config_sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(status['config_sha256'], frame['config_sha256'])
        self.assertEqual(status['config_sha256'], status['quality_goals']['config_sha256'])

    def test_all_excluded_intervals_leave_movement_unknown(self):
        t = SpatialTelemetry(); s = society()
        t.observe(observation(), s, now=0)
        t.observe(observation(), s, now=5)
        m = t.status('game-a', now=5)
        self.assertTrue(m['fresh'])
        self.assertEqual(m['coverage']['usable_percent'], 0)
        self.assertEqual(m['coverage']['usable_actor_seconds'], 0)
        self.assertIsNone(m['movement']['moving_percent'])
        self.assertEqual(m['movement']['speed_units_per_second'], {'n': 0, 'median': None, 'p95': None})
        self.assertEqual(m['current']['observed_stationary'], 0)
        self.assertEqual(m['current']['unmeasured_intervals'], 2)
        self.assertTrue(all(g['status'] != 'met' for g in m['quality_goals']['items']))

    def test_nonnumeric_metric_path_never_passes_a_target(self):
        config = copy.deepcopy(SpatialTelemetry().config)
        config['targets'][0].update(field='fresh', minimum_sample=0)
        t = SpatialTelemetry(config=config); t.observe(observation(), society(), now=0)
        target = t.status('game-a', now=0)['quality_goals']['items'][0]
        self.assertIsNone(target['current'])
        self.assertEqual(target['status'], 'unmeasured')


if __name__ == '__main__':
    unittest.main()
