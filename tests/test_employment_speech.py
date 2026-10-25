import copy
import unittest
import test_labour
from labour import work_opportunities
from catalog_fixture import native_ack


class EmploymentSpeechTests(unittest.TestCase):
    setUp = test_labour.LabourTests.setUp
    tearDown = test_labour.LabourTests.tearDown
    sync = test_labour.LabourTests.sync
    census = test_labour.LabourTests.census
    review = test_labour.LabourTests.review
    decide = test_labour.LabourTests.decide

    def start(self, scheduled=False):
        if scheduled:
            self.review();self.event=next(e['id'] for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
            self.world.begin_plan(self.event,self.obs,99,'need_review',voiced_trade=True);self.sync()
            self.decide('seek_work',self.event)
        else:
            self.event='heard-employment'
            self.world.begin_plan(self.event,self.obs,99,'work_shift',voiced_trade=True);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'travelling')
        self.assertEqual(self.world.agency_plan()['decisions'][-1]['actor_id'] if scheduled else len(self.world.agency_plan()['decisions']),99 if scheduled else 0)

    def arrive(self):
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'walk_to')
        self.obs['ack']={'id':command['id'],'status':'applied','movement':{'hasOwnedPackage':True,
            'expectedPackage':777,'aliasesConfirmed':True,'adapter':'papyrus-mailbox','actor':99,'target':108149}}
        self.world.observe(self.obs);self.sync()

    def attend(self):
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'conversation_attend')
        self.obs['conversationAttendance']={'id':command['id'],'phase':'attending','participants':[
            {'actor':a,'ownedPackage':True,'loaded':True} for a in command['participants']]}
        self.obs['ack']={'id':command['id'],'status':'applied'};self.world.observe(self.obs);self.sync()
        return command['id']

    def speak(self, complete=True):
        audio={'file':'a'*64+'.wav','sha256':'a'*64,'seconds':2,'voice':'bf_emma','engine':'kokoro-onnx-0.6.1'}
        self.world.prepare_trade_speech(self.event,audio,self.obs);self.sync()
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'speak')
        self.obs['speech']={'id':command['id'],'status':'ended','playedSeconds':2 if complete else .1,'nearbyThroughout':True}
        self.world.observe(self.obs);self.sync();return command

    def release(self):
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'release_routine')
        self.obs['conversationAttendance']=None
        self.obs['ack']={'id':command['id'],'status':'applied','released':True};self.world.observe(self.obs);self.sync()

    def test_refusal_is_heard_before_memory_and_earlier_review_without_assets(self):
        before=copy.deepcopy(self.obs['residents']);self.start(scheduled=True)
        with self.assertRaises(ValueError):self.world.claim_plan_decision(self.event,self.obs)
        self.arrive();self.attend();self.assertIn('hiring',self.speak()['line'])
        self.decide('defer',self.event)
        self.assertFalse(any(m['kind']=='employment_unavailable' for m in self.world.active['people']['99']['memories']))
        self.assertIn('not offering',self.speak()['line']);self.release()
        self.assertEqual(self.world.agency_plan()['outcome'],'employer_declined')
        self.assertEqual(self.obs['residents'],before)
        memory=next(m for m in self.world.active['people']['99']['memories'] if m['kind']=='employment_unavailable')
        self.assertNotIn('reason',memory);self.assertEqual(memory['other'],108149)
        self.assertAlmostEqual(self.world.active['people']['99']['agency']['next_review_day'],self.obs['gameDays']+15/1440)
        self.assertEqual(work_opportunities(self.world.active,self.obs,99),[])
        self.assertTrue(work_opportunities(self.world.active,self.obs,108186),'Another worker must not inherit this private refusal')
        obs=copy.deepcopy(self.obs);obs['gameDays']+=61/1440
        self.assertTrue(work_opportunities(self.world.active,obs,99))
        self.world.active['town']['businesses']['business-108149']['revision']+=1
        self.assertTrue(work_opportunities(self.world.active,self.obs,99),'New public terms allow reconsideration')

    def test_incomplete_refusal_audio_does_not_teach_worker_about_employer(self):
        self.start();self.arrive();self.attend();self.speak();self.decide('defer',self.event);self.speak(complete=False)
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertFalse(any(m['kind']=='employment_unavailable' for m in self.world.active['people']['99']['memories']))

    def test_next_needs_review_offers_food_instead_of_repeating_refused_job(self):
        self.start(scheduled=True);self.arrive();self.attend();self.speak();self.decide('defer',self.event);self.speak();self.release()
        self.world.active['people']['99']['needs']['hunger']=.9
        self.obs['gameDays']+=16/1440
        self.world.review_population(self.obs);self.sync()
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99 and e['status']=='pending')
        self.world.begin_plan(event['id'],self.obs,99,'need_review',voiced_trade=True);self.sync()
        claim=self.world.claim_plan_decision(event['id'],self.obs)['claim']
        options={o['id'] for o in claim['context']['options']}
        self.assertIn('eat_bread',options);self.assertFalse(any(a.startswith('seek_work') for a in options))
        self.assertTrue(any(m['kind']=='employment_unavailable' for m in claim['context']['memories']))

    def test_heard_contract_then_real_production_then_separate_receipt_attendance(self):
        self.start();self.arrive();first=self.attend();self.speak()
        self.decide('offer_shift',self.event);self.assertIn('2 gold',self.speak()['line'])
        self.decide('take_shift',self.event)
        contracts=lambda:self.world.active['town']['businesses']['business-108149']['contracts']
        self.assertEqual(contracts(),[],'Unheard acceptance must not create a contract')
        self.speak();self.assertEqual(contracts()[0]['status'],'accepted')
        self.release();self.arrive()
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'inventory_produce')
        for a in self.obs['residents']:
            if a['id'] in (99,108149):a['inventory']=copy.deepcopy(command['after']['worker' if a['id']==99 else 'employer'])
        self.obs['ack']=native_ack(command);self.world.observe(self.obs);self.sync()
        self.assertEqual(contracts()[0]['status'],'completed')
        self.assertNotEqual(self.attend(),first,'A completed native attendance command cannot be replayed')
        self.assertIn('received 2 gold',self.speak()['line']);self.release()
        self.assertEqual(self.world.agency_plan()['outcome'],'paid_work_completed')
        self.assertEqual(len(self.world.agency_plan()['economic_turns']),4)
        self.assertEqual(len(self.world.active['production']),1)

    def test_changed_terms_before_hearing_acceptance_hold_without_contract(self):
        self.start();self.arrive();self.attend();self.speak();self.decide('offer_shift',self.event);self.speak()
        self.decide('take_shift',self.event)
        self.world.active['town']['businesses']['business-108149']['revision']+=1
        self.speak()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(self.world.active['town']['businesses']['business-108149']['contracts'],[])

    def test_failed_approach_does_not_invoke_remote_employer(self):
        self.start();command=self.world.pending(self.obs['session'])
        self.obs['ack']={'id':command['id'],'status':'held'};self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(self.world.agency_plan()['decisions'],[])
        self.assertNotIn('economic_speech',self.world.agency_plan())
