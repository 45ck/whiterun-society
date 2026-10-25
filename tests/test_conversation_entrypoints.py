"""Explicit authored admission cannot be reached through ordinary worker defaults."""
import copy
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from server import begin_conversation_event
from tools.run_conversation import load_scenario, main


SCENARIO={'version':1,'id':'two-residents','participants':[501,502], 'max_turns':2,
          'provenance':'Authored offline demonstration fixture; not a spontaneous encounter'}


class ConversationEndpointTests(unittest.TestCase):
    def test_ordinary_endpoint_preserves_omitted_actor_without_authoring_a_pair(self):
        world=Mock();observation={'residents':[]}
        begin_conversation_event(world,observation,{'id':'ordinary'})
        world.start_conversation.assert_called_once_with('ordinary',observation,None,None,None,'combined_choice')
        world.start_scenario_conversation.assert_not_called()

    def test_explicit_endpoint_passes_definition_to_engine_as_separate_admission(self):
        world=Mock();observation={'residents':[]};definition=copy.deepcopy(SCENARIO)
        begin_conversation_event(world,observation,{'id':'demo','scenario':definition},scenario=True)
        world.start_scenario_conversation.assert_called_once_with('demo',observation,definition,reply_policy='separate_choice')
        world.start_conversation.assert_not_called()
        self.assertEqual(definition,SCENARIO)

    def test_cross_mode_and_command_fields_are_rejected_before_engine_dispatch(self):
        cases=[(False,{'scenario':SCENARIO}),(False,{'participants':[501,502]}),
               (True,{'scenario':SCENARIO,'actor':501}),(True,{'scenario':SCENARIO,'opportunity_batch':'batch'}),
               (True,{'scenario':SCENARIO,'max_turns':6}),(True,{'scenario':SCENARIO,'command':{'kind':'walk_to'}}),
               (True,{})]
        for scenario,extra in cases:
            with self.subTest(scenario=scenario,extra=extra):
                world=Mock()
                with self.assertRaises(ValueError):begin_conversation_event(world,{},dict(id='event',**extra),scenario=scenario)
                world.start_conversation.assert_not_called();world.start_scenario_conversation.assert_not_called()

    def test_engine_census_rejection_propagates_without_falling_back_to_scenario(self):
        world=Mock();world.start_conversation.side_effect=ValueError('Initialize the population census first')
        with self.assertRaisesRegex(ValueError,'census'):begin_conversation_event(world,{}, {'id':'ordinary'})
        world.start_scenario_conversation.assert_not_called()


class ConversationScenarioCLITests(unittest.TestCase):
    def fixture(self,root):
        runtime=root/'runtime';runtime.mkdir()
        (runtime/'bridge-config.json').write_text(json.dumps({'port':12345,'token':'offline-placeholder'}))
        config=runtime/'models.json';config.write_text(json.dumps({'key_file':str(root/'must-not-read-secret')}))
        argv=['worker','--root',str(root),'--id','event','--language-config',str(config),'--decision-config',str(config)]
        return argv

    def test_explicit_file_dispatches_scenario_and_duplicate_never_reads_credentials_or_calls_models(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);argv=self.fixture(root);source=root/'scene.json';source.write_text(json.dumps(SCENARIO))
            routes=[]
            def request(route,data=None):
                routes.append((route,data))
                if route=='/state':return {'bridge':{'last_seen':time.time()},'society':{'error':None,'transition':None}}
                self.assertEqual(route,'/conversation/scenario');self.assertEqual(data['scenario'],SCENARIO)
                return {'duplicate':True,'conversation':{'phase':'complete'}}
            with patch('sys.argv',argv+['--scenario',str(source)]),patch('tools.run_conversation.CheckpointHTTP',return_value=request),\
                 patch('tools.run_conversation.infer') as infer,patch('tools.run_conversation.propose') as propose,\
                 patch('tools.run_conversation.VoiceWorker') as voice,patch('builtins.print'):
                main();infer.assert_not_called();propose.assert_not_called();voice.assert_not_called()
            self.assertEqual([r for r,_ in routes],['/state','/conversation/scenario'])

    def test_normal_worker_without_census_fails_before_credentials_voice_or_inference(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);argv=self.fixture(root);routes=[]
            def request(route,data=None):
                routes.append(route)
                if route=='/state':return {'bridge':{'last_seen':time.time()},'society':{'error':None,'transition':None}}
                self.assertEqual(route,'/conversation/start');self.assertNotIn('scenario',data);self.assertNotIn('actor',data)
                raise ValueError('Initialize the population census before ordinary conversation')
            # An available file must never be discovered or selected implicitly.
            (root/'scenario.json').write_text(json.dumps(SCENARIO))
            with patch('sys.argv',argv),patch('tools.run_conversation.CheckpointHTTP',return_value=request),\
                 patch('tools.run_conversation.infer') as infer,patch('tools.run_conversation.propose') as propose,\
                 patch('tools.run_conversation.VoiceWorker') as voice:
                with self.assertRaisesRegex(ValueError,'census'):main()
                infer.assert_not_called();propose.assert_not_called();voice.assert_not_called()
            self.assertEqual(routes,['/state','/conversation/start'])

    def test_scenario_conflicts_fail_before_files_or_bridge_access(self):
        for option in (['--actor','501'],['--opportunity-batch','batch'],['--max-turns','4']):
            argv=['worker','--root','missing','--id','event','--language-config','missing','--decision-config','missing',
                  '--scenario','missing-scene',*option]
            with self.subTest(option=option),patch('sys.argv',argv),patch('sys.stderr',io.StringIO()),\
                 patch('tools.run_conversation.CheckpointHTTP') as client:
                with self.assertRaises(SystemExit):main()
                client.assert_not_called()

    def test_post_admission_credential_failure_holds_the_started_event(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);argv=self.fixture(root);routes=[]
            def request(route,data=None):
                routes.append(route)
                if route=='/state':return {'bridge':{'last_seen':time.time()},'society':{'error':None,'transition':None}}
                if route=='/conversation/start':return {'conversation':{'id':'event','phase':'choose_partner'}}
                self.assertEqual(route,'/conversation/hold');self.assertEqual(data['id'],'event');return {}
            with patch('sys.argv',argv),patch('tools.run_conversation.CheckpointHTTP',return_value=request),\
                 patch('tools.run_conversation.infer') as infer,patch('tools.run_conversation.propose') as propose,\
                 patch('tools.run_conversation.VoiceWorker') as voice:
                with self.assertRaises(FileNotFoundError):main()
                infer.assert_not_called();propose.assert_not_called();voice.assert_not_called()
            self.assertEqual(routes,['/state','/conversation/start','/conversation/hold'])
            receipt=json.loads(next((root/'runtime').glob('conversation-*.json')).read_text())
            self.assertEqual(receipt['status'],'held');self.assertEqual(sum(receipt['calls'].values()),0)

    def test_file_size_shape_duplicate_keys_and_native_injection_are_rejected(self):
        invalid=[' '*16385,'[]','{"version":1,"version":1}',
                 json.dumps(dict(SCENARIO,command={'kind':'inventory_trade'})),
                 json.dumps(dict(SCENARIO,participants=[501,501]))]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'scenario.json'
            for content in invalid:
                with self.subTest(content=content[:60]):
                    path.write_text(content)
                    with self.assertRaises(ValueError):load_scenario(path)


if __name__=='__main__':unittest.main()
