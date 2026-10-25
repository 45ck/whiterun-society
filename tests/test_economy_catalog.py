import copy
import hashlib
import json
import unittest
from unittest.mock import patch
import economy_catalog as catalog


def resolved_catalog(manifest=None):
    return {'available': True, 'type_verified': True, 'errors': {},
            'item_ids': list(catalog.commodity_ids(manifest)), 'catalog_hash': catalog.catalog_hash(manifest),
            'recipe_hashes': {rid: catalog.recipe_hash(rid, manifest) for rid in catalog.recipe_ids(manifest)}}


class EconomyCatalogTests(unittest.TestCase):
    def setUp(self):self.manifest = copy.deepcopy(catalog.ECONOMY_CATALOG)

    def test_seed_contains_only_offline_verified_existing_native_records(self):
        rows = {c['id']: c for c in self.manifest['commodities']}
        self.assertEqual(set(rows), {'gold', 'bread', 'grain'})
        self.assertEqual(rows['gold']['native'], {'plugin': 'Skyrim.esm', 'local_form_id': 15, 'record_type': 'MISC'})
        self.assertEqual(rows['bread']['native']['local_form_id'], 0x65c97)
        self.assertEqual(rows['bread']['native']['record_type'], 'ALCH')
        self.assertEqual(rows['grain']['native']['local_form_id'], 0x4b0ba)
        self.assertEqual(rows['grain']['native']['record_type'], 'INGR')
        self.assertEqual(catalog.recipe_ids(), ('bread_recipe',))
        self.assertEqual(catalog.catalog_hash(), '1f7f5d79e976a74ac5e8b2f9752734a759cbaf591b5941ae5cd82d33145ae554')
        self.assertEqual(catalog.recipe_hash('bread_recipe'), 'dcbe70560fbaa3c3e0c966da1e883abfd323695b14736e04b18cc781fa6c76cd')

    def test_canonical_unicode_key_order_and_full_recipe_hash_binding(self):
        self.assertEqual(catalog.canonical_json({'z': 'café', 'a': [True, 2]}), '{"a":[true,2],"z":"café"}')
        payload = {'catalog_hash': catalog.catalog_hash(), 'recipe': catalog.recipe_spec('bread_recipe')}
        self.assertEqual(catalog.recipe_hash('bread_recipe'), hashlib.sha256(catalog.canonical_json(payload).encode('utf-8')).hexdigest())
        self.manifest['commodities'][0]['label'] = 'Reviewed currency label'
        self.assertNotEqual(catalog.catalog_hash(self.manifest), catalog.catalog_hash())
        self.assertNotEqual(catalog.recipe_hash('bread_recipe', self.manifest), catalog.recipe_hash('bread_recipe'))
        for bad in (1.0, float('nan'), {'bad key': 1}, {'label': '\ud800'}, 2**53):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):catalog.canonical_json(bad)

    def test_unknown_fields_duplicate_ids_aliases_and_bad_native_types_rejected(self):
        variants=[]
        for key,value in (('schema_version',True),('schema_version',1.0),('extra','no')):
            candidate=copy.deepcopy(self.manifest);candidate[key]=value;variants.append(candidate)
        candidate=copy.deepcopy(self.manifest);candidate['commodities'].append(copy.deepcopy(candidate['commodities'][0]));variants.append(candidate)
        candidate=copy.deepcopy(self.manifest);candidate['commodities'][1]['native']={'plugin':'skyrim.ESM','local_form_id':15,'record_type':'MISC'};variants.append(candidate)
        for invalid in ('NPC_',[],None):
            candidate=copy.deepcopy(self.manifest);candidate['commodities'][1]['native']['record_type']=invalid;variants.append(candidate)
        candidate=copy.deepcopy(self.manifest);candidate['recipes'].append(copy.deepcopy(candidate['recipes'][0]));variants.append(candidate)
        for candidate in variants:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):catalog.validate_catalog(candidate)

    def test_recipe_forbids_free_inputs_currency_same_item_and_invalid_quantities(self):
        for side,value in (('inputs',{}),('inputs',{'grain':0}),('inputs',{'grain':True}),('inputs',{'grain':1.5}),
                           ('inputs',{'missing':1}),('inputs',{'gold':1}),('outputs',{'gold':2}),
                           ('outputs',{'grain':2}),('outputs',{'bread':1001}),('outputs',{'bread':1,'grain':1})):
            candidate=copy.deepcopy(self.manifest);candidate['recipes'][0][side]=value
            with self.subTest(side=side,value=value), self.assertRaises(ValueError):catalog.validate_catalog(candidate)
        candidate=copy.deepcopy(self.manifest);candidate['recipes'][0]['work_minutes']['minimum']=0
        with self.assertRaises(ValueError):catalog.validate_catalog(candidate)

    def test_cross_recipe_cycles_are_not_blanket_banned_or_claimed_balanced(self):
        reverse=copy.deepcopy(self.manifest['recipes'][0]);reverse.update(id='fixture_recycle',inputs={'bread':2},outputs={'grain':1})
        self.manifest['recipes'].append(reverse)
        self.assertEqual(len(catalog.validate_catalog(self.manifest)['recipes']),2)

    def test_complete_account_currency_and_unrelated_balances_preserved(self):
        extra={'id':'fixture_material','label':'Fixture material','currency':False,
               'native':{'plugin':'Fixture.esp','local_form_id':1,'record_type':'MISC'},
               'provenance':'Synthetic test definition; not a verified installed material.'}
        self.manifest['commodities'].append(extra)
        before={'gold':17,'grain':4,'bread':3,'fixture_material':12}
        self.assertEqual(catalog.apply_recipe(before,'bread_recipe',self.manifest),
                         {'gold':17,'grain':3,'bread':5,'fixture_material':12})
        self.assertEqual(before['grain'],4)
        for bad in ({'gold':17,'grain':4,'bread':3}, {**before,'secret':2}, {**before,'grain':0},
                    {**before,'gold':True}, {**before,'bread':catalog.MAX_STOCK}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):catalog.apply_recipe(bad,'bread_recipe',self.manifest)

    def test_native_proof_requires_resolved_type_checked_complete_matching_catalog(self):
        observation={'economy_catalog':resolved_catalog()}
        self.assertEqual(catalog.require_native_catalog(observation,'bread_recipe'),catalog.catalog_hash())
        for change in ({'available':False},{'type_verified':False},{'errors':{'grain':'Missing form'}},
                       {'item_ids':['gold']},{'catalog_hash':'0'*64},{'recipe_hashes':{}}, {'type_verified':None}):
            candidate={'economy_catalog':{**resolved_catalog(),**change}}
            with self.subTest(change=change):
                self.assertFalse(catalog.native_catalog_matches(candidate))
                with self.assertRaises(ValueError):catalog.require_native_catalog(candidate)
        with self.assertRaises(ValueError):catalog.require_native_catalog({})

    def test_reviewed_currency_mapping_change_changes_hash_instead_of_retargeting_old_intents(self):
        self.manifest['commodities'][0]['native']['plugin']='FixtureCurrency.esp'
        self.assertNotEqual(catalog.catalog_hash(self.manifest),catalog.catalog_hash())
        self.assertFalse(catalog.native_catalog_matches({'economy_catalog':resolved_catalog()},catalog=self.manifest))

    def test_128_recipe_catalog_uses_identical_hash_protocol_without_repeated_manifest_serialization(self):
        template=self.manifest['recipes'][0]
        self.manifest['recipes']=[{**copy.deepcopy(template),'id':'fixture_recipe_'+str(i)} for i in range(128)]
        digest=catalog.catalog_hash(self.manifest)
        hashes={r['id']:hashlib.sha256(catalog.canonical_json({'catalog_hash':digest,'recipe':r}).encode('utf-8')).hexdigest()
                for r in self.manifest['recipes']}
        observation={'economy_catalog':{'available':True,'type_verified':True,'errors':{},
            'item_ids':list(catalog.commodity_ids(self.manifest)),'catalog_hash':digest,'recipe_hashes':hashes}}
        with patch.object(catalog,'canonical_json',wraps=catalog.canonical_json) as canonical:
            self.assertTrue(catalog.native_catalog_matches(observation,catalog=self.manifest))
            # One validation pass and one digest pass touch the full manifest;
            # each remaining canonicalization touches only a recipe envelope.
            full_calls=[call for call in canonical.call_args_list if call.args[0] is not None
                        and isinstance(call.args[0],dict) and 'commodities' in call.args[0]]
            self.assertEqual(len(full_calls),2)
        for index in (0,63,127):
            rid=self.manifest['recipes'][index]['id']
            self.assertEqual(catalog.recipe_hash(rid,self.manifest),hashes[rid])
        observation['economy_catalog']['recipe_hashes']['fixture_recipe_127']='0'*64
        self.assertFalse(catalog.native_catalog_matches(observation,catalog=self.manifest))


