"""Cross-system owner work tests using real immutable checkpoint transitions.

Native receipts are explicitly authored test inputs. No live game, provider or
physical-effect execution is used by these tests.
"""
import copy
import time
import unittest
import test_owner_production
from test_conversation import AUDIO,CANDIDATES
from owner_work_jobs import _identity
from activity_leases import reserved_activity_actors
from economy_catalog import catalog_hash


class OwnerWorkIntegrationTests(unittest.TestCase):
    tearDown=test_owner_production.OwnerProductionTests.tearDown
    sync=test_owner_production.OwnerProductionTests.sync
    census=test_owner_production.OwnerProductionTests.census
    review=test_owner_production.OwnerProductionTests.review
    start=test_owner_production.OwnerProductionTests.start
    decide=test_owner_production.OwnerProductionTests.decide

    def setUp(self):
        test_owner_production.OwnerProductionTests.setUp(self)
        self.actor['baseId']=9099  # Explicit offline native identity fixture.
        self.obs['owner_work_jobs']={'available':True,'capacity':4,'jobs':[],'receipts':[]}

    def delegate(self):
        before=copy.deepcopy(self.actor['inventory'])
        self.decide(self.start(),stationary=False)
        self.assertEqual(self.actor['inventory'],before)
        self.assertEqual(self.world.agency_plan()['phase'],'delegated')
        job=self.world.active['work_jobs'][self.world.agency_plan()['work_job']]
        command=self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'],'owner_work_start')
        self.obs['ack']={**_identity(job),'id':command['id'],'status':'applied','accepted':True}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['work_jobs'][job['id']]['phase'],'running')
        self.assertIsNone(self.world.active['pending'])
        return job

    def attendance(self,job):
        now=time.time()*1000
        self.obs['gameDays']=job['created_day']+job['work_minutes']/1440+.00001
        receipt={**_identity(job),'phase':'attendance_verified','effects_issued':False,'release_verified':False,
                 'attendance':{'token':'test-only-'+job['id'],'slot':job['slot'],'serial':2,
                    'expected_package':job['expected_package'],'anchor':[1.,2.,3.],
                    'worked_minutes':job['work_minutes'],'samples':100,'ready_at':now-1,'expires_at':now+120000}}
        self.obs['owner_work_jobs']['receipts']=[receipt]
        self.world.observe(self.obs);self.sync()
        return receipt

    def commit(self,job):
        command=self.world.active['pending']['command']
        self.assertEqual(command['kind'],'inventory_self_produce_commit')
        self.actor['inventory']=copy.deepcopy(command['after']['owner'])
        self.obs['ack']={**_identity(job),'id':command['id'],'commit_id':command['id'],'status':'applied',
                         'attendance_token':command['attendance_token'],'inventory':copy.deepcopy(command['after']),
                         'effects_issued':True,'committed_inventory_verified':True,'mechanism':'native_owner_recipe'}
        self.world.observe(self.obs);self.sync()
        return command

    def test_background_result_settles_original_plan_only_after_release_and_ack(self):
        job=self.delegate();before=copy.deepcopy(self.actor['inventory']);source=self.event['id']
        other={'id':'later-unrelated-plan','actor':108186,'kind':'need_review','phase':'choose','remembered':True}
        state=copy.deepcopy(self.world.active);state['plans'].append(other)
        self.world._write(state,'Test fixture: another resident starts foreground decision');self.sync()
        self.attendance(job)
        self.assertEqual(self.world.active['work_jobs'][job['id']]['phase'],'attendance_verified')
        self.assertIsNone(self.world.active['pending'])
        self.assertEqual(self.world.agency_plan(),other)
        state=copy.deepcopy(self.world.active);state['plans'][-1]['phase']='complete'
        self.world._write(state,'Test fixture: unrelated resident finishes');self.sync()
        command=self.commit(job)
        self.assertEqual(command['before']['owner'],before)
        self.assertEqual(self.actor['inventory'],{'gold':before['gold'],'grain':before['grain']-1,'bread':before['bread']+2})
        self.assertEqual(next(p for p in self.world.active['plans'] if p['id']==source)['phase'],'delegated')
        self.assertIn(job['actor'],reserved_activity_actors(self.world.active))
        self.assertEqual(len(self.world.active['production']),1)
        self.assertEqual(self.world.active['people'][str(job['actor'])]['food_policy'],self.policy)
        self.obs['owner_work_jobs']['receipts']=[{**_identity(job),'phase':'complete','effects_issued':True,
             'release_verified':True,'committed_inventory_verified':True,'commit_id':command['id']}]
        self.world.observe(self.obs);self.sync()
        self.assertEqual(next(p for p in self.world.active['plans'] if p['id']==source)['phase'],'complete')
        self.assertEqual(self.world.agency_plan()['id'],other['id'])
        self.assertIn(job['actor'],reserved_activity_actors(self.world.active))
        ack=self.world.pending(self.obs['session']);self.assertEqual(ack['kind'],'owner_work_ack_receipt')
        self.obs['ack']={**_identity(job),'id':ack['id'],'status':'applied','acknowledged':True}
        self.world.observe(self.obs);self.sync()
        self.assertNotIn(job['actor'],reserved_activity_actors(self.world.active))
        snapshot=copy.deepcopy(self.world.active)
        self.world.observe(self.obs)
        self.assertIsNone(self.world.transition);self.assertEqual(self.world.active,snapshot)

    def test_unrelated_inventory_writer_is_not_overwritten_by_attendance(self):
        job=self.delegate();state=copy.deepcopy(self.world.active)
        unrelated={'id':'other-consume','status':'pending','command':{'id':'other-consume','kind':'inventory_consume','actor':108186,'catalog_hash':catalog_hash()},'evidence':None}
        state['pending']=copy.deepcopy(unrelated)
        self.world._write(state,'Test fixture: independent already-admitted food effect');self.sync()
        self.attendance(job)
        self.assertEqual(self.world.active['pending'],unrelated)
        self.assertEqual(self.world.active['work_jobs'][job['id']]['phase'],'running')
        self.assertNotIn('production',self.world.active)

    def test_attendance_arrival_cannot_replace_active_disjoint_speech(self):
        job=self.delegate();identifier='disjoint-social'
        self.world.start_conversation(identifier,self.obs,max_turns=2);self.sync()
        def decide(action):
            claim=self.world.claim_conversation(identifier,self.obs)['claim'];self.sync()
            self.world.finish_conversation_inference(identifier,claim['id'],{'model':'authored-test',
                 'decision':{'action_id':action,'reason':'Explicit offline test input','emotion':'calm'}},self.obs);self.sync()
        c=self.world.conversation_status()
        claim=self.world.claim_conversation(identifier,self.obs)['claim'];self.sync()
        selected=next(o['id'] for o in claim['context']['options'] if o['id'].startswith('approach_'))
        self.world.finish_conversation_inference(identifier,claim['id'],{'model':'authored-test',
             'decision':{'action_id':selected,'reason':'Explicit offline test input','emotion':'calm'}},self.obs);self.sync()
        c=self.world.conversation_status();command=self.world.pending(self.obs['session'])
        self.assertNotIn(job['actor'],c['speakers'])
        self.obs['ack']={'id':command['id'],'status':'applied','movement':{'actor':c['initiator'],'target':c['partner'],'ownedPackage':True}}
        self.world.observe(self.obs);self.sync();decide('chat')
        command=self.world.pending(self.obs['session'])
        attendance={'id':command['id'],'phase':'attending','participants':[{'actor':actor,'loaded':True,'ownedPackage':True} for actor in command['participants']]}
        self.obs['conversationAttendance']=attendance;self.obs['ack']={'id':command['id'],'status':'applied','attendance':attendance}
        self.world.observe(self.obs);self.sync()
        claim=self.world.claim_conversation(identifier,self.obs)['claim'];self.sync()
        self.world.finish_conversation_inference(identifier,claim['id'],{'model':'authored-test','proposal':{'candidates':CANDIDATES}},self.obs);self.sync()
        decide('option_1');self.world.prepare_speech(identifier,AUDIO,self.obs);self.sync()
        speech=copy.deepcopy(self.world.pending(self.obs['session']));self.assertEqual(speech['kind'],'speak')
        self.attendance(job)
        self.assertEqual(self.world.pending(self.obs['session']),speech)
        self.assertIsNone(self.world.active['pending'])
        self.assertEqual(self.world.conversation_status()['phase'],'speaking')
        self.assertEqual(self.world.active['work_jobs'][job['id']]['phase'],'running')
        self.assertEqual(self.world.active.get('production',[]),[])

    def test_save_load_of_prepared_recipe_never_replays_or_infers_completion(self):
        job=self.delegate();self.attendance(job)
        before=copy.deepcopy(self.actor['inventory']);command=copy.deepcopy(self.world.active['pending']['command'])
        self.obs['session']='loaded-before-recipe';self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertTrue(self.world.active['work_jobs'][job['id']]['effect_unreconciled'])
        self.assertIsNone(self.world.pending(self.obs['session']))
        self.assertEqual(self.actor['inventory'],before)
        # Matching output appearance does not manufacture a lost permit/receipt.
        self.actor['inventory']=copy.deepcopy(command['after']['owner'])
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active.get('production',[]),[])
        self.assertIn(job['actor'],reserved_activity_actors(self.world.active))

    def test_invalid_recipe_ack_holds_once_without_checkpoint_spin(self):
        job=self.delegate();self.attendance(job)
        command=self.world.active['pending']['command']
        self.obs['ack']={**_identity(job),'id':command['id'],'status':'applied'}
        self.world.observe(self.obs)
        # Real checkpoint binding must settle, not create a fresh held checkpoint
        # for the same rejected acknowledgement on every observation.
        self.sync()
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.world.observe(self.obs);self.assertIsNone(self.world.transition)
        self.assertEqual(self.world.active.get('production',[]),[])

    def test_exact_no_effect_recipe_rejection_cleans_up_without_output_credit(self):
        job=self.delegate();before=copy.deepcopy(self.actor['inventory']);self.attendance(job)
        command=self.world.active['pending']['command']
        self.obs['ack']={**_identity(job),'id':command['id'],'status':'held',
                         'no_effects_issued':True,'effects_issued':False,'error':'Permit expired before first effect'}
        self.world.observe(self.obs);self.sync()
        self.assertIsNone(self.world.active['pending'])
        self.assertEqual(self.world.active.get('production',[]),[])
        self.assertEqual(self.actor['inventory'],before)
        self.assertIn(job['actor'],reserved_activity_actors(self.world.active))
        self.obs['owner_work_jobs']['receipts']=[{**_identity(job),'phase':'held','effects_issued':False,
                                                  'release_verified':True,'error':'Permit expired before first effect'}]
        self.world.observe(self.obs);self.sync()
        ack=self.world.pending(self.obs['session']);self.assertEqual(ack['kind'],'owner_work_ack_receipt')
        self.obs['ack']={**_identity(job),'id':ack['id'],'status':'applied','acknowledged':True}
        self.world.observe(self.obs);self.sync()
        self.assertNotIn(job['actor'],reserved_activity_actors(self.world.active))
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(self.world.active.get('production',[]),[])

    def test_rollback_orphan_partial_recipe_keeps_account_quarantined(self):
        old=copy.deepcopy(self.obs);job=self.delegate()
        self.obs={**old,'session':'rollback-before-owner-work','owner_work_jobs':{'available':True,'capacity':4,'jobs':[],
                 'receipts':[{**_identity(job),'phase':'held','effects_issued':None,'release_verified':True,
                              'error':'Cold bridge lost issued-effect witness'}]}}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active.get('production',[]),[])
        self.assertIn(job['actor'],reserved_activity_actors(self.world.active))
        self.assertIsNone(self.world.owner_work_pending_command())


if __name__=='__main__':unittest.main()
