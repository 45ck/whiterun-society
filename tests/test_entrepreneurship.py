import copy
import unittest
import test_enterprises as fixtures
from entrepreneurship import enterprise_choices, knows_bread_recipe, learn_bread_recipe
from opportunities import food_sellers
from metrics import simulation_metrics


class EntrepreneurshipTests(unittest.TestCase):
    setUp = fixtures.EnterpriseTests.setUp
    tearDown = fixtures.EnterpriseTests.tearDown
    sync = fixtures.EnterpriseTests.sync
    decide = fixtures.EnterpriseTests.decide

    def begin(self, actor=9, event='livelihood'):
        self.world.active['town']['daily'] = {'queue':[
            {'id':event,'actor':actor,'kind':'need_review','status':'pending'}]}
        self.world.begin_plan(event,self.obs,actor,'need_review');self.sync()
        return self.world._plan_context(self.obs,self.world.agency_plan())

    def test_new_cast_registers_own_stock_without_native_asset_effects(self):
        before=copy.deepcopy(self.obs['residents'])
        context=self.begin()
        self.assertIn('offer_food_trade_resident-9',context['enterprise_options'])
        self.assertIn('offer_grain_trade_resident-9',context['enterprise_options'])
        self.assertFalse(context['own_recipe_knowledge']['bread'])
        self.assertNotIn('register_bakery_resident-9',context['enterprise_options'])
        self.decide('offer_food_trade_resident-9','livelihood')
        self.assertEqual(self.world.agency_plan()['outcome'],'enterprise_registered')
        business=self.world.active['town']['businesses']['resident-9']
        self.assertEqual((business['owner'],business['custodian'],business['revision']),(9,9,1))
        self.assertEqual(before,self.obs['residents'])
        self.assertIsNone(self.world.active['pending'])
        self.assertEqual([s['id'] for s in food_sellers(self.world.active,self.obs,8)],[9])
        event=self.world.active['town']['enterprise_events'][-1]
        self.assertEqual((event['actor'],event['plan_id'],event['inventory_effect']),(9,'livelihood','none'))
        self.assertEqual(self.world.active['people']['9']['memories'][-1]['kind'],'enterprise_changed')
        self.assertEqual(simulation_metrics(self.world.active)['economy']['resident_enterprise_changes'],1)

    def test_owner_can_expand_close_reopen_and_save_restores_revision(self):
        self.begin();self.decide('offer_food_trade_resident-9','livelihood')
        saved=copy.deepcopy(self.obs)
        self.begin(event='expand');self.decide('offer_grain_trade_resident-9','expand')
        self.assertEqual(self.world.agency_plan()['outcome'],'enterprise_expanded')
        self.begin(event='close');self.decide('close_enterprise_resident-9','close')
        self.assertEqual(self.world.agency_plan()['outcome'],'enterprise_closed')
        self.assertEqual(food_sellers(self.world.active,self.obs,8),[])
        options=self.begin(event='reopen')['enterprise_options']
        self.assertEqual(set(options),{'reopen_enterprise_resident-9'})
        self.decide('reopen_enterprise_resident-9','reopen')
        self.assertEqual(self.world.agency_plan()['outcome'],'enterprise_reopened')
        self.world.observe({**saved,'session':'before-enterprise-expansion'})
        business=self.world.active['town']['businesses']['resident-9']
        self.assertEqual((business['revision'],business['capabilities']),(1,['retail_food']))
        self.assertEqual(len(self.world.active['town']['enterprise_events']),1)

    def test_stale_revision_and_open_contract_invalidate_pending_choices(self):
        self.begin();self.decide('offer_food_trade_resident-9','livelihood')
        self.begin(event='stale')
        claim=self.world.claim_plan_decision('stale',self.obs)['claim'];self.sync()
        business=self.world.active['town']['businesses']['resident-9'];business['revision']+=1
        with self.assertRaisesRegex(ValueError,'enterprise revision changed'):
            self.world.finish_plan_decision('stale',claim['id'],{'decision':{
                'action_id':'close_enterprise_resident-9','reason':'Close','emotion':'calm'}},self.obs)
        self.assertTrue(business['active'])
        business['contracts']=[{'status':'accepted'}]
        self.assertEqual(enterprise_choices(self.world.active,self.obs,9),[])

    def test_no_cross_owner_control_or_others_private_knowledge(self):
        self.world.active['town']['businesses']['resident-9']={
            'owner':7,'custodian':7,'revision':1,'active':True,'capabilities':['retail_grain']}
        learn_bread_recipe(self.world.active['people']['7'],'verified-work')
        context=self.begin()
        self.assertEqual(context['enterprise_options'],{})
        self.assertFalse(context['own_recipe_knowledge']['bread'])

    def test_recipe_requires_verified_own_participation_and_inputs_or_capital(self):
        person=self.world.active['people']['9']
        person['memories'].append({'kind':'heard_recipe','grain_used':1,'bread_made':2})
        self.assertFalse(knows_bread_recipe(person))
        learn_bread_recipe(person,'production-proof')
        person['memories']=[]
        self.assertTrue(knows_bread_recipe(person))
        options={o['id'] for o in enterprise_choices(self.world.active,self.obs,9)}
        self.assertIn('register_bakery_resident-9',options)
        self.obs['residents'][2]['inventory']={'gold':0,'bread':0,'grain':0}
        self.assertEqual(enterprise_choices(self.world.active,self.obs,9),[])

    def test_guard_can_trade_own_stock_but_unclassified_or_busy_actor_cannot(self):
        native=self.obs['residents'][2];native['isGuard']=True
        self.world.active['town']['residents']['9']['is_guard']=True
        self.begin();self.decide('offer_grain_trade_resident-9','livelihood')
        self.assertEqual(self.world.active['town']['businesses']['resident-9']['custodian'],9)
        native['isPerson']=False
        self.assertEqual(enterprise_choices(self.world.active,self.obs,9),[])
        native['isPerson']=True;native['activity']={'in_combat':True}
        self.assertEqual(enterprise_choices(self.world.active,self.obs,9),[])

    def test_changed_stock_rejects_inference_without_registration(self):
        self.begin();claim=self.world.claim_plan_decision('livelihood',self.obs)['claim'];self.sync()
        self.obs['residents'][2]['inventory']['bread']=0
        with self.assertRaises(ValueError):
            self.world.finish_plan_decision('livelihood',claim['id'],{'decision':{
                'action_id':'offer_food_trade_resident-9','reason':'Sell','emotion':'calm'}},self.obs)
        self.assertEqual(self.world.active['town']['businesses'],{})

    def test_planned_legacy_industry_cannot_offer_an_invalid_charter_revision(self):
        self.world.active['town']['businesses']['workshop']={
            'owner':9,'custodian':9,'capabilities':['metalwork_planned'],'name':'Planned workshop'}
        choices=enterprise_choices(self.world.active,self.obs,9)
        self.assertEqual({c['id'] for c in choices},{'offer_food_trade_resident-9','offer_grain_trade_resident-9'})
        self.begin();self.decide('offer_food_trade_resident-9','livelihood')
        self.assertEqual(self.world.active['town']['businesses']['workshop']['capabilities'],['metalwork_planned'])
        self.assertEqual(self.world.active['town']['businesses']['resident-9']['capabilities'],['retail_food'])


if __name__=='__main__':unittest.main()
