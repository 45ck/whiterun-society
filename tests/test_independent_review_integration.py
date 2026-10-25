"""Independent resident decisions beside a foreground conversation.

Real SQLite checkpoints, claim validation, native rest/owner controllers and
effect receipts; actor/form/alias/physics/audio boundaries remain offline mocks.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import test_fresh_livelihood_integration as fresh
from test_resource_protocol_interop import NativeResourceProcess
from test_conversation import authored_pair_scenario
from activity_leases import work_account_conflict


class IndependentReviewNativeProcess(NativeResourceProcess):
    def __init__(self,observation):
        executable=shutil.which('node')
        if not executable:raise RuntimeError('Node is required for independent-review interoperability')
        root=Path(__file__).resolve().parents[1]
        self.process=subprocess.Popen([executable,str(root/'tests/independent-review-native.cjs'),json.dumps(observation)],
            cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8',bufsize=1)
        self.reader=ThreadPoolExecutor(max_workers=1)


class IndependentReviewIntegrationTests(unittest.TestCase):
    bind=fresh.FreshLivelihoodIntegrationTests.bind
    stock=fresh.FreshLivelihoodIntegrationTests.stock
    prior=fresh.FreshLivelihoodIntegrationTests.prior

    def setUp(self):
        fresh.FreshLivelihoodIntegrationTests.setUp(self)
        for slot,actor in enumerate((903,904),2):
            row=copy.deepcopy(self.obs['residents'][0])
            row.update(id=actor,baseId=actor+1000,name='Independent fixture '+str(actor),x=slot*100)
            row['activity']['package_id']=9000+slot
            self.obs['residents'].append(row)
            self.obs['resident_control']['activities'].append({'actor':actor,'slot':slot,'expectedPackage':9000+slot,
                'ownedPackage':True,'mode':'go_to','target':999,'serial':1,'phase':'travelling'})
        self.world.initialize_population('independent-newcomers','fresh-livelihood-seed',self.obs);self.bind()
        self.owner=self.prior()
        self.first,self.second,self.rester=sorted(actor for actor in (901,902,903,904) if actor!=self.owner)
        self.world.configure_enterprise('independent-charter',{'id':'independent-bakery','expected_revision':0,
            'name':'Authored independent bakery','custodian':self.owner,'capabilities':['bread_recipe'],'active':True,
            'recipe_policies':{'bread_recipe':{'target_bread':8,'wage_gold':2,'grain_per_shift':1,
                'bread_per_shift':2,'work_minutes':30}}},self.obs);self.bind()
        self.obs['resident_control'].update(available=True,goal_destinations=True)
        self.native=IndependentReviewNativeProcess(self.obs);self.addCleanup(self.native.close)
        self.observe_native(self.native.request('state'))
        self.world.configure_resident_control('independent-control',True,self.obs);self.bind()
        self.initial_stock=self.stock()
        self.world.start_scenario_conversation('foreground-chat',self.obs,
            authored_pair_scenario(self.first,self.second,identifier='independent-foreground-fixture'));self.bind()
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'walk_to')
        view=self.native.request('chat_start',command=command)
        self.assertEqual(view['result']['ack']['status'],'applied')
        self.observe_native(view)
        self.assertEqual(self.world.conversation_status()['phase'],'propose')
        self.foreground=copy.deepcopy(self.world.conversation_status())

    def observe_native(self,view):
        for key in ('gameDays','owner_work_jobs','activity_jobs','rest','economy_catalog','resident_control','residents'):
            self.obs[key]=copy.deepcopy(view[key])
        if (view.get('result') or {}).get('ack'):self.obs['ack']=copy.deepcopy(view['result']['ack'])
        else:self.obs.pop('ack',None)
        self.world.observe(self.obs);self.bind()

    def queue_goal_reviews(self,owner_focus='work'):
        wave=self.world.claim_resident_goals('independent-goal-wave',self.obs)['wave'];self.bind()
        self.assertEqual({m['actor'] for m in wave['members']},{self.rester,self.owner})
        result=self.world.finish_resident_goals('independent-goal-wave',wave['claim_id'],[
            {'actor':member['actor'],'result':{'model':'test-independent-goal-fixture','decision':{
                'action_id':'review_rest' if member['actor']==self.rester else 'review_'+owner_focus,
                'reason':'An explicit fixture personal goal while other residents talk.','emotion':'calm'}}}
            for member in wave['members']],self.obs);self.bind()
        self.assertTrue(all(row['accepted'] for row in result['results']),result)
        self.assertEqual(self.world.conversation_status(),self.foreground)
        self.sources={actor:self.world.active['people'][str(actor)]['standing_goal']['follow_through']['event_id']
                      for actor in (self.rester,self.owner)}

    def claim_reviews(self,owner_focus='work'):
        self.queue_goal_reviews(owner_focus)
        wave=self.world.claim_independent_reviews('independent-decisions',self.obs)['wave'];self.bind()
        self.assertEqual({m['actor'] for m in wave['members']},{self.rester,self.owner})
        self.assertEqual(self.world.conversation_status(),self.foreground)
        return wave

    def decisions(self,wave,owner_rest=False):
        result=[]
        for member in wave['members']:
            prefix='rest_' if member['actor']==self.rester or owner_rest else 'owner_'
            action=next(option['id'] for option in member['context']['options'] if option['id'].startswith(prefix))
            result.append({'actor':member['actor'],'result':{'model':'test-independent-review-fixture',
                'decision':{'action_id':action,'reason':'Choose an eligible bounded activity.','emotion':'calm'}}})
        return result

    def finish_reviews(self,wave,results):
        result=self.world.finish_independent_reviews('independent-decisions',wave['claim_id'],results,self.obs)
        self.bind();self.assertEqual(self.world.conversation_status(),self.foreground)
        return result

    def start_jobs(self):
        for _ in range(4):
            command=self.world.pending(self.obs['session'])
            if not command:break
            if command['kind'] not in ('activity_start_rest','owner_work_start'):break
            view=self.native.request('rest_start' if command['kind']=='activity_start_rest' else 'start',command=command,
                desired=self.world.owner_work_status(),restDesired=self.world.activity_status(),gameDays=self.obs['gameDays'])
            self.assertTrue(view['result']['ack']['accepted'],view['result']);self.observe_native(view)
        view=self.native.request('state')
        self.assertEqual(len(view['activity_jobs']['jobs']),1)
        self.assertEqual(len(view['owner_work_jobs']['jobs']),1)
        self.assertEqual(self.world.conversation_status(),self.foreground)
        self.assertEqual(view['calls'],[])

    def test_real_independent_rest_and_owner_work_preserve_foreground_and_serialize_effects(self):
        wave=self.claim_reviews();results=self.decisions(wave)
        self.assertTrue(self.world.claim_independent_reviews('independent-decisions',self.obs)['duplicate'])
        with self.assertRaises(ValueError):self.world.claim_independent_reviews('overlapping-claim',self.obs)
        finished=self.finish_reviews(wave,results)
        self.assertTrue(all(row['accepted'] for row in finished['results']),finished)
        before=copy.deepcopy(self.world.active)
        with self.assertRaises(ValueError):self.world.finish_independent_reviews('independent-decisions',wave['claim_id'],results,self.obs)
        self.assertEqual(self.world.active,before)
        self.assertEqual(self.world.active.get('plans',[]),[],'Independent decisions must not replace the foreground plan store')
        self.start_jobs()
        fatigue=self.world.active['people'][str(self.rester)]['needs']['fatigue']
        earned=self.native.request('earn',desired=self.world.owner_work_status(),restDesired=self.world.activity_status())
        self.assertEqual(earned['calls'],[])
        self.assertEqual(earned['activity_jobs']['receipts'][0]['status'],'applied')
        self.assertTrue(earned['activity_jobs']['receipts'][0]['rest']['exact_furniture_verified'])
        self.assertEqual(earned['owner_work_jobs']['receipts'][0]['phase'],'attendance_verified')
        self.observe_native(earned)
        self.assertEqual(self.world.conversation_status(),self.foreground)
        self.assertIsNone(self.world.active['pending'],'Owner effects must wait while foreground conversation owns execution')
        self.assertEqual(self.stock(),self.initial_stock)
        self.assertEqual(len(self.world.active['rests']),1)
        self.assertLess(self.world.active['people'][str(self.rester)]['needs']['fatigue'],fatigue)
        self.assertEqual(self.world.active['independent_reviews'][self.sources[self.rester]]['phase'],'complete')
        self.assertEqual(self.world.active['independent_plans'][self.sources[self.owner]]['phase'],'delegated')
        ack=self.world.pending(self.obs['session']);self.assertEqual(ack['kind'],'activity_ack_receipt')
        self.observe_native(self.native.request('rest_ack',command=ack))
        self.world.hold_conversation('foreground-chat','Explicit fixture ends the foreground exchange.',self.obs);self.bind()
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'release_routine')
        self.observe_native(self.native.request('chat_release',command=command))
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'inventory_self_produce_commit')
        for _ in range(5):
            produced=self.native.request('commit',command=command)
            if produced['result']['done']:break
        else:self.fail('Actual owner production did not finish within five frames')
        self.assertEqual(produced['result']['ack']['status'],'applied')
        self.assertEqual(produced['calls'],[{'actor':self.owner,'item':'grain','amount':-1},
                                          {'actor':self.owner,'item':'bread','amount':2}])
        self.observe_native(produced)
        replay=self.native.request('commit',command=command);self.assertEqual(replay['calls'],produced['calls'])
        self.observe_native(replay);self.assertEqual(len(self.world.active['production']),1)
        self.observe_native(self.native.request('release',desired=self.world.owner_work_status(),restDesired=self.world.activity_status()))
        ack=self.world.pending(self.obs['session']);self.assertEqual(ack['kind'],'owner_work_ack_receipt')
        self.observe_native(self.native.request('ack',command=ack))
        self.assertEqual(self.world.active['independent_reviews'][self.sources[self.owner]]['phase'],'complete')
        for event in self.world.active['town']['daily']['queue']:
            if event['id'] in self.sources.values():self.assertEqual(event['status'],'complete')
        self.assertEqual(len(self.world.active['rests']),1)

    def test_competing_seat_choices_cannot_create_two_native_seat_leases(self):
        wave=self.claim_reviews(owner_focus='rest')
        result=self.finish_reviews(wave,self.decisions(wave,owner_rest=True))
        self.assertTrue(all(row['accepted'] for row in result['results']))
        jobs=list(self.world.active.get('activity_jobs',{}).values())
        self.assertEqual(len(jobs),1)
        records=list(self.world.active['independent_reviews'].values())
        self.assertEqual(sorted(row['phase'] for row in records),['delegated','held'])
        self.assertEqual(self.native.request('state')['calls'],[])
        self.assertEqual(self.world.conversation_status(),self.foreground)

    def test_changed_identity_rejects_only_that_resident_without_foreground_mutation(self):
        wave=self.claim_reviews();results=self.decisions(wave)
        view=self.native.request('replace_identity',actor=self.owner,baseId=999999)
        self.observe_native(view)
        result=self.finish_reviews(wave,results)
        by_actor={row['actor']:row for row in result['results']}
        self.assertFalse(by_actor[self.owner]['accepted']);self.assertTrue(by_actor[self.rester]['accepted'])
        self.assertNotIn(self.sources[self.owner],self.world.active.get('independent_plans',{}))
        self.assertEqual(self.world.active.get('work_jobs',{}),{})
        self.assertEqual(self.native.request('state')['calls'],[])

    def test_live_owner_attendance_reserves_inventory_against_competing_purchase(self):
        wave=self.claim_reviews();self.finish_reviews(wave,self.decisions(wave));self.start_jobs()
        self.world.hold_conversation('foreground-chat','End fixture chat before testing the inventory lease.',self.obs);self.bind()
        command=self.world.pending(self.obs['session']);self.assertEqual(command['kind'],'release_routine')
        self.observe_native(self.native.request('chat_release',command=command))
        self.assertFalse(self.world.conversation_busy())
        self.assertIsNone(self.world.active['pending'])
        self.assertTrue(work_account_conflict(self.world.active,actors=(self.owner,),observation=self.obs))
        before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'independent activity lease|inventory account is reserved'):
            self.world.plan_trade('competing-owner-purchase',self.obs,self.owner,self.first,
                                  quantity=1,unit_price=1,commodity='grain')
        self.assertEqual(self.world.active,before)
        self.assertEqual(self.stock(),self.initial_stock)
        self.assertEqual(self.native.request('state')['calls'],[])


if __name__=='__main__':unittest.main()
