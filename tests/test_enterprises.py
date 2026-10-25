from catalog_fixture import native_ack
import copy
import json
import unittest
import test_population
import test_food
import test_labour
from enterprises import production_policy
from labour import work_opportunities
from opportunities import food_sellers
from population import person_seed
from legacy_fixture import author_fixture_identities
from observer import observer_state
import time


class EnterpriseTests(unittest.TestCase):
    tearDown = test_population.PopulationTests.tearDown
    sync = test_population.PopulationTests.sync
    decide = test_food.FoodTests.decide

    def setUp(self):
        test_population.PopulationTests.setUp(self)
        self.obs.update(gameDays=3.5, routing={'adapter':'papyrus-mailbox-v1','available':True})
        self.obs['residents'] = [
            {'id':aid,'baseId':aid+100000,'name':name,'isPerson':True,'isGuard':False,'x':aid,'y':0,'z':0,
             'inventory':{'gold':gold,'bread':bread,'grain':grain}}
            for aid,name,gold,bread,grain in [(7,'Unknown founder',20,0,4),(8,'Worker',3,1,0),(9,'Competitor',15,2,3)]]
        self.world.initialize_population('people','business-seed',self.obs);self.sync()
        # Remove compatibility-demo profiles; this scenario uses only a new cast.
        self.world.active['people'] = {str(a['id']):person_seed(a,'business-seed',3.5) for a in self.obs['residents']}
        author_fixture_identities(self.world.active,self.obs)
        self.spec = {'id':'mill-bakery','expected_revision':0,'name':'Mill bakery','custodian':7,
            'capabilities':['bread_recipe','retail_food'],'active':True,
            'production_policy':{'wage_gold':4,'work_minutes':10,'target_bread':12}}

    def configure(self, event='charter', spec=None):
        result=self.world.configure_enterprise(event,spec or self.spec,self.obs);self.sync();return result

    def archive_plan(self,event='shift'):
        test_labour.LabourTests.archive_plan(self,event,actor=8,business_id='mill-bakery')

    def work(self, event='shift'):
        """Explicit historical pending write; the current gate never emits this."""
        from production import work_inventory
        from employment import accept_contract
        self.archive_plan(event);plan=self.world.agency_plan()
        accept_contract(self.world.active,plan);plan['phase']='working'
        terms=plan['work_terms'];policy=terms['policy']
        before=work_inventory(self.obs,8,7);after=copy.deepcopy(before)
        after['employer']['grain']-=policy['grain_per_shift'];after['employer']['bread']+=policy['bread_per_shift']
        after['employer']['gold']-=policy['wage_gold'];after['worker']['gold']+=policy['wage_gold']
        command={'id':'produce-'+event,'kind':'inventory_produce','worker':8,'employer':7,
                 'recipe_id':terms['recipe_id'],'catalog_hash':terms['catalog_hash'],'recipe_hash':terms['recipe_hash'],
                 'work_minutes':policy['work_minutes'],'wage_gold':policy['wage_gold'],'before':before,'after':after}
        self.world.active['pending']={'id':command['id'],'command':command,'status':'pending'}
        return command

    def test_census_assigns_no_business_and_charter_neither_mints_nor_moves_stock(self):
        self.assertEqual(self.world.active['town']['businesses'],{})
        before=copy.deepcopy(self.obs['residents']);result=self.configure()
        self.assertEqual(before,self.obs['residents'])
        self.assertEqual(result['business']['resource_account'],'native-inventory:7')
        self.assertEqual(result['event']['inventory_effect'],'none')
        self.assertEqual([r['id'] for r in food_sellers(self.world.active,self.obs,8)],[7])
        self.assertEqual(work_opportunities(self.world.active,self.obs,8),[])
        policy=production_policy(result['business'])
        self.assertEqual((policy['wage_gold'],policy['work_minutes']),(4,10))

    def test_idempotent_retry_and_revision_conflicts_preserve_state(self):
        self.configure();before=copy.deepcopy(self.world.active)
        self.assertTrue(self.configure()['duplicate'])
        self.assertEqual(before,self.world.active)
        with self.assertRaisesRegex(ValueError,'reused'):
            self.configure(spec={**self.spec,'name':'Renamed'})
        with self.assertRaisesRegex(ValueError,'Stale'):
            self.configure('different-event')
        self.assertEqual(before,self.world.active)

    def test_close_and_reassign_changes_opportunities_not_physical_asset_ownership(self):
        self.configure();before=copy.deepcopy(self.obs['residents'])
        self.configure('close',{**self.spec,'expected_revision':1,'active':False})
        self.assertEqual(food_sellers(self.world.active,self.obs,8),[])
        self.assertEqual(work_opportunities(self.world.active,self.obs,8),[])
        self.configure('new-custodian',{**self.spec,'expected_revision':2,'custodian':9})
        self.assertEqual([r['id'] for r in food_sellers(self.world.active,self.obs,8)],[9])
        self.assertEqual(before,self.obs['residents'])
        self.assertEqual(self.world.active['town']['enterprise_events'][-1]['previous_custodian'],7)

    def test_invalid_terms_classification_and_unknown_capability_do_not_write(self):
        before=copy.deepcopy(self.world.active)
        for field,value in [('custodian',999),('custodian',True),('expected_revision',True),
                ('capabilities',['magic_gold']),('capabilities',['bread_recipe','bread_recipe']),
                ('name','\n'),('active','yes'),('production_policy',{'wage_gold':0}),
                ('production_policy',{'work_minutes':121}),('production_policy',{'bread_per_shift':20}),
                ('production_policy',{'unknown':5}),('production_policy',{'wage_gold':True})]:
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                self.configure(spec={**self.spec,field:value})
            self.assertIsNone(self.world.transition)
        self.obs['residents'][0]['isPerson']=False
        with self.assertRaisesRegex(ValueError,'initialized adult'):self.configure()
        self.assertEqual(before,self.world.active)

    def test_archived_custom_wage_after_state_cannot_credit_unqualified_work(self):
        self.configure();command=self.work()
        self.assertEqual((command['wage_gold'],command['work_minutes']),(4,10))
        self.assertEqual(command['after']['worker']['gold'],7)
        self.assertEqual(command['after']['employer'],{'gold':16,'bread':2,'grain':3})
        self.assertEqual(sum(v['gold'] for v in command['before'].values()),sum(v['gold'] for v in command['after'].values()))
        for actor in self.obs['residents']:
            if actor['id'] in (7,8):actor['inventory']=command['after']['employer' if actor['id']==7 else 'worker'].copy()
        self.obs['ack']=native_ack(command)
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['town']['businesses']['mill-bakery']['contracts'][0]['status'],'held')
        self.assertEqual(self.world.status()['production'],[])
        self.assertFalse(any(m['kind']=='paid_work' for m in self.world.active['people']['8']['memories']))
        self.assertNotIn('known_recipes',self.world.active['people']['8'])
        self.assertIsNone(self.world.pending(self.obs['session']))

    def test_work_policy_change_cannot_silently_change_offer_or_pending_inference(self):
        self.configure()
        self.archive_plan('offer')
        claim=self.world.claim_plan_decision('offer',self.obs)['claim'];self.sync()
        with self.assertRaisesRegex(ValueError,'active resident'):
            self.configure('edit',{**self.spec,'expected_revision':1})
        self.world.active['town']['businesses']['mill-bakery']['production_policy']['wage_gold']=5
        with self.assertRaisesRegex(ValueError,'terms changed'):
            self.world.finish_plan_decision('offer',claim['id'],{'decision':{'action_id':'offer_shift','reason':'Test','emotion':'calm'}},self.obs)

    def test_legacy_no_effect_attestation_cannot_release_quarantine(self):
        self.configure();command=self.work()
        self.obs['ack']=native_ack(command,status='held',no_effects_issued=True,error='Attendance interrupted')
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertIsNone(self.world.active['pending']['effects_issued'])
        self.assertFalse(self.world.active['pending']['no_effects_issued'])
        self.assertNotIn('cancelled_production',self.world.active)
        self.assertEqual(self.world.status()['production'],[])
        self.assertEqual(self.world.active['town']['businesses']['mill-bakery']['contracts'][0]['status'],'held')
        self.assertEqual(self.world.active['people']['8']['memories'],[])
        self.assertEqual(self.world.active['people']['7']['memories'],[])
        self.assertNotIn('known_recipes',self.world.active['people']['8'])
        self.assertIsNone(self.world.pending(self.obs['session']))

    def test_no_effect_attestation_cannot_override_an_observed_partial_mutation(self):
        self.configure();command=self.work();self.obs['residents'][0]['inventory']['grain']-=1
        self.obs['ack']=native_ack(command,status='held',no_effects_issued=True)
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertNotIn('cancelled_production',self.world.active)

    def test_historical_policy_provenance_text_does_not_change_agreed_terms(self):
        self.configure()
        self.archive_plan('old-provenance')
        self.world.agency_plan()['work_terms']['policy']['source']='Previous policy description'
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertIn('offer_shift',[o['id'] for o in context['options']])

    def test_distinct_enterprise_terms_do_not_advertise_disabled_paid_execution(self):
        self.configure()
        self.configure('second',{**self.spec,'id':'other-shop','custodian':9,'production_policy':{'wage_gold':6,'work_minutes':25}})
        self.world.active['town']['daily']={'queue':[{'id':'choose-job','actor':8,'kind':'need_review','status':'pending'}]}
        self.world.begin_plan('choose-job',self.obs,8,'need_review');self.sync()
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual(context['work_options'],{})
        self.assertFalse(any(o['id'].startswith('seek_work') for o in context['options']))
        self.assertNotIn('Competitor',json.dumps(context));self.assertNotIn('Unknown founder',json.dumps(context))
        self.assertEqual(production_policy(self.world.active['town']['businesses']['other-shop'])['wage_gold'],6)
        self.assertEqual(self.world.active['town']['businesses']['other-shop']['contracts'],[])

    def test_old_save_restores_charter_and_observer_reports_shared_native_account(self):
        self.configure();old=copy.deepcopy(self.obs)
        self.configure('raise-wage',{**self.spec,'expected_revision':1,'production_policy':{'wage_gold':8}})
        self.world.observe({**old,'session':'older-business-save'})
        business=self.world.active['town']['businesses']['mill-bakery']
        self.assertEqual((business['revision'],business['production_policy']['wage_gold']),(1,4))
        state=observer_state({'last_seen':time.time(),'observation':self.obs},self.world.status())
        self.assertEqual(state['businesses'][0]['observed_inventory']['gold'],20)
        self.assertIn('shared',state['businesses'][0]['account_scope'])


if __name__=='__main__':unittest.main()
