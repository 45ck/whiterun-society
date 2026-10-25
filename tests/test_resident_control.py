import copy
import unittest
import test_population
from resident_control import sync_resident_assignments
from tools.verify_plan_save import plugins_compatible


class ResidentControlTests(unittest.TestCase):
    setUp=test_population.PopulationTests.setUp
    tearDown=test_population.PopulationTests.tearDown
    sync=test_population.PopulationTests.sync
    census=test_population.PopulationTests.census
    initialize=test_population.PopulationTests.initialize

    def ready(self):
        self.census();self.initialize()
        self.obs['resident_control']={'available':True}

    def test_policy_is_save_bound_and_does_not_change_people_or_inventory(self):
        self.ready();before=copy.deepcopy(self.world.active);observation=copy.deepcopy(self.obs)
        result=self.world.configure_resident_control('enable',True,self.obs)
        self.assertTrue(self.world.transition)
        self.assertEqual(self.world.active['people'],before['people'])
        self.assertEqual(self.obs,observation)
        self.sync();control=self.world.population_status(self.obs)['resident_control']
        self.assertEqual(len(control['assignments']),3)
        self.assertTrue(all(a['mode']=='await_decision' for a in control['assignments'].values()))
        self.assertTrue(self.world.configure_resident_control('enable',True,self.obs)['duplicate'])
        with self.assertRaisesRegex(ValueError,'reused'):self.world.configure_resident_control('enable',False,self.obs)
        self.world.observe({**observation,'session':'restore-before-policy'})
        self.assertNotIn('resident_control',self.world.population_status())

    def test_unavailable_plugin_and_non_boolean_setting_cannot_mutate(self):
        self.ready();before=copy.deepcopy(self.world.active)
        self.obs['resident_control']['available']=False
        with self.assertRaisesRegex(ValueError,'unavailable'):self.world.configure_resident_control('enable',True,self.obs)
        with self.assertRaisesRegex(ValueError,'boolean'):self.world.configure_resident_control('enable',1,self.obs)
        self.assertEqual(self.world.active,before)

    def test_census_expands_control_without_reassigning_existing_slots(self):
        self.ready();self.world.configure_resident_control('enable',True,self.obs);self.sync()
        old=copy.deepcopy(self.world.population_status(self.obs)['resident_control']['assignments'])
        self.obs['residents'].append({'id':101,'baseId':1101,'name':'Arrival','isPerson':True,'inventory':{'gold':2,'bread':0,'grain':0}})
        self.initialize('later');new=self.world.population_status(self.obs)['resident_control']['assignments']
        self.assertEqual({key:new[key] for key in old},old)
        self.assertIn('101',new);self.assertEqual(len({a['slot'] for a in new.values()}),4)
        self.assertTrue(all(type(row['actor_base_id']) is int for row in new.values()))
        saved={key:{field:value for field,value in row.items() if field!='actor_base_id'} for key,row in new.items()}
        self.assertEqual(saved,self.world.active['town']['resident_control']['assignments'])
        self.world.observe({**self.obs,'session':'restore-expanded-census'})
        self.assertEqual(saved,self.world.active['town']['resident_control']['assignments'])

    def test_departures_release_slots_and_capacity_never_partially_enrolls(self):
        town={'residents':{'7':{},'9':{}},'resident_control':{'assignments':{}}}
        sync_resident_assignments(town);old=copy.deepcopy(town['resident_control']['assignments'])
        del town['residents']['7'];town['residents']['10']={};sync_resident_assignments(town)
        self.assertEqual(town['resident_control']['assignments']['9'],old['9'])
        self.assertEqual(town['resident_control']['assignments']['10']['slot'],old['7']['slot'])
        before=copy.deepcopy(town['resident_control']);town['residents']={str(i):{} for i in range(129)}
        with self.assertRaisesRegex(ValueError,'capacity'):sync_resident_assignments(town)
        self.assertEqual(town['resident_control'],before)

    def test_new_plugin_migration_is_append_only_and_explicit(self):
        old=[{'name':'WhiterunRouter.esp','sha256':'existing'}]
        new=old+[{'name':'WhiterunCitizens.esp','sha256':'new'}]
        self.assertFalse(plugins_compatible(old,new))
        self.assertTrue(plugins_compatible(old,new,'WhiterunCitizens.esp'))
        self.assertFalse(plugins_compatible(old,list(reversed(new)),'WhiterunCitizens.esp'))
        self.assertFalse(plugins_compatible(old,[{'name':'WhiterunRouter.esp','sha256':'changed'},new[-1]],'WhiterunCitizens.esp'))


if __name__=='__main__':unittest.main()
