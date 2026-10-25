import copy
import unittest
import test_food
from conversation import validate_candidates

CANDIDATES=[{'id':'option_1','intention':'Ask for bread','line':'Could you spare a loaf for me?','tone':'hopeful'},
            {'id':'option_2','intention':'Express frustration','line':'I worked hard and still have no bread.','tone':'frustrated'}]
AUDIO={'file':'a'*64+'.wav','sha256':'a'*64,'seconds':3.,'voice':'bf_emma','engine':'kokoro-onnx-0.6.1'}

def candidates_for(context):
    if context['event']['dialogue_stage'] in ('closing','refusal'):
        return [{'id':'option_1','intention':'Close politely','line':'Thanks. Take care.','tone':'calm'},
                {'id':'option_2','intention':'Say goodbye','line':'Goodbye.','tone':'calm'}]
    return copy.deepcopy(CANDIDATES)


class ConversationTests(unittest.TestCase):
    setUp=test_food.FoodTests.setUp
    tearDown=test_food.FoodTests.tearDown
    sync=test_food.FoodTests.sync

    def start(self):
        self.world.start_conversation('chat',self.obs);self.sync()
        self.obs['ack']={'id':'meet-chat','status':'applied','movement':{'id':'meet-chat','adapter':'papyrus-mailbox',
            'aliasesConfirmed':True,'actor':108186,'target':108149,'ownedPackage':True}}
        self.world.observe(self.obs);self.sync()

    def release(self):
        self.obs['ack']={'id':'release-chat-chat','status':'applied','released':True}
        self.world.observe(self.obs);self.sync()
    def select(self):
        claim=self.world.claim_conversation('chat',self.obs)['claim'];self.sync()
        self.world.finish_conversation_inference('chat',claim['id'],{'model':'test-llm','proposal':{'candidates':candidates_for(claim['context'])}},self.obs);self.sync()
        claim=self.world.claim_conversation('chat',self.obs)['claim'];self.sync()
        self.world.finish_conversation_inference('chat',claim['id'],{'model':'test-jev','decision':{'action_id':'option_1','reason':'test','emotion':'hopeful'}},self.obs);self.sync()
        self.world.prepare_speech('chat',AUDIO,self.obs);self.sync()
        return self.world.pending(self.obs['session'])
    def delivered(self,c):
        self.obs['speech']={'id':c['id'],'status':'ended','playedSeconds':3.,'nearbyThroughout':True}
        self.world.observe(self.obs);self.sync()
        if self.world.conversation_status()['phase']=='releasing':self.release()

    def test_layers_select_line_then_memory_only_after_delivery(self):
        self.start();c=self.select();before=copy.deepcopy(self.obs['residents'])
        self.assertEqual(self.world.status()['people']['108149']['memories'],[])
        self.delivered(c)
        memory=self.world.status()['people']['108149']['memories'][-1]
        self.assertEqual(memory['kind'],'heard_speech');self.assertEqual(memory['epistemic_status'],'claim, not verified fact')
        self.assertEqual(before,self.obs['residents'])
        context=self.world.claim_conversation('chat',self.obs)['claim']['context']
        self.assertEqual(context['heard_in_this_conversation'][0]['line'],CANDIDATES[0]['line'])
        self.assertNotIn('other_inventory',context)

    def test_duplicate_inference_and_stale_claim_cannot_be_applied(self):
        self.start();claim=self.world.claim_conversation('chat',self.obs)['claim'];self.sync()
        with self.assertRaisesRegex(ValueError,'claim already'):self.world.claim_conversation('chat',self.obs)
        with self.assertRaisesRegex(ValueError,'Stale'):self.world.finish_conversation_inference('chat','wrong',{},self.obs)

    def test_loading_same_claim_checkpoint_rejects_previous_session_result(self):
        self.start();claim=self.world.claim_conversation('chat',self.obs)['claim'];self.sync()
        self.obs['session']='loaded-claim-save';self.world.observe(self.obs)
        with self.assertRaisesRegex(ValueError,'Stale'):
            self.world.finish_conversation_inference('chat',claim['id'],{'model':'test','proposal':{'candidates':CANDIDATES}},self.obs)

    def test_save_load_during_speech_holds_without_replaying(self):
        self.start();self.select();self.obs['session']='new-load';self.world.observe(self.obs);self.sync()
        self.release()
        self.assertEqual(self.world.conversation_status()['phase'],'held')
        self.assertIsNone(self.world.pending('new-load'))
        self.assertEqual(self.world.status()['people']['108149']['memories'],[])

    def test_playback_failure_does_not_create_false_hearing(self):
        self.start();c=self.select();self.obs['speech']={'id':c['id'],'status':'failed','error':'blocked'}
        self.world.observe(self.obs);self.sync()
        self.release()
        self.assertEqual(self.world.conversation_status()['phase'],'held')
        self.assertEqual(self.world.status()['people']['108149']['memories'],[])

    def test_full_exchange_is_finite_and_duplicate_does_not_repeat(self):
        self.start()
        for _ in range(2):self.delivered(self.select())
        self.assertEqual(self.world.conversation_status()['phase'],'complete')
        self.assertTrue(self.world.start_conversation('chat',self.obs)['duplicate'])
        self.assertEqual(len(self.world.status()['people']['108149']['memories']),2)
        before=copy.deepcopy(self.world.active);self.world.observe(self.obs);self.assertEqual(before,self.world.active)

    def test_economic_plan_is_not_started_during_conversation(self):
        self.start()
        with self.assertRaisesRegex(ValueError,'conversation'):self.world.begin_plan('meal',self.obs, 108186)
        with self.assertRaisesRegex(ValueError,'conversation'):self.world.plan_trade('trade',self.obs,108186,108149)

    def reject_playback(self,extra):
        self.start();c=self.select();self.obs['speech']={'id':c['id'],'status':'ended',**extra}
        self.world.observe(self.obs);self.sync();self.release();self.assertEqual(self.world.conversation_status()['phase'],'held')
        self.assertEqual(self.world.status()['people']['108149']['memories'],[])

    def test_forged_early_completion_is_not_heard(self):
        self.reject_playback({'playedSeconds':.1,'nearbyThroughout':True})

    def test_departed_listener_is_not_heard(self):
        self.reject_playback({'playedSeconds':3.,'nearbyThroughout':False})

    def test_language_context_explains_economic_roles_without_private_motives(self):
        self.world.active['people']['108186']['memories']=[{'kind':'trade_offer_declined','role':'buyer','other':108149,'gold':5},
            {'kind':'paid_work','role':'worker','other':108149,'gold':2}]
        self.start();c=self.world.claim_conversation('chat',self.obs)['claim']['context']
        self.assertIn('BUY one loaf FROM',c['known_facts_in_first_person'][0])
        self.assertIn('bread belonged to them, not me',c['known_facts_in_first_person'][1])
        self.assertIsNone(c['own_food_policy']);self.assertNotIn('family',str(c['known_facts_in_first_person']))

    def test_text_contract_rejects_commands_and_unknown_fields(self):
        invalid=copy.deepcopy(CANDIDATES);invalid[0]['command']='addItem'
        with self.assertRaises(ValueError):validate_candidates({'candidates':invalid})


if __name__=='__main__':unittest.main()
