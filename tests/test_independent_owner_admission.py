"""Authored independent decision admission fixtures; no native effects executed."""
import copy
import unittest

from agency import Agency
from activity_leases import routine_actors
from activity_plan_sources import activity_plan_hash
from legacy_fixture import author_fixture_identities
from owner_production import owner_work_opportunities
import test_owner_work_jobs as owner_fixture


class IndependentOwnerWorld(owner_fixture.OwnerSavedWorld):
    def _agency_guard(self, observation, allow_routines=False):
        return Agency._agency_guard(self, observation, allow_routines=allow_routines)

    def routines_busy(self):return bool(routine_actors(self.active))


class IndependentOwnerAdmissionTests(unittest.TestCase):
    def setUp(self):
        fixture=owner_fixture.OwnerWorkJobsTests();fixture.setUp()
        self.world=IndependentOwnerWorld(fixture.state);self.obs=fixture.obs
        self.obs['ready']=True
        self.world.active['town']['residents']={'1':{'id':1}}
        author_fixture_identities(self.world.active,self.obs)
        terms=owner_work_opportunities(self.world.active,self.obs,1,require_owned=False)[0]
        self.world.active['plans']=[{'id':'unrelated-foreground','actor':21,'target':22,'phase':'talking'}]
        self.world.active['conversation']={'id':'unrelated-chat','initiator':21,'partner':22,'speakers':[21,22],'phase':'talking'}
        plan={'id':'independent-owner','actor':1,'actor_base_id':101,'session':self.world.session,
              'kind':'independent_review','phase':'ready_to_self_work','own_work_terms':terms,
              'independent_review':{'wave_id':'fixture-wave','claim_id':'fixture-claim','event_id':'independent-owner'}}
        self.world.active['independent_plans']={plan['id']:plan}
        self.world.active['independent_reviews']={plan['id']:{'event_id':plan['id'],'plan_id':plan['id'],
            'actor':1,'actor_base_id':101,'session':self.world.session,'accepted':True,'phase':'accepted',
            'wave_id':'fixture-wave','claim_id':'fixture-claim','plan_hash':activity_plan_hash(plan)}}
        self.world.active['town']['daily']['queue']=[{'id':plan['id'],'actor':1,'status':'started','independent_review':'fixture-wave'}]
        self.fixture=fixture;self.fixture.world=self.world;self.fixture.obs=self.obs

    def plan(self):return self.world.active['independent_plans']['independent-owner']

    def delegate(self):
        result=self.world.delegate_owner_work(self.plan(),self.obs);self.world.bind(self.obs)
        return self.world.active['work_jobs'][result['job_id']]

    def test_independent_owner_delegates_beside_disjoint_foreground_and_routine(self):
        self.world.active['routine_batches']=[{'phase':'travelling','members':[{'actor':31,'phase':'travelling'}]}]
        before=copy.deepcopy(self.world.active['plans']);chat=copy.deepcopy(self.world.active['conversation'])
        stock=copy.deepcopy(self.obs['residents']);job=self.delegate()
        self.assertEqual(self.world.active['plans'],before);self.assertEqual(self.world.active['conversation'],chat)
        self.assertEqual(self.plan()['phase'],'delegated');self.assertEqual(job['source_plan'],self.plan()['id'])
        self.assertEqual(self.obs['residents'],stock);self.assertNotIn('production',self.world.active)
        self.assertEqual(self.world.owner_work_pending_command()['kind'],'owner_work_start')

    def test_foreground_conversation_or_routine_actor_overlap_rejects_before_write(self):
        changes=[lambda s:s['plans'][-1].update(actor=1),lambda s:s['plans'][-1].update(target=1),
            lambda s:s['conversation'].update(partner=1),
            lambda s:s.update(routine_batches=[{'phase':'travelling','members':[{'actor':1,'phase':'travelling'}]}])]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                self.setUp();change(self.world.active);before=copy.deepcopy(self.world.active)
                with self.assertRaises(ValueError):self.world.delegate_owner_work(self.plan(),self.obs)
                self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_unaccepted_copied_or_changed_independent_decision_cannot_delegate(self):
        for mode in ('missing_review','thinking','changed_terms','copy','wrong_event','foreground_alias'):
            with self.subTest(mode=mode):
                self.setUp();plan=self.plan();record=self.world.active['independent_reviews'][plan['id']]
                if mode=='missing_review':self.world.active['independent_reviews'].clear()
                elif mode=='thinking':record['phase']='thinking'
                elif mode=='changed_terms':plan['own_work_terms']['revision']=2
                elif mode=='copy':plan=copy.deepcopy(plan)
                elif mode=='foreground_alias':
                    record['phase']='thinking';self.world.active['plans'].append(plan)
                else:self.world.active['town']['daily']['queue'][0]['status']='pending'
                before=copy.deepcopy(self.world.active)
                with self.assertRaises(ValueError):self.world.delegate_owner_work(plan,self.obs)
                self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_current_identity_catalog_stock_and_business_still_required(self):
        for mode in ('base','session','catalog','stock','business','account'):
            with self.subTest(mode=mode):
                self.setUp()
                if mode=='base':self.obs['residents'][0]['baseId']=999
                elif mode=='session':self.obs['session']='another-session'
                elif mode=='catalog':self.obs['economy_catalog']['available']=False
                elif mode=='stock':self.obs['residents'][0]['inventory']['grain']=0
                elif mode=='business':self.world.active['town']['businesses']['shop']['revision']=2
                else:self.world.active['pending']={'id':'unrelated-writer'}
                before=copy.deepcopy(self.world.active)
                with self.assertRaises(ValueError):self.world.delegate_owner_work(self.plan(),self.obs)
                self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_attendance_can_progress_but_inventory_waits_for_foreground_then_settles_source(self):
        foreground=copy.deepcopy(self.world.active['plans']);chat=copy.deepcopy(self.world.active['conversation'])
        job=self.delegate();self.obs['gameDays']+=job['work_minutes']/1440
        self.obs['owner_work_jobs']['receipts']=[self.fixture.attendance(job)]
        self.assertTrue(self.world.observe_owner_work_jobs(self.obs));self.world.bind(self.obs)
        self.world.foreground_busy=True;self.world.talking=True
        self.assertFalse(self.world.prepare_owner_work_recipe(self.obs));self.assertIsNone(self.world.active['pending'])
        self.world.foreground_busy=False;self.world.talking=False
        self.assertTrue(self.world.prepare_owner_work_recipe(self.obs));self.world.bind(self.obs)
        command=self.world.active['pending']['command'];self.obs['ack']=self.fixture.commit_ack(job,command)
        self.obs['residents'][0]['inventory']=copy.deepcopy(command['after']['owner'])
        self.assertTrue(self.world.observe_owner_work_recipe(self.obs));self.world.bind(self.obs)
        self.assertEqual(self.plan()['phase'],'delegated')
        self.obs['owner_work_jobs']['receipts']=[{**self.obs['ack'],'phase':'complete','release_verified':True}]
        self.assertTrue(self.world.observe_owner_work_jobs(self.obs));self.world.bind(self.obs)
        self.assertEqual(self.plan()['phase'],'complete');self.assertEqual(self.world.active['plans'],foreground)
        self.assertEqual(self.world.active['conversation'],chat)
        self.assertEqual(self.world.active['town']['daily']['queue'][0]['status'],'complete')

    def test_hold_updates_independent_source_without_overwriting_foreground(self):
        foreground=copy.deepcopy(self.world.active['plans']);job=self.delegate()
        self.world._hold_owner_job(self.world.active,job,'authored failure',unreconciled=True)
        self.assertEqual(self.plan()['phase'],'held');self.assertEqual(self.world.active['plans'],foreground)
        self.assertEqual(self.world.active['town']['daily']['queue'][0]['status'],'held')


if __name__=='__main__':unittest.main()
