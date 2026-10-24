import unittest
from dialogue_context import time_context,dialogue_frame,validate_situated_candidates
from conversation import validate_candidates
from dialogue_metrics import dialogue_metrics

class DialogueContextTests(unittest.TestCase):
    def test_time_bands_and_unknown_clock(self):
        for hour,period in ((4,'night'),(5,'morning'),(11,'morning'),(12,'afternoon'),(17,'evening'),(22,'night')):
            self.assertEqual(time_context(4+hour/24)['period'],period)
        for value in (None,True,float('nan'),-1):self.assertFalse(time_context(value)['known'])

    def test_latest_heard_question_and_own_commitments_are_explicit(self):
        c={'speakers':[1,2],'turn':2,'max_turns':6,'turns':[{'delivered':True,'speaker':1,'listener':2,'selected':{'line':'Hello there.'}},
            {'delivered':True,'speaker':2,'listener':1,'selected':{'line':'Have you eaten?'}}]}
        frame=dialogue_frame(c,{'gameDays':4.3},{'commitments':[]},1)
        self.assertEqual(frame['last_line_heard'],'Have you eaten?');self.assertTrue(frame['already_spoken'])
        self.assertTrue(frame['last_line_has_question_mark']);self.assertIsNone(frame['closing_reason'])
        self.assertNotIn('other_inventory',frame)

    def test_wrong_greeting_and_question_at_goodbye_are_rejected(self):
        frame={'clock':time_context(4.25)}
        with self.assertRaises(ValueError):validate_situated_candidates([{'line':'Good evening to you.'}],frame)
        with self.assertRaises(ValueError):validate_situated_candidates([{'line':'Goodbye. Where are you going?'}],frame,True)
        validate_situated_candidates([{'line':'Good morning to you.'}],frame)
        validate_situated_candidates([{'line':'Thank you. Take care.'}],frame,True)

    def test_short_acknowledgements_and_goodbyes_need_no_padding(self):
        self.assertEqual(len(validate_candidates({'candidates':[
            {'id':'option_1','line':'Thanks.','tone':'calm','intention':'Acknowledge'},
            {'id':'option_2','line':'Take care.','tone':'calm','intention':'Close'}]})),2)

    def test_context_metrics_keep_unobserved_clock_out_of_time_denominator(self):
        turns=[{'delivered':True,'speaker':1,'selected':{'line':'Good morning.'},'context':{'interaction':{'clock':time_context(4.75)}}},
               {'delivered':True,'speaker':2,'selected':{'line':'Good morning.'}},
               {'delivered':True,'speaker':1,'selected':{'line':'See you. Tomorrow?'},'context':{'event':{'dialogue_stage':'closing'}}}]
        m=dialogue_metrics([{'speakers':[1,2],'turns':turns}])
        self.assertEqual(m['time_checked_greetings'],1);self.assertEqual(m['time_mismatched_greetings'],1)
        self.assertEqual(m['closing_turns'],1);self.assertEqual(m['closing_question_marks'],1)
        self.assertIsNone(m['question_answer_relevance'])

    def test_refusal_cannot_claim_a_chat_happened_or_invent_a_task(self):
        c={'speakers':[1,2],'turn':0,'max_turns':1,'turns':[],'response':'decline'}
        frame=dialogue_frame(c,{'gameDays':4.7},{'commitments':[]},1)
        self.assertTrue(frame['is_refusal']);self.assertNotIn('budget',frame['closing_reason'])
        for line in ("It's been pleasant chatting. Take care.", 'I need to tend to some things at home. Goodbye.'):
            with self.assertRaises(ValueError):validate_situated_candidates([{'line':line}],frame,True)
        validate_situated_candidates([{'line':'Not now, sorry. Take care.'}],frame,True)
