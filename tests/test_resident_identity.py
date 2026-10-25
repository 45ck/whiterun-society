"""Reference reuse cannot silently transfer a save-bound person's identity."""
import copy
import unittest
from unittest.mock import patch
import economy_catalog
from resident_identity import resident_identity_status
from population import eligible_actors
import test_fresh_population as fixtures


def binding(actor,base):return {'schema_version':1,'actor':actor,'base_id':base,'event_id':'census-one'}


class ResidentIdentityTests(unittest.TestCase):
    def setUp(self):
        identity=binding(17,1017)
        self.state={'people':{'17':{'identity_binding':copy.deepcopy(identity)}},
            'town':{'residents':{'17':{'id':17,'identity_binding':identity}}}}
        self.obs={'ready':True,'session':'current','checkpoint':3,'residents':[
            {'id':17,'baseId':1017,'isPerson':True,'name':'Resident','inventory':{'gold':2,'bread':1,'grain':0}}]}
    def status(self):return resident_identity_status(self.state,self.obs,17)

    def test_exact_current_actor_base_is_qualified_independent_of_order(self):
        self.obs['residents'].insert(0,{'id':99,'baseId':1099,'isPerson':True})
        first=self.status();self.obs['residents'].reverse()
        self.assertEqual(first,self.status());self.assertEqual(first,{'qualified':True,'reason':'qualified_actor_base','actor':17,'base_id':1017})

    def test_missing_legacy_binding_is_unknown_not_adopted(self):
        self.state['town']['residents']['17'].pop('identity_binding');before=copy.deepcopy(self.state)
        self.assertEqual(self.status()['reason'],'identity_unbound');self.assertEqual(self.state,before)

    def test_changed_base_is_conflict_preserving_bound_base(self):
        self.obs['residents'][0]['baseId']=2017
        self.assertEqual(self.status()['reason'],'base_identity_conflict')
        self.assertEqual(self.state['town']['residents']['17']['identity_binding']['base_id'],1017)

    def test_missing_observed_base_never_uses_saved_base_as_evidence(self):
        self.obs['residents'][0].pop('baseId')
        self.assertEqual(self.status()['reason'],'base_identity_unavailable');self.assertIsNone(self.status()['base_id'])

    def test_duplicate_current_rows_are_unqualified_even_when_identical(self):
        self.obs['residents'].append(copy.deepcopy(self.obs['residents'][0]))
        self.assertEqual(self.status()['reason'],'duplicate_actor_observation')

    def test_explicit_child_dead_or_unloaded_cannot_become_qualified(self):
        for field,reason in [('isChild','actor_is_child'),('isDead','actor_is_dead'),('loaded','actor_not_loaded')]:
            with self.subTest(field=field):
                self.obs['residents'][0][field]=field!='loaded'
                self.assertEqual(self.status()['reason'],reason);self.obs['residents'][0].pop(field)

    def test_explicit_unknown_classification_flags_are_not_evidence(self):
        self.obs['residents'][0]['isChild']=None
        self.assertEqual(self.status()['reason'],'adult_classification_unavailable')

    def test_stale_row_session_or_checkpoint_is_not_current_identity(self):
        for field,value in [('session','old'),('checkpoint',2)]:
            with self.subTest(field=field):
                self.obs['residents'][0][field]=value
                self.assertEqual(self.status()['reason'],'stale_actor_observation');self.obs['residents'][0].pop(field)

    def test_bound_identity_survives_new_save_session_if_current_pair_matches(self):
        self.obs['session']='reloaded';self.obs['checkpoint']=8
        self.assertTrue(self.status()['qualified'])

    def test_current_unknown_classification_does_not_use_old_status(self):
        self.state['town']['residents']['17']['identity_status']={'qualified':True}
        self.obs['residents'][0]['isPerson']=None
        self.assertFalse(self.status()['qualified'])

    def test_person_and_roster_binding_disagreement_is_conflict(self):
        self.state['people']['17']['identity_binding']['base_id']=999
        self.assertEqual(self.status()['reason'],'identity_binding_conflict')

    def test_absent_observation_never_certifies_saved_identity(self):
        self.assertEqual(resident_identity_status(self.state,None,17)['reason'],'observation_unavailable')

    def test_malformed_binding_version_or_actor_is_not_qualified(self):
        for field,value in [('schema_version',True),('actor',True),('base_id',False),('event_id','')]:
            with self.subTest(field=field):
                original=self.state['town']['residents']['17']['identity_binding'][field]
                self.state['town']['residents']['17']['identity_binding'][field]=value
                self.assertEqual(self.status()['reason'],'identity_binding_invalid')
                self.state['town']['residents']['17']['identity_binding'][field]=original

    def test_invalid_or_missing_managed_person_cannot_qualify(self):
        self.assertFalse(resident_identity_status(self.state,self.obs,True)['qualified'])
        self.state['people'].pop('17');self.assertEqual(self.status()['reason'],'person_unavailable')


