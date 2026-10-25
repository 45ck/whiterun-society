import copy
import unittest
from unittest.mock import patch
import test_resident_control as fixtures
from resident_goals import goal_context,occupied,destinations,load_policy,validate_policy


class ResidentGoalTests(unittest.TestCase):
    setUp=fixtures.ResidentControlTests.setUp
    tearDown=fixtures.ResidentControlTests.tearDown
    sync=fixtures.ResidentControlTests.sync
    census=fixtures.ResidentControlTests.census
    initialize=fixtures.ResidentControlTests.initialize
    ready=fixtures.ResidentControlTests.ready

    def start(self):
        self.ready();self.obs['resident_control'].update(goal_destinations=True)
        self.obs['places']=[{'id':500,'name':'Public square','position':[1000,0,0],'available':True,'eligible_actors':[108186,108149]}]
        self.world.configure_resident_control('control',True,self.obs);self.sync()

    def claim(self):
        wave=self.world.claim_resident_goals('wave',self.obs)['wave'];self.sync();return wave

    def results(self,wave):
        return [{'actor':m['actor'],'result':{'model':'test-jev','decision':{'action_id':next((o['id'] for o in m['context']['options'] if o['id'].startswith('visit_') and o['id'][6:].isdigit()),'quiet'),'reason':'Test choice','emotion':'calm'},'usage':{'cost':.001}}} for m in wave['members']]

    def test_all_loaded_people_get_independent_goals_without_asset_or_need_changes(self):
        self.start();before=copy.deepcopy(self.world.active);obs=copy.deepcopy(self.obs)
        wave=self.claim();self.assertEqual(len(wave['members']),3)
        self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs);self.sync()
        people=self.world.active['people'];assignments=self.world.active['town']['resident_control']['assignments']
        self.assertEqual(people['108186']['standing_goal']['phase'],'travelling')
        self.assertEqual(assignments['108186']['target'],500)
        self.assertEqual(people['99']['standing_goal']['phase'],'quiet')
        for key in before['people']:self.assertEqual(people[key]['needs'],before['people'][key]['needs'])
        self.assertEqual(self.obs['residents'],obs['residents']);self.assertEqual(self.world.active['trades'],before['trades'])
        self.assertTrue(self.world.claim_resident_goals('wave',self.obs)['duplicate'])
        self.assertTrue(self.world.claim_resident_goals('later',self.obs)['empty'])

    def test_pending_claim_cannot_repeat_and_older_save_discards_new_goals(self):
        self.start();old=copy.deepcopy(self.obs);wave=self.claim()
        with self.assertRaisesRegex(ValueError,'already claimed'):self.world.claim_resident_goals('other',self.obs)
        self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs);self.sync()
        with self.assertRaisesRegex(ValueError,'resolved'):self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs)
        self.world.observe({**old,'session':'old-save'})
        self.assertNotIn('standing_goal',self.world.active['people']['108186'])

    def test_missing_destination_rejects_only_affected_people(self):
        self.start();wave=self.claim();self.obs['places'][0]['available']=False
        result=self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs);self.sync()
        self.assertEqual(sum(r['accepted'] for r in result['results']),1)
        self.assertEqual(self.world.active['town']['resident_control']['assignments']['108186']['mode'],'await_decision')

    def test_nearby_arrival_requires_goal_identity_ownership_and_distance(self):
        self.start();wave=self.claim();self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs);self.sync()
        goal=self.world.active['people']['108186']['standing_goal'];slot=self.world.active['town']['resident_control']['assignments']['108186']['slot']
        next(r for r in self.obs['residents'] if r['id']==108186).update(x=900,activity={'package_id':9000})
        a={'actor':108186,'target':500,'goal_id':goal['id'],'phase':'arrived','ownedPackage':True,'distance':100,'slot':slot,'expectedPackage':9000}
        for changes in ({'goal_id':'wrong'},{'ownedPackage':False},{'distance':400},{'target':999}):
            self.obs['resident_control']['activities']=[{**a,**changes}];self.world.observe(self.obs);self.assertIsNone(self.world.transition)
        self.obs['resident_control']['activities']=[a];self.world.observe(self.obs);self.sync()
        person=self.world.active['people']['108186'];self.assertEqual(person['standing_goal']['phase'],'arrived')
        self.assertEqual(person['memories'][-1]['kind'],'standing_goal_arrival')
        self.assertEqual(person['memories'][-1]['provenance'],'test_fixture')
        self.assertEqual(person['memories'][-1]['action_family'],'visit_public_place')
        self.assertGreaterEqual(person['memories'][-1]['elapsed_seconds'],0)
        self.assertEqual(person['memories'][-1]['travel_game_minutes'],0)
        self.assertEqual(self.world.active['town']['resident_control']['assignments']['108186']['mode'],'await_decision')

    def test_native_failure_is_held_without_fake_arrival(self):
        self.start();wave=self.claim();self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs);self.sync()
        goal=self.world.active['people']['108186']['standing_goal']
        self.obs['resident_control']['activities']=[{'actor':108186,'target':500,'goal_id':goal['id'],'phase':'failed','error':'No path'}]
        self.world.observe(self.obs);self.sync();self.assertEqual(self.world.active['people']['108186']['standing_goal']['phase'],'held')

    def test_model_only_receives_own_state_and_public_destinations(self):
        self.start();self.world.active['people']['108149']['memories'].append({'secret':'private memory'})
        context=goal_context(self.world.active,self.obs,108186)
        self.assertNotIn('private memory',str(context));self.assertNotIn('people',context)
        self.assertTrue(all(o['id']=='quiet' or o['id'].startswith(('visit_','review_')) for o in context['options']))

    def test_context_tracks_time_weather_and_only_own_native_activity(self):
        self.start();actor=next(r for r in self.obs['residents'] if r['id']==108186)
        actor.update(space={'cell':1,'interior':False,'world':2},outdoors=True,
            activity={'scene_id':0,'package_id':700,'in_combat':False,'sleep_state':0})
        other=next(r for r in self.obs['residents'] if r['id']==108149)
        other['activity']={'private_note':'hidden other activity'}
        self.world.active['people']['108149']['memories'].append({'secret':'private other memory'})
        self.obs.update(gameDays=3+1/24,weather={'id':20,'classification':2,'label':'rainy'})
        first=goal_context(self.world.active,self.obs,108186)
        self.assertEqual(first['clock']['period'],'night');self.assertEqual(first['clock']['hour'],1)
        self.assertEqual(first['weather']['observation']['label'],'rainy')
        self.assertEqual(first['own_observed_state']['position'],[actor[k] for k in ('x','y','z')])
        self.assertEqual(first['own_observed_state']['space'],actor['space'])
        self.assertEqual(first['own_observed_state']['activity']['package_id'],700)
        self.obs.update(gameDays=3+8/24,weather={'id':21,'classification':0,'label':'pleasant'})
        actor['activity']['package_id']=701
        second=goal_context(self.world.active,self.obs,108186)
        self.assertEqual(second['clock']['period'],'morning');self.assertEqual(second['clock']['game_days'],self.obs['gameDays'])
        self.assertEqual(second['weather']['observation']['label'],'pleasant')
        self.assertEqual(second['own_observed_state']['activity']['package_id'],701)
        self.assertEqual(first['own_observed_state']['activity']['package_id'],700)
        self.assertNotIn('hidden other activity',str(second));self.assertNotIn('private other memory',str(second))
        self.obs.pop('weather');self.obs['gameDays']=None;actor['x']=float('nan')
        unknown=goal_context(self.world.active,self.obs,108186)
        self.assertFalse(unknown['clock']['known']);self.assertIsNone(unknown['weather']['observation'])
        self.assertIsNone(unknown['own_observed_state']['position'])

    def test_foreground_participants_are_excluded_and_stale_claim_is_held(self):
        self.start();self.world.active['plans']=[{'id':'busy','phase':'choose','actor':108186,'target':108149}]
        wave=self.claim();self.assertEqual([m['actor'] for m in wave['members']],[99])
        self.world.observe({**self.obs,'session':'loaded-during-inference'});self.obs['session']='loaded-during-inference';self.sync()
        self.assertEqual(self.world.active['town']['goal_waves'][-1]['phase'],'held')

    def test_active_conversation_excludes_initiator_and_partner_not_just_speakers(self):
        self.start();self.world.active['conversation']={'id':'chat','phase':'choose_partner','initiator':108186,'partner':108149,'speakers':[]}
        self.assertEqual([m['actor'] for m in self.claim()['members']],[99])

    def test_claim_uses_immutable_policy_despite_later_configuration_change(self):
        self.start();wave=self.claim();changed=load_policy();changed.update(version='later-policy',minimum_distance=2000,maximum_distance=3000,review_game_minutes=100)
        with patch('resident_goals.load_policy',return_value=changed):
            self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs);self.sync()
        goal=self.world.active['people']['108186']['standing_goal']
        self.assertEqual(goal['policy'],wave['policy']);self.assertEqual(goal['policy_id'],wave['policy_id'])
        self.assertAlmostEqual(goal['next_review_day']-goal['decided_day'],wave['policy']['review_game_minutes']/1440)
        receipt=next(r for r in self.world.active['town']['goal_waves'][-1]['results'] if r['actor']==108186)
        context=next(m['context'] for m in wave['members'] if m['actor']==108186)
        self.assertEqual(receipt['option_count'],len(context['options']))
        self.assertIn('quiet',receipt['option_families']);self.assertIn('visit_public_place',receipt['option_families'])

    def test_invalid_configuration_is_rejected_before_claim_mutation(self):
        policy=load_policy()
        for change in ({'review_game_minutes':0},{'maximum_distance':True},{'arrival_distance':201},{'minimum_distance':float('nan')},{'version':''},{'claim_timeout_seconds':0}):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_policy({**policy,**change})

    def test_dynamic_destinations_reject_cross_space_and_deduplicate_reference(self):
        self.start();actor=next(r for r in self.obs['residents'] if r['id']==108186)
        actor['space']={'cell':1,'interior':True,'world':None}
        site=self.obs['places'][0];site['space']={'cell':2,'interior':True,'world':None}
        self.assertEqual(destinations(self.obs,108186),[])
        site['space']=dict(actor['space']);self.obs['rest']={'sites':[{**site,'loaded':True}]}
        self.assertEqual(len(destinations(self.obs,108186)),1)
        self.obs['places']=[];self.obs['rest']['sites'][0].update(id=501,name='Newly observed bench')
        self.assertEqual([s['id'] for s in destinations(self.obs,108186)],[501])

    def test_malformed_result_does_not_discard_other_residents_decisions(self):
        self.start();wave=self.claim();results=self.results(wave);results[0]['result']=['not an object']
        receipt=self.world.finish_resident_goals('wave',wave['claim_id'],results,self.obs);self.sync()
        self.assertEqual(receipt['results'][0]['failure'],'malformed_result');self.assertEqual(sum(r['accepted'] for r in receipt['results']),2)

    def test_departure_and_changed_base_identity_cannot_receive_old_decision(self):
        self.start()
        # Claim against the census-bound identities, then change one observation.
        wave=self.claim();self.obs['residents']=[r for r in self.obs['residents'] if r['id']!=108186]
        next(r for r in self.obs['residents'] if r['id']==108149)['baseId']=9999
        receipt=self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs);self.sync()
        failures={r['actor']:r['failure'] for r in receipt['results']}
        # Central durable identity admission excludes the replacement before
        # claim-local identity comparison can authorize any new decision.
        self.assertEqual(failures[108186],'resident_unavailable');self.assertEqual(failures[108149],'resident_unavailable')
        self.assertEqual(self.world.active['people']['108149']['standing_goal']['phase'],'held')
        self.assertNotIn('action_id',self.world.active['people']['108149']['standing_goal'])
        self.assertIsNone(failures[99])

    def test_expired_claim_settles_without_game_clock_progress_and_cannot_replay(self):
        self.start();wave=self.claim();day=self.obs['gameDays']
        with patch('resident_goals.time.time',return_value=wave['deadline_at']+1):
            with self.assertRaisesRegex(ValueError,'expired'):self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs)
            self.world.observe(self.obs);self.sync()
        self.assertEqual(self.obs['gameDays'],day);self.assertEqual(self.world.active['town']['goal_waves'][-1]['phase'],'held')
        self.assertTrue(self.world.claim_resident_goals('wave',self.obs)['duplicate'])
        self.assertIn('wave',self.world.active['town']['goal_claim_ids'])
        self.world.active['town']['goal_waves']=[]
        self.assertTrue(self.world.claim_resident_goals('wave',self.obs)['retired'])
        self.assertEqual(len(self.world.claim_resident_goals('new-wave',self.obs)['wave']['members']),3)

    def test_legacy_unbounded_claim_is_held_without_inference_replay(self):
        self.start();self.claim();del self.world.active['town']['goal_waves'][-1]['deadline_at']
        self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.active['town']['goal_waves'][-1]['phase'],'held')
        self.assertIn('Legacy claim',self.world.active['town']['goal_waves'][-1]['error'])

    def arrival_observation(self,actor):
        goal=self.world.active['people'][str(actor)]['standing_goal']
        slot=self.world.active['town']['resident_control']['assignments'][str(actor)]['slot']
        next(r for r in self.obs['residents'] if r['id']==actor).update(x=900,y=0,z=0,activity={'package_id':9000+slot})
        self.obs['resident_control']['activities']=[{'actor':actor,'target':500,'goal_id':goal['id'],
            'phase':'arrived','ownedPackage':True,'distance':100,'slot':slot,'expectedPackage':9000+slot}]

    def test_conversation_meeting_ack_precedes_disjoint_goal_arrival_checkpoint(self):
        self.start();self.obs['routing']={'adapter':'papyrus-mailbox-v1','available':True}
        next(r for r in self.obs['residents'] if r['id']==99).update(x=200,y=0,z=0)
        wave=self.claim();self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs);self.sync()
        self.world.start_conversation('priority-chat',self.obs,max_turns=2);self.sync()
        self.assertEqual(self.world.conversation_status()['initiator'],99)
        claim=self.world.claim_conversation('priority-chat',self.obs)['claim'];self.sync()
        self.world.finish_conversation_inference('priority-chat',claim['id'],{'model':'test-jev','decision':{
            'action_id':'approach_108149','reason':'Regression fixture choice','emotion':'calm'}},self.obs);self.sync()
        self.assertEqual(self.world.conversation_status()['phase'],'meeting')
        self.arrival_observation(108186)
        meeting_ack={'id':'meet-priority-chat','status':'applied','movement':{'id':'meet-priority-chat','adapter':'papyrus-mailbox',
            'aliasesConfirmed':True,'actor':99,'target':108149,'ownedPackage':True}}
        self.obs['ack']=copy.deepcopy(meeting_ack);self.world.observe(self.obs)
        prepared=self.world._read(self.world.transition['next'])
        self.assertEqual(prepared['conversation']['phase'],'respond')
        self.assertEqual(prepared['conversation']['meeting_evidence'],meeting_ack)
        self.assertEqual(prepared['people']['108186']['standing_goal']['phase'],'travelling')
        # The checkpoint replaces the one-shot native ack; the background arrival
        # must still settle from its retained physical observation afterwards.
        self.sync()
        self.assertEqual(self.world.conversation_status()['phase'],'respond')
        self.assertEqual(self.world.active['people']['108186']['standing_goal']['phase'],'arrived')
        self.assertEqual(sum(m['kind']=='standing_goal_arrival' for m in self.world.active['people']['108186']['memories']),1)

    def test_resident_plan_travel_ack_precedes_disjoint_goal_arrival_checkpoint(self):
        self.start();self.obs['routing']={'adapter':'papyrus-mailbox-v1','available':True}
        next(r for r in self.obs['residents'] if r['id']==99).update(x=0,y=0,z=0)
        self.obs['places'][0]['eligible_actors'].append(99)
        wave=self.claim();self.world.finish_resident_goals('wave',wave['claim_id'],self.results(wave),self.obs);self.sync()
        self.world.begin_plan('priority-plan',self.obs,108186);self.sync()
        claim=self.world.claim_plan_decision('priority-plan',self.obs)['claim'];self.sync()
        self.world.finish_plan_decision('priority-plan',claim['id'],{'model':'test-jev','decision':{
            'action_id':'visit_person_108149','reason':'Regression fixture choice','emotion':'calm'}},self.obs);self.sync()
        plan=self.world.agency_plan();self.assertEqual(plan['phase'],'travelling')
        self.arrival_observation(99)
        next(r for r in self.obs['residents'] if r['id']==108186)['x']=200
        travel_ack={'id':plan['travel_id'],'status':'applied','movement':{'actor':108186,'target':108149,
            'hasOwnedPackage':True,'aliasesConfirmed':True,'adapter':'papyrus-mailbox'}}
        self.obs['ack']=copy.deepcopy(travel_ack);self.world.observe(self.obs)
        prepared=self.world._read(self.world.transition['next'])
        self.assertEqual(prepared['plans'][-1]['phase'],'complete')
        self.assertEqual(prepared['plans'][-1]['travel'],travel_ack)
        self.assertEqual(prepared['people']['99']['standing_goal']['phase'],'travelling')
        self.sync()
        self.assertEqual(self.world.agency_plan()['outcome'],'visited_only')
        self.assertEqual(self.world.active['people']['99']['standing_goal']['phase'],'arrived')
