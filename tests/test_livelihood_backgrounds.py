"""Explicit prior-skill scenarios use real save checkpoints, never economic effects."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import economy_catalog
from catalog_fixture import native_catalog
from entrepreneurship import knows_recipe, learn_recipe, recipe_knowledge
from livelihood_backgrounds import (LivelihoodBackgrounds, load_livelihood_manifest,
    validate_livelihood_manifest, livelihood_manifest_hash, preview_livelihood_background,
    authored_prior_status)
from lineage import TimelineEconomy


class LivelihoodBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.world=TimelineEconomy(Path(self.temp.name)/'prior.sqlite');self.addCleanup(self.world.db.close)
        self.obs={'session':'prior-fixture','checkpoint':0,'ready':True,'gameDays':4.,
            'economy_catalog':native_catalog(),'routing':{'available':True,'adapter':'papyrus-mailbox-v1'},
            'residents':[{'id':actor,'baseId':actor+1000,'name':'Observed adult '+str(actor),
                'isPerson':True,'x':index*100,'y':0,'z':0,'inventory':{'gold':20,'bread':2,'grain':1}}
                for index,actor in enumerate((901,902,903))]}
        self.world.observe(self.obs);self.world.bootstrap(self.obs);self.bind()
        self.world.initialize_population('prior-census','prior-population',self.obs);self.bind()
        self.manifest=load_livelihood_manifest();self.hash=livelihood_manifest_hash(self.manifest)

    def bind(self):
        for _ in range(8):
            if not self.world.transition:
                self.assertIsNone(self.world.error);return
            self.obs['checkpoint']=self.world.transition['next'];self.obs.pop('ack',None)
            self.world.observe(self.obs)
        self.fail('Unexpected unbounded checkpoint transition')

    def preview(self,**changes):
        arguments={'state':self.world.active,'observation':self.obs,'event_id':'prior-event',
            'seed':'prior-seed','scenario_id':self.manifest['id'],'scenario_hash':self.hash,'actor_ids':[901,902,903]}
        arguments.update(changes)
        return preview_livelihood_background(**arguments)

    def apply(self):
        result=LivelihoodBackgrounds.establish_livelihood_background(self.world,'prior-event','prior-seed',
            self.manifest['id'],self.hash,[901,902,903],self.obs)
        self.bind();return result

    def selected(self):
        return self.world.active['town']['livelihood_backgrounds'][0]['assignments'][0]['actor']

    def test_pure_preview_is_order_independent_and_assigns_only_explicit_count(self):
        before=copy.deepcopy((self.world.active,self.obs));first=self.preview();second=self.preview(actor_ids=[903,901,902])
        self.assertEqual(first,second);self.assertEqual((self.world.active,self.obs),before)
        self.assertEqual(len(first['background']['assignments']),1)
        assignment=first['background']['assignments'][0]
        self.assertEqual(assignment['base_id'],assignment['actor']+1000)
        self.assertEqual(assignment['source'],'authored_livelihood_background')
        self.assertEqual(assignment['definition'],economy_catalog.recipe_spec('bread_recipe'))
        self.assertEqual(livelihood_manifest_hash(),'265793645cc8981896e253bfd72fa310685ccf180e8cb833105fc3c2c040e4cf')

    def test_apply_is_checkpointed_and_changes_no_assets_memories_or_enterprises(self):
        before=copy.deepcopy(self.world.active);native=copy.deepcopy(self.obs['residents'])
        result=LivelihoodBackgrounds.establish_livelihood_background(self.world,'prior-event','prior-seed',
            self.manifest['id'],self.hash,[901,902,903],self.obs)
        self.assertEqual(self.world.active,before,'proposal is not adopted before checkpoint binding')
        self.assertIsNotNone(self.world.transition);self.bind()
        self.assertEqual(self.obs['residents'],native)
        self.assertEqual(self.world.active['town']['businesses'],before['town']['businesses'])
        for field in ('trades','production','pending','starting_inventory'):
            self.assertEqual(self.world.active.get(field),before.get(field))
        recipients=[]
        for key,person in self.world.active['people'].items():
            expected=copy.deepcopy(before['people'][key])
            if 'authored_recipe_priors' in person:
                recipients.append(int(key));expected['authored_recipe_priors']=person['authored_recipe_priors']
            self.assertEqual(person,expected)
            self.assertNotIn('known_recipes',person)
        self.assertEqual(recipients,[self.selected()])
        self.assertEqual(result['background']['source_checkpoint'],self.world._read(result['checkpoint'])['town']['livelihood_backgrounds'][0]['source_checkpoint'])

    def test_prior_requires_current_identity_and_cannot_be_claimed_without_context(self):
        self.apply();actor=self.selected();person=self.world.active['people'][str(actor)]
        context={'state':self.world.active,'observation':self.obs,'actor_id':actor}
        self.assertFalse(knows_recipe(person,'bread_recipe'))
        self.assertTrue(knows_recipe(person,'bread_recipe',**context))
        projection=recipe_knowledge(person,**context)
        self.assertEqual(projection['provenance']['bread_recipe']['source'],'authored_livelihood_background')
        self.assertTrue(projection['recipes']['bread_recipe'])
        row=next(row for row in self.obs['residents'] if row['id']==actor)
        row['baseId']+=1
        self.assertFalse(knows_recipe(person,'bread_recipe',**context))
        self.assertFalse(authored_prior_status(self.world.active,self.obs,actor,'bread_recipe')['valid'])
        del row['baseId']
        self.assertFalse(knows_recipe(person,'bread_recipe',**context))

    def test_retries_cannot_change_seed_cohort_or_enroll_newcomers(self):
        self.apply();before=copy.deepcopy(self.world.active)
        self.assertTrue(self.preview(actor_ids=[903,902,901])['duplicate'])
        self.assertTrue(self.apply()['duplicate']);self.assertEqual(self.world.active,before)
        for changed in ({'seed':'other-seed'},{'actor_ids':[901,902]},
                        {'scenario_hash':'0'*64},{'event_id':'another-prior-event'}):
            with self.subTest(changed=changed),self.assertRaises(ValueError):self.preview(**changed)
        self.obs['residents'].append({'id':904,'baseId':1904,'name':'Newcomer','isPerson':True,
            'inventory':{'gold':2,'bread':1,'grain':0}})
        self.world.initialize_population('later-census','prior-population',self.obs);self.bind()
        self.assertNotIn('authored_recipe_priors',self.world.active['people']['904'])
        self.assertEqual(self.world.active['town']['livelihood_backgrounds'],before['town']['livelihood_backgrounds'])

    def test_old_save_rollback_does_not_inherit_future_prior(self):
        earlier=copy.deepcopy(self.obs);self.apply()
        self.world.observe({**earlier,'session':'earlier-prior-save'})
        self.assertFalse(self.world.active['town'].get('livelihood_backgrounds'))
        self.assertTrue(all('authored_recipe_priors' not in row for row in self.world.active['people'].values()))
        self.assertIsNone(self.world.transition)

    def test_changed_recipe_or_detached_prior_loses_authority_without_erasing_audit(self):
        self.apply();actor=self.selected();before=copy.deepcopy(self.world.active)
        changed=copy.deepcopy(economy_catalog.ECONOMY_CATALOG)
        changed['recipes'][0]['work_minutes']['default']=31
        with patch.object(economy_catalog,'ECONOMY_CATALOG',changed):
            self.assertFalse(authored_prior_status(self.world.active,self.obs,actor,'bread_recipe')['valid'])
        self.assertEqual(self.world.active,before)
        self.world.active['town']['livelihood_backgrounds'][0]['assignments']=[]
        self.assertFalse(authored_prior_status(self.world.active,self.obs,actor,'bread_recipe')['valid'])

    def test_verified_learning_records_actual_provenance_without_erasing_authored_prior(self):
        self.apply();actor=self.selected();person=self.world.active['people'][str(actor)]
        prior=copy.deepcopy(person['authored_recipe_priors'])
        learn_recipe(person,'fixture-verified-production-receipt','bread_recipe')
        self.assertEqual(person['known_recipes']['bread_recipe']['source'],'verified_native_production')
        self.assertEqual(person['known_recipes']['bread_recipe']['event_id'],'fixture-verified-production-receipt')
        self.assertEqual(person['authored_recipe_priors'],prior)
        self.assertEqual(recipe_knowledge(person)['provenance']['bread_recipe']['source'],'verified_native_production')

    def test_missing_legacy_binding_and_invalid_current_cohort_cannot_receive_priors(self):
        for change in ('binding','base','classification','duplicate'):
            state=copy.deepcopy(self.world.active);observation=copy.deepcopy(self.obs)
            if change=='binding':state['town']['residents']['901'].pop('identity_binding',None)
            elif change=='base':observation['residents'][0].pop('baseId')
            elif change=='classification':observation['residents'][0]['isPerson']=None
            else:observation['residents'].append(copy.deepcopy(observation['residents'][0]))
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'identity'):
                self.preview(state=state,observation=observation)

    def test_manifest_schema_rejects_implicit_unknown_or_aliased_rules(self):
        cases=[]
        for key,value in [('schema_version',True),('catalog_hash','0'*64),('selection','all_skills'),
                          ('rules',[]),('provenance','\ud800')]:
            raw=copy.deepcopy(self.manifest);raw[key]=value;cases.append(raw)
        for key,value in [('recipient_count',True),('recipient_count',0),('recipient_count',129),
                          ('recipe_id','unknown_recipe'),('recipe_hash','0'*64)]:
            raw=copy.deepcopy(self.manifest);raw['rules'][0][key]=value;cases.append(raw)
        raw=copy.deepcopy(self.manifest);raw['rules'].append(copy.deepcopy(raw['rules'][0]));cases.append(raw)
        for raw in cases:
            with self.subTest(raw=raw),self.assertRaises(ValueError):validate_livelihood_manifest(raw)
        path=Path(self.temp.name)/'duplicate.json';path.write_text('{"id":"one","id":"two"}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Duplicate'):load_livelihood_manifest(path)
        for actors in ([],[901,901],[True,902]):
            with self.subTest(actors=actors),self.assertRaises(ValueError):self.preview(actor_ids=actors)
