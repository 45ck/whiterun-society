import unittest
from decisions import make_context, validate_decision


class DecisionContractTests(unittest.TestCase):
    def setUp(self):
        self.event = {'id': 'rumour-1', 'kind': 'shortage_rumour'}
        self.world = {'ready': True, 'session': 'save-a', 'residents': [
            {'id': 108149, 'inventory': {'gold': 10, 'bread': 1}},
            {'id': 108186, 'inventory': {'gold': 2, 'bread': 0}}]}

    def test_cannot_offer_unaffordable_purchase(self):
        context = make_context(108186, self.event, self.world)
        self.assertNotIn('seek_bread_3', [o['id'] for o in context['options']])
        self.assertIn('ask_about_delivery', [o['id'] for o in context['options']])
        with self.assertRaises(ValueError):
            validate_decision({'action_id': 'seek_bread_3', 'reason': 'I want bread.', 'emotion': 'worried'}, context)

    def test_stock_changes_restrict_options(self):
        self.world['residents'][0]['inventory']['bread'] = 0
        context = make_context(108149, self.event, self.world)
        self.assertNotIn('offer_bread_3', [o['id'] for o in context['options']])
        self.assertNotIn('reserve_bread', [o['id'] for o in context['options']])

    def test_no_model_supplied_commands(self):
        context = make_context(108149, self.event, self.world)
        with self.assertRaises(ValueError):
            validate_decision({'action_id': 'reserve_bread', 'reason': 'Family first.',
                               'emotion': 'worried', 'command': 'give gold'}, context)

    def test_valid_proposal_and_limited_knowledge(self):
        context = make_context(108149, self.event, self.world)
        proposal = {'action_id': 'reserve_bread', 'reason': 'Family first.', 'emotion': 'worried'}
        self.assertEqual(validate_decision(proposal, context), proposal)
        self.assertIn('unconfirmed', context['event']['information'])
        self.assertEqual(context['memories'], [])

    def test_unloaded_actor_and_invalid_inventory_fail_closed(self):
        with self.assertRaises(ValueError):
            make_context(108156, self.event, self.world)
        self.world['residents'][0]['inventory']['gold'] = -1
        with self.assertRaises(ValueError):
            make_context(108149, self.event, self.world)
