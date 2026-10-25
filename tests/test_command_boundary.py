"""Offline operator command boundary; no native commands are dispatched."""
import copy
import io
from pathlib import Path
import runpy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from server import authored_walk_command


class CommandBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.world=SimpleNamespace(active={'people':{'7001':{},'8002':{}},'pending':None},
            marker=9,session='test',_agency_guard=Mock())
        self.obs={'session':'test','checkpoint':9,'routing':{'available':True,'adapter':'papyrus-mailbox-v1'},
            'residents':[{'id':7001,'isPerson':True},{'id':8002,'isPerson':True}]}
        self.data={'kind':'walk_to','actor':7001,'target':8002}

    def command(self,data=None):
        return authored_walk_command(self.world,self.obs,self.data if data is None else data,'test','operator-1')

    def test_arbitrary_initialized_residents_use_current_bound_mailbox(self):
        before=copy.deepcopy((self.world.active,self.obs,self.data))
        self.assertEqual(self.command(),{'id':'operator-1','kind':'walk_to','actor':7001,'target':8002,
            'method':'package','dynamic':True,'origin':'operator_request','session':'test','checkpoint':9})
        self.world._agency_guard.assert_called_once_with(self.obs)
        self.assertEqual((self.world.active,self.obs,self.data),before)

    def test_missing_invalid_or_uninitialized_identity_does_not_select_demo_actor(self):
        for key in ('actor','target'):
            for value in (None,True,'7001',7001.0,0,-1,0x100000000,108186):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    self.command({**self.data,key:value})
            with self.assertRaises(ValueError):self.command({k:v for k,v in self.data.items() if k!=key})
        with self.assertRaises(ValueError):self.command({**self.data,'target':7001})

    def test_legacy_methods_or_false_dynamic_are_rejected(self):
        for change in ({'method':'path'},{'method':'offset'},{'dynamic':False},{'dynamic':1}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.command({**self.data,**change})

    def test_unavailable_unknown_or_stale_native_route_is_rejected(self):
        for capability in (None,{}, {'available':False,'adapter':'papyrus-mailbox-v1'},
                {'available':True,'adapter':'fixed'}, {'available':True,'adapter':'papyrus-mailbox-v1','session':'old'}):
            self.obs['routing']=capability
            with self.subTest(capability=capability),self.assertRaises(ValueError):self.command()

    def test_missing_person_and_actor_lease_are_rejected(self):
        self.obs['residents'][1].pop('isPerson')
        with self.assertRaises(ValueError):self.command()
        self.obs['residents'][1]['isPerson']=True
        self.world.active['activity_jobs']={'job':{'actor':7001,'target':42,'slot':0,'phase':'running'}}
        with self.assertRaises(ValueError):self.command()

    def test_changed_session_and_world_guard_block_admission(self):
        with self.assertRaises(ValueError):authored_walk_command(self.world,self.obs,self.data,'old','one')
        self.world._agency_guard.side_effect=ValueError('Checkpoint unsettled')
        with self.assertRaisesRegex(ValueError,'Checkpoint unsettled'):self.command()

    def test_probe_missing_identity_and_legacy_method_fail_before_runtime_reads(self):
        script=Path(__file__).resolve().parents[1]/'tools/probe_movement.py'
        for arguments in ([],['--actor','7001'],['--target','8002'],
                ['--actor','7001','--target','8002','--method','path']):
            with self.subTest(arguments=arguments),patch('sys.argv',[str(script),*arguments]),\
                    patch('sys.stderr',new_callable=io.StringIO),patch.object(Path,'read_text') as read:
                with self.assertRaises(SystemExit) as error:runpy.run_path(str(script),run_name='__main__')
                self.assertEqual(error.exception.code,2)
                read.assert_not_called()
