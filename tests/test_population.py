import copy
import unittest
import test_food


class PopulationTests(unittest.TestCase):
    setUp=test_food.FoodTests.setUp
    tearDown=test_food.FoodTests.tearDown
    sync=test_food.FoodTests.sync

    def census(self):
        self.obs['gameDays']=3.5
        for a in self.obs['residents']:a.update(isPerson=True,isGuard=False,name=str(a['id']));a['inventory']['grain']=0
        self.obs['residents'] += [{'id':99,'name':'New resident','isPerson':True,'inventory':{'gold':7,'bread':1,'grain':0}},
                                 {'id':100,'name':'Cow','isPerson':False,'inventory':{'gold':0,'bread':0,'grain':0}}]
    def initialize(self,id='census'):
        self.world.initialize_population(id,'demo-seed',self.obs);self.sync()

    def test_seeds_all_classified_people_without_minting_or_animals(self):
        self.census();before=copy.deepcopy(self.obs['residents']);self.initialize()
        town=self.world.population_status();self.assertEqual(town['counts']['residents'],3)
        self.assertNotIn('100',self.world.active['people']);self.assertEqual(self.obs['residents'],before)
        person=self.world.active['people']['99'];self.assertEqual(len(person['profile']['big_five']),5)
        self.assertEqual(len(person['needs']),5);self.assertEqual(person['agency']['state'],'awaiting_first_daily_plan')
        self.assertIs(person['agency']['native_route_supported'],True)
        self.assertEqual(town['counts']['native_route_supported'],3)
        self.assertEqual(town['businesses'],{})  # Census does not assign named occupations.

    def test_existing_personality_memories_and_hunger_survive_expansion(self):
        self.census();old=copy.deepcopy(self.world.active['people']['108186']);self.initialize()
        person=self.world.active['people']['108186']
        self.assertEqual(person['profile'],old['profile']);self.assertEqual(person['memories'],old['memories'])
        self.assertEqual(person['needs']['hunger'],old['needs']['hunger'])

    def test_repeated_census_cannot_reseed_or_reset_people(self):
        self.census();self.initialize();before=copy.deepcopy(self.world.active)
        self.assertTrue(self.world.initialize_population('census','demo-seed',self.obs)['duplicate'])
        self.assertEqual(before,self.world.active)
        with self.assertRaisesRegex(ValueError,'reseeded'):self.world.initialize_population('second','other-seed',self.obs)

    def test_old_save_removes_future_population_and_census_adds_later_residents(self):
        self.census();old=copy.deepcopy(self.obs);self.initialize()
        self.obs['residents'].append({'id':101,'name':'Late arrival','isPerson':True,'inventory':{'gold':3,'bread':0,'grain':0}})
        self.initialize('later');self.assertEqual(self.world.population_status()['counts']['residents'],4)
        self.world.observe({**old,'session':'older-save'});self.assertIsNone(self.world.population_status())
        self.assertNotIn('99',self.world.active['people'])

    def test_unknown_classification_is_not_assumed_human(self):
        self.census()
        for a in self.obs['residents']:a['isPerson']=None
        with self.assertRaisesRegex(ValueError,'positively classified'):self.initialize()

    def test_bad_inventory_and_clock_are_rejected_before_state_changes(self):
        self.census();self.obs['residents'][0]['inventory']['gold']=-1
        with self.assertRaises(ValueError):self.initialize()
        self.obs['residents'][0]['inventory']['gold']=1;self.obs['gameDays']=float('nan')
        with self.assertRaises(ValueError):self.initialize()


if __name__=='__main__':unittest.main()
