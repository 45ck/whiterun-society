import copy
import json
from pathlib import Path
import tempfile
import unittest
from director_policy import (load_director_policy, resolve_run_policy, validate_director_policy,
                             load_run_policy, validate_run_policy, write_run_policy)


class DirectorPolicyTests(unittest.TestCase):
    def test_default_modes_have_explicit_finite_call_and_time_budgets(self):
        sample=resolve_run_policy();play=resolve_run_policy('play')
        self.assertEqual((sample['max_events'],sample['watch_seconds'],sample['goal_budget'],sample['goal_review_seconds']),(6,600,192,5))
        self.assertEqual((play['max_events'],play['watch_seconds'],play['goal_budget'],play['goal_review_seconds']),(96,3600,768,5))
        self.assertEqual(len(sample['policy_sha256']),64)
        self.assertNotEqual(sample['run_policy_sha256'],play['run_policy_sha256'])

    def test_explicit_observation_only_cli_preserves_zero_events_and_time(self):
        result=resolve_run_policy(max_events=0,watch_seconds=0)
        self.assertEqual(result['max_events'],0);self.assertEqual(result['watch_seconds'],0)
        self.assertEqual(validate_run_policy(result,0,0),result)

    def test_policy_rejects_extra_missing_and_invalid_mode_fields(self):
        base=load_director_policy()
        for mutate in (lambda c:c.update(secret='not-allowed'),lambda c:c.pop('version'),
                       lambda c:c['modes'].update(other={}),lambda c:c['modes']['sample'].update(extra=1),
                       lambda c:c.update(version='x'*65)):
            config=copy.deepcopy(base);mutate(config)
            with self.assertRaises(ValueError):validate_director_policy(config)

    def test_numeric_policy_fields_are_strict_integers_with_protocol_caps(self):
        base=load_director_policy()
        for field,invalid in [('goal_budget',[True,0,4097,1.0,float('inf'),float('nan'),'192']),
                              ('goal_review_seconds',[False,0,61,5.0]),
                              ('maximum_events',[0,13]),('default_events',[0,13]),
                              ('watch_seconds',[0,601])]:
            for value in invalid:
                with self.subTest(field=field,value=value):
                    config=copy.deepcopy(base);config['modes']['sample'][field]=value
                    with self.assertRaises(ValueError):validate_director_policy(config)
        config=copy.deepcopy(base);config['modes']['play']['watch_seconds']=3601
        with self.assertRaises(ValueError):validate_director_policy(config)

    def test_resolved_limits_cannot_exceed_config_or_accept_bool(self):
        for kwargs in ({'mode':[]},{'mode':'forever'},{'max_events':True},{'max_events':13},
                       {'watch_seconds':601},{'watch_seconds':float('inf')},{'max_events':-1}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):resolve_run_policy(**kwargs)

    def test_snapshot_is_detached_from_config_and_hash_covers_actual_settings(self):
        config=load_director_policy();result=resolve_run_policy(config=config)
        config['modes']['sample']['goal_budget']=1
        self.assertEqual(result['policy_snapshot']['modes']['sample']['goal_budget'],192)
        changed=resolve_run_policy(max_events=2)
        self.assertEqual(result['policy_sha256'],changed['policy_sha256'])
        self.assertNotEqual(result['run_policy_sha256'],changed['run_policy_sha256'])

    def test_frozen_file_roundtrip_checks_cli_arguments_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'run.policy.json';value=resolve_run_policy(max_events=3)
            write_run_policy(path,value)
            self.assertEqual(load_run_policy(path,3,600),value)
            for events,seconds in [(2,600),(3,599),(True,600)]:
                with self.assertRaises(ValueError):load_run_policy(path,events,seconds)
            value['goal_budget']=193;path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):load_run_policy(path)

    def test_frozen_file_uses_its_snapshot_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'run.policy.json';value=resolve_run_policy()
            write_run_policy(path,value)
            with self.assertRaises(FileExistsError):write_run_policy(path,value)
            self.assertEqual(load_run_policy(path),value)

    def test_flattened_float_or_bool_cannot_use_integer_equality_to_bypass_hash(self):
        value=resolve_run_policy();value['goal_review_seconds']=5.0
        with self.assertRaises(ValueError):validate_run_policy(value)
        value=resolve_run_policy();value['policy_sha256']='0'*64
        with self.assertRaises(ValueError):validate_run_policy(value)

    def test_oversized_policy_file_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'large.json';path.write_text(' '*32769)
            with self.assertRaises(ValueError):load_director_policy(path)
