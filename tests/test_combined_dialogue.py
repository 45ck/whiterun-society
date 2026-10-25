"""A reply/closing/quiet choice replaces the extra continuation inference."""
import copy
import unittest
import test_social as fixtures
from test_conversation import AUDIO
from dialogue_policy import recorded_model_results
from metrics import simulation_metrics


class CombinedDialogueTests(unittest.TestCase):
    setUp=fixtures.SocialTests.setUp
    tearDown=fixtures.SocialTests.tearDown
    sync=fixtures.SocialTests.sync
    census=fixtures.SocialTests.census
    review=fixtures.SocialTests.review
    decide=fixtures.SocialTests.decide
    meet=fixtures.SocialTests.meet
    release=fixtures.SocialTests.release

    def begin(self,limit=6):
        self.review();self.event=next(e for e in self.world.active['town']['daily']['queue'] if e['actor']==99)
        self.world.start_conversation(self.event['id'],self.obs,99,max_turns=limit,reply_policy='combined_choice');self.sync()
        self.meet();self.decide('chat')

    def propose(self,bad_closing=False):
        claim=self.world.claim_conversation(self.event['id'],self.obs)['claim'];self.sync()
        roles=claim['context']['candidate_roles']
        candidates=[{'id':key,'intention':role,'line':('Take care.' if key=='option_1' else 'Goodbye.') if role=='close_politely' else
                     'How are you?' if key=='option_1' else 'Hello there.','tone':'calm'} for key,role in roles.items()]
        if bad_closing:candidates[1]['line']='Where are you going?'
        self.world.finish_conversation_inference(self.event['id'],claim['id'],{'model':'test-language','usage':{'cost':.001},
            'proposal':{'candidates':candidates}},self.obs);self.sync()
        return claim

    def deliver(self,choice='option_1'):
        self.decide(choice)
        self.world.prepare_speech(self.event['id'],AUDIO,self.obs);self.sync()
        command=self.world.pending(self.obs['session'])
        self.obs['speech']={'id':command['id'],'status':'ended','playedSeconds':3,'nearbyThroughout':True}
        self.world.observe(self.obs);self.sync()

    def finish(self):
        self.release();self.decide('neutral');self.decide('neutral')

    def test_reply_choice_then_polite_ending_needs_no_continuation_inference(self):
        self.begin();first=self.propose();self.assertEqual(set(first['context']['candidate_roles'].values()),{'opening'})
        self.deliver();self.assertEqual(self.world.conversation_status()['phase'],'propose')
        reply=self.propose();self.assertEqual(reply['context']['candidate_roles'],{'option_1':'reply','option_2':'close_politely'})
        context=self.decide('option_2')
        self.assertEqual([o['id'] for o in context['options']],['option_1','option_2','leave_quietly'])
        self.assertEqual(len(context['heard_in_this_conversation']),1)
        self.assertNotIn('other_inventory',context)
        self.world.prepare_speech(self.event['id'],AUDIO,self.obs);self.sync()
        command=self.world.pending(self.obs['session']);self.obs['speech']={'id':command['id'],'status':'ended','playedSeconds':3,'nearbyThroughout':True}
        self.world.observe(self.obs);self.sync();self.finish()
        c=self.world.conversation_status();self.assertEqual(c['phase'],'complete')
        self.assertEqual(c['end_reason'],'polite_closure');self.assertEqual(len(c['turns']),2)
        self.assertEqual(len(recorded_model_results(c)),8) # four social decisions + two proposals + two choices
        self.assertNotIn('continue_dialogue',[r['stage'] for r in c['social_decisions']])

    def test_silent_departure_retains_billed_proposal_but_no_audio_or_heard_memory(self):
        self.begin();self.propose();self.deliver();self.propose()
        before=copy.deepcopy(self.world.active['people']);self.decide('leave_quietly')
        c=self.world.conversation_status()
        self.assertEqual(c['phase'],'releasing');self.assertNotIn('current',c)
        self.assertEqual(len(c['turns']),1);self.assertEqual(len(c['unspoken_turns']),1)
        self.assertFalse(c['unspoken_turns'][0]['delivered'])
        self.assertNotIn('audio',c['unspoken_turns'][0]);self.assertEqual(before,self.world.active['people'])
        with self.assertRaisesRegex(ValueError,'not awaiting synthesis'):self.world.prepare_speech(c['id'],AUDIO,self.obs)
        self.finish();c=self.world.conversation_status();self.assertEqual(len(recorded_model_results(c)),8)
        self.assertEqual(c['end_reason'],'left_quietly')
        # Use non-fixture provenance only to exercise metrics accounting.
        for result in recorded_model_results(c):result['model']='qualified-metrics-sample'
        metrics=simulation_metrics({'conversation':c})
        self.assertEqual(metrics['dialogue_policies']['combined_choice']['unspoken_proposals'],1)
        self.assertEqual(metrics['dialogue_policies']['combined_choice']['recorded_model_results'],8)
        self.assertEqual(metrics['dialogue_policies']['combined_choice']['delivered_turns'],1)

    def test_closing_slot_cannot_ask_a_new_question_even_when_reply_slot_may(self):
        self.begin();self.propose();self.deliver()
        with self.assertRaisesRegex(ValueError,'new question'):self.propose(bad_closing=True)
        self.assertEqual(self.world.conversation_status()['phase'],'thinking_propose')

    def test_hard_turn_limit_has_only_closing_lines_and_ten_decision_calls_maximum(self):
        self.begin()
        for i in range(6):
            claim=self.propose()
            if i==5:self.assertEqual(set(claim['context']['candidate_roles'].values()),{'close_politely'})
            self.deliver()
        self.finish();c=self.world.conversation_status()
        self.assertEqual(len(c['turns']),6);self.assertEqual(c['phase'],'complete')
        self.assertEqual(c['max_jev_calls'],10);self.assertEqual(len(recorded_model_results(c)),16)

    def test_policy_and_claim_survive_checkpoint_load_without_reinference(self):
        self.begin();self.propose();self.deliver()
        claim=self.world.claim_conversation(self.event['id'],self.obs)['claim'];self.sync()
        checkpoint=self.world.marker
        self.obs.update(session='different-session',checkpoint=checkpoint);self.world.observe(self.obs);self.sync()
        c=self.world.conversation_status();self.assertEqual(c['reply_policy'],'combined_choice')
        with self.assertRaises(ValueError):self.world.finish_conversation_inference(c['id'],claim['id'],{'model':'test','proposal':{}},self.obs)

    def test_event_id_cannot_be_reused_to_change_reply_protocol(self):
        self.begin()
        with self.assertRaisesRegex(ValueError,'another reply policy'):
            self.world.start_conversation(self.event['id'],self.obs,99,max_turns=6,reply_policy='separate_choice')
        with self.assertRaisesRegex(ValueError,'Unknown reply policy'):
            self.world.start_conversation('bad-policy',self.obs,reply_policy='guess')

    def test_rejected_billed_proposal_is_saved_once_without_speech_or_memory(self):
        self.begin();claim=self.world.claim_conversation(self.event['id'],self.obs)['claim'];self.sync()
        people=copy.deepcopy(self.world.active['people'])
        failure={'claim_id':claim['id'],'receipt':{'model':'cloud-example','elapsed_seconds':1.2,
            'usage':{'cost':.002,'total_tokens':100,'private':'discard'},'finish_reason':'stop',
            'validation_failure':'candidate_id','raw_text':'never persist this'}}
        self.world.hold_conversation(self.event['id'],'Invalid language candidates',self.obs,inference_failure=failure);self.sync()
        c=self.world.conversation_status();self.assertEqual(c['phase'],'releasing')
        self.assertIsNone(c['claim']);self.assertEqual(c['turns'],[]);self.assertNotIn('current',c)
        self.assertEqual(people,self.world.active['people'])
        self.assertEqual(len(recorded_model_results(c)),3)
        receipt=c['rejected_inferences'][0]['receipt']
        self.assertEqual(receipt['usage'],{'cost':.002,'total_tokens':100})
        self.assertNotIn('raw_text',receipt)
        self.assertTrue(self.world.hold_conversation(self.event['id'],'duplicate',self.obs,inference_failure=failure)['duplicate'])
        self.release();self.assertEqual(self.world.conversation_status()['phase'],'held')
        self.assertTrue(self.world.hold_conversation(self.event['id'],'duplicate',self.obs,inference_failure=failure)['duplicate'])
        c=self.world.conversation_status()
        for result in recorded_model_results(c):result['model']='cloud-example'
        metrics=simulation_metrics({'conversation':c})
        policy=metrics['dialogue_policies']['combined_choice']
        self.assertEqual(policy['rejected_inferences'],1)
        self.assertEqual(policy['language_validation_failures'],{'candidate_id':1})
        self.assertEqual(policy['recorded_model_results'],3)
        failure['receipt']['usage']['cost']=100
        with self.assertRaisesRegex(ValueError,'receipt changed'):
            self.world.hold_conversation(self.event['id'],'changed',self.obs,inference_failure=failure)

    def test_rejected_receipt_cannot_attach_to_another_claim_or_session(self):
        self.begin();claim=self.world.claim_conversation(self.event['id'],self.obs)['claim'];self.sync()
        failure={'claim_id':'wrong','receipt':{'model':'cloud-example','elapsed_seconds':1,'usage':{'cost':.001},
            'finish_reason':'stop','validation_failure':'invalid_json'}}
        before=copy.deepcopy(self.world.active)
        with self.assertRaisesRegex(ValueError,'Stale rejected inference'):
            self.world.hold_conversation(self.event['id'],'invalid',self.obs,inference_failure=failure)
        self.assertEqual(before,self.world.active)
        failure['claim_id']=claim['id'];self.world.active['conversation']['claim']['session']='old-session'
        with self.assertRaisesRegex(ValueError,'Stale rejected inference'):
            self.world.hold_conversation(self.event['id'],'invalid',self.obs,inference_failure=failure)
        self.assertNotIn('rejected_inferences',self.world.active['conversation'])


if __name__=='__main__':unittest.main()
