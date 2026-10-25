import copy
import unittest
import test_agency as fixtures
from catalog_fixture import native_ack


class EconomicSpeechTests(unittest.TestCase):
    setUp=fixtures.AgencyTests.setUp
    tearDown=fixtures.AgencyTests.tearDown
    sync=fixtures.AgencyTests.sync
    decide=fixtures.AgencyTests.decide
    arrive=fixtures.AgencyTests.arrive

    def start(self):
        self.world.begin_plan('meal-1',self.obs, 108186,voiced_trade=True);self.sync()
        self.decide('seek_bread');self.arrive()
        self.assertEqual(self.world.agency_plan()['phase'],'economic_attending')
        self.obs['conversationAttendance']={'id':'economic-attend-meal-1','phase':'attending','participants':[
            {'actor':actor,'ownedPackage':True,'loaded':True} for actor in (108186,108149)]}
        self.obs['ack']={'id':'economic-attend-meal-1','status':'applied'}
        self.world.observe(self.obs);self.sync()

    def speak(self,complete=True):
        audio={'file':'a'*64+'.wav','sha256':'a'*64,'seconds':2,'voice':'bf_emma','engine':'kokoro-onnx-0.6.1'}
        self.world.prepare_trade_speech('meal-1',audio,self.obs);self.sync()
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'speak')
        self.assertRegex(command['id'],r'^speech-[a-f0-9]{24}$')
        self.obs['speech']={'id':command['id'],'status':'ended','playedSeconds':2 if complete else .1,'nearbyThroughout':True}
        self.world.observe(self.obs);self.sync()
        return command

    def test_heard_offer_then_acceptance_then_physical_transfer_then_receipt(self):
        self.start()
        with self.assertRaises(ValueError):self.world.claim_plan_decision('meal-1',self.obs)
        self.assertIsNone(self.world.active['pending'])
        self.assertIn('3 gold',self.speak()['line']);self.decide('sell_bread')
        self.assertIsNone(self.world.active['pending'])
        self.assertIn('Agreed',self.speak()['line'])
        trade=self.world.pending('a');self.assertEqual(trade['kind'],'inventory_trade')
        self.assertFalse(self.world.agency_plan().get('purchase_completed',False))
        for index,role in ((0,'buyer'),(1,'seller')):self.obs['residents'][index]['inventory']=trade['after'][role]
        self.obs['ack']=native_ack(trade);self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['economic_speech']['act'],'receipt')
        self.assertEqual(len(self.world.active['trades']),1)
        self.speak();self.decide('keep_food')
        command=self.world.pending('a');self.assertEqual(command['participants'],[108186,108149])
        self.obs['ack']={'id':command['id'],'status':'applied','released':True};self.world.observe(self.obs);self.sync()
        self.assertFalse(self.world.agency_busy())
        self.assertEqual(len(self.world.agency_plan()['economic_turns']),3)
        self.assertEqual(sum(r['inventory']['gold'] for r in self.obs['residents']),31)

    def test_counteroffer_and_second_refusal_do_not_transfer_inventory(self):
        self.start();before=copy.deepcopy(self.obs['residents']);self.speak();self.decide('decline');self.speak()
        self.decide('raise_offer');self.assertIn('5 gold',self.speak()['line'])
        self.decide('decline');self.speak()
        self.assertEqual(self.world.agency_plan()['outcome'],'seller_declined')
        self.assertEqual(self.obs['residents'],before);self.assertEqual(self.world.active['trades'],[])

    def test_incomplete_audio_cannot_create_heard_memory_or_consent(self):
        self.start();self.speak(complete=False)
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertNotIn('economic_turns',self.world.agency_plan())
        self.assertFalse(any(m['kind']=='heard_speech' for p in self.world.active['people'].values() for m in p['memories']))
        self.assertIsNone(self.world.active['pending'])

    def test_save_change_holds_unspoken_terms_without_replay(self):
        self.start();self.obs['session']='new-session';self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(self.world.pending('new-session')['kind'],'release_routine')

    def test_replanning_releases_old_seller_before_new_destination(self):
        self.start();self.speak();self.decide('decline');self.speak();self.decide('visit_adrianne')
        self.assertEqual(self.world.agency_plan()['economic_speech']['listener'],108149)
        self.speak();command=self.world.pending('a');self.assertEqual(command['kind'],'release_routine')
        self.assertEqual(command['participants'],[108186,108149])
        self.obs['ack']={'id':command['id'],'status':'applied','released':True};self.world.observe(self.obs);self.sync()
        command=self.world.pending('a');self.assertEqual(command['kind'],'walk_to');self.assertEqual(command['target'],108156)

    def test_lost_attendance_blocks_synthesis_and_changes_no_assets(self):
        self.start();self.obs['conversationAttendance']['participants'][1]['ownedPackage']=False
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertIsNone(self.world.active['pending'])
