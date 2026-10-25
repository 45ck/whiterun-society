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

    def test_capacity_requires_funds_inputs_stock_gap_and_loaded_route(self):
        self.assertEqual(len(work_opportunities(self.world.active,self.obs,99)),1)
        for key,value in [('gold',1),('grain',0),('bread',8)]:
            obs=copy.deepcopy(self.obs);obs['residents'][1]['inventory'][key]=value
            self.assertEqual(work_opportunities(self.world.active,obs,99),[])
        self.obs['residents']=[a for a in self.obs['residents'] if a['id']!=108149]
        self.assertEqual(work_opportunities(self.world.active,self.obs,99),[])

    def test_guards_and_commitments_allow_job_choice_without_self_employment(self):
        self.assertEqual(work_opportunities(self.world.active,self.obs,108149),[])
        self.world.active['town']['residents']['99']['is_guard']=True
        self.assertEqual(len(work_opportunities(self.world.active,self.obs,99)),1)
        self.world.active['town']['residents']['99']['is_guard']=False
        self.world.active['people']['99']['commitments']=[{'kind':'existing obligation'}]
        self.assertEqual(len(work_opportunities(self.world.active,self.obs,99)),1)

    def test_scheduled_livelihood_requires_search_offer_and_acceptance(self):
        result=self.review()
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.assertIn(event['id'],result['new_events'])
        self.world.begin_plan(event['id'],self.obs,99,'need_review');self.sync()
        self.decide('seek_work',event['id']);self.decide('offer_shift',event['id'])
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual(context['actor_id'],99)
        self.assertEqual(context['observed_inventory']['gold'],7)
        self.assertNotIn('employer_inventory',context)
        self.assertEqual(self.world.active['town']['businesses']['business-108149']['contracts'],[])
        self.decide('decline_work',event['id'])
        self.assertEqual(self.world.agency_plan()['outcome'],'work_declined')
        self.assertEqual(self.world.active['town']['daily']['queue'][-1]['status'],'complete')
        self.assertEqual(self.world.status()['production'],[])

    def test_employer_deferral_remembers_worker_not_self(self):
        self.world.begin_plan('not-hiring',self.obs,99,'work_shift');self.sync()
        self.decide('defer','not-hiring')
        memory=self.world.active['people']['108149']['memories'][-1]
        self.assertEqual(memory['other'],99)
        self.assertEqual(self.world.active['town']['businesses']['business-108149']['contracts'],[])

    def test_nonlegacy_worker_executes_owned_work_and_contract_survives_only_its_save(self):
        old=copy.deepcopy(self.obs)
        self.world.begin_plan('new-worker',self.obs,99,'work_shift');self.sync()
        self.decide('offer_shift','new-worker');self.decide('take_shift','new-worker')
        plan=self.world.agency_plan()
        contract=self.world.active['town']['businesses']['business-108149']['contracts'][0]
        self.assertEqual(contract['status'],'accepted');self.assertTrue(plan['dynamic_route'])
        self.obs['ack']={'id':plan['travel_id'],'status':'applied','movement':{
            'hasOwnedPackage':True,'expectedPackage':99,'aliasesConfirmed':True,
            'adapter':'papyrus-mailbox','actor':99,'target':108149}}
        self.world.observe(self.obs);self.sync();command=self.world.pending(self.obs['session'])
        self.assertEqual(command['worker'],99)
        for a in self.obs['residents']:
            if a['id'] in (99,108149):a['inventory']=command['after']['worker' if a['id']==99 else 'employer'].copy()
        self.obs['ack']={'id':command['id'],'status':'applied'}
        self.world.observe(self.obs);self.sync()
        business=self.world.active['town']['businesses']['business-108149']
        self.assertEqual(business['contracts'][0]['status'],'completed');self.assertEqual(business['workers'],[99])
        self.assertEqual(self.obs['residents'][2]['inventory']['gold'],9)
        self.assertEqual(self.obs['residents'][1]['inventory'],{'gold':10,'bread':4,'grain':2})
        self.world.observe({**old,'session':'before-employment'})
        self.assertEqual(self.world.active['town']['businesses']['business-108149']['contracts'],[])

    def test_failed_travel_ends_contract_without_wages(self):
        self.world.begin_plan('interrupted',self.obs,99,'work_shift');self.sync()
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

    def test_unverified_production_holds_contract_without_completed_work_history(self):
        self.world.begin_plan('drift',self.obs,99,'work_shift');self.sync()
        self.decide('offer_shift','drift');self.decide('take_shift','drift')
        self.obs['ack']={'id':self.world.agency_plan()['travel_id'],'status':'applied','movement':{
            'hasOwnedPackage':True,'expectedPackage':99,'aliasesConfirmed':True,
            'adapter':'papyrus-mailbox','actor':99,'target':108149}}
        self.world.observe(self.obs);self.sync()
        self.obs['ack']={'id':'produce-drift','status':'applied'}
        self.world.observe(self.obs);self.sync()
        business=self.world.active['town']['businesses']['business-108149']
        self.assertEqual(business['contracts'][0]['status'],'held')
        self.assertEqual(business['workers'],[])
        self.assertEqual(self.world.status()['production'],[])

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
        self.assertFalse(any(e['actor']==108149 and e['status']=='pending' for e in self.world.active['town']['daily']['queue']))
        self.review(3)
        self.assertTrue(any(e['actor']==108149 and e['status']=='pending' for e in self.world.active['town']['daily']['queue']))

    def test_daily_event_kind_cannot_be_repurposed(self):
        self.world.active['people']['108149']['food_policy'].pop('reviewed_day')
        self.review()
        event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==108149)
        with self.assertRaisesRegex(ValueError,'matching pending'):
            self.world.begin_plan(event['id'],self.obs,108149,'need_review')


if __name__=='__main__':unittest.main()
