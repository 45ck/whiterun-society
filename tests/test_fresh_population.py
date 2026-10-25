"""Fresh population behavior uses the real checkpoint protocol, not legacy seeds."""
import copy
from pathlib import Path
import tempfile
import unittest
from lineage import TimelineEconomy
from catalog_fixture import native_catalog
from legacy_fixture import install_legacy_people


class FreshPopulationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.world=TimelineEconomy(Path(self.temp.name)/'fresh.sqlite')
        self.obs={'session':'fresh','checkpoint':0,'ready':True,'gameDays':4.,
            'economy_catalog':native_catalog(),'routing':{'adapter':'papyrus-mailbox-v1','available':True},
            'residents':[{'id':actor,'name':name,'isPerson':person,
                'inventory':{'gold':gold,'bread':bread,'grain':grain}}
                for actor,name,person,gold,bread,grain in
                [(17,'New artisan',True,13,1,3),(90341,'New neighbour',True,4,2,0),(77,'Observed animal',False,0,0,0)]]}
        self.world.observe(self.obs)

    def tearDown(self):
        self.world.db.close();self.temp.cleanup()

    def bind(self):
        self.assertIsNotNone(self.world.transition)
        self.obs['checkpoint']=self.world.transition['next'];self.obs.pop('ack',None)
        self.world.observe(self.obs)
        self.assertIsNone(self.world.transition)
        self.assertIsNone(self.world.error)

    def bootstrap(self):
        result=self.world.bootstrap(self.obs);self.bind();return result

    def census(self,event='observed-people',seed='explicit-seed'):
        result=self.world.initialize_population(event,seed,self.obs)
        if self.world.transition:self.bind()
        return result

    def test_bootstrap_creates_no_people_even_when_adults_are_observed(self):
        snapshot=copy.deepcopy(self.obs['residents']);self.bootstrap()
        self.assertEqual(self.world.active['people'],{})
        self.assertNotIn('town',self.world.active)
        self.assertEqual(self.world.active['starting_inventory'],snapshot)
        self.assertEqual(self.world.active['starting_inventory_provenance']['session'],'fresh')
        self.assertEqual(self.world.active['starting_inventory_provenance']['checkpoint'],0)
        self.assertIn('not a spendable account',self.world.active['starting_inventory_provenance']['scope'])
        self.assertEqual(self.world.active['trades'],[]);self.assertIsNone(self.world.active['pending'])
        self.assertEqual(self.obs['residents'],snapshot)
        state=copy.deepcopy(self.world.active)
        self.world.observe(self.obs)
        self.assertEqual(self.world.active,state)

    def test_explicit_census_handles_arbitrary_ids_without_original_cast(self):
        self.bootstrap();result=self.census()
        self.assertEqual(set(result['added']),{17,90341})
        self.assertEqual(set(self.world.active['people']),{'17','90341'})
        self.assertEqual(self.world.population_status()['counts']['residents'],2)
        for person in self.world.active['people'].values():
            self.assertEqual(person['initialization']['seed'],'explicit-seed')
            self.assertEqual(set(person['needs']),{'hunger','fatigue','social_contact','safety','comfort'})
            self.assertEqual(len(person['profile']['big_five']),5)

    def test_census_creates_no_assets_acquaintances_or_claimed_history(self):
        self.bootstrap();before=copy.deepcopy(self.obs['residents']);self.census()
        self.assertEqual(self.obs['residents'],before)
        self.assertEqual(self.world.active['starting_inventory'],before)
        self.assertEqual(self.world.active['town']['businesses'],{})
        self.assertEqual(self.world.active['trades'],[]);self.assertIsNone(self.world.active['pending'])
        for person in self.world.active['people'].values():
            self.assertEqual(person['known_people'],{});self.assertEqual(person['relationships'],{})
            self.assertEqual(person['memories'],[]);self.assertEqual(person['commitments'],[])
            self.assertNotIn('known_recipes',person)
        self.assertNotIn('resource_program',self.world.active['town'])

    def test_bootstrap_cannot_replace_bound_history_or_repeat_an_unbound_transition(self):
        self.world.bootstrap(self.obs)
        with self.assertRaisesRegex(ValueError,'transition pending'):self.world.bootstrap(self.obs)
        self.bind();before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'zero-marker'):self.world.bootstrap(self.obs)
        self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_explicit_seed_cannot_silently_change_after_population_initialization(self):
        self.bootstrap();self.census();before=copy.deepcopy(self.world.active)
        self.assertTrue(self.census()['duplicate'])
        for event in ('observed-people','another-census'):
            with self.subTest(event=event),self.assertRaises(ValueError):self.census(event,'another-seed')
        self.assertEqual(self.world.active,before);self.assertIsNone(self.world.transition)

    def test_unknown_classification_is_not_replaced_with_named_demo_profiles(self):
        for row in self.obs['residents']:row['isPerson']=None
        self.bootstrap()
        with self.assertRaisesRegex(ValueError,'positively classified'):self.census()
        self.assertEqual(self.world.active['people'],{})
        self.assertNotIn('town',self.world.active);self.assertIsNone(self.world.transition)

    def test_existing_saved_profiles_and_history_survive_census_and_old_save_load(self):
        self.obs['residents'].append({'id':108186,'name':'Current observed label','isPerson':True,
            'inventory':{'gold':8,'bread':0,'grain':0}})
        self.bootstrap();install_legacy_people(self.world);self.bind()
        saved=copy.deepcopy(self.world.active)
        old=saved['people']['108186']
        old['profile']['priorities']=['A saved personal priority']
        old['memories']=[{'event_id':'historical-test-receipt','kind':'heard','quote':'A saved utterance'}]
        old['trust']={'17':2};old['needs']['hunger']=.73
        self.world._write(saved,'Authored historical checkpoint for preservation test');self.bind()
        earlier=copy.deepcopy(self.obs)
        original=copy.deepcopy(self.world.active['people']['108186'])
        self.census()
        person=self.world.active['people']['108186']
        for field in ('profile','memories','trust'):self.assertEqual(person[field],original[field])
        self.assertEqual(person['needs']['hunger'],.73)
        self.assertEqual(self.world.active['people']['17']['initialization']['seed'],'explicit-seed')
        self.world.observe({**earlier,'session':'loaded-history'})
        self.assertEqual(self.world.active['people']['108186'],original)
        self.assertNotIn('town',self.world.active)
        self.assertNotIn('17',self.world.active['people'])

    def test_test_fixture_is_explicit_and_refuses_to_overwrite_current_people(self):
        self.bootstrap();self.census();before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'empty, bound'):install_legacy_people(self.world)
        self.assertEqual(self.world.active,before)
        self.assertIsNone(self.world.transition)


if __name__=='__main__':unittest.main()
