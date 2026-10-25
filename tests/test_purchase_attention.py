"""Unmocked configured 18-resident purchase attention, offline checkpoint admission."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import test_generic_procurement as fixtures
from agency import Agency
from catalog_fixture import native_catalog
from context_window import (bounded_economic_context, encoded_size, purchase_attention_policy,
    purchase_catalogue_hash, purchase_decision_counts, check_purchase_decision_budget)
from lineage import TimelineEconomy
from population import person_seed
from procurement import input_procurement, PINS
from legacy_fixture import author_fixture_identities


class PurchaseAttentionTests(unittest.TestCase):
    def setUp(self):
        fixtures.GenericProcurementTests.setUp(self)
        for actor in range(9,25):
            row=copy.deepcopy(self.obs['residents'][1]);row.update(id=actor,baseId=1000+actor,x=100+actor)
            self.obs['residents'].append(row);self.state['people'][str(actor)]=person_seed(row,'fixture',1)
            self.state['town']['residents'][str(actor)]={'id':actor}
            self.state['town']['businesses']['supply-'+str(actor)]={'owner':actor,'custodian':actor,'revision':3,
                'capabilities':['retail_goods'],'sale_commodities':['ore']}
        self.obs.update(session='offline-attention',gameDays=1,economy_catalog=native_catalog(),ready=True,checkpoint=0)
        author_fixture_identities(self.state,self.obs,event_id='purchase-attention-fixture')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.world=TimelineEconomy(Path(self.temp.name)/'timeline.sqlite');self.addCleanup(self.world.db.close)
        self.world.observe(self.obs);self.world.bootstrap(self.obs);self.bind()
        state=copy.deepcopy(self.world.active);state.update(people=self.state['people'],town=self.state['town'])
        self.event={'id':'offline-attention-review','actor':7,'kind':'need_review','status':'pending'}
        state['town']['daily']={'queue':[self.event]}
        self.world._write(state,'explicit 18-resident offline fixture');self.bind()
        self.world.begin_plan(self.event['id'],self.obs,7,'need_review');self.bind()

    def bind(self):
        while self.world.transition:
            self.obs['checkpoint']=self.world.transition['next'];self.world.observe(self.obs)

    def claim(self):
        claim=self.world.claim_plan_decision(self.event['id'],self.obs)['claim'];self.bind()
        self.assertLessEqual(encoded_size(claim['context']),12000)
        return claim

    def choose(self,claim,action):
        self.world.finish_plan_decision(self.event['id'],claim['id'],{'model':'offline-fixture-choice',
            'decision':{'action_id':action,'reason':'Inspect an explicitly configured alternative','emotion':'calm'}},self.obs)
        self.bind()

    def open_menu(self):
        claim=self.claim();self.assertEqual(claim['context']['purchase_attention']['total_choices'],68)
        self.assertFalse(claim['context']['purchase_options'])
        self.choose(claim,'review_input_purchases')
        return claim

    def test_18_resident_real_claim_and_every_alternative_reachable_under_12kb(self):
        opening=self.open_menu();original=input_procurement(self.world.active,self.obs,7)
        self.assertEqual(len(self.obs['residents']),18);self.assertEqual(len(original),68)
        plan=copy.deepcopy(self.world.agency_plan());stack=[plan];found={};sizes=[encoded_size(opening['context'])];depths=[]
        while stack:
            current=stack.pop();context=bounded_economic_context(self.world._plan_context(self.obs,current),[])
            sizes.append(encoded_size(context));self.assertLessEqual(sizes[-1],12000)
            self.assertNotIn('7139',json.dumps(context));self.assertNotIn('Secret seller',json.dumps(context))
            if context['purchase_attention']['stage']=='groups':
                self.assertTrue(any('observed distance' in option['effect'] for option in context['options']))
            self.assertLessEqual(len(context['purchase_options']),6)
            for action,row in context['purchase_options'].items():
                self.assertNotIn(action,found);found[action]=row;depths.append(len(current['purchase_menu']['trail'])+1)
            for nav in context['purchase_navigation'].values():
                if nav['kind']!='group':continue
                child=copy.deepcopy(current);menu=child['purchase_menu'];menu['trail'].append(menu['range']);menu['range']=nav['range'];stack.append(child)
        self.assertEqual(found,{row['id']:row for row in original})
        self.assertEqual({r['supplier'] for r in found.values()},set(range(8,25)))
        self.assertEqual({r['quantity'] for r in found.values()},{1,2,5,10})
        self.assertLessEqual(max(depths),purchase_attention_policy()['maximum_navigation_calls'])
        self.measurements={'contexts':len(sizes),'maximum_bytes':max(sizes),'maximum_selection_calls':max(depths)}
        print('ATTENTION_MEASUREMENTS '+json.dumps(self.measurements))

    def test_supplier_motion_before_inspection_does_not_change_catalogue_identity(self):
        claim=self.claim();original_hash=claim['context']['purchase_attention']['catalogue_hash']
        self.obs['residents'][1]['x']=240
        current=self.world._plan_context(self.obs,{**self.world.agency_plan(),'phase':'choose'})
        self.assertEqual(current['purchase_attention']['catalogue_hash'],original_hash)
        self.choose(claim,'review_input_purchases')
        self.assertEqual(self.world.agency_plan()['phase'],'purchase_select')
        self.assertEqual(self.world.agency_plan()['purchase_menu']['choices'][0]['supplier'],8)

    def test_far_leaf_real_claim_keeps_original_purchase_and_initial_proof(self):
        self.open_menu();snapshot=self.world.agency_plan()['purchase_menu']['choices'];selected=copy.deepcopy(snapshot[-1]);index=len(snapshot)-1
        while True:
            claim=self.claim()
            if selected['id'] in claim['context']['purchase_options']:break
            action=next(key for key,nav in claim['context']['purchase_navigation'].items()
                        if nav['kind']=='group' and nav['range'][0]<=index<nav['range'][1])
            self.choose(claim,action)
        self.assertEqual(claim['context']['purchase_options'][selected['id']],selected)
        self.choose(claim,selected['id']);plan=self.world.agency_plan()
        self.assertEqual(plan['phase'],'travelling');self.assertEqual(plan['procurement'],selected)
        self.assertEqual(plan['procurement_claim_id'],claim['id'])
        self.assertEqual(purchase_decision_counts(plan),{'economic':1,'purchase_navigation':2})
        retained=next(d for d in plan['decisions'] if d['claim_id']==claim['id'])
        self.assertEqual(retained['context']['purchase_options'][selected['id']],selected)

    def test_back_and_exit_restore_options_without_spending_or_selecting(self):
        self.open_menu();before=copy.deepcopy(self.obs['residents']);claim=self.claim()
        action=next(key for key,nav in claim['context']['purchase_navigation'].items() if nav['kind']=='group')
        self.choose(claim,action);claim=self.claim();self.choose(claim,'purchase_back')
        self.assertEqual(self.world.agency_plan()['purchase_menu']['range'],[0,68])
        claim=self.claim();self.choose(claim,'cancel_purchase_review')
        self.assertEqual(self.world.agency_plan()['phase'],'choose');self.assertNotIn('procurement',self.world.agency_plan())
        self.assertEqual(self.obs['residents'],before);self.assertIsNone(self.world.active['pending'])

    def test_removed_listing_is_visible_unavailable_and_old_claim_cannot_select_it(self):
        self.open_menu();menu=self.world.agency_plan()['purchase_menu'];menu['trail']=[[0,68],[0,9]];menu['range']=[0,2]
        claim=self.claim();selected=next(iter(claim['context']['purchase_options'].values()))
        self.world.active['town']['businesses'][selected['listing_business_id']]['revision']+=1
        with self.assertRaisesRegex(ValueError,'not currently allowed'):self.choose(claim,selected['id'])
        context=self.world._plan_context(self.obs,{**self.world.agency_plan(),'phase':'purchase_select'})
        self.assertIn(selected['id'],[r['id'] for r in context['purchase_attention']['unavailable_choices']])
        self.assertNotIn(selected['id'],context['purchase_options']);self.assertNotIn('procurement',self.world.agency_plan())

    def test_malformed_ranges_catalogue_or_unknown_navigation_never_reinterpret(self):
        self.open_menu();original=copy.deepcopy(self.world.agency_plan())
        for change in ('range','hash','policy'):
            plan=copy.deepcopy(original)
            if change=='range':plan['purchase_menu']['range']=[1,3]
            elif change=='hash':plan['purchase_menu']['catalogue_hash']='0'*64
            else:plan['purchase_menu']['policy']['branches']=7
            with self.subTest(change=change),self.assertRaises(ValueError):self.world._plan_context(self.obs,plan)
        claim=self.claim()
        with self.assertRaisesRegex(ValueError,'not currently allowed'):self.choose(claim,'inspect_purchase_group_0_999')

    def test_navigation_and_economic_budgets_are_independently_bounded(self):
        plan={'phase':'purchase_select','decisions':[{'call_lane':'purchase_navigation'} for _ in range(16)]}
        with self.assertRaisesRegex(ValueError,'purchase_navigation'):check_purchase_decision_budget(plan)
        plan['phase']='quote';check_purchase_decision_budget(plan)
        plan['decisions'] += [{} for _ in range(6)]
        with self.assertRaisesRegex(ValueError,'economic'):check_purchase_decision_budget(plan)
        self.assertEqual(purchase_decision_counts(plan),{'economic':6,'purchase_navigation':16})


if __name__=='__main__':unittest.main()
