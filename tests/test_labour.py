from catalog_fixture import native_ack
import copy
import unittest
import test_daily_life
import test_food
from labour import work_opportunities


class LabourTests(unittest.TestCase):
    tearDown = test_daily_life.DailyLifeTests.tearDown
    sync = test_daily_life.DailyLifeTests.sync
    census = test_daily_life.DailyLifeTests.census
    review = test_daily_life.DailyLifeTests.review
    decide = test_food.FoodTests.decide

    def setUp(self):
        test_daily_life.DailyLifeTests.setUp(self)
        self.obs['routing'] = {'adapter':'papyrus-mailbox-v1','available':True}
        for a in self.obs['residents']:
            a.update(x=100,y=0,z=0)
            if a['id']==108149:a['inventory'].update(gold=12,bread=2,grain=3)
        for p in self.world.active['people'].values():
            p['needs'].update(hunger=.3,fatigue=.2,social_contact=.2)

    def archive_plan(self, event, voiced=False, actor=99, business_id="business-108149", scheduled=False):
        """Explicit pre-gate dialogue fixture; never a newly available paid job."""
        from economy_catalog import catalog_hash, recipe_hash
        from market_policy import policy_hash
        from enterprises import production_policy
        from employment import approach_employer
        state=copy.deepcopy(self.world.active)
        business=state['town']['businesses'][business_id]
        plan={'id':event,'kind':'work_shift','actor':actor,'target':business['custodian'],'phase':'job_offer',
              'decisions':[],'claim':None,'travel':None,'trade_id':'meal-'+event,
              'unit_price':3,'quantity':1,'commodity':'bread','purpose':'food',
              'market_policy_hash':policy_hash(),'catalog_hash':catalog_hash(),
              'refusals_recorded':0,'food_actions':True,
              'fixture_provenance':'Authored archived employment dialogue; no completed work',
              'work_terms':{'business_id':business['id'],'employer':business['custodian'],
                  'revision':business['revision'],'policy':production_policy(business),
                  'recipe_id':'bread_recipe','catalog_hash':catalog_hash(),
                  'recipe_hash':recipe_hash('bread_recipe')}}
        if scheduled:
            plan['scheduled']=True
            state['town'].setdefault('daily',{'last_day':self.obs['gameDays'],'sequence':0,'queue':[],'reviews':[]}).setdefault('queue',[]).append(
                {'id':event,'actor':actor,'kind':'work_shift','status':'started'})
        if voiced:
            plan['voiced_trade']=True;approach_employer(plan)
        state.setdefault('plans',[]).append(plan)
        self.world._write(state,'Explicit archived employment dialogue test fixture');self.sync()

    def test_paid_gate_stays_closed_with_or_without_capacity(self):
        self.assertEqual(work_opportunities(self.world.active,self.obs,99),[])
        for key,value in [('gold',1),('grain',0),('bread',8)]:
            obs=copy.deepcopy(self.obs);obs['residents'][1]['inventory'][key]=value
            self.assertEqual(work_opportunities(self.world.active,obs,99),[])
        self.obs['residents']=[a for a in self.obs['residents'] if a['id']!=108149]
        self.assertEqual(work_opportunities(self.world.active,self.obs,99),[])

    def test_guard_or_commitment_state_cannot_bypass_paid_gate(self):
        self.assertEqual(work_opportunities(self.world.active,self.obs,108149),[])
        self.world.active['town']['residents']['99']['is_guard']=True
        self.assertEqual(work_opportunities(self.world.active,self.obs,99),[])
        self.world.active['town']['residents']['99']['is_guard']=False
        self.world.active['people']['99']['commitments']=[{'kind':'existing obligation'}]
        self.assertEqual(work_opportunities(self.world.active,self.obs,99),[])

    def test_scheduled_livelihood_does_not_offer_unqualified_paid_execution(self):
        result=self.review()
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.assertIn(event['id'],result['new_events'])
        self.world.begin_plan(event['id'],self.obs,99,'need_review');self.sync()
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertFalse(any(o['id'].startswith('seek_work') for o in context['options']))
        self.assertEqual(self.world.active['town']['businesses']['business-108149']['contracts'],[])
        self.assertEqual(self.world.status()['production'],[])

    def test_archived_offer_can_be_declined_without_stock_or_contract_effects(self):
        before=copy.deepcopy(self.obs['residents']);self.archive_plan('archived-offer')
        self.decide('offer_shift','archived-offer')
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual(context['actor_id'],99)
        self.assertEqual(context['observed_inventory']['gold'],7)
        self.assertNotIn('employer_inventory',context)
        self.decide('decline_work','archived-offer')
        self.assertEqual(self.world.agency_plan()['outcome'],'work_declined')
        self.assertEqual(before,self.obs['residents'])
        self.assertEqual(self.world.active['town']['businesses']['business-108149']['contracts'],[])

    def test_employer_deferral_remembers_worker_not_self(self):
        self.archive_plan('not-hiring')
        self.decide('defer','not-hiring')
        memory=self.world.active['people']['108149']['memories'][-1]
        self.assertEqual(memory['other'],99)
        self.assertEqual(self.world.active['town']['businesses']['business-108149']['contracts'],[])

    def test_archived_accepted_contract_cannot_execute_and_rolls_back_with_its_save(self):
        old=copy.deepcopy(self.obs);stock=copy.deepcopy(self.obs['residents'])
        self.archive_plan('new-worker')
        self.decide('offer_shift','new-worker');self.decide('take_shift','new-worker')
        plan=self.world.agency_plan()
        contract=self.world.active['town']['businesses']['business-108149']['contracts'][0]
        self.assertEqual(contract['status'],'accepted');self.assertTrue(plan['dynamic_route'])
        self.obs['ack']={'id':plan['travel_id'],'status':'applied','movement':{
            'hasOwnedPackage':True,'expectedPackage':99,'aliasesConfirmed':True,
            'adapter':'papyrus-mailbox','actor':99,'target':108149}}
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(stock,self.obs['residents'])
        self.assertEqual(self.world.status()['production'],[])
        self.assertNotEqual((self.world.pending(self.obs['session']) or {}).get('kind'),'inventory_produce')
        self.assertEqual(self.world.active['town']['businesses']['business-108149']['workers'],[])
        self.world.observe({**old,'session':'before-employment'})
        self.assertEqual(self.world.active['town']['businesses']['business-108149']['contracts'],[])

    def test_failed_travel_ends_contract_without_wages(self):
        self.archive_plan('interrupted')
        self.decide('offer_shift','interrupted');self.decide('take_shift','interrupted')
        self.obs['ack']={'id':self.world.agency_plan()['travel_id'],'status':'held'}
        self.world.observe(self.obs);self.sync()
        self.obs['ack']={'id':'release-interrupted','status':'applied'}
        self.world.observe(self.obs);self.sync()
        contract=self.world.active['town']['businesses']['business-108149']['contracts'][0]
        self.assertEqual(contract['status'],'ended');self.assertEqual(contract['outcome'],'held')
        self.assertEqual(self.world.status()['production'],[])

    def test_fatigue_prevents_livelihood_queue_and_depleted_business_cannot_start_job(self):
        self.world.active['people']['99']['needs']['fatigue']=.9
        self.review()
        self.assertNotIn(99,[e['actor'] for e in self.world.active['town']['daily']['queue']])
        self.assertEqual(self.world.active['people']['99']['agency']['state'],'unmet_rest_need')
        self.obs['residents'][1]['inventory']['grain']=0
        with self.assertRaisesRegex(ValueError,'No feasible'):
            self.world.begin_plan('empty-job',self.obs,99,'work_shift')

    def test_legacy_after_shaped_production_receipt_holds_without_work_credit(self):
        from production import work_inventory
        from employment import accept_contract
        self.archive_plan('drift');plan=self.world.agency_plan()
        accept_contract(self.world.active,plan);plan['phase']='working'
        before=work_inventory(self.obs,99,108149);after=copy.deepcopy(before)
        after['employer']['grain']-=1;after['employer']['bread']+=2
        after['employer']['gold']-=2;after['worker']['gold']+=2
        terms=plan['work_terms']
        command={'id':'produce-drift','kind':'inventory_produce','worker':99,'employer':108149,
                 'recipe_id':terms['recipe_id'],'catalog_hash':terms['catalog_hash'],
                 'recipe_hash':terms['recipe_hash'],'work_minutes':30,'wage_gold':2,
                 'before':before,'after':after}
        self.world.active['pending']={'id':command['id'],'command':command,'status':'pending'}
        people=copy.deepcopy(self.world.active['people'])
        for row in self.obs['residents']:
            if row['id'] in (99,108149):row['inventory']=copy.deepcopy(after['worker' if row['id']==99 else 'employer'])
        self.obs['ack']=native_ack(command)
        self.world.observe_production(self.obs);self.sync()
        business=self.world.active['town']['businesses']['business-108149']
        self.assertEqual(business['contracts'][0]['status'],'held')
        self.assertEqual(business['workers'],[])
        self.assertEqual(self.world.status()['production'],[])
        self.assertEqual(self.world.active['people'],people)
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertIsNone(self.world.pending(self.obs['session']))

    def test_scheduled_business_review_reconsiders_reserve_without_minting_stock(self):
        self.world.active['people']['108149']['food_policy'].pop('reviewed_day')
        before=copy.deepcopy(self.obs['residents']);self.review()
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==108149)
        self.assertEqual(event['kind'],'stock_review')
        self.world.begin_plan(event['id'],self.obs,108149,'stock_review');self.sync()
        self.decide('reserve_one',event['id'])
        self.assertEqual(before,self.obs['residents'])
        self.assertEqual(self.world.active['people']['108149']['food_policy']['reviewed_day'],self.obs['gameDays'])
        settled=next(e for e in self.world.active['town']['daily']['queue'] if e['id']==event['id'])
        self.assertEqual(settled['status'],'complete')
        self.review(1)
        self.assertFalse(any(e['actor']==108149 and e['status']=='pending' and e['kind']=='stock_review' for e in self.world.active['town']['daily']['queue']))
        livelihood=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==108149 and e['status']=='pending')
        self.assertEqual(livelihood['kind'],'need_review')  # A livelihood choice is distinct from repeating reserve allocation.
        self.review(3)
        self.assertTrue(any(e['actor']==108149 and e['status']=='pending' for e in self.world.active['town']['daily']['queue']))

    def test_daily_event_kind_cannot_be_repurposed(self):
        self.world.active['people']['108149']['food_policy'].pop('reviewed_day')
        self.review()
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==108149)
        with self.assertRaisesRegex(ValueError,'matching pending'):
            self.world.begin_plan(event['id'],self.obs,108149,'need_review')


if __name__=='__main__':unittest.main()
