"""Cross-runtime catalog contracts; local Node fixtures, never native execution."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch
from economy_catalog import (load_catalog,validate_catalog,canonical_json,catalog_hash,
                             recipe_hash,apply_recipe,native_catalog_matches)

REPO=Path(__file__).resolve().parents[1]
JS=r"""
const fs=require('node:fs'),api=require('./bridge/economy-catalog.js');
const request=JSON.parse(fs.readFileSync(0,'utf8'));
if(request.operation==='validate'){
 console.log(JSON.stringify(request.catalogs.map(raw=>{try{const result=api.validateEconomyCatalog(raw);
  return {ok:true,canonical:api.canonicalJson(raw),catalog_hash:result.catalog_hash,recipe_hashes:result.recipe_hashes};
 }catch(error){return {ok:false,error:String(error.message||error)};}})));
}else{
 const raw=request.catalog,forms=new Map(),byId=new Map(),types={MISC:32,ALCH:46,INGR:30};
 for(const item of raw.commodities){if(request.missing===item.id)continue;
  const actual=request.alias&&item.id===request.alias?15:item.native.local_form_id;
  const form={name:item.id,getFormID:()=>actual,getType:()=>request.wrong_type===item.id?999:types[item.native.record_type]};
  forms.set(item.native.plugin.toLowerCase()+':'+item.native.local_form_id,form);byId.set(actual,form);
 }
 const sp={Game:{getFormFromFile:(id,plugin)=>forms.get(plugin.toLowerCase()+':'+id),getFormEx:id=>byId.get(id)}};
 const controller=api.createEconomyCatalogController(()=>sp,raw);
 const inventory=controller.readInventory({getItemCount:form=>request.inventory?.[form.name]??7});
 const result={status:controller.status(),inventory};
 if(request.command)result.validation=controller.validateOwnerCommand(request.command);
 console.log(JSON.stringify(result));
}
"""


def node(request):
    executable=shutil.which('node')
    if executable is None:raise RuntimeError('Node is required for Python/native catalog parity qualification')
    result=subprocess.run([executable,'-e',JS],input=json.dumps(request),text=True,encoding='utf-8',
                          cwd=REPO,capture_output=True,timeout=15,check=True)
    return json.loads(result.stdout)


def reverse_objects(value):
    if isinstance(value,dict):return {key:reverse_objects(value[key]) for key in reversed(value)}
    if isinstance(value,list):return [reverse_objects(v) for v in value]
    return value


class EconomyCatalogIntegrationTests(unittest.TestCase):
    def setUp(self):self.catalog=load_catalog()

    def assert_parity(self,catalogs):
        native=node({'operation':'validate','catalogs':catalogs})
        for index,(raw,result) in enumerate(zip(catalogs,native)):
            with self.subTest(vector=index):
                try:validated=validate_catalog(raw)
                except ValueError:
                    self.assertFalse(result['ok'],result)
                    continue
                self.assertTrue(result['ok'],result)
                self.assertEqual(result['canonical'],canonical_json(validated))
                self.assertEqual(result['catalog_hash'],catalog_hash(validated))
                self.assertEqual(result['recipe_hashes'],{r['id']:recipe_hash(r['id'],validated) for r in validated['recipes']})

    def test_seed_order_unicode_and_identifier_boundaries_hash_identically(self):
        unicode=copy.deepcopy(self.catalog);unicode['commodities'][1]['label']='Caf\u00e9 \U0001f35e and \u96ea'
        astral=copy.deepcopy(self.catalog);astral['commodities'][1]['label']='\U0001f35e'*120
        identifiers=copy.deepcopy(self.catalog);key='Resource-'+('X'*55)
        identifiers['commodities'][2]['id']=key;identifiers['recipes'][0]['inputs']={key:1}
        identifiers['recipes'][0]['id']='Recipe-'+('X'*57)
        self.assert_parity([self.catalog,reverse_objects(self.catalog),unicode,astral,identifiers])
        self.assertEqual(catalog_hash(self.catalog),catalog_hash(reverse_objects(self.catalog)))

    def test_invalid_quantities_aliases_and_schema_boundaries_fail_in_both_runtimes(self):
        cases=[]
        for count in (-1,0,1.5,True,1001):
            value=copy.deepcopy(self.catalog);value['recipes'][0]['inputs']['grain']=count;cases.append(value)
        for label in ('x'*121,' padded','padded ','\x85edge','\ud800'):
            value=copy.deepcopy(self.catalog);value['commodities'][1]['label']=label;cases.append(value)
        value=copy.deepcopy(self.catalog);value['commodities'][1]['native']=copy.deepcopy(value['commodities'][0]['native']);cases.append(value)
        value=copy.deepcopy(self.catalog);value['commodities'][1]['native']=copy.deepcopy(value['commodities'][0]['native']);value['commodities'][1]['native']['plugin']='skyrim.ESM';cases.append(value)
        value=copy.deepcopy(self.catalog);value['commodities'][1]['currency']=True;cases.append(value)
        value=copy.deepcopy(self.catalog);value['recipes'][0]['inputs']={};cases.append(value)
        value=copy.deepcopy(self.catalog);value['recipes'][0]['outputs']={'grain':2};cases.append(value)
        value=copy.deepcopy(self.catalog);value['recipes'][0]['inputs']={'gold':1};cases.append(value)
        value=copy.deepcopy(self.catalog);value['recipes'][0]['version']=1000001;cases.append(value)
        value=copy.deepcopy(self.catalog);value['recipes'][0]['work_minutes']['minimum']=0;cases.append(value)
        self.assert_parity(cases)

    def test_costly_cross_recipe_cycle_is_allowed_without_claiming_amplification_proof(self):
        raw=copy.deepcopy(self.catalog)
        raw['recipes'].append({'id':'recycle_bread','version':1,'inputs':{'bread':3},'outputs':{'grain':1},
            'work_minutes':{'minimum':5,'default':10,'maximum':120},'provenance':'Authored test recycling with loss and labour cost'})
        self.assertEqual(len(validate_catalog(raw)['recipes']),2)
        self.assert_parity([raw])

    def test_catalog_edits_change_all_recipe_pins_and_old_advertisement_is_rejected(self):
        old=copy.deepcopy(self.catalog);new=copy.deepcopy(old);new['commodities'][1]['label']='Revised catalog description'
        old_status={'economy_catalog':node({'catalog':old})['status']}
        self.assertTrue(native_catalog_matches(old_status,catalog=old))
        self.assertFalse(native_catalog_matches(old_status,catalog=new))
        self.assertNotEqual(recipe_hash('bread_recipe',old),recipe_hash('bread_recipe',new))
        # Historical identity is computed from the saved definition, never silently
        # replaced by whichever configuration happens to be installed now.
        self.assertEqual(recipe_hash('bread_recipe',old),hashlib.sha256(canonical_json({
            'catalog_hash':catalog_hash(old),'recipe':old['recipes'][0]}).encode('utf-8')).hexdigest())

    def expanded_catalog(self):
        raw=copy.deepcopy(self.catalog)
        for item,local in (('Ore',0x101001),('Ingot',0x101002),('Untouched',0x101003)):
            raw['commodities'].append({'id':item,'label':item,'native':{'plugin':'Fixture.esp','local_form_id':local,'record_type':'MISC'},
                                      'currency':False,'provenance':'Explicit offline test form; not an installed-game claim'})
        raw['recipes'].append({'id':'smelt-test','version':1,'inputs':{'Ore':2},'outputs':{'Ingot':1},
            'work_minutes':{'minimum':5,'default':10,'maximum':120},'provenance':'Authored test recipe'})
        return raw

    def test_added_recipe_works_without_named_residents_or_embedded_deltas_and_preserves_other_stock(self):
        raw=self.expanded_catalog();before={c['id']:7 for c in raw['commodities']}
        after=apply_recipe(before,'smelt-test',raw)
        self.assertEqual(after,{**before,'Ore':5,'Ingot':8})
        command={'recipe_id':'smelt-test','catalog_hash':catalog_hash(raw),'recipe_hash':recipe_hash('smelt-test',raw),
                 'work_minutes':10,'before':{'owner':before},'after':{'owner':after}}
        native=node({'catalog':raw,'inventory':before,'command':command})
        self.assertTrue(native['status']['available']);self.assertTrue(native['validation']['ok'])
        command['after']['owner']['Untouched']+=1
        self.assertFalse(node({'catalog':raw,'inventory':before,'command':command})['validation']['ok'])
        command['after']['owner']=after;command['recipe_hash']='0'*64
        self.assertFalse(node({'catalog':raw,'command':command})['validation']['ok'])

    def test_unknown_wrong_type_and_runtime_aliases_are_unavailable_not_zero_stock(self):
        for mode in ('missing','wrong_type'):
            native=node({'catalog':self.catalog,mode:'grain'})
            self.assertFalse(native['status']['available']);self.assertIsNone(native['inventory']['grain'])
        raw=copy.deepcopy(self.catalog)
        raw['commodities'].append({'id':'Counterfeit','label':'Distinct plugin mapping','native':{
            'plugin':'Fixture.esp','local_form_id':15,'record_type':'MISC'},'currency':False,'provenance':'Authored alias collision test'})
        native=node({'catalog':raw,'alias':'Counterfeit'})
        self.assertFalse(native['status']['available']);self.assertIsNone(native['inventory']['Counterfeit'])

    def test_changed_catalog_holds_prepared_native_intent_without_reinterpreting_old_recipe(self):
        import test_owner_work_integration
        helper=test_owner_work_integration.OwnerWorkIntegrationTests();helper.setUp()
        try:
            job=helper.delegate();helper.attendance(job)
            saved_definition=copy.deepcopy(helper.world.active['work_jobs'][job['id']]['recipe_definition'])
            before=copy.deepcopy(helper.actor['inventory'])
            revised=copy.deepcopy(self.catalog);revised['recipes'][0]['outputs']['bread']=3
            with patch('economy_catalog.ECONOMY_CATALOG',revised):
                helper.world.observe(helper.obs);helper.sync()
                stored=helper.world.active['work_jobs'][job['id']]
                self.assertEqual(stored['phase'],'held')
                self.assertTrue(stored['effect_unreconciled'])
                self.assertEqual(stored['recipe_definition'],saved_definition)
                self.assertEqual(stored['recipe_hash'],recipe_hash('bread_recipe',self.catalog))
                self.assertEqual(helper.world.active['pending']['status'],'held')
                self.assertIsNone(helper.world.pending(helper.obs['session']))
                self.assertEqual(helper.actor['inventory'],before)
                self.assertEqual(helper.world.active.get('production',[]),[])
        finally:helper.tearDown()

    def test_pre_catalog_job_remains_readable_but_cannot_start_a_new_recipe(self):
        import test_owner_work_integration
        helper=test_owner_work_integration.OwnerWorkIntegrationTests();helper.setUp()
        try:
            job=helper.delegate();state=copy.deepcopy(helper.world.active)
            old=state['work_jobs'][job['id']]
            for key in ('catalog_hash','recipe_hash','recipe_definition'):old.pop(key,None)
            old['receipt']={'phase':'historical_example','source':'Explicit old-save fixture, no native completion claim'}
            historical=copy.deepcopy(old['receipt'])
            helper.world._write(state,'Test fixture: pre-catalog saved owner job');helper.sync()
            status=helper.world.owner_work_status()
            projected=next(row for row in status['jobs'] if row['id']==job['id'])
            self.assertEqual(projected['phase'],'held')
            self.assertNotIn('catalog_hash',projected)
            self.assertEqual(helper.world.active['work_jobs'][job['id']]['receipt'],historical)
            self.assertIsNone(helper.world.owner_work_pending_command())
            self.assertIsNone(helper.world.active['pending'])
            self.assertEqual(helper.world.active.get('production',[]),[])
        finally:helper.tearDown()

    def test_two_recipes_in_one_dynamic_enterprise_keep_distinct_model_choices(self):
        import test_owner_work_integration
        import market_policy
        from catalog_fixture import native_catalog
        helper=test_owner_work_integration.OwnerWorkIntegrationTests();helper.setUp()
        try:
            raw=self.expanded_catalog()
            with patch('economy_catalog.ECONOMY_CATALOG',raw):
                policy=copy.deepcopy(market_policy.MARKET_POLICY);policy['catalog_hash']=catalog_hash()
                market=patch.object(market_policy,'MARKET_POLICY',policy);market.start();self.addCleanup(market.stop)
                helper.obs['economy_catalog']=native_catalog()
                for actor in helper.obs['residents']:
                    actor['inventory'].update(Ore=7,Ingot=0,Untouched=11)
                helper.world.active['town']['businesses']['new-owner']['capabilities']=['bread_recipe','smelt-test']
                claim=helper.start();context=claim['context']
                actions=context['owner_work_actions'];terms=context['work_options']
                self.assertEqual(len(actions),2)
                self.assertEqual(len(set(actions)),2)
                self.assertEqual({terms[action]['recipe_id'] for action in actions},{'bread_recipe','smelt-test'})
                self.assertEqual(len({o['id'] for o in context['options']}),len(context['options']))
                wire=json.dumps(context)
                self.assertNotIn('local_form_id',wire);self.assertNotIn('record_type',wire)
                selected=next(action for action in actions if terms[action]['recipe_id']=='smelt-test')
                decision={'action_id':selected,'reason':'Explicit offline test choice','emotion':'calm'}
                with self.assertRaises(ValueError):
                    helper.world.finish_plan_decision(helper.event['id'],claim['id'],{'model':'test',
                        'decision':{**decision,'native_form_id':123,'output_count':999999}},helper.obs)
                helper.world.finish_plan_decision(helper.event['id'],claim['id'],{'model':'test','decision':decision},helper.obs)
                helper.sync()
                plan=helper.world.agency_plan();job=helper.world.active['work_jobs'][plan['work_job']]
                self.assertEqual(job['actor'],helper.actor['id'])
                self.assertEqual(job['recipe_id'],'smelt-test')
                self.assertEqual(job['input_reservation'],{'Ore':2})
                self.assertEqual(job['recipe_hash'],recipe_hash('smelt-test',raw))
                self.assertEqual(helper.actor['inventory']['Untouched'],11)
        finally:helper.tearDown()


if __name__=='__main__':unittest.main()
