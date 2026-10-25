"""Presentation cannot reissue a historical destination to a replacement actor."""
import copy
import unittest

from resident_control import resident_control_projection
import test_identity_inflight as fixtures


class ResidentControlIdentityTests(unittest.TestCase):
    setUp=fixtures.IdentityInflightTests.setUp
    tearDown=fixtures.IdentityInflightTests.tearDown
    sync=fixtures.IdentityInflightTests.sync
    goals=fixtures.IdentityInflightTests.goals

    def standing(self):
        self.goals()
        state=copy.deepcopy(self.world.active)
        state['town']['resident_control']['assignments']['17'].update(mode='go_to',target=500,goal_id='saved-trip')
        state['people']['17']['standing_goal']={'id':'saved-trip','phase':'travelling','target':500}
        self.world._write(state,'Authored saved journey fixture; no arrival or native release evidence');self.sync()

    def test_current_assignment_is_pinned_without_modifying_saved_policy(self):
        self.standing();before=copy.deepcopy(self.world.active);writes=self.world.db.total_changes
        projected=self.world.status()['town']['resident_control']
        self.assertEqual(projected['assignments']['17']['actor_base_id'],1017)
        self.assertEqual(projected['assignments']['17']['target'],500)
        self.assertEqual(projected['identity_holds'],{})
        self.assertEqual(self.world.active,before);self.assertEqual(self.world.db.total_changes,writes)
        projected['assignments']['17']['target']=999
        self.assertEqual(self.world.active['town']['resident_control']['assignments']['17']['target'],500)

    def test_changed_base_holds_original_slot_without_publishing_destination(self):
        self.standing();self.obs['residents'][0]['baseId']=2017
        self.world.observe(self.obs)
        before=copy.deepcopy(self.world.active);writes=self.world.db.total_changes
        control=self.world.status()['town']['resident_control']
        self.assertNotIn('17',control['assignments']);self.assertIn('19',control['assignments'])
        hold=control['identity_holds']['17']
        self.assertEqual(hold['assignment'],before['town']['resident_control']['assignments']['17'])
        self.assertEqual(hold['reason'],'base_identity_conflict');self.assertFalse(hold['release_verified'])
        self.assertEqual(self.world.active,before);self.assertEqual(self.world.db.total_changes,writes)
        self.assertEqual(self.world.active['people']['17']['standing_goal']['phase'],'travelling')

    def test_missing_observation_or_legacy_binding_cannot_reissue_saved_routes(self):
        self.standing();before=copy.deepcopy(self.world.active)
        empty=resident_control_projection(self.world.active)
        self.assertEqual(empty['assignments'],{})
        self.assertEqual(set(empty['identity_holds']),{'17','19'})
        state=copy.deepcopy(self.world.active);state['town']['residents']['17'].pop('identity_binding')
        projected=resident_control_projection(state,self.obs)
        self.assertNotIn('17',projected['assignments'])
        self.assertEqual(projected['identity_holds']['17']['reason'],'identity_unbound')
        observation=copy.deepcopy(self.obs);observation['residents'][0].pop('baseId')
        projected=resident_control_projection(self.world.active,observation)
        self.assertNotIn('17',projected['assignments'])
        self.assertEqual(projected['identity_holds']['17']['reason'],'base_identity_unavailable')
        self.assertEqual(self.world.active,before)

    def test_current_identity_does_not_override_an_existing_conflicting_assignment_pin(self):
        self.standing();state=copy.deepcopy(self.world.active)
        state['town']['resident_control']['assignments']['17']['actor_base_id']=2017
        before=copy.deepcopy(state);projected=resident_control_projection(state,self.obs)
        self.assertNotIn('17',projected['assignments'])
        self.assertEqual(projected['identity_holds']['17']['reason'],'saved_assignment_base_conflict')
        self.assertEqual(state,before)

    def test_observation_for_another_session_or_marker_is_not_used_by_status(self):
        self.standing()
        for field,value in (('session','unbound-session'),('checkpoint',999)):
            self.world.latest_observation={**copy.deepcopy(self.obs),field:value}
            control=self.world.status()['town']['resident_control']
            self.assertEqual(control['assignments'],{})
            self.assertEqual(set(control['identity_holds']),{'17','19'})

    def test_malformed_assignment_envelope_is_not_executable_or_repaired(self):
        self.standing();state=copy.deepcopy(self.world.active)
        state['town']['resident_control']['assignments']=[{'actor':17,'slot':0}]
        before=copy.deepcopy(state)
        projected=resident_control_projection(state,self.obs)
        self.assertEqual(projected['assignments'],{})
        self.assertEqual(projected['identity_projection_error'],'invalid_saved_assignments')
        self.assertEqual(state,before)
