import copy
import unittest
from unittest.mock import patch

import places
import test_parallel_routines
from places import at_market, market_opportunities, market_opportunity, registered_venues, validate_venue_catalog
from rest import rest_opportunities


SPACE = {'cell': 10, 'interior': False, 'world': 20}


def catalog():
    return {'version': 'changed-town-v2', 'knowledge': 'Authored changed-town public map; not visual perception.',
            'venues': [
                {'id': 700, 'kind': 'public_place', 'name': 'East square', 'access': 'public', 'provenance': 'Inspected test reference'},
                {'id': 800, 'kind': 'public_place', 'name': 'West exchange', 'access': 'public', 'provenance': 'Inspected test reference'},
                {'id': 900, 'kind': 'rest_bench', 'name': 'Garden seat', 'access': 'inspected_unowned', 'provenance': 'Inspected test reference'}]}


def site(venue, x=0):
    return {**venue, 'position': [x, 0, 0], 'space': SPACE, 'available': True,
            'eligible_actors': [1], 'loaded': True, 'occupancy_known': True, 'occupied': False,
            'catalog_version': 'changed-town-v2'}


def observed():
    c = catalog()
    return {'gameDays': 2, 'routing': {'available': True, 'places': True},
            'residents': [{'id': 1, 'isPerson': True, 'x': 100, 'y': 0, 'z': 0, 'space': SPACE}],
            'places': [site(c['venues'][0]), site(c['venues'][1], 1000)],
            'rest': {'available': True, 'sites': [site(c['venues'][2], 300)],
                     'sensors': {'1': {'sit_available': True, 'furniture_reference_available': True, 'sit_state': 0, 'furniture': 0}}}}


class VenueCatalogTests(unittest.TestCase):
    def test_added_renamed_and_reordered_public_venues_follow_observation(self):
        c, obs = catalog(), observed()
        with patch.object(places, 'VENUE_CATALOG', validate_venue_catalog(c)):
            self.assertEqual([s['id'] for s in market_opportunities({}, obs, 1)], [700, 800])
            self.assertEqual(market_opportunity({}, obs, 1)['name'], 'East square')
            self.assertTrue(at_market(obs, 1, 700)); self.assertFalse(at_market(obs, 1, 800))
        c['venues'].reverse()
        next(v for v in c['venues'] if v['id'] == 700)['name'] = 'Renamed square'
        with patch.object(places, 'VENUE_CATALOG', validate_venue_catalog(c)):
            self.assertEqual(market_opportunity({}, obs, 1)['id'], 800)  # Old native name is stale.
            obs['places'][0]['name'] = 'Renamed square'
            self.assertEqual(market_opportunity({}, obs, 1)['name'], 'Renamed square')
            self.assertEqual([s['id'] for s in market_opportunities({}, obs, 1)], [700, 800])

    def test_memory_cooldown_is_per_place_and_removal_has_no_fallback(self):
        c, obs = catalog(), observed()
        state = {'people': {'1': {'memories': [{'kind': 'market_seller_not_observed', 'place': 700, 'day': 1.99}]}}}
        with patch.object(places, 'VENUE_CATALOG', validate_venue_catalog(c)):
            self.assertEqual([s['id'] for s in market_opportunities(state, obs, 1)], [800])
            self.assertIsNone(market_opportunity(state, obs, 1, 700))
        c['venues'] = [v for v in c['venues'] if v['kind'] != 'public_place']
        with patch.object(places, 'VENUE_CATALOG', validate_venue_catalog(c)):
            self.assertEqual(market_opportunities({}, obs, 1), [])
            self.assertFalse(at_market(obs, 1))

    def test_new_bench_is_available_and_removed_bench_cannot_recover(self):
        c, obs = catalog(), observed()
        with patch.object(places, 'VENUE_CATALOG', validate_venue_catalog(c)):
            seats = rest_opportunities({}, obs, 1)
            self.assertEqual([(v['id'], v['name']) for v in seats], [(900, 'Garden seat')])
            obs['rest']['sites'][0]['space'] = {'cell': 90, 'interior': True, 'world': None}
            self.assertEqual(rest_opportunities({}, obs, 1), [])
            obs['rest']['sites'][0]['space'] = SPACE
        c['venues'] = [v for v in c['venues'] if v['kind'] != 'rest_bench']
        with patch.object(places, 'VENUE_CATALOG', validate_venue_catalog(c)):
            self.assertEqual(rest_opportunities({}, obs, 1), [])

    def test_missing_space_stale_catalog_and_nonfinite_positions_do_not_enable_live_venues(self):
        with patch.object(places, 'VENUE_CATALOG', validate_venue_catalog(catalog())):
            for mutation in ({'space': None}, {'catalog_version': 'old-version'}, {'position': [float('nan'), 0, 0]}, {'eligible_actors': []}):
                obs = observed(); obs['places'] = [{**obs['places'][0], **mutation}]
                self.assertEqual(market_opportunities({}, obs, 1), [])
                self.assertFalse(at_market(obs, 1, 700))

    def test_invalid_catalog_is_rejected_and_registered_metadata_is_copied(self):
        c = catalog()
        for mutation in ({'id': True}, {'id': 0}, {'id': 0x100000000}, {'kind': 'private_house'}, {'access': 'private'}, {'name': ''}):
            changed = copy.deepcopy(c); changed['venues'][0].update(mutation)
            with self.assertRaises(ValueError): validate_venue_catalog(changed)
        changed = copy.deepcopy(c); changed['venues'].append(changed['venues'][0])
        with self.assertRaises(ValueError): validate_venue_catalog(changed)
        with patch.object(places, 'VENUE_CATALOG', validate_venue_catalog(c)):
            entries = registered_venues('public_place'); entries[700]['name'] = 'Mutated'
            self.assertEqual(registered_venues('public_place')[700]['name'], 'East square')


