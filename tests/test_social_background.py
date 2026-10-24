import copy
import unittest
import test_population
from knowledge import person_view


class SocialBackgroundTests(unittest.TestCase):
    setUp=test_population.PopulationTests.setUp
    tearDown=test_population.PopulationTests.tearDown
    sync=test_population.PopulationTests.sync
    census=test_population.PopulationTests.census
    initialize=test_population.PopulationTests.initialize

    def test_established_neighbours_know_names_without_invented_events_or_friendship(self):
        self.census();self.initialize();before=copy.deepcopy(self.world.active)
        result=self.world.establish_social_background('neighbours',[99,108186],self.obs);self.sync()
        self.assertEqual(result['background']['new_known_names'],2)
        view=person_view(self.world.active,99,108186)
        self.assertTrue(view['name_known']);self.assertEqual(view['identity_source']['kind'],'authored_shared_town_background')
        person=self.world.active['people']['99'];relation=person['relationships']['108186']
        self.assertEqual(relation['heard_turns'],0);self.assertEqual(relation['affinity'],0)
        self.assertEqual(person['memories'],before['people']['99']['memories'])
        self.assertFalse(person_view(self.world.active,99,108149)['name_known'])
        applied=copy.deepcopy(self.world.active)
        self.assertTrue(self.world.establish_social_background('neighbours',[108186,99],self.obs)['duplicate'])
        self.assertEqual(applied,self.world.active)
        with self.assertRaises(ValueError):self.world.establish_social_background('neighbours',[99,108149],self.obs)

    def test_background_preserves_learned_identity_and_affinity_and_restores_with_save(self):
        self.census();self.initialize()
        self.world.active['people']['99']['known_people']['108186']={'name':'Known alias','name_source':{'kind':'heard_self_introduction'},'heard_events':['heard-1']}
        self.world.active['people']['99']['relationships']['108186']={'affinity':-.3,'familiarity':.5,'heard_turns':7,'appraisals':[]}
        # Persist fixture in its own checkpoint so reload has a meaningful oracle.
        self.world._write(copy.deepcopy(self.world.active),'fixture existing acquaintance');self.sync();before=copy.deepcopy(self.obs)
        self.world.establish_social_background('neighbours',[99,108186],self.obs);self.sync()
        p=self.world.active['people']['99']
        self.assertEqual(p['known_people']['108186']['name'],'Known alias')
        self.assertEqual(p['relationships']['108186']['affinity'],-.3)
        self.assertEqual(p['relationships']['108186']['familiarity'],.5)
        self.world.observe({**before,'session':'before-background'})
        self.assertNotIn('background',self.world.active['people']['99']['relationships']['108186'])

    def test_invalid_or_unknown_cohort_is_atomic(self):
        self.census();self.initialize();before=copy.deepcopy(self.world.active)
        for cohort in ([99],[99,99],[True,99],[99,999],None):
            with self.assertRaises(ValueError):self.world.establish_social_background('bad',cohort,self.obs)
            self.assertEqual(before,self.world.active)
