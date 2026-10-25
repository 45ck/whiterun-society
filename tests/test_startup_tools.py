"""Mocked loopback only: startup intent never crosses a changed save boundary."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
from tools.checkpoint_http import CheckpointHTTP
from tools.initialize_population import initialize,parser as census_parser
from tools.configure_enterprise import configure,parser as enterprise_parser
from tools.apply_livelihood_background import apply_background,parser as background_parser
from tools.startup_checkpoint import definition_hash
from livelihood_backgrounds import load_livelihood_manifest,livelihood_manifest_hash,preview_livelihood_background


def state(marker=1,session='test-save'):
    actors=[{'id':actor,'baseId':actor+100,'name':'Observed resident '+str(actor),'isPerson':True,
             'inventory':{'gold':10,'bread':2,'grain':3}} for actor in (7,9)]
    bindings={str(row['id']):{'id':row['id'],'identity_binding':{
        'schema_version':1,'actor':row['id'],'base_id':row['baseId'],'event_id':'prior-census'}} for row in actors}
    return {'bridge':{'session':session,'last_seen':100,'observation':{
        'session':session,'checkpoint':marker,'ready':True,'gameDays':1,'residents':actors}},
        'society':{'checkpoint':marker,'transition':None,'error':None,'people':{'7':{},'9':{}},
            'town':{'seed':'explicit-seed','residents':bindings,'businesses':{},'enterprise_events':[],
                    'census_events':[],'livelihood_backgrounds':[]}}}


SPEC={'id':'foundry-shop','name':'Authored shop','custodian':7,'capabilities':['retail_goods'],
      'sale_commodities':['grain'],'active':True,'expected_revision':0}


class StartupToolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.runtime=Path(self.temp.name)
        clock=patch('tools.startup_checkpoint.time.time',return_value=100.);clock.start();self.addCleanup(clock.stop)
        self.calls=[]

    def transport(self,replies):
        pending=list(replies)
        def open_(request,**kwargs):
            self.calls.append(request)
            if not pending:raise AssertionError('Unexpected HTTP call')
            value=pending.pop(0)
            if isinstance(value,Exception):raise value
            if callable(value):value=value(request)
            return io.BytesIO(json.dumps(value).encode())
        mocked=patch('tools.checkpoint_http.urllib.request.urlopen',side_effect=open_)
        mocked.start();self.addCleanup(mocked.stop)
        return CheckpointHTTP('http://127.0.0.1:1234','fixture-token')

    def writes(self):return [call for call in self.calls if call.get_method()=='POST']

    def test_every_cli_defaults_to_preview_and_background_requires_explicit_cohort(self):
        self.assertFalse(census_parser().parse_args(['--root','lab','--id','c','--seed','s']).apply)
        self.assertFalse(enterprise_parser().parse_args(['--runtime','lab','--id','e','--spec','s.json']).apply)
        args=background_parser().parse_args(['--root','lab','--id','b','--seed','s','--scenario','s.json','--actors','7','9'])
        self.assertFalse(args.apply);self.assertEqual(args.actors,[7,9])

    def test_census_preview_lists_observed_ids_without_post_or_evidence_write(self):
        result=initialize(self.transport([state()]),'census','explicit-seed',self.runtime)
        self.assertEqual(result['status'],'preview');self.assertFalse(result['confirmed'])
        self.assertEqual(result['cohort'],[{'actor':7,'base_id':107},{'actor':9,'base_id':109}])
        self.assertEqual(self.writes(),[]);self.assertEqual(list(self.runtime.iterdir()),[])

    def test_census_apply_forwards_frozen_cohort_and_confirms_its_own_event(self):
        after=state(2);after['society']['town']['census_events']=[{'id':'census'}]
        result=initialize(self.transport([state(),state(),{'checkpoint':2},after]),'census','explicit-seed',self.runtime,apply=True)
        self.assertEqual(json.loads(self.writes()[0].data),{'id':'census','seed':'explicit-seed','expected_checkpoint':1,
            'expected_cohort':[{'actor':7,'base_id':107},{'actor':9,'base_id':109}]})
        self.assertEqual(self.writes()[0].get_header('X-society-session'),'test-save')
        self.assertEqual(result['status'],'checkpoint_confirmed');self.assertTrue(result['confirmed'])
        self.assertEqual(result['confirmation']['saved_record']['census_event']['id'],'census')
        self.assertEqual(json.loads(Path(result['evidence']).read_text())['status'],'checkpoint_confirmed')

    def test_changed_save_or_marker_before_write_prevents_census_mutation(self):
        for changed in (state(session='different-save'),state(2)):
            with self.subTest(changed=changed['bridge']['session']):
                self.calls=[];client=self.transport([state(),changed])
                with self.assertRaises(ValueError):initialize(client,'census','explicit-seed',self.runtime,apply=True)
                self.assertEqual(self.writes(),[])

    def test_same_marker_roster_or_base_change_is_not_silently_applied(self):
        for kind in ('base','new-adult'):
            changed=state()
            if kind=='base':changed['bridge']['observation']['residents'][0]['baseId']=999
            else:changed['bridge']['observation']['residents'].append({'id':11,'baseId':111,'name':'New observed adult','isPerson':True,'inventory':{'gold':0,'bread':0,'grain':0}})
            self.calls=[];client=self.transport([state(),changed])
            with self.subTest(kind=kind),self.assertRaises(ValueError):initialize(client,'census','explicit-seed',self.runtime,apply=True)
            self.assertEqual(self.writes(),[])

    def test_stale_unbound_and_nonadult_observations_cannot_authorize_startup(self):
        cases=[]
        for change in ('stale','unbound','wrong-session','child','base-missing'):
            current=state()
            if change=='stale':current['bridge']['last_seen']=80
            elif change=='unbound':current['bridge']['observation']['checkpoint']=0
            elif change=='wrong-session':current['bridge']['observation']['session']='other'
            elif change=='child':current['bridge']['observation']['residents'][0]['isChild']=True
            else:current['bridge']['observation']['residents'][0].pop('baseId')
            cases.append((change,current))
        for change,current in cases:
            self.calls=[]
            with self.subTest(change=change),self.assertRaises(ValueError):
                initialize(self.transport([current]),'census','explicit-seed',self.runtime,apply=True,actor_ids=[7,9])
            self.assertEqual(self.writes(),[])

    def test_enterprise_preview_validates_without_mutating_state_or_forwarding_defaults(self):
        before=state();original=copy.deepcopy(before)
        result=configure(self.transport([before]),'charter',SPEC,self.runtime)
        self.assertEqual(result['definition'],SPEC);self.assertEqual(result['definition_hash'],definition_hash(SPEC))
        self.assertEqual(before,original);self.assertEqual(self.writes(),[])

    def test_enterprise_apply_forwards_the_exact_reviewed_definition(self):
        spec=copy.deepcopy(SPEC);after=state(2)
        after['society']['town']['enterprise_events']=[{'id':'charter','request':copy.deepcopy(SPEC)}]
        def preflight(request):spec['name']='Mutation after preview';return state()
        result=configure(self.transport([state(),preflight,{'checkpoint':2},after]),'charter',spec,self.runtime,apply=True)
        self.assertEqual(json.loads(self.writes()[0].data),{'id':'charter','enterprise':SPEC,'expected_checkpoint':1})
        self.assertEqual(result['definition'],SPEC);self.assertTrue(result['confirmed'])
        self.assertEqual(result['confirmation']['saved_record']['enterprise_event']['request'],SPEC)

    def test_correct_checkpoint_without_matching_definition_stays_pending(self):
        after=state(2);after['society']['town']['enterprise_events']=[{'id':'charter','request':{**SPEC,'active':False}}]
        result=configure(self.transport([state(),state(),{'checkpoint':2},after]),'charter',SPEC,self.runtime,apply=True,wait_seconds=0)
        self.assertEqual(result['status'],'checkpoint_pending');self.assertFalse(result['confirmed'])
        self.assertEqual(len(self.writes()),1)

    def test_duplicate_requires_saved_exact_request_and_preserves_earlier_evidence(self):
        existing=self.runtime/'enterprise-earlier.json';existing.write_text('original evidence')
        before=state(4);event={'id':'charter','request':copy.deepcopy(SPEC)}
        before['society']['town']['enterprise_events']=[event]
        result=configure(self.transport([before,before,{'duplicate':True,'event':event},before]),
            'charter',SPEC,self.runtime,apply=True)
        self.assertEqual(result['status'],'duplicate_confirmed');self.assertTrue(result['confirmed'])
        self.assertEqual(existing.read_text(),'original evidence')
        self.assertNotEqual(result['evidence'],str(existing))

    def test_session_changed_after_post_is_interrupted_never_confirmed_or_retried(self):
        client=self.transport([state(),state(),{'checkpoint':2},state(2,'different-save')])
        with self.assertRaisesRegex(ValueError,'session changed'):configure(client,'charter',SPEC,self.runtime,apply=True)
        self.assertEqual(len(self.writes()),1)
        receipt=json.loads(next(self.runtime.glob('enterprise-*.json')).read_text())
        self.assertEqual(receipt['status'],'observation_interrupted');self.assertFalse(receipt['confirmed'])

    def test_unknown_transport_outcome_is_recorded_without_replay(self):
        client=self.transport([state(),state(),TimeoutError('unknown apply result')])
        with self.assertRaises(TimeoutError):configure(client,'charter',SPEC,self.runtime,apply=True)
        self.assertEqual(len(self.writes()),1)
        receipt=json.loads(next(self.runtime.glob('enterprise-*.json')).read_text())
        self.assertEqual(receipt['status'],'request_outcome_unknown');self.assertFalse(receipt['confirmed'])

    def background(self):
        before=state();manifest=load_livelihood_manifest();digest=livelihood_manifest_hash(manifest)
        proposal=preview_livelihood_background(before['society'],before['bridge']['observation'],'background','seed',manifest['id'],digest,[7,9])
        return manifest,proposal

    def test_livelihood_preview_only_sends_exact_manifest_identity_and_cohort(self):
        manifest,proposal=self.background();client=self.transport([state(),proposal])
        result=apply_background(client,'background','seed',manifest,[9,7],self.runtime)
        self.assertEqual(result['background'],proposal['background']);self.assertFalse(result['confirmed'])
        self.assertEqual(self.writes()[0].full_url,'http://127.0.0.1:1234/town/livelihood-background/preview')
        self.assertEqual(json.loads(self.writes()[0].data),{'id':'background','seed':'seed','scenario_id':manifest['id'],
            'scenario_hash':livelihood_manifest_hash(manifest),'actor_ids':[7,9],'expected_checkpoint':1})
        self.assertEqual(len(self.writes()),1);self.assertEqual(list(self.runtime.iterdir()),[])

    def test_livelihood_apply_keeps_frozen_assignment_definitions_and_confirms_saved_journal(self):
        manifest,proposal=self.background();saved=copy.deepcopy(proposal['background']);saved.update(source_checkpoint=1,source_session='test-save')
        after=state(2);after['society']['town']['livelihood_backgrounds']=[saved]
        client=self.transport([state(),proposal,state(),{'checkpoint':2,'background':saved},after])
        result=apply_background(client,'background','seed',manifest,[7,9],self.runtime,apply=True)
        self.assertTrue(result['confirmed']);self.assertEqual(result['background']['assignments'],saved['assignments'])
        self.assertEqual(self.writes()[0].data,self.writes()[1].data)
        self.assertTrue(self.writes()[1].full_url.endswith('/town/livelihood-background'))

    def test_wrong_manifest_or_cohort_preview_and_changed_session_cannot_apply(self):
        manifest,proposal=self.background()
        for kind in ('manifest','cohort','session'):
            wrong=copy.deepcopy(proposal)
            if kind=='manifest':wrong['background']['manifest']['provenance']='Changed definition'
            if kind=='cohort':wrong['background']['cohort'][0]['base_id']=999
            self.calls=[];client=self.transport([state(),wrong,state(session='other')])
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                apply_background(client,'background','seed',manifest,[7,9],self.runtime,apply=True)
            self.assertEqual(len(self.writes()),1,'Only the non-mutating preview was posted')


if __name__=='__main__':unittest.main()
