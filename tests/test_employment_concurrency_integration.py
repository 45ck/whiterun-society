"""Employer social freedom and employee attendance over actual controller APIs.

Native alias binding, locomotion and audio playback are explicit offline inputs.
Real routers, meeting leases, saved social choices and paid controllers decide
their outcomes. No game process or fabricated economic receipt is used.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import market_policy
import test_paid_employment_integration as paid_fixture
from test_resource_protocol_interop import NativeResourceProcess
from test_conversation import AUDIO
from activity_leases import paid_work_activity_actors, reserved_work_accounts
from employment_concurrency_metrics import EmploymentConcurrencyTelemetry


class ConcurrentNativeProcess(NativeResourceProcess):
    def __init__(self,observation,manifest):
        root=Path(__file__).resolve().parents[1]
        executable=shutil.which('node')
        if not executable:raise RuntimeError('Node is required for concurrency interoperability')
        self.process=subprocess.Popen([executable,str(root/'tests/employment-concurrency-native.cjs'),
            json.dumps(observation),json.dumps(manifest),json.dumps(market_policy.MARKET_POLICY)],
            cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8',bufsize=1)
        self.reader=ThreadPoolExecutor(max_workers=1)


class EmploymentConcurrencyIntegrationTests(unittest.TestCase):
    bind=paid_fixture.PaidEmploymentIntegrationTests.bind
    stock=paid_fixture.PaidEmploymentIntegrationTests.stock
    arrival=paid_fixture.PaidEmploymentIntegrationTests.arrival
    speech=paid_fixture.PaidEmploymentIntegrationTests.speech
    decide=paid_fixture.PaidEmploymentIntegrationTests.decide
    agree=paid_fixture.PaidEmploymentIntegrationTests.agree
    release_meeting=paid_fixture.PaidEmploymentIntegrationTests.release_meeting
    finish_native=paid_fixture.PaidEmploymentIntegrationTests.finish_native
    metrics=paid_fixture.PaidEmploymentIntegrationTests.metrics

    def setUp(self):
        paid_fixture.PaidEmploymentIntegrationTests.setUp(self)
        self.other=903
        row=copy.deepcopy(self.obs['residents'][0])
        row.update(id=self.other,baseId=1903,name='Third observed fixture resident',x=900)
        row['activity']['package_id']=9002
        self.obs['residents'].append(row)
        self.obs['resident_control']['activities'].append({'actor':self.other,'slot':2,
            'expectedPackage':9002,'ownedPackage':True,'mode':'go_to','target':999,'serial':1,'phase':'travelling'})
        # A second real census discovers the newcomer without replacing people.
        self.world.initialize_population('concurrent-newcomer','paid-seed',self.obs);self.bind()
        self.native=ConcurrentNativeProcess(self.obs,self.catalog);self.addCleanup(self.native.close)
        self.observe_controller(self.native.request('state'))
        self.initial_stock=self.stock()
        self.telemetry=EmploymentConcurrencyTelemetry()
        self.sample_time=0

    def observe_controller(self,view):
        self.obs['conversationAttendance']=copy.deepcopy(view.get('conversationAttendance'))
        paid_fixture.PaidEmploymentIntegrationTests.observe_controller(self,view)

    def sample_overlap(self,advance=5):
        # Explicit monotonic fixture time: these are paired-sample protocol
        # measurements, not elapsed gameplay or continuously audible seconds.
        self.sample_time+=advance
        return self.telemetry.observe(self.world.active,self.obs,now=self.sample_time)

    def start_work(self):
        command=self.agree()
        view=self.native.request('start',command=command,desired=self.world.paid_employment_status(),gameDays=self.obs['gameDays'])
        self.assertTrue(view['result']['ack']['accepted']);self.observe_controller(view)
        self.assertEqual(set(view['paid_employment']['account_reserved_actors']),{self.worker,self.employer})
        self.assertEqual(set(view['paid_employment']['activity_reserved_actors']),{self.worker})
        self.assertEqual(paid_work_activity_actors(self.world.active,self.obs),{self.worker})
        self.assertEqual(reserved_work_accounts(self.world.active,self.obs),
                         {'native-inventory:'+str(actor) for actor in (self.worker,self.employer)})
        self.assertEqual(view['calls'],[])
        first=self.sample_overlap(advance=0)
        self.assertTrue(first['jobs'][0]['employer_non_economic_eligible'])
        self.assertEqual(first['coverage']['qualified_attendance_intervals'],0)
        for channel in first['overlap'].values():
            self.assertEqual(channel['n'],0)
            self.assertIsNone(channel['sampled_overlap_seconds'])
        return view

    def social_choice(self,action):
        claim=self.world.claim_conversation('concurrent-chat',self.obs)['claim'];self.bind()
        self.world.finish_conversation_inference('concurrent-chat',claim['id'],{
            'model':'explicit-concurrency-decision-fixture','decision':{
                'action_id':action,'reason':'An authored offline social choice.','emotion':'calm'}},self.obs)
        self.bind()

    def say_social(self):
        claim=self.world.claim_conversation('concurrent-chat',self.obs)['claim'];self.bind()
        closing=claim['context']['event']['dialogue_stage']=='closing'
        candidates=[{'id':'option_1','intention':'Say goodbye' if closing else 'Enjoy the day',
                     'line':'Take care. See you around.' if closing else 'The air feels lovely today.', 'tone':'calm'},
                    {'id':'option_2','intention':'End politely' if closing else 'Make small talk',
                     'line':'Goodbye for now.' if closing else 'It is nice to have a quiet morning.', 'tone':'calm'}]
        self.world.finish_conversation_inference('concurrent-chat',claim['id'],{
            'model':'explicit-non-economic-speech-fixture','proposal':{'candidates':candidates}},self.obs);self.bind()
        self.social_choice('option_1')
        self.world.prepare_speech('concurrent-chat',AUDIO,self.obs);self.bind()
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'speak')
        self.obs['speech']={'id':command['id'],'status':'ended','playedSeconds':3.,'nearbyThroughout':True}
        self.world.observe(self.obs);self.bind()
        # Paid attendance samples continue while dialogue playback is observed.
        self.observe_controller(self.native.request('sample',desired=self.world.paid_employment_status()))
        self.sample_overlap()

    def chat_while_worker_attends(self):
        self.world.start_conversation('concurrent-chat',self.obs,max_turns=2);self.bind()
        self.assertEqual(self.world.conversation_status()['initiator'],self.employer)
        self.social_choice('approach_'+str(self.other))
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'walk_to')
        moving=self.native.request('move_start',command=command)
        self.assertEqual(moving['movement']['phase'],'travelling');self.assertFalse(moving['result']['done'])
        self.observe_controller(moving)
        stationary=self.sample_overlap()
        self.assertEqual(stationary['overlap']['employer_movement']['sampled_overlap_seconds'],0)
        arrived=self.native.request('move_arrive',command=command)
        self.assertEqual(arrived['result']['ack']['status'],'applied')
        self.assertTrue(arrived['result']['ack']['movement']['aliasesConfirmed'])
        self.observe_controller(arrived)
        moved=self.sample_overlap()
        self.assertEqual(moved['overlap']['employer_movement']['positive_intervals'],1)
        self.assertEqual(moved['overlap']['employer_movement']['sampled_overlap_seconds'],5)
        self.assertEqual(moved['overlap']['employer_movement']['sampled_overlap_game_minutes'],.5)
        rows={row['id']:row for row in self.obs['residents']}
        self.assertGreater(abs(rows[self.employer]['x']-rows[self.worker]['x']),300)
        self.social_choice('chat')
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'conversation_attend')
        attendance=self.native.request('social_attend',command=command)
        self.assertEqual(attendance['result']['ack']['status'],'applied')
        self.assertTrue(all(row['ownedPackage'] for row in attendance['conversationAttendance']['participants']))
        self.observe_controller(attendance)
        joining=self.sample_overlap()
        self.assertEqual(joining['overlap']['employer_conversation']['positive_intervals'],0,
                         'One owned endpoint cannot prove a paired conversation interval')
        for _ in range(2):self.say_social()
        overlap=self.telemetry.status(self.obs['session'],now=self.sample_time)
        self.assertEqual(overlap['coverage']['qualified_attendance_intervals'],5)
        self.assertEqual(overlap['overlap']['employer_movement']['positive_intervals'],1)
        self.assertEqual(overlap['overlap']['employer_conversation']['positive_intervals'],2)
        self.assertEqual(overlap['overlap']['employer_conversation']['sampled_overlap_seconds'],10)
        self.assertEqual(overlap['overlap']['employer_conversation']['sampled_overlap_game_minutes'],1)
        repeated=self.sample_overlap(advance=1)
        self.assertEqual(repeated['overlap'],overlap['overlap'],'Repeated observation must not inflate overlap')
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'release_routine')
        self.observe_controller(self.native.request('social_release',command=command))
        self.social_choice('felt_supported');self.social_choice('neutral')
        conversation=self.world.conversation_status()
        self.assertEqual(conversation['outcome'],'social_exchange_completed')
        self.assertEqual(len(conversation['turns']),2)
        self.assertEqual(self.stock(),self.initial_stock)
        view=self.native.request('state')
        job=view['paid_employment']['jobs'][0]
        self.assertEqual(job['phase'],'working')
        self.assertGreater(job['attendance']['worked_minutes'],0)
        self.assertEqual(view['calls'],[])
        return view

    def finish_paid(self):
        earned=self.native.request('earn',desired=self.world.paid_employment_status())
        self.assertEqual(earned['paid_employment']['receipts'][0]['phase'],'attendance_verified')
        self.observe_controller(earned)
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'inventory_paid_work_commit')
        effects=self.finish_native(command);self.assertEqual(effects['result']['ack']['status'],'applied')
        self.observe_controller(effects)
        self.observe_controller(self.native.request('release',desired=self.world.paid_employment_status()))
        ack=self.world.pending(self.obs['session']);self.assertEqual(ack['kind'],'paid_work_ack_receipt')
        self.observe_controller(self.native.request('ack',command=ack))
        self.metrics(output_verified=True,wage_paid=True,completed=True,released=True)
        self.assertEqual(len(self.world.active['production']),1)

    def test_employer_moves_and_chats_while_employee_attends_then_both_wage_legs_settle(self):
        self.start_work()
        before=copy.deepcopy(self.world.active)
        with self.assertRaises(ValueError):
            self.world.plan_trade('reserved-employer-purchase',self.obs,self.employer,self.other,
                                  quantity=1,unit_price=1,commodity='grain')
        self.assertEqual(self.world.active,before)
        # A fresh real employer review remains possible, but its inventory
        # reservation removes food consumption and rejects a stale model choice.
        self.world.begin_plan('reserved-employer-meal',self.obs,self.employer,'meal_time');self.bind()
        claim=self.world.claim_plan_decision('reserved-employer-meal',self.obs)['claim'];self.bind()
        self.assertNotIn('eat_bread',{row['id'] for row in claim['context']['options']})
        before=copy.deepcopy(self.world.active)
        with self.assertRaises(ValueError):
            self.world.finish_plan_decision('reserved-employer-meal',claim['id'],{
                'model':'explicit-concurrency-fixture','decision':{
                    'action_id':'eat_bread','reason':'Attempt reserved account mutation.','emotion':'calm'}},self.obs)
        self.assertEqual(self.world.active,before)
        self.world.finish_plan_decision('reserved-employer-meal',claim['id'],{
            'model':'explicit-concurrency-fixture','decision':{
                'action_id':'defer','reason':'Leave the reserved stock intact.','emotion':'calm'}},self.obs);self.bind()
        self.assertEqual(self.world.active.get('consumptions',[]),[])
        self.assertEqual(self.native.request('state')['calls'],[])
        self.chat_while_worker_attends()
        self.finish_paid()

    def test_worker_unloads_during_employer_social_activity_holds_without_economic_effects(self):
        self.start_work();self.chat_while_worker_attends()
        self.native.request('unload',actor=self.worker)
        view=self.native.request('sample',desired=self.world.paid_employment_status());self.observe_controller(view)
        self.assertEqual(view['paid_employment']['jobs'][0]['phase'],'held')
        self.assertEqual(view['calls'],[])
        self.assertEqual(self.world.active.get('production',[]),[])
        interrupted=self.sample_overlap()
        self.assertEqual(interrupted['coverage']['qualified_attendance_intervals'],5)
        self.assertEqual(interrupted['coverage']['excluded']['worker_attendance_not_paired'],1)

    def test_employer_identity_replacement_restores_conservative_physical_hold(self):
        self.start_work()
        self.native.request('replace_identity',actor=self.employer,baseId=999999)
        view=self.native.request('sample',desired=self.world.paid_employment_status());self.observe_controller(view)
        self.assertEqual(set(view['paid_employment']['activity_reserved_actors']),{self.worker,self.employer})
        self.assertEqual(view['paid_employment']['jobs'][0]['phase'],'held')
        self.assertEqual(view['calls'],[])
        self.assertEqual(self.world.active.get('production',[]),[])
        replaced=self.sample_overlap()
        self.assertEqual(replaced['coverage']['qualified_attendance_intervals'],0)
        self.assertIsNone(replaced['overlap']['employer_movement']['sampled_overlap_seconds'])

    def test_prepared_paid_admission_allows_employer_physical_activity_without_account_conflict(self):
        command=self.agree()
        view=self.native.request('start',command=command,desired=self.world.paid_employment_status(),
                                 gameDays=self.obs['gameDays'],blockedActors=[self.employer],blockedAccounts=[])
        self.assertTrue(view['result']['ack']['accepted'])
        self.assertEqual(view['result']['ack']['status'],'applied')
        self.assertEqual(view['calls'],[])
        self.observe_controller(view)
        self.assertEqual(paid_work_activity_actors(self.world.active,self.obs),{self.worker})
        self.assertEqual(set(view['paid_employment']['account_reserved_actors']),{self.worker,self.employer})
        self.finish_paid()


if __name__=='__main__':unittest.main()
