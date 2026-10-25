"""Fresh service checkpoints and real JS paid-work controllers, fake native APIs.

Starting stock, livelihood knowledge and model decisions are explicitly authored
test inputs. Attendance and economic receipts come from the actual controller.
This is protocol interoperability evidence, not an in-game labour demonstration.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import economy_catalog as catalog
import livelihood_backgrounds
import market_policy
from paid_employment_metrics import paid_employment_metrics
from agency_metrics import account_cashflow
from lineage import TimelineEconomy
from catalog_fixture import native_catalog
from test_catalog_enterprises import expanded_catalog
from test_resource_protocol_interop import NativeResourceProcess
import test_fresh_livelihood_integration as fresh_livelihood
from trade_execution_fixture import qualify_trade_observation


class PaidNativeProcess(NativeResourceProcess):
    def __init__(self, observation, manifest):
        executable=shutil.which('node')
        if not executable:raise RuntimeError('Node is required for paid-work interoperability proof')
        root=Path(__file__).resolve().parents[1]
        self.process=subprocess.Popen([executable,str(root/'tests/paid-employment-native.cjs'),
            json.dumps(observation),json.dumps(manifest),json.dumps(market_policy.MARKET_POLICY)],cwd=root,stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1)
        self.reader=ThreadPoolExecutor(max_workers=1)


class PaidEmploymentIntegrationTests(unittest.TestCase):
    bind=fresh_livelihood.FreshLivelihoodIntegrationTests.bind
    stock=fresh_livelihood.FreshLivelihoodIntegrationTests.stock

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.catalog=expanded_catalog()
        mock=patch.object(catalog,'ECONOMY_CATALOG',self.catalog);mock.start();self.addCleanup(mock.stop)
        policy=copy.deepcopy(market_policy.MARKET_POLICY);policy['catalog_hash']=catalog.catalog_hash()
        mock=patch.object(market_policy,'MARKET_POLICY',policy);mock.start();self.addCleanup(mock.stop)
        self.world=TimelineEconomy(Path(self.temp.name)/'paid.sqlite');self.addCleanup(self.world.db.close)
        self.obs={'session':'paid-native-interop','checkpoint':0,'ready':True,'gameDays':4.5,
            'economy_catalog':native_catalog(),'routing':{'available':True,'adapter':'papyrus-mailbox-v1'},
            'residents':[{'id':actor,'baseId':actor+1000,'name':'Paid fixture '+str(actor),
                'isPerson':True,'isChild':False,'isDead':False,'loaded':True,'x':index*100,'y':0,'z':0,'cell_id':77,
                'inventory':{'gold':8,'bread':1,'grain':3,'ore':4,'ingot':0},
                'activity':{'package_id':9000+index,'scene_id':0,'in_combat':False,'sleep_state':0}}
                for index,actor in enumerate((901,902))],
            'resident_control':{'activities':[{'actor':actor,'slot':index,'expectedPackage':9000+index,
                'ownedPackage':True,'mode':'go_to','target':999,'serial':1,'phase':'travelling'}
                for index,actor in enumerate((901,902))]}}
        qualify_trade_observation(self.obs)
        self.native=PaidNativeProcess(self.obs,self.catalog);self.addCleanup(self.native.close)
        view=self.native.request('state')
        self.obs['paid_employment']=view['paid_employment'];self.obs['economy_catalog']=view['economy_catalog']
        self.obs['trade_execution']=view['trade_execution']
        self.world.observe(self.obs);self.world.bootstrap(self.obs);self.bind()
        self.assertEqual(self.world.active['people'],{})
        self.world.initialize_population('paid-census','paid-seed',self.obs);self.bind()
        self.assertEqual(set(self.world.active['people']),{'901','902'})
        self.assertEqual(self.world.active['town']['businesses'],{})
        manifest={'schema_version':1,'id':'paid-prior','catalog_hash':catalog.catalog_hash(),
            'selection':'ranked_initial_cohort_v1','rules':[{'id':'fixture-metal-prior','recipe_id':'metal_recipe',
                'recipe_hash':catalog.recipe_hash('metal_recipe'),'recipient_count':1}],
            'provenance':'Explicit offline fixture knowledge, not observed skill or game assets.'}
        path=Path(self.temp.name)/'background.json';path.write_text(json.dumps(manifest),encoding='utf-8')
        mock=patch.object(livelihood_backgrounds,'DEFAULT_PATH',path);mock.start();self.addCleanup(mock.stop)
        result=self.world.establish_livelihood_background('paid-prior','paid-seed',manifest['id'],
            livelihood_backgrounds.livelihood_manifest_hash(manifest),[901,902],self.obs);self.bind()
        self.employer=result['background']['assignments'][0]['actor']
        self.worker=next(actor for actor in (901,902) if actor!=self.employer)
        self.business='fixture-metal-charter'
        self.world.configure_enterprise('paid-charter',{'id':self.business,'expected_revision':0,
            'name':'Authored metal fixture','custodian':self.employer,'capabilities':['metal_recipe'],'active':True,
            'recipe_policies':{'metal_recipe':{'target_output':8,'wage_gold':3,'work_minutes':12}}},self.obs)
        self.bind();self.initial_stock=self.stock();self.events={}

    def observe_controller(self, view):
        for key in ('gameDays','paid_employment','trade_execution','economy_catalog','resident_control','residents'):
            self.obs[key]=copy.deepcopy(view[key])
        if (view.get('result') or {}).get('ack'):self.obs['ack']=copy.deepcopy(view['result']['ack'])
        else:self.obs.pop('ack',None)
        self.world.observe(self.obs);self.bind()

    def metrics(self, **expected_stages):
        result=paid_employment_metrics(self.world.active,self.obs,fresh=True)
        self.assertEqual(result['retained_jobs'],1)
        for stage,expected in expected_stages.items():
            self.assertEqual(result['jobs'][0]['stages'][stage],expected,(stage,result))
            self.assertEqual(result['stages'][stage],{
                'success':int(expected is True),'n':int(expected is not None),
                'unknown':int(expected is None),'percent':None if expected is None else 100. if expected else 0.})
        self.assertEqual(result['provenance_counts'],{'controlled_fixture':1})
        self.assertNotIn('attendance_token',json.dumps(result))
        return result

    def arrival(self):
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'walk_to')
        self.obs['ack']={'id':command['id'],'status':'applied','movement':{
            'hasOwnedPackage':True,'expectedPackage':9000+(901,902).index(self.worker),
            'aliasesConfirmed':True,'adapter':'papyrus-mailbox','actor':self.worker,'target':self.employer}}
        self.world.observe(self.obs);self.bind()

    def speech(self):
        """Authored audio playback observation; paid economic effects are never mocked."""
        command=self.world.pending(self.obs['session'])
        if command and command['kind']=='conversation_attend':
            self.obs['conversationAttendance']={'id':command['id'],'phase':'attending','participants':[
                {'actor':actor,'ownedPackage':True,'loaded':True} for actor in command['participants']]}
            self.obs['ack']={'id':command['id'],'status':'applied'};self.world.observe(self.obs);self.bind()
        audio={'file':'a'*64+'.wav','sha256':'a'*64,'seconds':2,'voice':'bf_emma','engine':'kokoro-onnx-0.6.1'}
        self.world.prepare_trade_speech(self.event,audio,self.obs);self.bind()
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'speak')
        self.obs['speech']={'id':command['id'],'status':'ended','playedSeconds':2,'nearbyThroughout':True}
        self.world.observe(self.obs);self.bind()
        return command

    def decide(self, action):
        claim=self.world.claim_plan_decision(self.event,self.obs)['claim'];self.bind()
        self.assertIn(action,{row['id'] for row in claim['context']['options']})
        self.world.finish_plan_decision(self.event,claim['id'],{'model':'explicit-offline-paid-fixture',
            'decision':{'action_id':action,'reason':'Explicit authored test decision.','emotion':'calm'}},self.obs)
        self.bind()

    def agree(self):
        self.event='paid-encounter'
        self.world.begin_plan(self.event,self.obs,self.worker,'work_shift',voiced_trade=True);self.bind()
        self.arrival();self.speech()
        self.decide('offer_shift');offer=self.speech()
        self.assertIn('ore',offer['line']);self.assertIn('ingot',offer['line'])
        self.decide('take_shift');self.speech()
        if self.world.pending(self.obs['session'])['kind']=='release_routine':
            self.release_meeting()
        self.arrival()
        if self.world.pending(self.obs['session'])['kind']=='release_routine':
            self.release_meeting()
        command=self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'],'paid_work_start')
        self.assertEqual(command['recipe_id'],'metal_recipe')
        self.assertEqual(self.stock(),self.initial_stock)
        return command

    def release_meeting(self):
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'release_routine')
        self.obs['conversationAttendance']=None
        self.obs['ack']={'id':command['id'],'status':'applied','released':True}
        self.world.observe(self.obs);self.bind()

    def permit(self):
        command=self.agree()
        started=self.native.request('start',command=command,desired=self.world.paid_employment_status(),gameDays=self.obs['gameDays'])
        self.assertTrue(started['result']['ack']['accepted'],started['result']);self.assertEqual(started['calls'],[])
        self.observe_controller(started)
        attended=self.native.request('earn',desired=self.world.paid_employment_status())
        self.assertEqual(attended['calls'],[])
        self.assertEqual(attended['paid_employment']['receipts'][0]['phase'],'attendance_verified')
        for key in ('gameDays','paid_employment','economy_catalog','resident_control','residents'):
            self.obs[key]=copy.deepcopy(attended[key])
        self.obs.pop('ack',None);self.world.observe(self.obs)
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'bind_checkpoint',
                         'Attendance cannot immediately authorize an unbound inventory command')
        self.bind()
        command=self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'],'inventory_paid_work_commit')
        self.assertFalse(self.world.active['people'][str(self.worker)].get('known_recipes'))
        self.assertEqual(self.world.active.get('production',[]),[])
        self.metrics(offered=True,accepted=True,attendance_qualified=True,output_verified=None,wage_paid=None,completed=False)
        self.assertEqual(account_cashflow(self.world.active)['accounts'],[])
        return command

    def finish_native(self, command):
        for _ in range(8):
            view=self.native.request('commit',command=command)
            if view['result']['done']:return view
        self.fail('Paid native execution exceeded eight offline frames')

    def assert_paid_cashflow(self):
        command=self.permit();view=self.finish_native(command)
        ack=view['result']['ack'];self.assertEqual(ack['status'],'applied',ack)
        self.assertTrue(ack['output_verified']);self.assertTrue(ack['wages_verified'])
        recipe=catalog.recipe_spec('metal_recipe')
        self.assertEqual([leg['leg'] for leg in ack['legs']],
                         ['input']*len(recipe['inputs'])+['output']*len(recipe['outputs'])+['wage_debit','wage_credit'])
        self.assertTrue(all(leg['issued'] and leg['observed'] for leg in ack['legs']))
        expected_calls=[{'actor':self.employer,'item':item,'amount':-amount} for item,amount in recipe['inputs'].items()]
        expected_calls += [{'actor':self.employer,'item':item,'amount':amount} for item,amount in recipe['outputs'].items()]
        expected_calls += [
            {'actor':self.employer,'item':'gold','amount':-3},
            {'actor':self.worker,'item':'gold','amount':3}]
        self.assertEqual(view['calls'],expected_calls)
        self.observe_controller(view)
        expected=copy.deepcopy(self.initial_stock)
        for item,amount in recipe['inputs'].items():expected[str(self.employer)][item]-=amount
        for item,amount in recipe['outputs'].items():expected[str(self.employer)][item]+=amount
        expected[str(self.employer)]['gold']=5;expected[str(self.worker)]['gold']=11
        self.assertEqual(self.stock(),expected)
        self.assertEqual(len(self.world.active['production']),1)
        self.assertFalse(self.world.active['people'][str(self.worker)].get('known_recipes'),
                         'Observed economic effects alone do not prove released contract completion')
        effects=self.metrics(output_verified=True,wage_paid=True,completed=False,released=None)
        self.assertEqual(effects['committed_wage_gold'],3)
        self.assertEqual(effects['committed_output_goods'],{'ingot':1})
        cash=account_cashflow(self.world.active)
        self.assertEqual(cash['recognized_record_kinds'],{'inventory_paid_work_commit':1})
        accounts={row['actor']:row for row in cash['accounts']}
        self.assertEqual(accounts[self.worker]['wages_received'],3)
        self.assertEqual(accounts[self.employer]['wages_paid'],3)
        self.assertEqual(accounts[self.employer]['production_events'],1)
        replay=self.native.request('commit',command=command);self.assertEqual(replay['calls'],view['calls'])
        self.observe_controller(replay);self.assertEqual(len(self.world.active['production']),1)
        released=self.native.request('release',desired=self.world.paid_employment_status());self.observe_controller(released)
        self.assertIn('metal_recipe',self.world.active['people'][str(self.worker)]['known_recipes'])
        learning=copy.deepcopy(self.world.active['people'][str(self.worker)]['known_recipes'])
        self.observe_controller(released)
        self.assertEqual(self.world.active['people'][str(self.worker)]['known_recipes'],learning)
        self.assertEqual(len(self.world.active['production']),1)
        complete=self.metrics(offered=True,accepted=True,attendance_qualified=True,
                              output_verified=True,wage_paid=True,completed=True,released=True,held=False)
        self.assertEqual(complete['committed_wage_gold'],3)
        self.assertEqual(complete['committed_output_goods'],{'ingot':1})
        self.assertEqual(complete['partial_effects']['observed_output_goods'],{})
        self.assertEqual(account_cashflow(self.world.active),cash)
        release_ack=self.world.pending(self.obs['session']);self.assertEqual(release_ack['kind'],'paid_work_ack_receipt')
        self.observe_controller(self.native.request('ack',command=release_ack))
        self.assertFalse(self.world.paid_employment_status()['jobs'])
        self.purchase_with_earned_wages(len(expected_calls),expected)

    def test_generic_job_attendance_effects_wages_learning_and_replay(self):
        self.assert_paid_cashflow()

    def purchase_with_earned_wages(self,paid_calls,paid_stock):
        # Explicit operator trade fixture, not an invented second agent choice.
        # The price exceeds the worker's initial purse, so witnessed wages matter.
        self.assertLess(self.initial_stock[str(self.worker)]['gold'],9)
        self.world.plan_trade('earned-wage-purchase',self.obs,self.worker,self.employer,
                              quantity=1,unit_price=9,commodity='grain')
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'bind_checkpoint');self.bind()
        arm=self.world.pending(self.obs['session']);self.assertEqual(arm['phase'],'arm')
        armed=self.native.request('trade',command=arm)
        self.assertEqual(armed['result']['ack']['phase'],'armed');self.assertEqual(len(armed['calls']),paid_calls)
        self.observe_controller(armed)
        command=self.world.pending(self.obs['session']);self.assertEqual(command['phase'],'deliver')
        for _ in range(5):
            delivered=self.native.request('trade',command=command)
            if delivered['result']['done']:break
        else:self.fail('Earned-wage purchase did not finish in five native frames')
        self.assertEqual(delivered['result']['ack']['phase'],'complete')
        self.observe_controller(delivered)
        self.assertEqual(len(self.world.active['trades']),1)
        self.assertEqual(self.stock()[str(self.worker)]['gold'],2)
        self.assertEqual(self.stock()[str(self.employer)]['gold'],14)
        self.assertEqual(self.stock()[str(self.worker)]['grain'],paid_stock[str(self.worker)]['grain']+1)
        self.assertEqual(self.stock()[str(self.employer)]['grain'],paid_stock[str(self.employer)]['grain']-1)
        self.assertEqual(sum(row['gold'] for row in self.stock().values()),16)
        replay=self.native.request('trade',command=command)
        self.assertEqual(replay['calls'],delivered['calls']);self.observe_controller(replay)
        self.assertEqual(len(self.world.active['trades']),1)
        cash=account_cashflow(self.world.active)
        self.assertEqual(cash['recognized_record_kinds'],{'inventory_paid_work_commit':1,'inventory_trade':1})
        accounts={row['actor']:row for row in cash['accounts']}
        self.assertEqual((accounts[self.worker]['wages_received'],accounts[self.worker]['purchases_paid']),(3,9))
        self.assertEqual((accounts[self.employer]['wages_paid'],accounts[self.employer]['sales_receipts']),(3,9))
        self.assertEqual(cash['observed_transfer_balance_septims'],0)
        self.assertIsNone(cash['profit'])

    def test_partial_wage_is_visible_held_and_does_not_teach_recipe(self):
        command=self.permit();self.native.request('drop_credit')
        for _ in range(4):view=self.native.request('commit',command=command)
        self.assertFalse(view['result']['done']);self.assertEqual(len(view['calls']),4)
        self.native.request('advance_clock',milliseconds=6001)
        held=self.native.request('commit',command=command)
        self.assertEqual(held['result']['ack']['status'],'held')
        self.assertTrue(held['result']['ack']['output_verified']);self.assertFalse(held['result']['ack']['wages_verified'])
        self.observe_controller(held)
        self.assertEqual(self.world.active.get('production',[]),[])
        self.assertFalse(self.world.active['people'][str(self.worker)].get('known_recipes'))
        self.assertEqual(self.world.active['pending']['status'],'held')
        metrics=self.metrics(output_verified=True,wage_paid=False,completed=False,held=True)
        self.assertEqual(metrics['committed_wage_gold'],0)
        self.assertEqual(metrics['committed_output_goods'],{})
        self.assertEqual(metrics['partial_effects'],{'output_verified_without_commit':1,
            'wage_debit_without_verified_credit':1,'wages_verified_without_commit':0,'observed_output_goods':{'ingot':1}})
        cash=account_cashflow(self.world.active)
        self.assertEqual(cash['accounts'],[]);self.assertEqual(cash['recognized_record_kinds'],{})
        self.assertIsNone(cash['observed_transfer_balance_septims'])
        expected=copy.deepcopy(self.initial_stock)
        expected[str(self.employer)].update(ore=2,ingot=1,gold=5)
        self.assertEqual(self.stock(),expected,'Unpaid output remains physical and cannot be called a complete contract')
        replay=self.native.request('commit',command=command);self.assertEqual(replay['calls'],held['calls'])

    def test_reset_after_issued_input_cannot_replay_or_award_output(self):
        command=self.permit();first=self.native.request('commit',command=command)
        self.assertEqual(first['calls'],[{'actor':self.employer,'item':'ore','amount':-2}])
        self.native.request('reset')
        held=self.native.request('commit',command=command)
        self.assertEqual(held['result']['ack']['status'],'held');self.assertEqual(held['calls'],first['calls'])
        self.observe_controller(held)
        self.assertEqual(self.world.active.get('production',[]),[])
        self.assertFalse(self.world.active['people'][str(self.worker)].get('known_recipes'))

    def test_replaced_employer_before_first_effect_cannot_spend(self):
        command=self.permit()
        self.native.request('replace_identity',actor=self.employer,baseId=900000)
        held=self.native.request('commit',command=command)
        self.assertEqual(held['result']['ack']['status'],'held');self.assertEqual(held['calls'],[])
        self.observe_controller(held)
        self.assertEqual(self.world.active.get('production',[]),[])

    def test_cold_controller_loses_permit_without_reconstructing_existing_input_debit(self):
        command=self.permit();first=self.native.request('commit',command=command)
        self.assertEqual(first['calls'],[{'actor':self.employer,'item':'ore','amount':-2}])
        # Replace the actual JS controller while keeping native actors, purses,
        # mailbox, elapsed game clock and already applied input debit intact.
        cold=self.native.request('cold_restart',desired=self.world.paid_employment_status())
        self.assertNotEqual(cold['paid_employment']['epoch'],command['epoch'])
        held=self.native.request('commit',command=command)
        self.assertEqual(held['result']['ack']['status'],'held')
        self.assertEqual(held['calls'],first['calls'])
        self.observe_controller(held)
        self.assertEqual(self.world.active.get('production',[]),[])
        self.assertFalse(self.world.active['people'][str(self.worker)].get('known_recipes'))
        self.assertEqual(self.world.active['pending']['status'],'held')

    def test_native_blocked_start_holds_service_instead_of_retrying_admission(self):
        command=self.agree()
        rejected=self.native.request('start',command=command,desired=self.world.paid_employment_status(),
                                     gameDays=self.obs['gameDays'],blockedActors=[self.employer])
        self.assertFalse(rejected['result']['ack']['accepted'])
        self.assertEqual(rejected['result']['ack']['status'],'held')
        self.assertEqual(rejected['calls'],[])
        self.observe_controller(rejected)
        self.assertNotEqual((self.world.pending(self.obs['session']) or {}).get('kind'),'paid_work_start')
        self.assertEqual(self.world.active.get('production',[]),[])
        self.metrics(accepted=True,attendance_qualified=None,output_verified=None,wage_paid=None,completed=False,held=True)
        self.observe_controller(self.native.request('state'))
        self.assertNotEqual((self.world.pending(self.obs['session']) or {}).get('kind'),'paid_work_start')
        self.assertEqual(account_cashflow(self.world.active)['accounts'],[])


if __name__=='__main__':unittest.main()
