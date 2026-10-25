import copy
import tempfile
import unittest
from pathlib import Path
from lineage import TimelineEconomy
from legacy_fixture import install_legacy_people
from catalog_fixture import native_catalog
from trade_execution_fixture import qualify_trade_observation, arm_trade, trade_ack


class AgencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.world = TimelineEconomy(Path(self.temp.name)/'timeline.sqlite')
        self.obs = {'session': 'a', 'checkpoint': 0, 'ready': True, 'economy_catalog': native_catalog(), 'residents': [
            {'id': 108186, 'x': 1000, 'y': 0, 'z': 0, 'inventory': {'gold': 9, 'bread': 0, 'grain': 0}},
            {'id': 108149, 'x': 0, 'y': 0, 'z': 0, 'inventory': {'gold': 10, 'bread': 3, 'grain': 0}},
            {'id': 108156, 'x': -1000, 'y': 0, 'z': 0, 'inventory': {'gold': 12, 'bread': 0, 'grain': 0}}]}
        self.obs['routing']={'available':True,'adapter':'papyrus-mailbox-v1'}
        for resident in self.obs['residents']:resident['isPerson']=True
        qualify_trade_observation(self.obs)
        self.world.observe(self.obs)
        self.world.bootstrap(self.obs)
        self.sync()
        install_legacy_people(self.world)
        self.sync()
        # Authored public charter, separate from historical people. No inferred
        # occupation, stock grant, or knowledge of another person's identity.
        state=copy.deepcopy(self.world.active)
        state['town']={'residents':{str(row['id']):{'id':row['id']} for row in self.obs['residents']},'households':{},
                      'businesses':{'fixture-food-shop':{'custodian':108149,
                          'capabilities':['retail_goods'],'sale_commodities':['bread'],
                          'active':True,'revision':1}}}
        self.world._write(state,'Explicit authored public food listing fixture')
        self.sync()

    def tearDown(self):
        self.world.db.close()
        self.temp.cleanup()

    def sync(self):
        for _ in range(8):
            if not self.world.transition:
                return
            self.obs['checkpoint'] = self.world.transition['next']
            self.obs.pop('ack', None)
            self.world.observe(self.obs)
        self.fail('Checkpoint loop did not settle')

    def start(self):
        self.world.begin_plan('meal-1', self.obs, 108186)
        self.sync()

    def decide(self, action):
        claim = self.world.claim_plan_decision('meal-1', self.obs)['claim']
        self.assertEqual(self.world.pending('a')['kind'], 'bind_checkpoint')
        self.sync()
        result = {'decision': {'action_id': action, 'reason': 'An authored test decision.', 'emotion': 'calm'},
                  'model': 'unit-test', 'elapsed_seconds': 0}
        self.world.finish_plan_decision('meal-1', claim['id'], result, self.obs)
        self.sync()

    def arrive(self, owned=True):
        self.obs['residents'][0]['x'] = 200
        self.obs['ack'] = {'id': 'travel-meal-1', 'status': 'applied', 'movement': {
            'hasOwnedPackage': owned, 'aliasesConfirmed':True, 'adapter':'papyrus-mailbox',
            'actor':108186, 'target':108149}}
        self.world.observe(self.obs)
        self.sync()

    def test_choice_travel_consent_trade_memory_and_release(self):
        self.start()
        self.decide('seek_bread')
        command = self.world.pending('a')
        self.assertEqual((command['kind'], command['target'], command['retain']), ('walk_to',108149,True))
        self.arrive()
        self.assertEqual(self.world.agency_plan()['phase'], 'quote')
        self.decide('bid_price_3')
        self.assertEqual(self.world.agency_plan()['phase'], 'consent')
        self.assertIsNone(self.world.pending('a'))
        self.decide('sell_bread')
        command = arm_trade(self.world,self.obs,self.sync)
        self.assertEqual(command['kind'], 'inventory_trade')
        self.assertEqual(command['phase'], 'deliver')
        self.assertEqual(command['catalog_hash'],native_catalog()['catalog_hash'])
        for index, role in [(0, 'buyer'), (1, 'seller')]:
            self.obs['residents'][index]['inventory'] = command['after'][role]
        self.obs['ack'] = trade_ack(command)
        self.world.observe(self.obs)
        self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'after_purchase')
        self.decide('keep_food')
        self.assertEqual(self.world.agency_plan()['outcome'], 'bought_bread')
        self.assertEqual(len(self.world.status()['people']['108186']['memories']), 1)
        self.assertEqual(self.world.pending('a')['kind'], 'release_routine')
        self.obs['ack'] = {'id': 'release-meal-1', 'status': 'applied'}
        self.world.observe(self.obs)
        self.sync()
        self.assertFalse(self.world.agency_busy())
        self.assertIsNone(self.world.pending('a'))
        # A second event receives the actual earlier trade memory.
        self.world.begin_plan('meal-2', self.obs, 108186)
        self.sync()
        claim = self.world.claim_plan_decision('meal-2', self.obs)['claim']
        self.assertEqual(claim['context']['memories'][0]['event_id'], 'meal-meal-1')
        self.assertNotIn('seek_bread', [o['id'] for o in claim['context']['options']])

    def test_seller_can_refuse_without_mutating_inventory(self):
        self.start(); self.decide('seek_bread'); self.arrive(); self.decide('bid_price_3')
        before = copy.deepcopy(self.obs['residents'])
        self.decide('decline')
        self.assertEqual(self.world.agency_plan()['phase'], 'reconsider')
        self.assertEqual(self.world.status()['people']['108186']['memories'][-1]['kind'], 'trade_offer_declined')
        self.decide('leave_without_food')
        self.assertEqual(self.world.agency_plan()['outcome'], 'left_without_food')
        self.assertEqual(self.obs['residents'], before)
        self.assertEqual(self.world.state(), [])
        self.obs['ack']={'id':'release-meal-1','status':'applied'}
        self.world.observe(self.obs);self.sync()
        memory=self.world.status()['people']['108186']['memories'][0]
        self.assertEqual(memory['kind'],'trade_offer_declined')
        self.assertEqual(self.world.status()['people']['108186']['trust'],{})

    def test_reconsideration_receives_refusal_and_cannot_repeat_unchanged_offer(self):
        self.start(); self.decide('seek_bread'); self.arrive(); self.decide('bid_price_3'); self.decide('decline')
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertEqual(context['memories'][-1]['gold'],3)
        self.assertTrue({'leave_without_food','visit_person_108156','bid_price_5'} <= {o['id'] for o in context['options']})
        self.assertNotIn('bid_price_3',[o['id'] for o in context['options']])
        self.obs['residents'][0]['inventory']['gold']=4
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertNotIn('bid_price_5',[o['id'] for o in context['options']])

    def test_higher_offer_requires_new_seller_consent_and_moves_exact_agreed_price(self):
        self.start(); self.decide('seek_bread'); self.arrive(); self.decide('bid_price_3'); self.decide('decline')
        self.decide('bid_price_5')
        self.assertEqual(self.world.agency_plan()['phase'],'consent')
        self.assertEqual(self.world.state(),[])
        context=self.world._plan_context(self.obs,self.world.agency_plan())
        self.assertIn('5 septims',context['event']['information'])
        self.assertEqual(context['memories'][-1]['role'],'seller')
        self.decide('sell_bread')
        command=self.world.pending('a')
        self.assertEqual(command['cost'],5)
        self.assertEqual(command['after']['buyer'],{'gold':4,'bread':1,'grain':0})
        self.assertEqual(command['after']['seller'],{'gold':15,'bread':2,'grain':0})

    def test_second_refusal_ends_negotiation_without_duplicate_memories(self):
        self.start(); self.decide('seek_bread'); self.arrive(); self.decide('bid_price_3'); self.decide('decline')
        self.decide('bid_price_5'); self.decide('decline')
        self.assertEqual(self.world.agency_plan()['outcome'],'seller_declined')
        self.obs['ack']={'id':'release-meal-1','status':'applied'}
        self.world.observe(self.obs);self.sync();self.world.observe(self.obs)
        for person in ('108186','108149'):
            self.assertEqual([m['gold'] for m in self.world.status()['people'][person]['memories']],[3,5])
        self.assertFalse(self.world.agency_busy())

    def test_changed_destination_has_a_new_native_command_and_keeps_old_trip_evidence(self):
        self.start();self.decide('seek_bread');self.arrive();self.decide('bid_price_3');self.decide('decline')
        old=self.world.agency_plan()['travel_id']
        self.decide('visit_person_108156')
        new=self.world.pending('a')
        self.assertNotEqual(new['id'],old)
        self.assertEqual(new['target'],108156)
        self.assertEqual(self.world.agency_plan()['travel_history'][0]['id'],old)

    def test_loading_before_reconsideration_removes_later_refusal_and_offer(self):
        self.start();self.decide('seek_bread');self.arrive();self.decide('bid_price_3')
        before=copy.deepcopy(self.obs)
        self.decide('decline');self.decide('bid_price_5')
        self.world.observe({**before,'session':'restored-before-refusal'})
        self.assertEqual(self.world.agency_plan()['phase'],'consent')
        self.assertEqual(self.world.agency_plan()['unit_price'],3)
        self.assertEqual(self.world.status()['people']['108186']['memories'],[])

    def test_private_seller_stock_is_not_revealed_by_buyers_options(self):
        self.obs['residents'][1]['inventory']['bread']=0
        self.start()
        context=self.world.claim_plan_decision('meal-1',self.obs)['claim']['context']
        self.assertIn('seek_bread',[o['id'] for o in context['options']])
        self.assertNotIn('residents',context)

    def test_vanilla_proximity_cannot_advance_to_consent(self):
        self.start(); self.decide('seek_bread'); self.arrive(False)
        self.assertEqual(self.world.agency_plan()['phase'], 'held')
        self.assertEqual(self.world.pending('a')['kind'], 'release_routine')

    def test_unqualified_vision_does_not_leak_sensor_diagnostics_or_hidden_people(self):
        self.obs['perception']={'108186':{'available':False,'visible':[{'id':108149}],
                                        'diagnostics':{'nearby':7}}}
        self.start()
        context=self.world.claim_plan_decision('meal-1',self.obs)['claim']['context']
        self.assertFalse(context['perception']['available'])
        self.assertNotIn('diagnostics',context['perception'])
        self.assertNotIn('visible',context['perception'])

    def test_claim_is_not_reissued_and_old_save_restores_old_plan(self):
        before = copy.deepcopy(self.obs)
        self.start()
        self.world.claim_plan_decision('meal-1', self.obs)
        self.sync()
        with self.assertRaises(ValueError):
            self.world.claim_plan_decision('meal-1', self.obs)
        thinking = copy.deepcopy(self.obs)
        self.world.observe({**before, 'session': 'old-save'})
        self.assertIsNone(self.world.agency_plan())
        self.world.observe({**thinking, 'session': 'thinking-save'})
        self.obs = {**thinking, 'session': 'thinking-save'}
        self.sync()
        self.assertEqual(self.world.agency_plan()['phase'], 'held')

    def test_replayed_event_does_not_repeat_hunger_or_model_claim(self):
        self.start(); self.decide('defer')
        hunger = self.world.status()['people']['108186']['needs']['hunger']
        result = self.world.begin_plan('meal-1', self.obs, 108186)
        self.assertTrue(result['duplicate'])
        self.assertEqual(self.world.status()['people']['108186']['needs']['hunger'], hunger)
        self.assertIsNone(self.world.transition)

    def test_missing_and_invalid_actor_rejected_without_state_changes(self):
        from server import begin_agency_event
        before=copy.deepcopy(self.world.active)
        marker=self.world.marker
        changes=self.world.db.total_changes
        for actor in (None,True,False,'108186',108186.0,0,-1,0x100000000,987654321):
            for api in (False,True):
                with self.subTest(actor=actor,api=api),self.assertRaisesRegex(ValueError,'explicit valid resident'):
                    if api:begin_agency_event(self.world,self.obs,{'id':'invalid-actor','actor':actor})
                    else:self.world.begin_plan('invalid-actor',self.obs,actor)
                self.assertEqual(self.world.active,before)
                self.assertEqual(self.world.marker,marker)
                self.assertEqual(self.world.db.total_changes,changes)
                self.assertIsNone(self.world.transition)
        with self.assertRaisesRegex(ValueError,'explicit valid resident'):
            self.world.begin_plan('missing-actor',self.obs)
        with self.assertRaisesRegex(ValueError,'explicit valid resident'):
            begin_agency_event(self.world,self.obs,{'id':'missing-actor'})
        self.assertEqual(self.world.active,before)
        self.assertEqual(self.world.db.total_changes,changes)

    def test_event_dispatch_accepts_an_explicit_new_resident_and_replays_idempotently(self):
        from server import begin_agency_event
        actor=7654321
        self.world.active['people'][str(actor)]=copy.deepcopy(self.world.active['people']['108186'])
        self.obs['residents'].append({**self.obs['residents'][0],'id':actor})
        original=copy.deepcopy(self.world.active['people']['108186'])
        data={'id':'new-resident','actor':actor}
        result=begin_agency_event(self.world,self.obs,data)
        self.assertEqual(result['plan']['actor'],actor)
        self.sync()
        before=copy.deepcopy(self.world.active)
        changes=self.world.db.total_changes
        self.assertTrue(begin_agency_event(self.world,self.obs,data)['duplicate'])
        self.assertEqual(self.world.active,before)
        self.assertEqual(self.world.db.total_changes,changes)
        self.assertEqual(self.world.active['people']['108186'],original)
        with self.assertRaisesRegex(ValueError,'reused'):
            begin_agency_event(self.world,self.obs,{**data,'actor':108186})
        self.assertEqual(self.world.active,before)

    def test_legacy_saved_travel_is_held_before_cached_arrival_ack(self):
        self.start();self.decide('seek_bread')
        current=copy.deepcopy(self.world.active)
        for flag in (None,False,1):
            with self.subTest(dynamic_route=flag):
                state=copy.deepcopy(current)
                if flag is None:state['plans'][-1].pop('dynamic_route',None)
                else:state['plans'][-1]['dynamic_route']=flag
                self.world._write(state,'offline legacy saved plan fixture')
                self.obs['checkpoint']=self.world.transition['next']
                self.arrive()  # Cached applied arrival is present as the saved plan binds.
                plan=self.world.agency_plan()
                self.assertEqual(plan['phase'],'held')
                self.assertIn('dynamic mailbox',plan['error'])
                self.assertTrue(plan['release_required'])
                self.assertIsNone(plan['travel'])
                self.assertEqual(self.world.pending('a')['kind'],'release_routine')
                self.assertEqual(self.world.state(),[])
