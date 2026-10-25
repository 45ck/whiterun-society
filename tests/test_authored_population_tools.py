"""Offline admission/census contracts; never invoke a live authored lab tool."""
import copy
import unittest
from unittest.mock import Mock, patch
from tools.authored_population import (census_spec, initialize_fresh_population,
    validate_market_contract, validate_participants)


def fixture(checkpoint=1):
    actors=[{'id':actor,'name':'Observed '+str(actor),'isPerson':True,'loaded':True,
             'inventory':{'gold':12,'bread':3,'grain':2}} for actor in (108186,108149,900001)]
    return {'bridge':{'session':'test-session','observation':{'session':'test-session','checkpoint':checkpoint,'gameDays':8.,'residents':actors}},
            'society':{'checkpoint':checkpoint,'transition':None,'error':None,'people':{},'town':None}}


def managed():
    state=fixture()
    state['society']['people']={str(actor):{'profile':{'name':'Preserved'},'memories':[{'id':'old'}]} for actor in (108186,108149)}
    state['society']['town']={'seed':'existing-seed','residents':{},'businesses':{},'census_events':[]}
    return state


class AuthoredPopulationToolTests(unittest.TestCase):
    def test_seed_is_explicit_stable_bounded_and_scenario_specific(self):
        a=census_spec('market-day','trial')
        self.assertEqual(a,census_spec('market-day','trial'))
        self.assertNotEqual(a,census_spec('save-lineage','trial'))
        self.assertTrue(all(len(v)<=48 for v in a.values()))
        with self.assertRaises(ValueError):census_spec('arbitrary','trial')
        with self.assertRaises(ValueError):census_spec('market-day','')

    def test_missing_replaced_unclassified_unloaded_or_incomplete_actor_rejected(self):
        for change in ('missing','replacement','classification','loaded','inventory'):
            state=fixture();actor=state['bridge']['observation']['residents'][0]
            if change=='missing':state['bridge']['observation']['residents'].pop(0)
            elif change=='replacement':actor['id']=900002
            elif change=='classification':actor['isPerson']=False
            elif change=='loaded':actor['loaded']=False
            else:actor['inventory'].pop('grain')
            before=copy.deepcopy(state)
            with self.subTest(change=change),self.assertRaises(ValueError):validate_participants(state)
            self.assertEqual(state,before)

    def test_census_requires_bound_checkpoint_and_never_touches_managed_profiles(self):
        for state in (managed(),fixture(0),fixture()):
            if not state['society']['people'] and state['society']['checkpoint']==1:
                state['bridge']['observation']['checkpoint']=0
            request=Mock();before=copy.deepcopy(state)
            with self.assertRaises(ValueError):initialize_fresh_population(request,Mock(),state,'market-day','trial')
            request.assert_not_called();self.assertEqual(state,before)

    def test_fresh_census_waits_for_its_exact_checkpoint_seed_and_event(self):
        start=fixture();expected=census_spec('save-lineage','trial');result=fixture(2)
        result['society']['people']={str(a['id']):{'profile':{'provenance':'uniform'}} for a in result['bridge']['observation']['residents']}
        result['society']['town']={'seed':expected['seed'],'census_events':[{'id':expected['id']}],'businesses':{}}
        request=Mock(return_value={'checkpoint':2})
        def wait(predicate):
            self.assertFalse(predicate(start))
            for field,value in [('seed','different'),('census_events',[])]:
                wrong=copy.deepcopy(result);wrong['society']['town'][field]=value
                self.assertFalse(predicate(wrong))
            wrong=copy.deepcopy(result);wrong['bridge']['observation']['checkpoint']=1
            self.assertFalse(predicate(wrong))
            self.assertTrue(predicate(result));return result
        after,proof=initialize_fresh_population(request,wait,start,'save-lineage','trial')
        request.assert_called_once_with('/town/initialize',expected,session='test-session')
        self.assertEqual(len(after['society']['people']),3)
        self.assertEqual(proof['seed'],expected['seed'])
        self.assertIn('Fresh choices may differ',proof['historical_comparability'])
        self.assertFalse(after['society']['town']['businesses'])

    def test_census_refuses_missing_or_mismatched_initial_session_before_mutation(self):
        for bridge_session, observation_session in ((None,'test-session'),('',''),('test-session',None),('test-session','other')):
            state=fixture();state['bridge']['session']=bridge_session
            state['bridge']['observation']['session']=observation_session
            request=Mock()
            with self.subTest(bridge=bridge_session,observation=observation_session),self.assertRaisesRegex(ValueError,'sessions'):
                initialize_fresh_population(request,Mock(),state,'save-lineage','trial')
            request.assert_not_called()

    def test_census_cannot_accept_same_checkpoint_and_provenance_from_another_session(self):
        spec=census_spec('save-lineage','trial')
        for bridge_session, observation_session in (('other','other'),('other','test-session'),('test-session','other')):
            result=managed();result['society']['checkpoint']=2
            result['society']['town'].update(seed=spec['seed'],census_events=[{'id':spec['id']}])
            result['bridge']['session']=bridge_session
            result['bridge']['observation'].update(checkpoint=2,session=observation_session)
            def wait(predicate):
                self.assertFalse(predicate(result));return result
            with self.subTest(bridge=bridge_session,observation=observation_session),self.assertRaisesRegex(ValueError,'not observed'):
                initialize_fresh_population(Mock(return_value={'checkpoint':2}),wait,fixture(),'save-lineage','trial')

    def test_completed_current_scenario_duplicate_needs_no_current_people_or_charter(self):
        state=fixture();state['bridge']['observation']['residents']=[]
        state['society']['market_day']={'id':'completed-trial','status':'complete'}
        with patch('tools.authored_population.work_opportunities') as work:
            validate_market_contract(state,'completed-trial');work.assert_not_called()
        state['society']['market_day']['status']='running'
        with self.assertRaises(ValueError):validate_market_contract(state,'completed-trial')

    def test_bad_census_ack_or_wait_result_cannot_claim_initialized(self):
        for acknowledgement in ({},{'duplicate':True},{'checkpoint':1},{'checkpoint':True}):
            with self.subTest(ack=acknowledgement),self.assertRaises(ValueError):
                initialize_fresh_population(Mock(return_value=acknowledgement),Mock(),fixture(),'market-day','trial')
        with self.assertRaises(ValueError):
            initialize_fresh_population(Mock(return_value={'checkpoint':2}),Mock(return_value=fixture()),fixture(),'market-day','trial')

    def test_managed_validation_preserves_existing_profiles_and_seed(self):
        state=managed();before=copy.deepcopy(state)
        validate_participants(state,require_saved=True)
        self.assertEqual(state,before)
        state['society']['people'].pop('108186')
        with self.assertRaisesRegex(ValueError,'not initialized'):validate_participants(state,require_saved=True)

    def test_fresh_uniform_town_never_invents_missing_business_charters(self):
        state=managed();before=copy.deepcopy(state)
        with patch('tools.authored_population.work_opportunities') as work:
            with self.assertRaisesRegex(ValueError,'explicit active'):validate_market_contract(state,'trial')
            work.assert_not_called()
        self.assertEqual(state,before)

    def test_market_work_requires_explicit_charter_and_current_feasible_authored_employer(self):
        state=managed();state['society']['town']['businesses']={'observed-business':
            {'active':True,'custodian':108149,'capabilities':['bread_recipe','retail_food']}}
        for offers in ([],[{'employer':900001}],[{'employer':108149}]):
            with patch('tools.authored_population.work_opportunities',return_value=offers):
                if offers and offers[0]['employer']==108149:validate_market_contract(state,'trial')
                else:
                    with self.assertRaisesRegex(ValueError,'currently feasible'):validate_market_contract(state,'trial')
        state['society']['market_day']={'id':'trial','status':'running','cursor':2}
        with patch('tools.authored_population.work_opportunities') as work:
            validate_market_contract(state,'trial');work.assert_not_called()
