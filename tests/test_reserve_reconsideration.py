import copy
import unittest
import test_agency as fixtures
import test_economic_speech as speech_fixtures
from food import allocation
from metrics import simulation_metrics
from trade_consent import reserved_sale_consent
from catalog_fixture import native_ack


class ReserveReconsiderationTests(unittest.TestCase):
    setUp=fixtures.AgencyTests.setUp
    tearDown=fixtures.AgencyTests.tearDown
    sync=fixtures.AgencyTests.sync
    decide=fixtures.AgencyTests.decide
    arrive=fixtures.AgencyTests.arrive
    speak=speech_fixtures.EconomicSpeechTests.speak

    def prepare(self,voiced=False):
        self.policy={'mode':'household_all','reserve_target':0,'observed_bread':3,'reviewed_day':1,'source_event':'old-household-choice'}
        self.world.active['people']['108149']['food_policy']=copy.deepcopy(self.policy)
        self.world.begin_plan('meal-1',self.obs, 108186,voiced_trade=voiced);self.sync()
        # The buyer learns neither household allocation nor willingness.
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertNotEqual(context['own_food_allocation'].get('policy'),self.policy)
        self.decide('seek_bread');self.arrive()
        if voiced:
            self.obs['conversationAttendance']={'id':'economic-attend-meal-1','phase':'attending','participants':[
                {'actor':actor,'ownedPackage':True,'loaded':True} for actor in (108186,108149)]}
            self.obs['ack']={'id':'economic-attend-meal-1','status':'applied'}
            self.world.observe(self.obs);self.sync();self.speak()

    def commit_trade(self):
        command=self.world.pending('a');self.assertEqual(command['kind'],'inventory_trade')
        for index,role in ((0,'buyer'),(1,'seller')):self.obs['residents'][index]['inventory']=command['after'][role].copy()
        self.obs['ack']=native_ack(command);self.world.observe(self.obs);self.sync()

    def test_one_offer_can_be_accepted_without_unlocking_remaining_household_stock(self):
        self.prepare();before=copy.deepcopy(self.obs['residents'])
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual({o['id'] for o in context['options']},{'decline','sell_reserved_bread'})
        self.decide('sell_reserved_bread')
        self.assertEqual(self.obs['residents'],before)
        self.assertEqual(simulation_metrics(self.world.active)['economy']['household_release_sales'],0)
        self.commit_trade()
        seller=self.world.active['people']['108149'];self.assertEqual(seller['food_policy'],self.policy)
        self.assertEqual(allocation(seller,self.obs['residents'][1]['inventory'])['for_sale'],0)
        self.assertEqual(self.obs['residents'][1]['inventory']['bread'],2)
        self.assertEqual(sum(r['inventory']['gold'] for r in self.obs['residents']),31)
        self.assertEqual(sum(r['inventory']['bread'] for r in self.obs['residents']),3)
        self.assertEqual(simulation_metrics(self.world.active)['economy']['household_release_sales'],1)
        with self.assertRaisesRegex(ValueError,'household reserve'):
            self.world.plan_trade('reuse-consent',self.obs,108186,108149,agency_plan='meal-1')

    def test_direct_trade_cannot_claim_consent_and_declining_preserves_stock(self):
        self.prepare();before=copy.deepcopy(self.obs['residents'])
        with self.assertRaisesRegex(ValueError,'household reserve'):
            self.world.plan_trade('meal-meal-1',self.obs,108186,108149,agency_plan='meal-1')
        self.decide('decline');self.assertEqual(self.obs['residents'],before)
        self.assertNotIn('reserve_release',self.world.agency_plan())
        self.assertEqual(self.world.agency_plan()['phase'],'reconsider')

    def test_voice_acceptance_must_finish_before_the_reserved_trade_is_prepared(self):
        self.prepare(voiced=True);self.decide('sell_reserved_bread')
        self.assertIsNone(self.world.active['pending'])
        self.assertEqual(self.world.agency_plan()['phase'],'economic_synthesize')
        self.assertEqual(self.world.agency_plan()['economic_speech']['act'],'accept')
        self.speak();self.assertIn('reserve_release',self.world.active['pending'])
        self.commit_trade();self.assertEqual(self.world.agency_plan()['economic_speech']['act'],'receipt')

    def test_changed_policy_during_inference_requires_a_new_decision(self):
        self.prepare();claim=self.world.claim_plan_decision('meal-1',self.obs)['claim'];self.sync()
        self.world.active['people']['108149']['food_policy']['source_event']='changed-policy'
        with self.assertRaisesRegex(ValueError,'allocation changed'):
            self.world.finish_plan_decision('meal-1',claim['id'],{'decision':{'action_id':'sell_reserved_bread','reason':'Fixture','emotion':'calm'}},self.obs)
        self.assertNotIn('reserve_release',self.world.agency_plan())

    def test_authority_is_bound_to_every_term_and_does_not_survive_old_save_load(self):
        self.prepare();old=copy.deepcopy(self.obs)
        claim=self.world.claim_plan_decision('meal-1',self.obs)['claim'];self.sync()
        self.world.finish_plan_decision('meal-1',claim['id'],{'decision':{'action_id':'sell_reserved_bread','reason':'Fixture','emotion':'calm'}},self.obs)
        # Prepared checkpoint exists, but no native trade command is dispatched until it binds.
        state=self.world._read(self.world.transition['next'])
        args=['meal-meal-1',108186,108149,1,3,'meal-1',{'gold':10,'bread':3,'grain':0}]
        self.assertIsNotNone(reserved_sale_consent(state,*args))
        for index,value in enumerate(['another-trade',108156,108186,2,5,'another-plan',{'gold':10,'bread':2,'grain':0}]):
            changed=copy.deepcopy(args);changed[index]=value
            self.assertIsNone(reserved_sale_consent(state,*changed))
        for field,value in [('phase','after_purchase'),('actor',108156),('target',108156)]:
            changed=copy.deepcopy(state);changed['plans'][-1][field]=value
            self.assertIsNone(reserved_sale_consent(changed,*args))
        self.world.observe({**old,'session':'before-reserve-release'})
        self.assertNotIn('reserve_release',self.world.agency_plan())

    def test_failed_native_transfer_is_not_counted_as_a_sale(self):
        self.prepare();self.decide('sell_reserved_bread');command=self.world.pending('a')
        self.obs['ack']=native_ack(command)
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(simulation_metrics(self.world.active)['economy']['household_release_sales'],0)


if __name__=='__main__':unittest.main()