class CatalogOwnerFlowTests(unittest.TestCase):
    def fixture(self, manifest=None):
        from test_owner_work_jobs import OwnerWorkJobsTests
        fixture=OwnerWorkJobsTests();fixture.setUp();fixture.obs['economy_catalog']=resolved_catalog(manifest)
        return fixture

    def test_modern_owner_command_and_receipts_pin_catalog_and_recipe(self):
        fixture=self.fixture();job,command=fixture.prepared_recipe()
        self.assertEqual(job['catalog_hash'],catalog.catalog_hash())
        self.assertEqual(command['recipe_hash'],catalog.recipe_hash('bread_recipe'))
        self.assertEqual(command['after']['owner'],catalog.apply_recipe(command['before']['owner'],'bread_recipe'))
        self.assertEqual(job['recipe_definition'],catalog.recipe_spec('bread_recipe'))

    def test_changed_catalog_or_legacy_unbound_job_is_held_without_replay(self):
        for missing in (True,False):
            fixture=self.fixture();job=fixture.delegate()
            if missing:
                fixture.world.active['work_jobs'][job['id']].pop('catalog_hash')
                fixture.world.active['work_jobs'][job['id']].pop('recipe_hash')
            else:fixture.world.active['work_jobs'][job['id']]['catalog_hash']='0'*64
            self.assertIsNone(fixture.world.owner_work_pending_command())
            self.assertTrue(fixture.world.observe_owner_work_jobs(fixture.obs));fixture.world.bind(fixture.obs)
            self.assertEqual(fixture.world.active['work_jobs'][job['id']]['phase'],'held')
            self.assertNotIn('production',fixture.world.active)
            self.assertEqual(fixture.world.owner_work_status()['jobs'][0]['phase'],'held')

    def test_configured_second_recipe_changes_opportunities_and_deltas_without_name_branches(self):
        from owner_production import owner_work_opportunities
        manifest=copy.deepcopy(catalog.ECONOMY_CATALOG)
        second=copy.deepcopy(manifest['recipes'][0]);second.update(id='fixture_batch',inputs={'grain':2},outputs={'bread':3})
        manifest['recipes'].append(second)
        with patch.object(catalog,'ECONOMY_CATALOG',catalog.validate_catalog(manifest)):
            fixture=self.fixture(manifest)
            fixture.world.active['town']['businesses']['shop']['capabilities']=['fixture_batch']
            options=owner_work_opportunities(fixture.world.active,fixture.obs,1,require_owned=False)
            self.assertEqual([o['recipe_id'] for o in options],['fixture_batch'])
            job,command=fixture.prepared_recipe()
            self.assertEqual(job['recipe_id'],'fixture_batch')
            self.assertEqual(job['input_reservation'],{'grain':2})
            self.assertEqual(command['after']['owner'],{'gold':5,'bread':3,'grain':0})
            fixture.obs['residents'][0]['inventory']=copy.deepcopy(command['after']['owner'])
            fixture.obs['ack']=fixture.commit_ack(job,command)
            self.assertTrue(fixture.world.observe_owner_work_recipe(fixture.obs));fixture.world.bind(fixture.obs)
            memory=fixture.world.active['people']['1']['memories'][-1]
            self.assertEqual(memory['recipe_id'],'fixture_batch');self.assertEqual(memory['inputs'],{'grain':2})
            self.assertNotIn('bread_made',memory)

    def test_prepared_recipe_catalog_mismatch_quarantines_writer_without_credit(self):
        fixture=self.fixture();job,command=fixture.prepared_recipe()
        fixture.obs['economy_catalog']['catalog_hash']='0'*64
        fixture.obs['residents'][0]['inventory']=copy.deepcopy(command['after']['owner'])
        fixture.obs['ack']=fixture.commit_ack(job,command)
        self.assertTrue(fixture.world.observe_owner_work_recipe(fixture.obs));fixture.world.bind(fixture.obs)
        self.assertEqual(fixture.world.active['pending']['status'],'held')
        self.assertFalse(fixture.world.observe_owner_work_recipe(fixture.obs))
        self.assertNotIn('production',fixture.world.active)


if __name__=='__main__':unittest.main()
