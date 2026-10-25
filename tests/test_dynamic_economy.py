import copy
import json
import unittest
import test_daily_life as daily_fixtures
from population import person_seed
from opportunities import food_sellers
from trade_execution_fixture import qualify_trade_observation


class DynamicEconomyTests(unittest.TestCase):
    tearDown = daily_fixtures.DailyLifeTests.tearDown
    sync = daily_fixtures.DailyLifeTests.sync
    census = daily_fixtures.DailyLifeTests.census
    review = daily_fixtures.DailyLifeTests.review

    def setUp(self):
        daily_fixtures.DailyLifeTests.setUp(self)
        self.obs['routing'] = {'adapter': 'papyrus-mailbox-v1', 'available': True}
        day = self.obs['gameDays']
        rows = [{'id': aid, 'name': name, 'isPerson': True, 'isGuard': False,
                 'x': x, 'y': 0, 'z': 0, 'inventory': {'gold': gold, 'bread': bread, 'grain': 0}}
                for aid, name, x, gold, bread in [(99, 'Buyer', 0, 7, 0),
                    (501, 'Secret seller name', 100, 7139, 2), (502, 'Second secret name', 200, 9173, 0)]]
        self.obs['residents'] = rows
        qualify_trade_observation(self.obs)
        self.world.active['people'] = {str(r['id']): person_seed(r, 'dynamic-economy', day) for r in rows}
        self.world.active['people']['99']['needs'].update(hunger=.9, fatigue=.1)
        town = self.world.active['town']
        town['residents'] = {str(r['id']): {'id': r['id'], 'name': r['name'], 'observed_game_day': day,
                                         'is_guard': False} for r in rows}
        town['businesses'] = {'new-shop': {'custodian': 501, 'capabilities': ['retail_food']}}
        self.review()
        self.event = next(e for e in town.get('daily', {}).get('queue', []) if e['actor'] == 99) if town.get('daily') else next(
            e for e in self.world.active['town']['daily']['queue'] if e['actor'] == 99)

    def claim(self):
        self.world.begin_plan(self.event['id'], self.obs, 99, 'need_review'); self.sync()
        claim = self.world.claim_plan_decision(self.event['id'], self.obs)['claim']; self.sync()
        return claim

    def choose(self, claim, action='seek_bread'):
        return self.world.finish_plan_decision(self.event['id'], claim['id'], {'model': 'fixture', 'decision':
            {'action_id': action, 'reason': 'Find food', 'emotion': 'calm'}}, self.obs)

    def test_new_business_owner_is_selected_without_private_name_or_stock(self):
        claim = self.claim()
        context = claim['context']
        self.assertEqual(context['option_targets']['seek_bread'], 501)
        for secret in ('Secret seller name', 'Second secret name', '7139', '9173', 'Carlotta', 'Adrianne'):
            self.assertNotIn(secret, json.dumps(context))
        self.choose(claim); self.sync()
        command = self.world.pending(self.obs['session'])
        self.assertEqual((command['actor'], command['target']), (99, 501))
        self.assertTrue(command['dynamic'])

    def test_shop_selection_does_not_assume_stock_or_consent(self):
        before = copy.deepcopy(self.obs)
        self.world.active['town']['businesses']['other-shop'] = {'custodian': 502, 'capabilities': ['retail_food']}
        candidates = food_sellers(self.world.active, self.obs, 99)
        self.assertEqual([c['id'] for c in candidates], [501, 502])
        self.assertEqual(before, self.obs)
        self.assertNotIn('inventory', json.dumps(candidates))

    def test_changed_shop_cannot_redirect_an_inflight_choice(self):
        claim = self.claim()
        self.world.active['town']['businesses']['new-shop']['custodian'] = 502
        with self.assertRaisesRegex(ValueError, 'destination changed'):self.choose(claim)
        self.assertEqual(self.world.agency_plan()['phase'], 'thinking')

    def test_unloaded_seller_cannot_be_selected(self):
        claim = self.claim()
        self.obs['residents'] = [r for r in self.obs['residents'] if r['id'] != 501]
        with self.assertRaisesRegex(ValueError, 'not currently allowed'):self.choose(claim)

    def test_line_of_sight_does_not_reveal_roster_name(self):
        self.obs['perception'] = {'99': {'available': True, 'visible': [
            {'id': 501, 'name': 'Secret seller name', 'distance': 100, 'inventory': {'gold': 7139}}]}}
        context = self.claim()['context']
        self.assertEqual(context['perception']['visible'][0]['name'], 'an unfamiliar resident')
        self.assertNotIn('Secret seller name', json.dumps(context))
        self.assertNotIn('7139', json.dumps(context))