class CensusIdentityTests(unittest.TestCase):
    tearDown=fixtures.FreshPopulationTests.tearDown
    bind=fixtures.FreshPopulationTests.bind
    bootstrap=fixtures.FreshPopulationTests.bootstrap
    census=fixtures.FreshPopulationTests.census
    def setUp(self):
        fixtures.FreshPopulationTests.setUp(self)
        for row in self.obs['residents']:row['baseId']=row['id']+100000
        self.bootstrap()

    def test_new_census_saves_matching_person_and_roster_identity_without_assets(self):
        before=copy.deepcopy(self.obs['residents']);source=self.obs['checkpoint'];self.census()
        for key in ('17','90341'):
            resident=self.world.active['town']['residents'][key];person=self.world.active['people'][key]
            self.assertEqual(resident['identity_binding'],person['identity_binding'])
            self.assertEqual(resident['identity_binding']['source_checkpoint'],source)
            self.assertEqual(resident['identity_binding']['event_id'],'observed-people')
            self.assertTrue(resident_identity_status(self.world.active,self.obs,int(key))['qualified'])
            self.assertEqual(person['memories'],[]);self.assertNotIn('known_recipes',person)
        self.assertEqual(self.obs['residents'],before);self.assertEqual(self.world.active['trades'],[])
        self.assertNotIn('resource_program',self.world.active['town'])

    def test_replacement_preserves_profile_skills_history_charter_and_binding(self):
        self.census();state=copy.deepcopy(self.world.active)
        state['people']['17']['known_recipes']={'fixture-recipe':{'source':'historical-test'}}
        state['people']['17']['memories']=[{'kind':'heard','event_id':'past'}]
        state['town']['businesses']={'retained':{'custodian':17,'revision':1}}
        self.world._write(state,'Authored history preservation fixture');self.bind()
        person=copy.deepcopy(self.world.active['people']['17']);identity=copy.deepcopy(self.world.active['town']['residents']['17']['identity_binding'])
        self.obs['residents'][0].update(baseId=999999,name='Replacement observed label')
        self.census('replacement-observed')
        self.assertEqual(self.world.active['people']['17'],person)
        self.assertEqual(self.world.active['town']['residents']['17']['identity_binding'],identity)
        self.assertEqual(self.world.active['town']['businesses'],state['town']['businesses'])
        self.assertEqual(self.world.population_status(self.obs)['residents']['17']['identity_status']['reason'],'base_identity_conflict')

    def test_missing_base_census_remains_managed_but_later_observation_cannot_bind_it(self):
        self.obs['residents'][0].pop('baseId');self.census()
        self.assertNotIn('identity_binding',self.world.active['town']['residents']['17'])
        self.obs['residents'][0]['baseId']=100017;self.census('later-complete-base')
        self.assertEqual(resident_identity_status(self.world.active,self.obs,17)['reason'],'identity_unbound')
        self.assertNotIn('identity_binding',self.world.active['people']['17'])

    def test_legacy_person_first_roster_enrollment_is_not_retroactively_bound(self):
        self.world.active['people']['17']={'profile':{'name':'Historical'},'needs':{},'memories':[{'kind':'heard'}],'known_recipes':{'legacy':{}}}
        self.census()
        person=self.world.active['people']['17'];self.assertEqual(person['profile']['name'],'Historical')
        self.assertEqual(person['known_recipes'],{'legacy':{}});self.assertNotIn('identity_binding',person)
        self.assertEqual(resident_identity_status(self.world.active,self.obs,17)['reason'],'identity_unbound')

    def test_same_census_retry_reports_current_conflict_without_mutation(self):
        self.census();before=copy.deepcopy(self.world.active);self.obs['residents'][0]['baseId']=999999
        result=self.census()
        self.assertTrue(result['duplicate']);self.assertEqual(self.world.active,before)
        self.assertEqual(result['identity_status']['17']['reason'],'base_identity_conflict')

    def test_child_and_dead_rows_skipped_with_reason_without_deleting_existing_people(self):
        self.census();before=copy.deepcopy(self.world.active['people'])
        self.obs['residents'][0]['isChild']=True
        self.obs['residents'].append({'id':88,'name':'Dead','isPerson':True,'isDead':True,'baseId':1088,'inventory':{'gold':0,'bread':0,'grain':0}})
        result=self.census('filtered-observation')
        self.assertIn({'actor':17,'reason':'actor_is_child'},result['skipped'])
        self.assertIn({'actor':88,'reason':'actor_is_dead'},result['skipped'])
        before['17']['agency']['native_route_supported']=False
        self.assertEqual(self.world.active['people']['17'],before['17']);self.assertNotIn('88',self.world.active['people'])
        self.assertFalse(resident_identity_status(self.world.active,self.obs,17)['qualified'])

    def test_duplicate_rows_abort_census_without_partial_population(self):
        self.obs['residents'].append(copy.deepcopy(self.obs['residents'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):self.census()
        self.assertEqual(self.world.active['people'],{});self.assertIsNone(self.world.transition)

    def test_projection_uses_current_observation_without_mutating_saved_status(self):
        self.census();before=copy.deepcopy(self.world.active)
        self.assertEqual(self.world.population_status(self.obs)['counts']['identity_qualified'],2)
        self.assertEqual(self.world.population_status()['counts']['identity_qualified'],0)
        self.obs['residents'][0]['baseId']=999999
        self.assertEqual(self.world.population_status(self.obs)['counts']['identity_conflicts'],1)
        self.assertEqual(self.world.active,before)

    def test_old_save_restores_prebinding_identity_state_not_latest_census(self):
        earlier=copy.deepcopy(self.obs);self.census()
        self.world.observe({**earlier,'session':'older-identity'})
        self.assertNotIn('town',self.world.active);self.assertEqual(self.world.active['people'],{})

    def test_generic_catalog_inventory_requires_every_registered_good_and_bounds(self):
        catalog=copy.deepcopy(economy_catalog.ECONOMY_CATALOG)
        catalog['commodities'].append({'id':'ore','label':'Ore','native':{'plugin':'Skyrim.esm','local_form_id':388,'record_type':'MISC'},'currency':False,'provenance':'Identity inventory fixture'})
        with patch.object(economy_catalog,'ECONOMY_CATALOG',economy_catalog.validate_catalog(catalog)):
            with self.assertRaisesRegex(ValueError,'catalog inventory'):eligible_actors(self.obs)
            for row in self.obs['residents']:row['inventory']['ore']=0
            self.assertEqual(len(eligible_actors(self.obs)),2)
            self.obs['residents'][0]['inventory']['ore']=economy_catalog.MAX_STOCK+1
            with self.assertRaisesRegex(ValueError,'bounded'):eligible_actors(self.obs)
