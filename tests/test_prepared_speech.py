import copy
import unittest
from unittest.mock import Mock
from tools.prepared_speech import PreparedSpeech


class PreparedSpeechTests(unittest.TestCase):
    def setUp(self):
        self.worker=Mock();self.worker.submit.side_effect=['voice-1','voice-2','voice-3','voice-4']
        self.worker.result.side_effect=lambda identity:{'audio':{'file':identity},'synthesis_seconds':1}
        self.plan={'id':'event-1','economic_turns':[], 'economic_speech':{
            'actor':10,'listener':20,'canonical_line':'An offer.',
            'candidates':[{'line':'Please. [[TERMS]]'},{'line':'[[TERMS]] Thank you.'}]}}
        self.prepared=PreparedSpeech()

    def test_only_exact_selected_clip_can_be_retrieved_and_prepare_is_once(self):
        self.assertEqual(self.prepared.prepare(self.worker,self.plan,'session','bf_alice'),2)
        self.assertEqual(self.prepared.prepare(self.worker,self.plan,'session','bf_alice'),0)
        self.worker.result.assert_not_called()
        self.plan['economic_speech']['line']='An offer. Thank you.'
        audio,timing=self.prepared.selected(self.worker,self.plan,'session','bf_alice')
        self.assertEqual(audio['audio']['file'],'voice-2')
        self.assertEqual(timing['mode'],'prepared_candidate')
        self.worker.result.assert_called_once_with('voice-2')

    def test_fallback_changed_voice_session_or_turn_cannot_use_old_clip(self):
        self.prepared.prepare(self.worker,self.plan,'session','bf_alice')
        self.plan['economic_speech']['line']='Please. An offer.'
        for field,value in [('actor',11),('listener',21),('canonical_line','Changed terms.'),('line','An offer.')]:
            plan=copy.deepcopy(self.plan);plan['economic_speech'][field]=value
            self.assertIsNone(self.prepared.selected(self.worker,plan,'session','bf_alice'))
        self.assertIsNone(self.prepared.selected(self.worker,self.plan,'new-session','bf_alice'))
        self.assertIsNone(self.prepared.selected(self.worker,self.plan,'session','bm_lewis'))
        plan=copy.deepcopy(self.plan);plan['economic_turns'].append({})
        self.assertIsNone(self.prepared.selected(self.worker,plan,'session','bf_alice'))
        plan=copy.deepcopy(self.plan);plan['id']='event-2'
        self.assertIsNone(self.prepared.selected(self.worker,plan,'session','bf_alice'))
        self.worker.result.assert_not_called()

    def test_identical_direct_candidates_share_one_synthesis(self):
        self.plan['economic_speech']['candidates']=[{'line':'[[TERMS]]'},{'line':'[[TERMS]]'}]
        self.assertEqual(self.prepared.prepare(self.worker,self.plan,'session','bf_alice'),1)
        self.worker.submit.assert_called_once_with('An offer.','bf_alice')
