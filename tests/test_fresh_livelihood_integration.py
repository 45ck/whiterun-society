"""Fresh save → authored prior → resident choices, with no legacy population.

Every decision is an explicit offline model fixture. Observed starting stock is
test input, never an effect of census, background assignment, or registration.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from lineage import TimelineEconomy
from catalog_fixture import native_catalog
from trade_execution_fixture import qualify_trade_observation
from livelihood_backgrounds import load_livelihood_manifest, livelihood_manifest_hash, authored_prior_status
from entrepreneurship import enterprise_choices, knows_recipe
from procurement import input_procurement
from owner_production import owner_work_opportunities
from resident_identity import resident_identity_status
from agency import owner_work_choice_id
from test_resource_protocol_interop import NativeResourceProcess


class FreshOwnerProcess(NativeResourceProcess):
    """Use existing bounded JSON process transport with real JS controllers."""
    def __init__(self,observation):
        executable=shutil.which('node')
        if not executable:raise RuntimeError('Node is required for fresh livelihood integration proof')
        root=Path(__file__).resolve().parents[1]
        self.process=subprocess.Popen([executable,str(root/'tests/fresh-livelihood-native.cjs'),json.dumps(observation)],
            cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1)
        self.reader=ThreadPoolExecutor(max_workers=1)


class FreshLivelihoodIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.world=TimelineEconomy(Path(self.temp.name)/'fresh.sqlite');self.addCleanup(self.world.db.close)
        self.obs={'session':'fresh-livelihood','checkpoint':0,'ready':True,'gameDays':4.5,
            'economy_catalog':native_catalog(),'routing':{'available':True,'adapter':'papyrus-mailbox-v1'},
            'residents':[{'id':actor,'baseId':actor+1000,'name':'Fixture resident '+str(actor),
                'isPerson':True,'isChild':False,'isDead':False,'loaded':True,'x':index*100,'y':0,'z':0,
                'inventory':{'gold':8,'bread':0,'grain':3},
                'activity':{'package_id':9000+index,'scene_id':0,'in_combat':False,'sleep_state':0}}
                for index,actor in enumerate((901,902))],
            'resident_control':{'activities':[{'actor':actor,'slot':index,'expectedPackage':9000+index,
                'ownedPackage':True,'mode':'go_to','target':999,'serial':1,'phase':'travelling'}
                for index,actor in enumerate((901,902))]},
            'owner_work_jobs':{'available':True,'capacity':4,'jobs':[],'receipts':[]}}
        qualify_trade_observation(self.obs)
        self.initial_stock=self.stock()
        self.world.observe(self.obs);self.world.bootstrap(self.obs);self.bind()
        self.assertEqual(self.world.active['people'],{})
        self.world.initialize_population('fresh-census','fresh-livelihood-seed',self.obs);self.bind()
        self.assertEqual(set(self.world.active['people']),{'901','902'})
        self.assertEqual(self.world.active['town']['businesses'],{})
        self.manifest=load_livelihood_manifest()
        self.manifest_hash=livelihood_manifest_hash(self.manifest)
        self.events={}

    def stock(self):
        return {str(row['id']):copy.deepcopy(row['inventory']) for row in self.obs['residents']}

    def bind(self):
        for _ in range(12):
            if not self.world.transition:
                self.assertIsNone(self.world.error);return
            self.obs['checkpoint']=self.world.transition['next'];self.obs.pop('ack',None)
            self.world.observe(self.obs)
        self.fail('Fresh livelihood checkpoint loop exceeded bound')

    def prior(self):
        result=self.world.establish_livelihood_background('founding-prior','fresh-livelihood-seed',
            self.manifest['id'],self.manifest_hash,[r['id'] for r in self.obs['residents']],self.obs)
        self.bind()
        assignments=result['background']['assignments'];self.assertEqual(len(assignments),1)
        return assignments[0]['actor']

    def claim(self,actor,event,kind='need_review'):
        # Advance the observed fixture game clock so the real daily scheduler
        # can offer a fresh livelihood review; no event is inserted directly.
        due=self.world.active['people'][str(actor)]['agency']['next_review_day']
        self.obs['gameDays']=max(self.obs['gameDays']+16/1440,due+1/1440)
        self.world.review_population(self.obs);self.bind()
        queued=next(row for row in self.world.active['town']['daily']['queue']
                    if row['actor']==actor and (kind is None or row['kind']==kind) and row['status']=='pending')
        self.events[event]=queued['id']
        self.world.begin_plan(queued['id'],self.obs,actor,queued['kind']);self.bind()
        claim=self.world.claim_plan_decision(queued['id'],self.obs)['claim'];self.bind()
        return claim

    def choose(self,event,claim,action):
        self.assertIn(action,{row['id'] for row in claim['context']['options']})
        result=self.world.finish_plan_decision(self.events[event],claim['id'],{'model':'offline-livelihood-fixture',
            'decision':{'action_id':action,'reason':'An explicit test decision from the offered menu.','emotion':'calm'}},self.obs)
        self.bind();return result

    def register(self,actor,event,recipe=False):
        claim=self.claim(actor,event)
        candidates=[(action,spec) for action,spec in claim['context']['enterprise_options'].items()
                    if ('bread_recipe' in spec['capabilities'] if recipe else 'grain' in spec.get('sale_commodities',[]))]
        self.assertEqual(len(candidates),1)
        action,spec=candidates[0]
        self.assertEqual(self.world.active['town']['businesses'].get(spec['id']),None)
        self.choose(event,claim,action)
        self.assertEqual(self.world.agency_plan()['outcome'],'enterprise_registered')
        return spec['id']

    def observe_controller(self,view):
        for key in ('gameDays','owner_work_jobs','economy_catalog','resident_control','residents'):
            self.obs[key]=copy.deepcopy(view[key])
        if (view.get('result') or {}).get('ack'):self.obs['ack']=copy.deepcopy(view['result']['ack'])
        else:self.obs.pop('ack',None)
        self.world.observe(self.obs);self.bind()

    def test_real_js_owner_receipt_upgrades_prior_only_after_observed_production(self):
        native=FreshOwnerProcess(self.obs);self.addCleanup(native.close)
        self.observe_controller(native.request('state'))
        actor=self.prior();business=self.register(actor,'native-founder-choice',recipe=True)
        prior=copy.deepcopy(self.world.active['people'][str(actor)]['authored_recipe_priors']['bread_recipe'])
        claim=self.claim(actor,'owner-production-choice',kind=None)
        if self.world.agency_plan()['kind']=='stock_review':
            self.choose('owner-production-choice',claim,'reserve_one')
            claim=self.claim(actor,'owner-production-choice')
        self.choose('owner-production-choice',claim,owner_work_choice_id({'business_id':business,'recipe_id':'bread_recipe'}))
        command=self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'],'owner_work_start')
        self.assertFalse(self.world.active['people'][str(actor)].get('known_recipes'))
        started=native.request('start',command=command,desired=self.world.owner_work_status(),gameDays=self.obs['gameDays'])
        self.assertTrue(started['result']['ack']['accepted']);self.assertEqual(started['calls'],[])
        self.observe_controller(started)
        attended=native.request('earn',desired=self.world.owner_work_status())
        self.assertEqual(attended['calls'],[])
        self.assertEqual(attended['owner_work_jobs']['receipts'][0]['phase'],'attendance_verified')
        self.observe_controller(attended)
        self.assertFalse(self.world.active['people'][str(actor)].get('known_recipes'))
        command=self.world.pending(self.obs['session'])
        self.assertEqual(command['kind'],'inventory_self_produce_commit')
        for _ in range(5):
            produced=native.request('commit',command=command)
            if produced['result']['done']:break
        else:self.fail('Controller recipe did not finish within five offline frames')
        ack=produced['result']['ack']
        self.assertEqual(ack['status'],'applied')
        self.assertEqual(ack['effect_witness'],{'input_issued':True,'input_observed':True,'output_issued':True,'output_observed':True})
        self.assertEqual(produced['calls'],[{'actor':actor,'item':'grain','amount':-1},{'actor':actor,'item':'bread','amount':2}])
        self.observe_controller(produced)
        person=self.world.active['people'][str(actor)]
        self.assertEqual(person['known_recipes']['bread_recipe']['source'],'verified_native_production')
        self.assertEqual(person['authored_recipe_priors']['bread_recipe'],prior)
        self.assertEqual(len(self.world.active['production']),1)
        self.assertTrue(knows_recipe(person,'bread_recipe'))
        expected=copy.deepcopy(self.initial_stock);expected[str(actor)]['grain']-=1;expected[str(actor)]['bread']+=2
        self.assertEqual(self.stock(),expected)
        replay=native.request('commit',command=command)
        self.assertEqual(replay['calls'],produced['calls'])
        self.observe_controller(replay);self.assertEqual(len(self.world.active['production']),1)
        released=native.request('release',desired=self.world.owner_work_status());self.observe_controller(released)
        release_ack=self.world.pending(self.obs['session'])
        self.assertEqual(release_ack['kind'],'owner_work_ack_receipt')
        self.observe_controller(native.request('ack',command=release_ack))
        self.assertFalse(self.world.owner_work_status()['jobs'])
        self.assertEqual(self.world.agency_plan()['outcome'],'owner_work_completed')

    def test_explicit_prior_enables_choice_not_a_business_asset_or_work_memory(self):
        before_prior=copy.deepcopy(self.obs)
        for actor in (901,902):
            person=self.world.active['people'][str(actor)]
            self.assertEqual(person['memories'],[])
            self.assertFalse(knows_recipe(person,'bread_recipe',state=self.world.active,observation=self.obs,actor_id=actor))
            self.assertFalse(any('bread_recipe' in row['specification']['capabilities']
                                 for row in enterprise_choices(self.world.active,self.obs,actor)))
        actor=self.prior();person=self.world.active['people'][str(actor)]
        self.assertTrue(authored_prior_status(self.world.active,self.obs,actor,'bread_recipe')['valid'])
        self.assertFalse(knows_recipe(person,'bread_recipe'),'A detached prior must not grant authority')
        self.assertEqual(self.world.active['town']['businesses'],{})
        self.assertEqual(self.stock(),self.initial_stock)
        self.assertTrue(all(p['memories']==[] and not p.get('known_recipes') for p in self.world.active['people'].values()))
        business=self.register(actor,'founder-choice',recipe=True)
        other=next(r['id'] for r in self.obs['residents'] if r['id']!=actor)
        supplier=self.register(other,'supplier-choice')
        self.assertEqual(self.stock(),self.initial_stock)
        self.assertIsNone(self.world.active['pending'])
        self.assertEqual(self.world.active.get('production',[]),[])
        work=owner_work_opportunities(self.world.active,self.obs,actor)
        self.assertEqual([(r['business_id'],r['recipe_id']) for r in work],[(business,'bread_recipe')])
        purchases=input_procurement(self.world.active,self.obs,actor)
        self.assertTrue(purchases)
        self.assertTrue(all(p['supplier']==other and p['listing_business_id']==supplier and p['commodity']=='grain'
                            and p['shortfall']==1 for p in purchases))
        self.assertEqual({m['kind'] for p in self.world.active['people'].values() for m in p['memories']},{'enterprise_changed'})
        self.world.observe({**before_prior,'session':'before-livelihood-prior'})
        self.assertEqual(self.world.active['town']['businesses'],{})
        self.assertTrue(all(not p.get('authored_recipe_priors') and p['memories']==[]
                            for p in self.world.active['people'].values()))

    def test_replaced_or_missing_identity_cannot_receive_initial_prior(self):
        for mode in ('missing_base','replacement','unloaded'):
            with self.subTest(mode=mode):
                obs=copy.deepcopy(self.obs)
                if mode=='missing_base':obs['residents'][0].pop('baseId')
                elif mode=='replacement':obs['residents'][0]['baseId']+=1
                else:obs['residents'].pop(0)
                before=copy.deepcopy(self.world.active)
                with self.assertRaises(ValueError):
                    self.world.establish_livelihood_background('unqualified-prior','fresh-livelihood-seed',
                        self.manifest['id'],self.manifest_hash,[901,902],obs)
                self.assertEqual(self.world.active,before)
                self.assertIsNone(self.world.transition)
                self.assertEqual(self.stock(),self.initial_stock)

    def test_identity_change_revokes_prior_menu_and_inflight_charter_choice(self):
        actor=self.prior();claim=self.claim(actor,'identity-sensitive-choice')
        action=next(action for action,spec in claim['context']['enterprise_options'].items()
                    if 'bread_recipe' in spec['capabilities'])
        row=next(r for r in self.obs['residents'] if r['id']==actor);base=row['baseId']
        before=copy.deepcopy(self.world.active)
        for replacement in (None,base+1):
            with self.subTest(base=replacement):
                if replacement is None:row.pop('baseId',None)
                else:row['baseId']=replacement
                self.assertFalse(resident_identity_status(self.world.active,self.obs,actor)['qualified'])
                self.assertFalse(authored_prior_status(self.world.active,self.obs,actor,'bread_recipe')['valid'])
                self.assertFalse(any('bread_recipe' in option['specification']['capabilities']
                                     for option in enterprise_choices(self.world.active,self.obs,actor)))
                with self.assertRaises(ValueError):self.choose('identity-sensitive-choice',claim,action)
                self.assertEqual(self.world.active,before)
                self.assertIsNone(self.world.transition)
        row['baseId']=base
        self.assertEqual(self.world.active['town']['businesses'],{})
        self.assertEqual(self.stock(),self.initial_stock)

    def test_saved_charter_cannot_enable_work_for_replaced_or_unidentified_actor(self):
        actor=self.prior();self.register(actor,'identity-bound-charter',recipe=True)
        self.assertTrue(owner_work_opportunities(self.world.active,self.obs,actor))
        before=copy.deepcopy(self.world.active)
        for mode in ('missing_base','replacement'):
            with self.subTest(mode=mode):
                obs=copy.deepcopy(self.obs);row=next(r for r in obs['residents'] if r['id']==actor)
                if mode=='missing_base':row.pop('baseId')
                else:row['baseId']+=1
                self.assertEqual(owner_work_opportunities(self.world.active,obs,actor),[])
                with self.assertRaises(ValueError):self.world.begin_plan('unqualified-work',obs,actor)
                self.assertEqual(self.world.active,before)
                self.assertIsNone(self.world.transition)
                self.assertIsNone(self.world.active['pending'])


if __name__=='__main__':unittest.main()
