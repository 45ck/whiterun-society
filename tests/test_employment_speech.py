import copy
import unittest
import test_labour
from labour import work_opportunities
from employment import recently_refused


class EmploymentSpeechTests(unittest.TestCase):
    setUp = test_labour.LabourTests.setUp
    tearDown = test_labour.LabourTests.tearDown
    sync = test_labour.LabourTests.sync
    census = test_labour.LabourTests.census
    review = test_labour.LabourTests.review
    decide = test_labour.LabourTests.decide
    archive_plan = test_labour.LabourTests.archive_plan

    def start(self, scheduled=False):
        # Archived dialogue remains testable; today's scheduler advertises no paid jobs.
        self.event='heard-employment'
        self.archive_plan(self.event,voiced=True,scheduled=scheduled)
        self.assertEqual(self.world.agency_plan()['phase'],'travelling')
        self.assertEqual(self.world.agency_plan()['decisions'],[])

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
        revision=self.world.active['town']['businesses']['business-108149']['revision']
        refused=lambda worker,rev,day:recently_refused(self.world.active,worker,'business-108149',rev,day)
        self.assertTrue(refused(99,revision,self.obs['gameDays']))
        self.assertFalse(refused(108186,revision,self.obs['gameDays']),'Private refusal does not transfer to another worker')
        self.assertFalse(refused(99,revision,self.obs['gameDays']+61/1440))
        self.assertFalse(refused(99,revision+1,self.obs['gameDays']),'Changed terms invalidate the old refusal context')
        self.assertEqual(work_opportunities(self.world.active,self.obs,108186),[],'Paid execution remains gated independently')

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

    def test_heard_archived_contract_does_not_authorize_unqualified_production(self):
        before=copy.deepcopy(self.obs['residents'])
        self.start();self.arrive();self.attend();self.speak()
        self.decide('offer_shift',self.event);self.assertIn('2 gold',self.speak()['line'])
        self.decide('take_shift',self.event)
        contracts=lambda:self.world.active['town']['businesses']['business-108149']['contracts']
        self.assertEqual(contracts(),[],'Unheard acceptance must not create a contract')
        self.speak();self.assertEqual(contracts()[0]['status'],'accepted')
        self.release();self.arrive()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertNotEqual((self.world.pending(self.obs['session']) or {}).get('kind'),'inventory_produce')
        self.assertEqual(self.obs['residents'],before)
        self.assertEqual(self.world.status()['production'],[])
        self.assertNotEqual(contracts()[0]['status'],'completed')
        self.assertEqual(len(self.world.agency_plan()['economic_turns']),3)
        self.assertFalse(any(turn.get('speech_act')=='work_receipt' for turn in self.world.agency_plan()['economic_turns']))

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
