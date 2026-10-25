"""Positive fixtures opt into identities; legacy/unbound cases stay unchanged."""
import copy
import unittest
from legacy_fixture import author_fixture_identities,historical_people
from resident_identity import resident_identity_status


class FixtureIdentityAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.state={'people':{'7':{'memories':[{'kind':'existing'}]},'8':{}},
                    'town':{'residents':{'7':{'id':7},'8':{'id':8}}}}
        self.obs={'ready':True,'session':'fixture','checkpoint':1,'residents':[
            {'id':actor,'baseId':actor+100,'isPerson':True} for actor in (7,8,9)]}

    def test_positive_binding_is_explicit_and_preserves_history(self):
        self.assertEqual(resident_identity_status(self.state,self.obs,7)['reason'],'identity_unbound')
        author_fixture_identities(self.state,self.obs,[7])
        self.assertTrue(resident_identity_status(self.state,self.obs,7)['qualified'])
        self.assertEqual(self.state['people']['7']['memories'],[{'kind':'existing'}])
        self.assertEqual(resident_identity_status(self.state,self.obs,8)['reason'],'identity_unbound')
        self.assertTrue(all('identity_binding' not in person for person in historical_people().values()))

    def test_pre_census_binds_existing_people_only_without_creating_cohort(self):
        self.state.pop('town')
        self.assertEqual(author_fixture_identities(self.state,self.obs,[7,9]),[7])
        self.assertNotIn('town',self.state);self.assertNotIn('9',self.state['people'])
        self.assertNotIn('identity_binding',self.state['people']['8'])

    def test_missing_base_and_saved_conflict_fail_without_partial_binding(self):
        self.obs['residents'][1].pop('baseId');before=copy.deepcopy(self.state)
        with self.assertRaises(ValueError):author_fixture_identities(self.state,self.obs,[7,8])
        self.assertEqual(self.state,before)
        self.obs['residents'][1]['baseId']=108
        author_fixture_identities(self.state,self.obs,[7])
        self.obs['residents'][0]['baseId']=999;before=copy.deepcopy(self.state)
        with self.assertRaisesRegex(ValueError,'cannot overwrite'):author_fixture_identities(self.state,self.obs,[7,8])
        self.assertEqual(self.state,before)


if __name__=='__main__':unittest.main()
