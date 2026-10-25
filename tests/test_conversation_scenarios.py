import copy
from pathlib import Path
import tempfile
import unittest
from catalog_fixture import native_catalog
from conversation import cleanup_participants,meeting_route
from conversation_scenarios import validate_scenario,scenario_hash
from lineage import TimelineEconomy


def spec():
    return {'version':1,'id':'fixture-pair','participants':[7001,8002],
        'max_turns':2,'provenance':'Explicit offline authored pair, not autonomous choice'}


class ScenarioValidationTests(unittest.TestCase):
    def test_snapshot_is_defensive_and_digest_canonical(self):
        raw=spec();snapshot=validate_scenario(raw)
        self.assertEqual(scenario_hash(raw),scenario_hash(dict(reversed(list(raw.items())))))
        raw['participants'][0]=9003
        self.assertEqual(snapshot['participants'],[7001,8002])
        self.assertNotEqual(scenario_hash(raw),scenario_hash(snapshot))

    def test_invalid_spec_boundaries(self):
        for changes in ({'version':True},{'version':2},{'id':'spaces forbidden'},
                {'participants':[7001,7001]},{'participants':[True,8002]},
                {'participants':[7001,0x100000000]},{'participants':[7001]},
                {'max_turns':True},{'max_turns':1},{'max_turns':7},
                {'provenance':' '},{'provenance':'a'*501},{'provenance':'line\nbreak'},
                {'provenance':'\ud800'},{'extra':1}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate_scenario({**spec(),**changes})

    def test_cleanup_uses_original_owner_despite_reversed_speech(self):
        c={'meeting_route':meeting_route(7001,8002,'old'),'initiator':7001,'partner':8002,'speakers':[8002,7001]}
        self.assertEqual(cleanup_participants(c),[7001,8002])
        self.assertEqual(cleanup_participants({'speakers':[7001,8002]}),[7001,8002])
        for changes in ({'initiator':9003},{'partner':None},{'speakers':[7001,9003]},
                {'meeting_route':{}},{'speakers':[]},{'initiator':True}):
            with self.subTest(changes=changes):self.assertIsNone(cleanup_participants({**c,**changes}))


class ConversationScenarioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.world=TimelineEconomy(Path(self.temp.name)/'timeline.sqlite')
        self.obs={'session':'scenario-test','checkpoint':0,'ready':True,'gameDays':10,
            'economy_catalog':native_catalog(),'routing':{'available':True,'adapter':'papyrus-mailbox-v1'},
            'residents':[{'id':a,'baseId':a+10000,'name':'Fixture '+str(a),'isPerson':True,'x':i*100,'y':0,'z':0,
                'inventory':{'gold':10,'bread':2,'grain':1}} for i,a in enumerate((7001,8002))]}
        self.world.observe(self.obs);self.world.bootstrap(self.obs);self.sync()

    def tearDown(self):
        self.world.db.close();self.temp.cleanup()

    def sync(self):
        for _ in range(10):
            if not self.world.transition:return
            self.obs['checkpoint']=self.world.transition['next'];self.obs.pop('ack',None)
            self.world.observe(self.obs)
        self.fail('Checkpoint loop did not settle')

    def census(self):
        self.world.initialize_population('fixture-census','fixture-seed',self.obs);self.sync()

    def test_ordinary_new_conversation_requires_census_without_mutation(self):
        before=copy.deepcopy(self.world.active);changes=self.world.db.total_changes
        for actor in (None,7001):
            with self.subTest(actor=actor),self.assertRaisesRegex(ValueError,'census'):
                self.world.start_conversation('ordinary',self.obs,actor)
            self.assertEqual(self.world.active,before)
            self.assertEqual(self.world.db.total_changes,changes)

    def test_census_operator_opportunity_still_uses_resident_choice(self):
        self.census()
        self.world.start_conversation('offered',self.obs,max_turns=2);self.sync()
        c=self.world.conversation_status()
        self.assertEqual(c['phase'],'choose_partner')
        self.assertEqual(c['mode'],'autonomous_social')
        self.assertIn(c['initiator'],(7001,8002))
        self.assertIsNone(c['partner'])
        self.assertNotIn('scenario',c)
        self.assertIn('Operator offered opportunity',c['source'])

    def test_explicit_scenario_frozen_binding_and_idempotent_history(self):
        self.census();raw=spec()
        self.world.start_scenario_conversation('authored',self.obs,raw);self.sync()
        c=self.world.conversation_status();raw['participants'][0]=9003
        self.assertEqual(c['scenario'],spec())
        self.assertEqual(c['scenario_hash'],scenario_hash(spec()))
        command=self.world.pending(self.world.session)
        self.assertEqual((command['actor'],command['target'],command['origin']),(7001,8002,'authored_encounter'))
        changes=self.world.db.total_changes
        self.assertTrue(self.world.start_scenario_conversation('authored',self.obs,spec())['duplicate'])
        self.assertEqual(self.world.db.total_changes,changes)
        self.world.active['conversation_history']=[c]
        self.world.active.pop('conversation')
        self.world.active.pop('town',None)
        self.obs['residents']=[]
        self.assertTrue(self.world.start_scenario_conversation('authored',self.obs,spec())['duplicate'])
        with self.assertRaisesRegex(ValueError,'authored scenario'):self.world.start_conversation('authored',self.obs)
        with self.assertRaisesRegex(ValueError,'different authored content'):
            self.world.start_scenario_conversation('other',self.obs,{**spec(),'max_turns':4})

    def test_ordinary_legacy_history_remains_readable_but_cannot_be_reinterpreted(self):
        old={'id':'historical','phase':'complete','speakers':[7001,8002],'turn_limit':2,'turns':[]}
        self.world.active['conversation_history']=[old]
        before=copy.deepcopy(self.world.active)
        self.assertTrue(self.world.start_conversation('historical',self.obs)['duplicate'])
        with self.assertRaisesRegex(ValueError,'another scenario'):
            self.world.start_scenario_conversation('historical',self.obs,spec())
        self.assertEqual(self.world.active,before)

    def test_scenario_rejects_missing_people_capability_and_actor_lease(self):
        with self.assertRaises(ValueError):self.world.start_scenario_conversation('scene',self.obs,spec())
        self.census();before=copy.deepcopy(self.world.active)
        self.obs['routing']['available']=False
        with self.assertRaises(ValueError):self.world.start_scenario_conversation('scene',self.obs,spec())
        self.assertEqual(self.world.active,before)
        self.obs['routing']['available']=True
        self.world.active['activity_jobs']={'held':{'actor':7001,'target':42,'slot':0,'phase':'running'}}
        with self.assertRaises(ValueError):self.world.start_scenario_conversation('scene',self.obs,spec())

    def test_failed_release_remains_quarantined_without_completion_credit(self):
        self.census();self.world.start_scenario_conversation('scene',self.obs,spec());self.sync()
        self.world.active['conversation'].update(phase='releasing',final_phase='complete')
        self.obs['ack']={'id':'release-chat-scene','status':'held','released':True}
        self.world.observe(self.obs);self.sync()
        c=self.world.conversation_status()
        self.assertEqual(c['phase'],'held');self.assertTrue(c['release_required'])
        self.assertTrue(c['cleanup_review_required']);self.assertTrue(self.world.conversation_busy())
        self.assertNotIn('finished_at',c)
        self.obs['ack']={'id':'release-chat-scene','status':'applied','released':True}
        self.world.observe(self.obs);self.sync()
        self.assertTrue(self.world.conversation_status()['release_required'])

    def test_background_journey_member_rejected_before_write_but_disjoint_pair_allowed(self):
        self.census()
        self.world.active['routine_batches']=[{'id':'background','phase':'travelling','background':True,
            'launched':True,'members':[{'actor':7001,'phase':'travelling'}]}]
        before=copy.deepcopy(self.world.active);changes=self.world.db.total_changes
        with self.assertRaisesRegex(ValueError,'journey'):
            self.world.start_scenario_conversation('scene',self.obs,spec())
        self.assertEqual(self.world.active,before);self.assertEqual(self.world.db.total_changes,changes)
        self.world.active['routine_batches'][-1]['members'][0]['actor']=9003
        self.world.start_scenario_conversation('scene',self.obs,spec())
        self.assertIsNotNone(self.world.transition)

    def test_old_session_cleanup_releases_exact_original_owner_without_route_replay(self):
        self.census();self.world.start_scenario_conversation('scene',self.obs,spec());self.sync()
        c=self.world.active['conversation'];c['meeting_route']['session']='older-game'
        c['speakers']=[8002,7001]
        self.assertIsNone(self.world.speech_command(self.world.session))
        self.world.observe(self.obs);self.sync()
        command=self.world.pending(self.world.session)
        self.assertEqual((command['kind'],command['actor']),('release_routine',7001))
        self.assertEqual(self.world.conversation_status()['final_phase'],'held')

    def test_contradictory_cleanup_never_releases_wrong_actor_or_accepts_cached_ack(self):
        self.census();self.world.start_scenario_conversation('scene',self.obs,spec());self.sync()
        c=self.world.active['conversation'];c.update(phase='releasing',final_phase='complete',initiator=9003)
        self.assertIsNone(self.world.speech_command(self.world.session))
        self.obs['ack']={'id':'release-chat-scene','status':'applied','released':True}
        self.world.observe(self.obs);self.sync()
        c=self.world.conversation_status()
        self.assertEqual(c['phase'],'held');self.assertTrue(c['cleanup_review_required'])
        self.assertNotIn('release_evidence',c)
        self.assertTrue(self.world.conversation_busy())
        self.assertIsNone(self.world.speech_command(self.world.session))
        with self.assertRaisesRegex(ValueError,'active'):self.world.start_conversation('next',self.obs)
