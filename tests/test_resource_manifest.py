"""Schema and Python/native digest parity; no inventory or provider calls."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import economy_catalog
from resource_manifest import load_manifest,validate_manifest,manifest_hash,select_grant

ROOT=Path(__file__).resolve().parents[1]
NODE=r"""
const fs=require('node:fs'),api=require('./bridge/resource-manifest.js');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
console.log(JSON.stringify(input.cases.map(row=>{try{
 const manifest=api.validateResourceManifest(row.manifest,input.catalog_hash,input.item_ids);
 return {ok:true,manifest_hash:api.resourceManifestHash(manifest),selection:api.selectResourceGrant(manifest,row.actor??99,row.base??100)};
}catch(error){return {ok:false};}})));
"""


def override(actor=99,base=100,identifier='explicit-example'):
    return {'id':identifier,'selector':{'actor':actor,'actor_base_id':base},
            'grant':{'gold':100,'bread':2,'grain':20},'provenance':'Explicit synthetic test override, not a live NPC assignment'}


class ResourceManifestTests(unittest.TestCase):
    def setUp(self):self.manifest=load_manifest()

    def parity(self,cases,catalog_hash=None,item_ids=None):
        executable=shutil.which('node')
        if executable is None:self.fail('Node is required for resource manifest parity qualification')
        result=subprocess.run([executable,'-e',NODE],cwd=ROOT,input=json.dumps({'cases':cases,
            'catalog_hash':catalog_hash or economy_catalog.catalog_hash(),'item_ids':item_ids or list(economy_catalog.commodity_ids())},ensure_ascii=True),
            text=True,encoding='utf-8',capture_output=True,timeout=15,check=True)
        return json.loads(result.stdout)

    def assert_parity(self,cases):
        native=self.parity(cases)
        for index,(case,result) in enumerate(zip(cases,native)):
            with self.subTest(vector=index):
                try:
                    manifest=validate_manifest(case['manifest'])
                    selection=select_grant(manifest,case.get('actor',99),case.get('base',100))
                except ValueError:self.assertFalse(result['ok']);continue
                self.assertTrue(result['ok']);self.assertEqual(result['manifest_hash'],manifest_hash(manifest))
                self.assertEqual(result['selection'],selection)
        return native

    def test_default_is_uniform_data_with_shared_fixed_digest(self):
        self.assertEqual(self.manifest['id'],'founding-resources-v2')
        self.assertEqual(self.manifest['default_grant'],{'gold':20,'bread':2,'grain':2})
        self.assertEqual(self.manifest['overrides'],[])
        self.assertEqual(manifest_hash(self.manifest),'f361660497f1be6d256fcf2908c47fbdf2e7b3bb96a8161f9147a5b57c981d17')
        result=self.assert_parity([{'manifest':self.manifest,'actor':actor,'base':actor+1} for actor in (99,108149,800001)])
        self.assertEqual(len({row['selection']['grant_hash'] for row in result}),3)
        for row in result:self.assertEqual(row['selection']['grant'],self.manifest['default_grant'])

    def test_exact_selector_never_falls_back_after_base_identity_changes(self):
        self.manifest['overrides']=[override()]
        cases=[{'manifest':self.manifest,'actor':99,'base':base} for base in (100,101)]
        cases.append({'manifest':self.manifest,'actor':98,'base':100})
        result=self.assert_parity(cases)
        self.assertEqual(result[0]['selection']['selector_id'],'explicit-example')
        self.assertFalse(result[1]['ok']);self.assertEqual(result[2]['selection']['selector_id'],'default')

    def test_schema_numeric_identity_and_proto_rejections_match(self):
        cases=[]
        def changed(mutate):
            value=copy.deepcopy(self.manifest);mutate(value);cases.append({'manifest':value})
        for key,value in [('schema_version',True),('schema_version',2),('version',None),('id','__proto__'),
                          ('overrides',{}),('max_recipient_stock',True),('max_recipient_stock',-1),
                          ('max_recipient_stock',2**31),('catalog_hash','a'*64)]:changed(lambda m,k=key,v=value:m.update({k:v}))
        for value in (True,-1,.5,2**31):changed(lambda m,v=value:m['default_grant'].update(gold=v))
        changed(lambda m:m['default_grant'].update(gold=1001))
        changed(lambda m:m['default_grant'].update(gold=0,bread=0,grain=0))
        changed(lambda m:m['default_grant'].pop('grain'))
        changed(lambda m:m['capacity'].update(unknown=1))
        changed(lambda m:m.update(__proto__={'id':'injected'}))
        changed(lambda m:m['default_grant'].update(__proto__=1))
        changed(lambda m:m.update(overrides=[override(),override(99,101,'different-base')]))
        changed(lambda m:m.update(overrides=[override(),override(98,100)]))
        changed(lambda m:m.update(overrides=[override(identifier='default')]))
        for value in (True,0,-1,1.5,2**32):changed(lambda m,v=value:m.update(overrides=[override(actor=v)]))
        changed(lambda m:m.update(overrides=[override(base=True)]))
        changed(lambda m:m.update(overrides=[dict(override(),selector={'actor_base_id':100})]))
        changed(lambda m:m.update(overrides=[dict(override(),selector={'actor':99,'actor_base_id':100,'name':'Someone'})]))
        self.assertTrue(all(not row['ok'] for row in self.assert_parity(cases)))

    def test_unicode_scalar_count_and_whitespace_match(self):
        values=['Authored café 猫 🌾','🌾'*500,'🌾'*501,' leading','trailing\u0085','control\ntext','bad\ud800','']
        cases=[{'manifest':dict(self.manifest,provenance=value)} for value in values]
        results=self.assert_parity(cases)
        self.assertEqual([row['ok'] for row in results],[True,True,False,False,False,False,False,False])

    def test_reordered_objects_are_identical_and_policy_changes_change_both_hashes(self):
        def reverse(value):
            if isinstance(value,dict):return {key:reverse(value[key]) for key in reversed(value)}
            if isinstance(value,list):return [reverse(row) for row in value]
            return value
        revised=copy.deepcopy(self.manifest);revised['default_grant']['grain']=3
        results=self.assert_parity([{'manifest':m} for m in (self.manifest,reverse(self.manifest),revised)])
        self.assertEqual(results[0],results[1]);self.assertNotEqual(results[0]['manifest_hash'],results[2]['manifest_hash'])
        self.assertNotEqual(results[0]['selection']['grant_hash'],results[2]['selection']['grant_hash'])

    def test_changed_catalog_or_item_set_cannot_recertify_old_policy(self):
        modified=copy.deepcopy(economy_catalog.ECONOMY_CATALOG);modified['version']='other-reviewed-catalog'
        with patch.object(economy_catalog,'ECONOMY_CATALOG',modified):
            with self.assertRaisesRegex(ValueError,'catalog'):validate_manifest(self.manifest)
            result=self.parity([{'manifest':self.manifest}])
            self.assertFalse(result[0]['ok'])
        self.assertFalse(self.parity([{'manifest':self.manifest}],item_ids=['gold','bread','grain','ore'])[0]['ok'])

    def test_validated_and_selected_outputs_are_detached_from_input(self):
        original=copy.deepcopy(self.manifest);validated=validate_manifest(self.manifest)
        selected=select_grant(validated,99,100);selected['grant']['gold']=999
        validated['capacity']['gold']=1
        self.assertEqual(self.manifest,original)
        self.assertEqual(select_grant(self.manifest,99,100)['grant']['gold'],20)

    def test_file_loader_rejects_duplicate_fields_and_bounded_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'manifest.json'
            path.write_text('{"schema_version":1,"schema_version":1}')
            with self.assertRaisesRegex(ValueError,'Duplicate'):load_manifest(path)
            path.write_bytes(b' '*262145)
            with self.assertRaisesRegex(ValueError,'256 KiB'):load_manifest(path)

    def test_override_limit_and_positive_capacity_boundary(self):
        allowed=copy.deepcopy(self.manifest)
        allowed['overrides']=[override(actor=i+1,base=i+101,identifier='recipient-'+str(i)) for i in range(128)]
        rejected=copy.deepcopy(allowed);rejected['overrides'].append(override(actor=200,base=300,identifier='extra'))
        results=self.assert_parity([{'manifest':allowed,'actor':999,'base':1000},{'manifest':rejected}])
        self.assertEqual([row['ok'] for row in results],[True,False])


if __name__=='__main__':unittest.main()
