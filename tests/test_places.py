import copy
import unittest
import test_agency
from places import MARKET, market_opportunity


class PlacesTests(unittest.TestCase):
    tearDown=test_agency.AgencyTests.tearDown
    sync=test_agency.AgencyTests.sync
    start=test_agency.AgencyTests.start
    decide=test_agency.AgencyTests.decide

    def setUp(self):
        test_agency.AgencyTests.setUp(self)
        self.obs['gameDays']=3.
        self.obs['routing']={'available':True,'places':True,'adapter':'papyrus-mailbox-v1'}
        self.obs['places']=[{'id':MARKET,'available':True,'position':[0,0,0],'eligible_actors':[108186]}]
        self.seller=self.obs['residents'].pop(1)
        for r in self.obs['residents']:r.update(isPerson=True,isGuard=False)

    def arrive_market(self,owned=True,kind='place'):
        self.obs['residents'][0]['x']=200
        self.obs['ack']={'id':'travel-meal-1','status':'applied','movement':{
            'hasOwnedPackage':owned,'aliasesConfirmed':True,'adapter':'papyrus-mailbox',
            'actor':108186,'target':MARKET,'target_kind':kind}}
        self.world.observe(self.obs);self.sync()

    def test_known_destination_does_not_disclose_absent_seller_stock(self):
        self.start();context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertIn('check_market',[o['id'] for o in context['options']])
        self.assertNotIn('seek_bread',[o['id'] for o in context['options']])
        self.assertEqual(context['observed_inventory'],{'gold':9,'bread':0,'grain':0})
        self.decide('check_market')
        command=self.world.pending('a')
        self.assertEqual((command['target'],command['target_kind'],command['dynamic']),(MARKET,'place',True))

    def test_absent_seller_means_no_trade_no_need_relief_and_a_bounded_memory(self):
        self.start();self.decide('check_market');before=copy.deepcopy(self.obs['residents'])
        hunger=self.world.active['people']['108186']['needs']['hunger']
        self.arrive_market()
        self.assertEqual(self.world.agency_plan()['outcome'],'market_seller_not_observed')
        self.assertEqual(self.world.pending('a')['kind'],'release_routine')
        self.obs['ack']={'id':'release-meal-1','status':'applied'}
        self.world.observe(self.obs);self.sync();self.world.observe(self.obs);self.sync()
        person=self.world.active['people']['108186']
        self.assertEqual(person['needs']['hunger'],hunger)
        self.assertEqual(self.obs['residents'][0]['inventory'],before[0]['inventory'])
        self.assertEqual(person['memories'][-1]['kind'],'market_seller_not_observed')
        self.assertIsNone(market_opportunity(self.world.active,self.obs,108186))
        self.obs['gameDays']+=5/24
        self.assertIsNotNone(market_opportunity(self.world.active,self.obs,108186))

    def test_seller_found_on_arrival_still_needs_consent(self):
        self.start();self.decide('check_market')
        self.obs['residents'].append({**self.seller,'isPerson':True})
        self.obs['places'][0]['eligible_actors'].append(108149)
        self.arrive_market()
        self.assertEqual(self.world.agency_plan()['phase'],'quote')
        self.assertEqual(self.world.state(),[])
        self.decide('bid_price_3')
        self.assertEqual(self.world.agency_plan()['phase'],'consent')
        self.assertEqual(self.world.agency_plan()['target'],108149)
        self.assertEqual(self.world.state(),[])

    def test_same_coordinates_in_another_space_are_not_a_seller_encounter(self):
        self.start();self.decide('check_market');self.obs['residents'].append(self.seller)
        self.arrive_market()
        self.assertEqual(self.world.agency_plan()['outcome'],'market_seller_not_observed')

    def test_place_binding_and_owned_arrival_are_required(self):
        for owned,kind in [(False,'place'),(True,'resident')]:
            with self.subTest(owned=owned,kind=kind):
                if self.world.agency_plan():
                    self.tearDown();self.setUp()
                self.start();self.decide('check_market');self.arrive_market(owned,kind)
                self.assertEqual(self.world.agency_plan()['phase'],'held')

    def test_role_and_duties_allow_choice_but_sensor_and_space_are_required(self):
        for change in ('guard','commitment','sensor','space'):
            with self.subTest(change=change):
                state=copy.deepcopy(self.world.active);obs=copy.deepcopy(self.obs)
                if change=='guard':obs['residents'][0]['isGuard']=True
                if change=='commitment':state['people']['108186']['commitments']=['duty']
                if change=='sensor':obs.pop('places')
                if change=='space':obs['places'][0]['eligible_actors']=[]
                if change in ('guard','commitment'):self.assertIsNotNone(market_opportunity(state,obs,108186))
                else:self.assertIsNone(market_opportunity(state,obs,108186))

    def test_stale_available_place_cannot_validate_new_choice(self):
        self.start();claim=self.world.claim_plan_decision('meal-1',self.obs)['claim'];self.sync()
        self.obs['places'][0]['available']=False
        with self.assertRaisesRegex(ValueError,'currently allowed'):
            self.world.finish_plan_decision('meal-1',claim['id'],{'decision':{
                'action_id':'check_market','reason':'test','emotion':'calm'}},self.obs)
