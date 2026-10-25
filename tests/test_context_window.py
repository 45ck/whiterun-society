import copy
import io
import json
import unittest
from unittest.mock import patch
from context_window import bounded_social_context,encoded_size,load_policy,memory_view
from decision_provider import infer_jev


def crowded_context(count):
    background={'kind':'authored_shared_town_background','epistemic_status':'scenario initial acquaintance, not witnessed interaction or canonical lore','event_id':'initial-background'}
    candidates=[{'id':i+100,'name':'Known resident '+str(i),'name_known':True,'distance':i*10,
        'identity_source':copy.deepcopy(background),'source':'native nearby proximity; vision is not qualified',
        'my_relationship':{'affinity':0,'familiarity':.35,'heard_turns':7,'background':copy.deepcopy(background),
            'appraisals':[{'choice':'neutral','basis':'completed nearby audio playback; subjective authored response, not verified truth','event_id':'earlier-'+str(j)} for j in range(7)] if i==0 else []}}
        for i in range(count)]
    memories=[{'kind':'standing_goal_arrival','place':i,'source':'Native owned destination receipt; no rest, production, trade or conversation implied',
        'event_id':'completed-journey-'+str(i),'day':1,'policy_version':'policy','model':'jev','provenance':'model_decision',
        'elapsed_seconds':40,'travel_game_minutes':12,'settled_at':1,'decided_day':.5,'settled_day':1,'timing_scope':'model and executor telemetry '*12}
        for i in range(8)]
    return {'actor_id':1,'profile':{'name':'Observer','big_five':{'extraversion':.5}},'scenario_state':{'needs':{'hunger':.5}},
        'clock':{'period':'morning'},'memories':memories,'trust':{},'own_commitments':[],
        'event':{'kind':'choose_partner','information':'Choose a partner or continue quietly; proximity is not consent.'},
        'nearby_candidates':candidates,'options':[{'id':'defer','effect':'Continue quietly; no approach or speech.'}]+[
            {'id':'approach_'+str(c['id']),'effect':'Approach '+c['name']+' and let them choose whether to chat.'} for c in candidates]}


class ContextWindowTests(unittest.TestCase):
    def test_populated_history_fits_without_discarding_eighteen_available_partners(self):
        original=crowded_context(18);before=copy.deepcopy(original)
        self.assertGreater(encoded_size(original),16000)
        result=bounded_social_context(original)
        self.assertLessEqual(encoded_size(result),12000);self.assertEqual(len(result['nearby_candidates']),18)
        self.assertEqual([o['id'] for o in result['options']],[o['id'] for o in original['options']])
        self.assertEqual(original,before)
        options=[o['id'] for o in result['options']]
        payload={'answers':{'action':{'choice':'defer','probabilities':{o:1 if o=='defer' else 0 for o in options}}}}
        with patch('decision_provider.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())) as call:
            infer_jev(result,{'model':'typesafe/jev-1.14','url':'https://openrouter.ai/api/alpha/decisions'},'placeholder')
        self.assertLessEqual(len(call.call_args.args[0].data),16000)

    def test_large_crowd_has_explicit_nearest_attention_window_with_matching_options(self):
        original=crowded_context(128);result=bounded_social_context(original)
        ids=[c['id'] for c in result['nearby_candidates']]
        self.assertLess(len(ids),128);self.assertGreater(len(ids),1);self.assertEqual(ids,list(range(100,100+len(ids))))
        self.assertEqual([o['id'] for o in result['options']],['defer']+['approach_'+str(i) for i in ids])
        self.assertEqual(result['context_window']['available_candidates'],128)
        self.assertEqual(result['context_window']['considered_candidates'],len(ids));self.assertLessEqual(encoded_size(result),12000)

    def test_recent_relevant_memory_survives_many_travel_receipts_with_epistemic_status(self):
        memories=[{'kind':'heard','speaker':99,'listener':1,'quote':'A merchant told me the mill is closed.','epistemic_status':'heard claim, not verified fact'}]
        memories+=crowded_context(1)['memories']*3
        result=memory_view(memories,{99},load_policy())
        self.assertIn(memories[0],result);self.assertLessEqual(len(result),8)
        self.assertTrue(all('model' not in m and 'timing_scope' not in m for m in result))
        self.assertTrue(any(m.get('source','').startswith('Native owned') for m in result))

    def test_shared_provenance_retains_exact_qualification_without_borrowing_identity(self):
        context=crowded_context(3);context['nearby_candidates'][0].update(name='an unfamiliar resident',name_known=False,identity_source=None)
        result=bounded_social_context(context);first=result['nearby_candidates'][0]
        self.assertFalse(first['name_known']);self.assertIsNone(first['identity_source']);self.assertEqual(first['name'],'an unfamiliar resident')
        second=result['nearby_candidates'][1];ref=second['identity_source']['source_ref']
        self.assertEqual(result['evidence_sources'][ref]['epistemic_status'],context['nearby_candidates'][1]['identity_source']['epistemic_status'])

    def test_irreducible_required_context_fails_before_claim_or_provider_call(self):
        context=crowded_context(1);context['profile']['priority']='x'*20000
        with self.assertRaisesRegex(ValueError,'Required social context'):bounded_social_context(context)

    def test_fresh_validation_checks_world_eligibility_not_shifted_attention(self):
        import test_social
        fixture=test_social.SocialTests('test_private_partner_state_is_not_exposed_to_social_context');fixture.setUp()
        try:
            fixture.begin();claim=fixture.world.claim_conversation(fixture.event['id'],fixture.obs)['claim'];fixture.sync()
            with patch('social.bounded_social_context',side_effect=AssertionError('Fresh eligibility must not apply a second attention window')):
                fixture.world.finish_conversation_inference(fixture.event['id'],claim['id'],{'model':'test','decision':{'action_id':'approach_108149','reason':'Choice','emotion':'calm'}},fixture.obs)
            fixture.sync();self.assertEqual(fixture.world.conversation_status()['phase'],'meeting')
        finally:fixture.tearDown()


if __name__=='__main__':unittest.main()
