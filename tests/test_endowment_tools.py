import copy
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from catalog_fixture import native_catalog
from resource_manifest import load_manifest, manifest_hash, select_grant
from server import begin_endowment_event
from tools import endow_population as one, endow_town as town


class EndowmentToolTests(unittest.TestCase):
    def setUp(self):
        self.manifest=load_manifest();self.digest=manifest_hash(self.manifest)
        self.state={'bridge':{'last_seen':time.time(),'session':'session-a','observation':{
            'economy_catalog':native_catalog(),'resource_import':{'available':True,'protocol':2,'epoch':'epoch-a',
                'catalog_hash':self.manifest['catalog_hash'],'manifest_hash':self.digest},
            'residents':[{'id':7,'baseId':17,'isPerson':True,'inventory':{'gold':0,'bread':0,'grain':0}}]}},
            'society':{'checkpoint':4,'town':{'residents':{'7':{}},'resource_program':None}}}
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.runtime=Path(self.temp.name)

    def delivered(self):
        result=copy.deepcopy(self.state)
        record={'id':'grant-7','status':'committed','command':{'protocol':2,'phase':'deliver',
            'source':self.manifest['id'],'manifest_hash':self.digest,'catalog_hash':self.manifest['catalog_hash'],**select_grant(self.manifest,7,17),'actor':7,'actor_base_id':17,'grant_id':'grant-7'}}
        result['society']['checkpoint']=6
        result['society']['town']['resource_program']={'protocol':2,'id':self.manifest['id'],
            'manifest_hash':self.digest,'grants':{'7':record}}
        return result

    def test_route_requires_exact_explicit_selection_without_mutating_on_bad_payload(self):
        world=Mock();data={'actor':7,'scenario_id':self.manifest['id'],'scenario_hash':self.digest}
        for bad in ({'actor':7},{**data,'manifest':self.manifest},{**data,'actor':True},
                    {**data,'scenario_hash':'wrong'},{**data,'scenario_id':None}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):begin_endowment_event(world,{},bad)
        world.plan_endowment.assert_not_called()
        begin_endowment_event(world,{'proof':'native'},data)
        world.plan_endowment.assert_called_once_with(7,{'proof':'native'},self.manifest['id'],self.digest)

    def test_cli_requires_scenario_before_any_io(self):
        with patch('sys.stderr',new=io.StringIO()):
            for cli,args in ((one,['--root','missing','--actor','7']),(town,['--root','missing'])):
                with self.assertRaises(SystemExit):cli.main(args)

    def test_exact_selected_payload_one_write_and_retained_receipt(self):
        client=Mock(side_effect=[self.state,{'grant_id':'grant-7','checkpoint':5},self.delivered()])
        with patch('sys.stdout',new=io.StringIO()):result=one.deliver(client,self.manifest,7,self.runtime)
        self.assertEqual(result['status'],'committed');self.assertEqual(result['request_checkpoint'],4)
        self.assertEqual(result['request_session'],'session-a')
        self.assertEqual(client.call_args_list[1].args,('/town/endow',{'actor':7,'scenario_id':self.manifest['id'],'scenario_hash':self.digest}))
        evidence=json.loads(next(self.runtime.glob('*.json')).read_text())
        self.assertEqual(evidence['receipt']['id'],'grant-7');self.assertEqual(evidence['scenario'],self.manifest)

    def test_unknown_post_failure_is_not_replayed_and_evidence_is_held(self):
        client=Mock(side_effect=[self.state,TimeoutError('unknown request result')])
        with patch('sys.stdout',new=io.StringIO()),self.assertRaises(TimeoutError):one.deliver(client,self.manifest,7,self.runtime)
        self.assertEqual(client.call_count,2)
        self.assertEqual(json.loads(next(self.runtime.glob('*.json')).read_text())['status'],'held')

    def test_timeout_after_admission_never_resubmits(self):
        client=Mock(side_effect=[self.state,{'grant_id':'grant-7'}])
        with patch('sys.stdout',new=io.StringIO()),self.assertRaises(TimeoutError):one.deliver(client,self.manifest,7,self.runtime,wait_seconds=0)
        self.assertEqual(client.call_count,2)

    def test_legacy_changed_program_missing_capability_or_identity_never_posts(self):
        cases=[]
        for program in ({'id':'old','grants':{}},{'protocol':2,'id':'other','manifest_hash':self.digest}):
            state=copy.deepcopy(self.state);state['society']['town']['resource_program']=program;cases.append(state)
        state=copy.deepcopy(self.state);del state['bridge']['observation']['resource_import'];cases.append(state)
        state=copy.deepcopy(self.state);del state['bridge']['observation']['residents'][0]['baseId'];cases.append(state)
        state=copy.deepcopy(self.state);del state['bridge']['observation']['economy_catalog'];cases.append(state)
        for state in cases:
            client=Mock(return_value=state)
            with self.subTest(state=state),self.assertRaises(ValueError):one.deliver(client,self.manifest,7,self.runtime)
            client.assert_called_once_with('/state')

    def test_mismatched_receipt_and_session_cannot_report_success(self):
        for field,value in (('actor_base_id',99),('grant_id','different'),('manifest_hash','0'*64),('grant',{'gold':999}),('grant_hash','0'*64),('catalog_hash','old')):
            state=self.delivered();state['society']['town']['resource_program']['grants']['7']['command'][field]=value
            with self.assertRaises(ValueError):one.matching_receipt(state,self.manifest,7,17,{'grant_id':'grant-7'})
        state=self.delivered();state['bridge']['session']='new-session'
        client=Mock(side_effect=[self.state,{'grant_id':'grant-7'},state])
        with patch('sys.stdout',new=io.StringIO()),self.assertRaisesRegex(ValueError,'session changed'):one.deliver(client,self.manifest,7,self.runtime)

    def test_batch_freezes_targets_and_manifest_while_reusing_one_client(self):
        changed=copy.deepcopy(self.state);changed['society']['town']['residents']['8']={}
        client=Mock(side_effect=[self.state,changed,changed])
        with patch.object(town,'deliver',return_value={'status':'committed','receipt':{'id':'grant-7'}}) as delivery,patch('sys.stdout',new=io.StringIO()):
            result=town.run_batch(client,self.manifest,self.runtime)
        self.assertEqual(result['targets'],[7]);self.assertEqual(result['scenario_hash'],self.digest)
        delivery.assert_called_once_with(client,self.manifest,7,self.runtime)

    def test_batch_changed_session_or_base_stops_before_delivery(self):
        for change in ('session','base'):
            state=copy.deepcopy(self.state)
            if change=='session':state['bridge']['session']='other'
            else:state['bridge']['observation']['residents'][0]['baseId']=18
            client=Mock(side_effect=[self.state,state])
            with patch.object(town,'deliver') as delivery,patch('sys.stdout',new=io.StringIO()),self.assertRaises(ValueError):
                town.run_batch(client,self.manifest,self.runtime)
            delivery.assert_not_called()

    def test_same_scenario_duplicate_receipt_is_read_without_a_second_delivery(self):
        state=self.delivered();receipt=state['society']['town']['resource_program']['grants']['7']
        client=Mock(side_effect=[state,{'duplicate':True,'grant':receipt},state])
        with patch('sys.stdout',new=io.StringIO()):result=one.deliver(client,self.manifest,7,self.runtime)
        self.assertEqual(result['status'],'duplicate');self.assertEqual(client.call_count,3)


if __name__=='__main__':unittest.main()
