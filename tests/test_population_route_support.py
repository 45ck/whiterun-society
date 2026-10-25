"""Observed route capability reporting; no native execution or model calls."""
import copy
import unittest
from population import Population, person_seed, ROUTE_SUPPORT_BASIS
from daily_life import DailyLife


class ReportingWorld(Population,DailyLife):
    def __init__(self):
        self.active={'people':{},'plans':[]};self.session='reporting';self.writes=[]
    def _agency_guard(self,observation):pass
    def agency_busy(self):return False
    def conversation_busy(self):return False
    def _write(self,state,reason):self.active=state;self.writes.append(reason);return len(self.writes)


def actor(actor_id):
    return {'id':actor_id,'name':'Resident '+str(actor_id),'isPerson':True,
        'inventory':{'gold':0,'bread':0,'grain':0}}


def observation(ids=(108149,108186,108156,99),routing=None):
    obs={'session':'reporting','gameDays':1.,'residents':[actor(key) for key in ids]}
    if routing is not None:obs['routing']=routing
    return obs


def executor():return {'adapter':'papyrus-mailbox-v1','available':True,'session':'reporting'}


class PopulationRouteSupportTests(unittest.TestCase):
    def initialize(self,obs):
        world=ReportingWorld();world.initialize_population('census','fixture',obs)
        return world

    def test_original_and_arbitrary_ids_have_identical_unknown_or_supported_seed(self):
        obs=observation(routing=executor())
        for row in obs['residents']:
            self.assertIsNone(person_seed(row,'fixture',1.)['agency']['native_route_supported'])
            self.assertIs(person_seed(row,'fixture',1.,obs)['agency']['native_route_supported'],True)
        world=self.initialize(obs)
        self.assertEqual(world.population_status()['counts']['native_route_supported'],4)
        self.assertEqual(world.population_status()['counts']['native_route_unknown'],0)

    def test_missing_stale_and_explicit_unavailable_evidence_stay_distinct(self):
        for proof,expected in [(None,None),({},None),({**executor(),'session':'old'},None),
                ({**executor(),'available':False},False),({**executor(),'adapter':'unsupported'},False)]:
            obs=observation(routing=proof);world=self.initialize(obs);town=world.population_status()
            with self.subTest(proof=proof):
                self.assertTrue(all(r['native_route_supported'] is expected for r in town['residents'].values()))
                self.assertEqual(town['counts']['native_route_unknown'],4 if expected is None else 0)
                self.assertEqual(town['counts']['native_route_unavailable'],4 if expected is False else 0)
                self.assertEqual(town['counts']['native_route_supported'],0)

    def test_valid_executor_single_actor_does_not_require_an_invented_destination(self):
        world=self.initialize(observation(ids=(72411,),routing=executor()))
        self.assertIs(world.population_status()['residents']['72411']['native_route_supported'],True)
        self.assertEqual(world.active['plans'],[])
        self.assertEqual(world.active['people']['72411']['known_people'],{})

    def test_census_support_does_not_grant_knowledge_memories_or_inventory(self):
        obs=observation(routing=executor());before=copy.deepcopy(obs)
        world=self.initialize(obs)
        self.assertEqual(obs,before)
        self.assertEqual(world.active['town']['businesses'],{})
        self.assertNotIn('pending',world.active)
        for key,person in world.active['people'].items():
            self.assertEqual(person['known_people'],{});self.assertEqual(person['memories'],[])
            self.assertNotIn('known_recipes',person)
            self.assertEqual(world.active['town']['residents'][key]['initial_observed_inventory'],{'gold':0,'bread':0,'grain':0})

    def test_legacy_id_derived_flags_project_unknown_without_rewriting_saved_evidence(self):
        world=self.initialize(observation(routing=executor()))
        for row in world.active['town']['residents'].values():row.pop('native_route_support_basis')
        before=copy.deepcopy(world.active)
        status=world.population_status()
        self.assertTrue(all(row['native_route_supported'] is None for row in status['residents'].values()))
        self.assertEqual(status['counts']['native_route_unknown'],4)
        self.assertEqual(status['counts']['residents'],4)
        self.assertEqual(world.active,before)

    def test_malformed_saved_support_value_is_unknown_not_truthy_supported(self):
        world=self.initialize(observation(ids=(99,),routing=executor()))
        world.active['town']['residents']['99']['native_route_supported']='yes'
        status=world.population_status()
        self.assertIsNone(status['residents']['99']['native_route_supported'])
        self.assertEqual(status['counts']['native_route_supported'],0)
        self.assertEqual(status['counts']['native_route_unavailable'],0)
        self.assertEqual(status['counts']['native_route_unknown'],1)

    def test_new_census_refreshes_absent_residents_as_unknown_without_reseeding(self):
        obs=observation(routing=executor());world=self.initialize(obs)
        original=copy.deepcopy(world.active['people']['99']['profile'])
        obs['residents']=[r for r in obs['residents'] if r['id']!=99]
        result=world.initialize_population('recensus','fixture',obs)
        self.assertEqual(result['added'],[])
        self.assertIsNone(world.active['people']['99']['agency']['native_route_supported'])
        self.assertEqual(world.population_status()['counts']['native_route_unknown'],1)
        self.assertEqual(world.active['people']['99']['profile'],original)

    def test_stale_or_unloaded_person_cannot_receive_initial_supported_flag(self):
        for extra in ({'loaded':False},{'session':'old'},{'activity':{}}):
            obs=observation(ids=(99,),routing=executor());obs['residents'][0].update(extra)
            world=self.initialize(obs)
            with self.subTest(extra=extra):
                self.assertIsNone(world.population_status()['residents']['99']['native_route_supported'])
                self.assertIsNone(world.active['people']['99']['agency']['native_route_supported'])

    def test_daily_refresh_revokes_stale_support_without_inventing_actions(self):
        obs=observation(routing=executor());world=self.initialize(obs)
        for person in world.active['people'].values():
            person['needs']={key:.2 for key in person['needs']};person['agency']['next_review_day']=100
        before_inventory=copy.deepcopy(obs['residents'])
        world.review_population(obs)
        obs.pop('routing');obs['gameDays']+=1/24
        world.review_population(obs)
        self.assertEqual(world.population_status()['counts']['native_route_unknown'],4)
        self.assertEqual(world.active['town']['daily']['queue'],[])
        obs['routing']={**executor(),'available':False};obs['gameDays']+=1/24
        world.review_population(obs)
        self.assertEqual(world.population_status()['counts']['native_route_unavailable'],4)
        self.assertEqual(obs['residents'],before_inventory)
        for person in world.active['people'].values():
            self.assertEqual(person['memories'],[]);self.assertEqual(person['known_people'],{})
            self.assertEqual(person['agency']['native_route_support_basis'],ROUTE_SUPPORT_BASIS)

    def test_lease_availability_does_not_relabel_executor_capability_or_cancel_job(self):
        obs=observation(ids=(99,),routing=executor());world=self.initialize(obs)
        person=world.active['people']['99'];person['agency']['state']='working'
        person['standing_goal']={'id':'saved','phase':'travelling'}
        world.active['work_jobs']={'job':{'actor':99,'phase':'running','receipt_acknowledged':False}}
        before=copy.deepcopy(world.active['work_jobs'])
        world.review_population(obs)
        self.assertIs(world.active['people']['99']['agency']['native_route_supported'],True)
        self.assertEqual(world.active['people']['99']['agency']['state'],'working')
        self.assertEqual(world.active['people']['99']['standing_goal'],{'id':'saved','phase':'travelling'})
        self.assertEqual(world.active['work_jobs'],before)
        self.assertEqual(world.active['town']['daily']['queue'],[])


if __name__=='__main__':unittest.main()
