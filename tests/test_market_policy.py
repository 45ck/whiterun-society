"""Shared market policy schema and digest contract, without game or inference."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import economy_catalog
import market_policy

ROOT = Path(__file__).resolve().parents[1]
NODE = r"""
const fs=require('node:fs'),api=require('./bridge/market-policy.js');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
console.log(JSON.stringify(input.cases.map(policy=>{try{
 const checked=api.validateMarketPolicy(policy,input.hash,input.metadata);
 return {ok:true,hash:api.marketPolicyHash(checked),goods:checked.goods.map(row=>api.marketGood(checked,row.commodity))};
}catch(error){return {ok:false};}})));
"""


def fourth_catalog():
    catalog=copy.deepcopy(economy_catalog.ECONOMY_CATALOG)
    catalog['commodities'].append({'id':'test_clay','label':'Synthetic test clay',
        'native':{'plugin':'TestFixture.esp','local_form_id':100,'record_type':'MISC'},
        'currency':False,'provenance':'Synthetic fixture only; no activated native asset'})
    return economy_catalog.validate_catalog(catalog)


class MarketPolicyTests(unittest.TestCase):
    def setUp(self):self.policy=market_policy.load_policy()

    def parity(self,cases):
        node=shutil.which('node')
        if node is None:self.fail('Node is required for market policy parity qualification')
        result=subprocess.run([node,'-e',NODE],cwd=ROOT,input=json.dumps({'cases':cases,
            'hash':economy_catalog.catalog_hash(),'metadata':economy_catalog.ECONOMY_CATALOG['commodities']}),
            capture_output=True,text=True,encoding='utf-8',check=True,timeout=15)
        native=json.loads(result.stdout)
        for index,(policy,actual) in enumerate(zip(cases,native)):
            with self.subTest(vector=index):
                try:checked=market_policy.validate_policy(policy)
                except ValueError:self.assertFalse(actual['ok']);continue
                self.assertTrue(actual['ok'])
                self.assertEqual(actual['hash'],market_policy.policy_hash(checked))
                self.assertEqual(actual['goods'],checked['goods'])
        return native

    def test_reviewed_defaults_and_detached_copies_have_shared_digest(self):
        results=self.parity([self.policy,dict(reversed(list(self.policy.items())))])
        self.assertEqual(results[0]['hash'],'559996ebd13e46c4af46846e4ebc9358a160a5a49f44e3a239594240f685ae48')
        self.assertEqual(results[0]['hash'],results[1]['hash'])
        self.assertEqual(market_policy.tradable_ids(),('bread','grain'))
        self.assertEqual(market_policy.goods_policy('bread')['quantity_choices'],[1,2,5,10])
        result=market_policy.goods_policy('bread');result['quantity_choices'].clear()
        self.assertEqual(market_policy.goods_policy('bread')['quantity_choices'],[1,2,5,10])
        with self.assertRaises(ValueError):market_policy.goods_policy('gold')

    def test_invalid_schema_bounds_aliases_currency_and_prototype_keys_match(self):
        cases=[]
        for field,value in [('schema_version',True),('schema_version',1.5),('id','bad id'),
                            ('catalog_hash','0'*64),('goods',[]),('provenance',' '),
                            ('provenance','\ud800'),('provenance','\u0085bad')]:
            policy=copy.deepcopy(self.policy);policy[field]=value;cases.append(policy)
        for field,value in [('commodity','gold'),('commodity','unknown'),('max_quantity',True),
            ('max_quantity',11),('quantity_choices',[1,1]),('quantity_choices',[2,1]),('quantity_choices',[1.5]),
            ('quantity_choices',[]),('quantity_choices',[11]),('price_min',0),('price_max',101),
            ('price_choices',[0,1]),('price_choices',[1,True]),('price_choices',[3,2]),
            ('reserve_mode','unknown'),('legacy_retail_capability','retail_goods')]:
            policy=copy.deepcopy(self.policy);policy['goods'][0][field]=value;cases.append(policy)
        for edit in ('commodity','legacy_retail_capability'):
            policy=copy.deepcopy(self.policy);policy['goods'][1][edit]=policy['goods'][0][edit];cases.append(policy)
        policy=copy.deepcopy(self.policy);policy['goods'][1]['reserve_mode']='existing_food_policy';cases.append(policy)
        policy=copy.deepcopy(self.policy);policy['__proto__']={};cases.append(policy)
        self.assertTrue(all(not row['ok'] for row in self.parity(cases)))

    def test_unicode_provenance_and_nullable_alias_parity(self):
        self.policy['provenance']='Authored café policy 🏙; quantities remain experimental'
        self.policy['goods'][1]['legacy_retail_capability']=None
        self.assertTrue(self.parity([self.policy])[0]['ok'])

    def test_fourth_good_is_data_and_catalog_changes_do_not_retarget_policy(self):
        catalog=fourth_catalog()
        with patch.object(economy_catalog,'ECONOMY_CATALOG',catalog):
            with self.assertRaisesRegex(ValueError,'catalog'):market_policy.validate_policy(self.policy)
            self.policy['catalog_hash']=economy_catalog.catalog_hash()
            self.policy['goods'].append({**copy.deepcopy(self.policy['goods'][1]),
                'commodity':'test_clay','legacy_retail_capability':None})
            self.assertTrue(self.parity([self.policy])[0]['ok'])
            self.assertEqual(market_policy.tradable_ids(self.policy),('bread','grain','test_clay'))
            self.assertEqual(market_policy.advertised_goods({'capabilities':['retail_goods'],
                'sale_commodities':['test_clay']},self.policy),('test_clay',))

    def test_public_declarations_do_not_infer_stock_recipes_or_personal_names(self):
        self.assertEqual(market_policy.advertised_goods({'capabilities':['bread_recipe']}),())
        self.assertEqual(market_policy.advertised_goods({'capabilities':['retail_goods']}),())
        self.assertEqual(market_policy.advertised_goods({'capabilities':['retail_food']}),('bread',))
        self.assertEqual(market_policy.advertised_goods({'capabilities':['retail_food'],'sale_commodities':[]}),())
        self.assertEqual(market_policy.advertised_goods({'capabilities':['retail_food'],'sale_commodities':['grain']}),())
        self.assertEqual(market_policy.advertised_goods({'capabilities':['retail_goods'],'sale_commodities':['grain'],'active':False}),())
        self.assertEqual(market_policy.advertised_goods({'capabilities':['retail_goods'],'sale_commodities':['gold']}),())

    def test_duplicate_json_and_oversize_load_fail_without_mutating_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'policy.json'
            path.write_text('{"id":"one","id":"two"}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Duplicate'):market_policy.load_policy(path)
            path.write_bytes(b' '*(market_policy.MAX_BYTES+1))
            with self.assertRaisesRegex(ValueError,'size'):market_policy.load_policy(path)