class DynamicJourneyCatalogTests(unittest.TestCase):
    setUp = test_parallel_routines.ParallelRoutineTests.setUp
    tearDown = test_parallel_routines.ParallelRoutineTests.tearDown
    sync = test_parallel_routines.ParallelRoutineTests.sync
    census = test_parallel_routines.ParallelRoutineTests.census
    review = test_parallel_routines.ParallelRoutineTests.review
    start = test_parallel_routines.ParallelRoutineTests.start
    choose = test_parallel_routines.ParallelRoutineTests.choose

    def configure(self):
        c = catalog(); self.catalog_patch = patch.object(places, 'VENUE_CATALOG', validate_venue_catalog(c))
        self.catalog_patch.start(); self.addCleanup(self.catalog_patch.stop)
        for actor in self.obs['residents']: actor['space'] = SPACE
        self.obs['places'] = [{**site(c['venues'][0], 0), 'eligible_actors': self.ids},
                              {**site(c['venues'][1], 3000), 'eligible_actors': self.ids}]

    def test_selected_dynamic_destination_survives_reordering_and_receipt_targets_it(self):
        self.configure(); self.start()
        self.assertEqual(set(self.batch['members'][0]['context']['destinations']), {'check_market', 'check_market_800'})
        self.obs['places'].reverse()
        self.choose(('check_market_800', 'check_market_800'))
        jobs = self.world.pending(self.obs['session'])['jobs']
        self.assertEqual({j['target'] for j in jobs}, {800})
        receipts = [{'id': j['id'], 'slot': j['slot'], 'actor_base_id':j['actor_base_id'], 'status': 'applied', 'release_verified': True, 'seller_nearby': False,
                     'movement': {'actor': j['actor'], 'target': 800, 'target_kind': 'place', 'distance': 200,
                                  'aliasesConfirmed': True, 'hasOwnedPackage': True, 'adapter': 'papyrus-mailbox'}} for j in jobs]
        self.obs['ack'] = {'id': 'cohort', 'status': 'applied', 'routines': receipts}
        self.world.observe(self.obs); self.sync()
        self.assertEqual(self.world.routine_batch()['phase'], 'complete')
        for actor in self.ids:
            self.assertEqual(self.world.active['people'][str(actor)]['memories'][-1]['place'], 800)

    def test_departure_cannot_silently_retarget_a_removed_claimed_venue(self):
        self.configure(); self.start()
        self.obs['places'] = [p for p in self.obs['places'] if p['id'] != 800]
        self.choose(('check_market_800', 'check_market_800'))
        self.assertIsNone(self.world.pending(self.obs['session']))
        self.assertEqual(self.world.routine_batch()['phase'], 'held')
        self.assertTrue(all(m['outcome'] == 'changed_before_departure' for m in self.world.routine_batch()['members']))


if __name__ == '__main__': unittest.main()
