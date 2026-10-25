import copy
from pathlib import Path
import tempfile
import unittest

from catalog_fixture import native_catalog
from lineage import TimelineEconomy


class IdentityInflightTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.world=TimelineEconomy(Path(self.temp.name)/'timeline.sqlite')
        self.obs={'ready':True,'session':'identity-test','checkpoint':0,'gameDays':3,
            'economy_catalog':native_catalog(),'routing':{'available':True,'adapter':'papyrus-mailbox-v1'},
            'residents':[{'id':a,'baseId':a+1000,'name':'Fixture '+str(a),'isPerson':True,
                'x':i*100,'y':0,'z':0,'inventory':{'gold':20,'bread':2,'grain':1}}
                for i,a in enumerate((17,19))]}
        self.world.observe(self.obs);self.world.bootstrap(self.obs);self.sync()
        self.world.initialize_population('fixture-census','fixture-seed',self.obs);self.sync()

    def tearDown(self):
        self.world.db.close();self.temp.cleanup()

    def sync(self):
        for _ in range(8):
            if not self.world.transition:return
            self.obs['checkpoint']=self.world.transition['next'];self.obs.pop('ack',None)
            self.world.observe(self.obs)
        self.fail('Fixture checkpoint did not settle')

    def goals(self):
        self.obs['resident_control']={'available':True,'goal_destinations':True}
        self.world.configure_resident_control('fixture-control',True,self.obs);self.sync()

    def test_goal_claim_excludes_changed_base_without_claiming_that_actor(self):
        self.goals();self.obs['residents'][0]['baseId']=2017
        result=self.world.claim_resident_goals('goals-a',self.obs)
        self.assertEqual([m['actor'] for m in result['wave']['members']],[19])
        self.assertNotIn('standing_goal',self.world.active['people']['17'])

    def test_paid_goal_result_rejects_changed_base_but_settles_disjoint_actor(self):
        self.goals();wave=self.world.claim_resident_goals('goals-a',self.obs)['wave'];self.sync()
        assignments=copy.deepcopy(self.world.active['town']['resident_control']['assignments'])
        self.obs['residents'][0]['baseId']=2017
        results=[{'actor':m['actor'],'result':{'model':'test-identity','decision':
            {'action_id':'quiet','reason':'A quiet interval.','emotion':'calm'}}} for m in wave['members']]
        settled=self.world.finish_resident_goals('goals-a',wave['claim_id'],results,self.obs)
        receipts={row['actor']:row for row in settled['results']}
        self.assertFalse(receipts[17]['accepted']);self.assertTrue(receipts[19]['accepted'])
        self.sync()
        self.assertEqual(self.world.active['town']['resident_control']['assignments']['17'],assignments['17'])
        self.assertEqual(self.world.active['people']['17']['standing_goal']['phase'],'held')
        self.assertEqual(self.world.active['town']['goal_waves'][-1]['phase'],'complete')

    def test_changed_base_arrival_cannot_credit_journey_or_queue_followup(self):
        self.obs['places']=[{'id':500,'name':'Fixture square','position':[1000,0,0],
            'available':True,'eligible_actors':[17,19]}]
        self.goals();wave=self.world.claim_resident_goals('goals-a',self.obs)['wave'];self.sync()
        results=[{'actor':m['actor'],'result':{'model':'test-identity','decision':
            {'action_id':'visit_500','reason':'Visit the square.','emotion':'calm'}}} for m in wave['members']]
        self.world.finish_resident_goals('goals-a',wave['claim_id'],results,self.obs);self.sync()
        goal=self.world.active['people']['17']['standing_goal']
        assignment=self.world.active['town']['resident_control']['assignments']['17']
        self.obs['residents'][0].update(baseId=2017,x=900,activity={'package_id':9000})
        self.obs['resident_control']['activities']=[{'actor':17,'target':500,'goal_id':goal['id'],
            'phase':'arrived','ownedPackage':True,'distance':100,'slot':assignment['slot'],'expectedPackage':9000}]
        before=copy.deepcopy(self.world.active);writes=self.world.db.total_changes
        self.assertFalse(self.world.observe_resident_goals(self.obs))
        self.assertEqual(self.world.active,before);self.assertEqual(self.world.db.total_changes,writes)

    def speech_fixture(self,phase):
        claim={'id':'wording-fixture','stage':'propose','session':self.world.session,'context':{}}
        plan={'id':'speech-fixture','actor':17,'target':19,'phase':phase,'voiced_trade':True,
            'natural_trade':True,'economic_pair':[17,19],'decisions':[],
            'economic_attendance':{'status':'applied'},'economic_attendance_id':'attendance-fixture',
            'economic_speech':{'actor':17,'listener':19,'origin_session':self.world.session,
                'claim':claim,'act':'offer','line':'Fixture only.','resume_phase':'consent',
                'delivery_id':'fixture-delivery','audio':{'file':'a'*64+'.wav','sha256':'a'*64,
                    'seconds':2,'voice':'bf_emma','engine':'kokoro-onnx-0.6.1'}},'release_required':True}
        state=copy.deepcopy(self.world.active);state['plans']=[plan]
        self.obs['conversationAttendance']={'id':'attendance-fixture','phase':'attending',
            'participants':[{'actor':a,'ownedPackage':True,'loaded':True} for a in (17,19)]}
        self.world._write(state,'Authored in-flight speech fixture; no native playback proof');self.sync()
        self.assertTrue(self.world.economic_present(self.world.agency_plan(),self.obs))

    def test_changed_speaker_or_listener_blocks_claim_result_and_audio_without_writes(self):
        for phase in ('economic_propose','economic_thinking_propose','economic_synthesize'):
            for index in (0,1):
                with self.subTest(phase=phase,index=index):
                    for row in self.obs['residents']:row['baseId']=row['id']+1000
                    self.speech_fixture(phase)
                    self.obs['residents'][index]['baseId']+=1000
                    before=copy.deepcopy(self.world.active);writes=self.world.db.total_changes
                    with self.assertRaisesRegex(ValueError,'attending|left|nearby'):
                        if phase=='economic_propose':self.world.claim_economic_wording('speech-fixture',self.obs)
                        elif phase=='economic_thinking_propose':self.world.finish_economic_wording('speech-fixture','wording-fixture',{},self.obs)
                        else:self.world.prepare_trade_speech('speech-fixture',{'file':'a'*64+'.wav','sha256':'a'*64,
                            'seconds':2,'voice':'bf_emma','engine':'kokoro-onnx-0.6.1'},self.obs)
                    self.assertEqual(self.world.active,before);self.assertEqual(self.world.db.total_changes,writes)

    def test_identity_loss_during_speech_holds_without_delivery_credit(self):
        self.speech_fixture('economic_speaking');self.obs['residents'][1]['baseId']=2019
        self.obs['speech']={'id':'irrelevant','status':'ended','playedSeconds':2,'nearbyThroughout':True}
        self.assertTrue(self.world.observe_trade_speech(self.obs));self.sync()
        plan=self.world.agency_plan()
        self.assertEqual(plan['phase'],'held');self.assertTrue(plan['release_required'])
        self.assertFalse(plan.get('economic_turns'))

    def test_changed_identity_conversation_can_hold_and_release_original_route(self):
        scenario={'version':1,'id':'fixture-pair','participants':[17,19],
            'max_turns':2,'provenance':'Explicit offline authored cleanup fixture'}
        self.world.start_scenario_conversation('fixture-chat',self.obs,scenario);self.sync()
        before=self.world.pending(self.world.session)
        self.assertEqual((before['actor'],before['target']),(17,19))
        self.obs['residents'][0]['baseId']=2017
        self.world.hold_conversation('fixture-chat','Identity changed during meeting',self.obs);self.sync()
        held=self.world.conversation_status()
        self.assertTrue(held['release_required'])
        self.assertEqual(held['phase'],'releasing')
        command=self.world.pending(self.world.session)
        self.assertEqual(command['kind'],'release_routine')
        self.assertEqual(command['actor'],17)
        self.assertNotIn('participants',command,'Only the meeting walker owned a route; do not release an unacquired pair')
        self.assertFalse(held.get('turns'))

    def test_changed_identity_cannot_receive_successful_social_playback_credit(self):
        scenario={'version':1,'id':'fixture-pair','participants':[17,19],
            'max_turns':2,'provenance':'Explicit offline authored delivery fixture'}
        self.world.start_scenario_conversation('fixture-chat',self.obs,scenario);self.sync()
        state=copy.deepcopy(self.world.active);chat=state['conversation']
        chat['phase']='speaking'
        chat['current']={'speaker':17,'listener':19,'delivery_session':self.world.session,
            'delivery_id':'fixture-social-speech','audio':{'seconds':2},
            'selected':{'line':'My name is Fixture 17.','tone':'calm'}}
        self.world._write(state,'Authored pending social playback fixture');self.sync()
        before=copy.deepcopy(self.world.active['people'])
        self.obs['residents'][1]['baseId']=2019
        self.obs['speech']={'id':'fixture-social-speech','status':'ended',
            'playedSeconds':2,'nearbyThroughout':True}
        self.world.observe_conversation(self.obs);self.sync()
        chat=self.world.conversation_status()
        self.assertEqual(chat['phase'],'releasing')
        self.assertTrue(chat['release_required'])
        self.assertFalse(chat.get('turns'))
        self.assertEqual(self.world.active['people'],before)


if __name__=='__main__':unittest.main()
