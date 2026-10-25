import copy
import unittest
import test_economic_speech as fixtures
from economic_language import validate_wording, economic_context
from metrics import simulation_metrics


def proposal(first='Please. [[TERMS]]',second='[[TERMS]] Thank you.'):
    return {'candidates':[{'id':f'option_{i+1}','intention':'A courteous manner','line':line,'tone':'hopeful'}
                          for i,line in enumerate((first,second))]}


class EconomicLanguageTests(unittest.TestCase):
    setUp=fixtures.EconomicSpeechTests.setUp
    tearDown=fixtures.EconomicSpeechTests.tearDown
    sync=fixtures.EconomicSpeechTests.sync
    decide=fixtures.EconomicSpeechTests.decide
    arrive=fixtures.EconomicSpeechTests.arrive
    speak=fixtures.EconomicSpeechTests.speak

    def start(self):
        self.world.begin_plan('meal-1',self.obs, 108186,voiced_trade=True,natural_trade=True);self.sync()
        self.decide('seek_bread');self.arrive()
        self.obs['conversationAttendance']={'id':'economic-attend-meal-1','phase':'attending','participants':[
            {'actor':a,'ownedPackage':True,'loaded':True} for a in (108186,108149)]}
        self.obs['ack']={'id':'economic-attend-meal-1','status':'applied'};self.world.observe(self.obs);self.sync()

    def resolve(self,result):
        claim=self.world.claim_economic_wording('meal-1',self.obs)['claim'];self.sync()
        self.world.finish_economic_wording('meal-1',claim['id'],result,self.obs);self.sync()
        return claim

    def select(self):
        return self.resolve({'model':'test-jev','elapsed_seconds':.3,'usage':{'cost':.002},
            'decision':{'action_id':'option_2','reason':'A polite manner','emotion':'calm'}})

    def test_three_layers_change_wording_without_changing_terms_or_inventory(self):
        self.start();before=copy.deepcopy(self.obs['residents'])
        self.assertEqual(self.world.agency_plan()['phase'],'economic_propose')
        self.resolve({'proposal':proposal(),'model':'test-language','usage':{'cost':.001}})
        self.assertEqual(self.world.agency_plan()['phase'],'economic_select')
        self.select();turn=self.world.agency_plan()['economic_speech']
        self.assertEqual(turn['line'],turn['canonical_line']+' Thank you.')
        self.assertEqual(turn['act'],'offer');self.assertNotIn('[[TERMS]]',turn['line'])
        self.assertEqual(before,self.obs['residents']);self.assertEqual(self.world.active['trades'],[])
        command=self.speak();self.assertEqual(command['tone'],'hopeful')
        self.assertEqual(self.world.agency_plan()['phase'],'consent')
        memory=self.world.active['people']['108149']['memories'][-1]
        self.assertEqual(memory['quote'],turn['line'])
        metrics=simulation_metrics(self.world.active)['economy']['wording']
        self.assertEqual(metrics['delivered_generated_turns'],1)
        self.assertEqual(metrics['recorded_calls'],2);self.assertAlmostEqual(metrics['known_cost_usd'],.003)

    def test_claim_is_persisted_once_and_cannot_be_replayed(self):
        self.start();claim=self.world.claim_economic_wording('meal-1',self.obs)['claim']
        with self.assertRaises(ValueError):self.world.finish_economic_wording('meal-1',claim['id'],{'proposal':proposal()},self.obs)
        self.sync()
        with self.assertRaises(ValueError):self.world.claim_economic_wording('meal-1',self.obs)
        self.world.finish_economic_wording('meal-1',claim['id'],{'proposal':proposal()},self.obs);self.sync()
        before=copy.deepcopy(self.world.active)
        with self.assertRaises(ValueError):self.world.finish_economic_wording('meal-1',claim['id'],{'proposal':proposal()},self.obs)
        self.assertEqual(before,self.world.active)

    def test_rejected_numeric_or_contradictory_qualifiers_fall_back_without_extra_call(self):
        self.start();canonical=self.world.agency_plan()['economic_speech']['canonical_line']
        self.resolve({'proposal':proposal('Actually 9 gold. [[TERMS]]','[[TERMS]] I will pay instead.'),'model':'test-language','usage':{'cost':.01}})
        turn=self.world.agency_plan()['economic_speech']
        self.assertEqual(self.world.agency_plan()['phase'],'economic_synthesize')
        self.assertEqual(turn['line'],canonical);self.assertEqual(turn['wording_fallback'],'no_qualified_options')
        self.assertEqual(turn['wording_results'][0]['usage']['cost'],.01)
        self.assertNotIn('candidates',turn)

    def test_one_bad_candidate_does_not_discard_a_valid_reply(self):
        self.start();self.resolve({'proposal':proposal('Actually 9 gold. [[TERMS]]')})
        turn=self.world.agency_plan()['economic_speech']
        self.assertEqual(turn['direct_wording_ids'],['option_1'])
        self.assertEqual(turn['candidates'][0]['line'],'[[TERMS]]')
        self.select();self.assertEqual(self.world.agency_plan()['economic_speech']['selected']['id'],'option_2')
        self.assertNotIn('wording_fallback',self.world.agency_plan()['economic_speech'])

    def test_jev_can_select_direct_terms_without_counting_them_as_generated(self):
        self.start();self.resolve({'proposal':proposal('Please. [[TERMS]]','Actually 9 gold. [[TERMS]]')})
        self.select();self.speak()
        metrics=simulation_metrics(self.world.active)['economy']['wording']
        self.assertEqual(metrics['delivered_generated_turns'],0);self.assertEqual(metrics['fallback_turns'],1)
        self.assertEqual(metrics['rejected_candidates'],1)

    def test_provider_failure_uses_terms_and_records_only_finite_telemetry(self):
        self.start();self.resolve({'failure':'provider_error','model':'test-language',
            'raw_response':'private response','usage':{'cost':.002,'private':'secret'}})
        turn=self.world.agency_plan()['economic_speech']
        self.assertEqual(turn['wording_fallback'],'provider_error')
        self.assertNotIn('raw_response',turn['wording_results'][0])
        self.assertEqual(turn['wording_results'][0]['usage'],{'cost':.002})
        self.assertEqual(simulation_metrics(self.world.active)['economy']['wording']['fallback_turns'],1)

    def test_changed_session_or_departed_listener_cannot_accept_late_language(self):
        self.start();claim=self.world.claim_economic_wording('meal-1',self.obs)['claim'];self.sync()
        self.obs['conversationAttendance']['participants'][1]['ownedPackage']=False
        with self.assertRaisesRegex(ValueError,'left during inference'):
            self.world.finish_economic_wording('meal-1',claim['id'],{'proposal':proposal()},self.obs)
        self.obs['session']='loaded-save';self.world.observe(self.obs);self.sync()
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        with self.assertRaises(ValueError):self.world.finish_economic_wording('meal-1',claim['id'],{'proposal':proposal()},self.obs)

    def test_context_has_own_state_and_heard_words_not_listener_private_state(self):
        self.start();self.world.active['people']['108149']['memories'].append({'kind':'secret','quote':'PRIVATE_FACT'})
        claim=self.world.claim_economic_wording('meal-1',self.obs)['claim'];self.sync()
        self.assertNotIn('PRIVATE_FACT',str(claim['context']))
        self.assertFalse(claim['context']['listener']['name_known'])
        self.assertEqual(claim['context']['observed_inventory']['gold'],9)
        self.assertEqual(claim['context']['interaction']['delivered_turns'],0)

    def test_marker_time_weather_and_repeated_greetings_are_checked(self):
        self.start();context=economic_context(self.world.active,self.world.agency_plan(),self.obs)
        for line in ('A different deal.','[[TERMS]] [[TERMS]]','Good morning. [[TERMS]]',
                     'Fine weather. [[TERMS]]','[[TERMS]] I will pay instead.','I understand, [[TERMS]]'):
            with self.subTest(line=line),self.assertRaises(ValueError):validate_wording(proposal(line),context)
        context['interaction']['already_spoken']=True
        with self.assertRaises(ValueError):validate_wording(proposal('Hello. [[TERMS]]'),context)

    def test_incomplete_generated_audio_does_not_teach_terms_or_authorize_trade(self):
        self.start();self.resolve({'proposal':proposal()});self.select();self.speak(complete=False)
        self.assertEqual(self.world.agency_plan()['phase'],'held')
        self.assertEqual(self.world.active['trades'],[])
        self.assertFalse(any(m['kind']=='heard_speech' for p in self.world.active['people'].values() for m in p['memories']))


if __name__=='__main__':unittest.main()
