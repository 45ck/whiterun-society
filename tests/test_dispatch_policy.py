import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dispatch_policy import can_insert_social, dispatch_metrics, fair_pending, load_policy


def event(name, age=0, priority=1, kind='need_review', **extra):
    return dict(id=name, created_day=10 - age / 1440, priority=priority, kind=kind, **extra)


class DispatchPolicyTests(unittest.TestCase):
    def test_old_resident_does_not_remain_at_position_seventeen(self):
        old = event('merchant-own-needs', age=57.48 * 60)
        newer = [event(str(i), age=120, conversation_followups=[{'encounter_id':str(i)}]) for i in range(17)]
        queued = newer + [old]
        original = copy.deepcopy(queued)
        self.assertIs(fair_pending(queued, game_day=10)[0], old)
        self.assertFalse(can_insert_social(queued, game_day=10))
        self.assertEqual(queued, original)

    def test_overdue_global_fifo_prevents_new_urgent_work_starving_older_social(self):
        old_social = event('old-social', age=300, priority=.4, kind='social_review')
        urgent = event('newer-urgent', age=61)
        followup = event('fresh-followup', conversation_followups=[{}])
        self.assertEqual([e['id'] for e in fair_pending([urgent, followup, old_social], game_day=10)],
                         ['old-social', 'newer-urgent', 'fresh-followup'])

    def test_age_thresholds_are_inclusive_and_urgency_is_configured(self):
        for priority, threshold in ((.8,60),(.79,240)):
            with self.subTest(priority=priority):
                self.assertTrue(can_insert_social([event('a',threshold-.01,priority)],game_day=10))
                self.assertFalse(can_insert_social([event('a',threshold,priority)],game_day=10))

    def test_both_followup_sources_receive_bounded_continuity(self):
        followups = [event('f'+str(i),priority=.4,**{source:[{}]})
                     for i,source in enumerate(['conversation_followups','goal_followups','goal_followups'])]
        ordinary = [event('o'+str(i)) for i in range(3)]
        result = fair_pending(followups+ordinary,game_day=10)
        self.assertEqual([e['id'][0] for e in result],['f','o']*3)
        for row in followups:
            self.assertFalse(can_insert_social([row],game_day=10))

    def test_followups_alone_are_all_preserved(self):
        rows = [event(str(i),goal_followups=[{}]) for i in range(9)]
        self.assertEqual(fair_pending(rows,game_day=10), rows)

    def test_no_clock_preserves_social_economic_alternation_without_fabricated_ages(self):
        rows = [event('e'+str(i)) for i in range(20)]
        rows += [event('s'+str(i),priority=.4,kind='social_review') for i in range(3)]
        self.assertEqual([e['kind'] for e in fair_pending(rows)[:6]], ['social_review','need_review']*3)
        self.assertEqual(fair_pending(rows,False)[0]['kind'],'need_review')
        self.assertEqual(dispatch_metrics(rows)['age_unknown_count'],23)
        self.assertIsNone(dispatch_metrics(rows)['maximum_wait_game_minutes'])
        self.assertFalse(can_insert_social(rows))

    def test_invalid_missing_future_age_is_not_overdue_but_blocks_urgent_insertion(self):
        for created in (None, float('nan'), float('inf'), True, '9', -1, 11):
            with self.subTest(created=created):
                rows=[{**event('a'), 'created_day':created}]
                self.assertEqual(dispatch_metrics(rows,10)['overdue_count'],0)
                self.assertEqual(dispatch_metrics(rows,10)['age_unknown_count'],1)
                self.assertFalse(can_insert_social(rows,10))
        for day in (None, float('nan'), float('inf'), True, '10'):
            self.assertEqual(dispatch_metrics([event('a')],day)['age_known_count'],0)

    def test_metrics_record_waiting_not_simulated_quality(self):
        rows=[event('old',300,.4),event('urgent',61),event('new',0,goal_followups=[{}]),
              {'id':'unknown','priority':.4}]
        metrics=dispatch_metrics(rows,10)
        self.assertEqual(metrics['pending_count'],4)
        self.assertEqual(metrics['age_known_count'],3)
        self.assertEqual(metrics['overdue_count'],2)
        self.assertEqual(metrics['followup_count'],1)
        self.assertAlmostEqual(metrics['maximum_wait_game_minutes'],300)

    def test_new_arrivals_cannot_overtake_old_overdue_queue(self):
        remaining=[event('original-'+str(i),age=300+i,priority=.4) for i in range(20)]
        served=[]
        for tick in range(20):
            remaining.append(event('new-'+str(tick),age=0,goal_followups=[{}]))
            chosen=fair_pending(remaining,game_day=10+tick/1440)[0]
            served.append(chosen['id'])
            remaining.remove(chosen)
        self.assertEqual(set(served),{'original-'+str(i) for i in range(20)})

    def test_deterministic_ties_and_no_dropped_or_duplicated_requests(self):
        rows=[event(str(i),age=(i%4)*100,priority=.4 if i%2 else 1,
                    kind='social_review' if i%3 else 'need_review') for i in range(35)]
        first=fair_pending(rows,game_day=10)
        self.assertEqual(first,fair_pending(list(reversed(rows)),game_day=10))
        self.assertEqual(len(first),len(rows))
        self.assertEqual({e['id'] for e in first},{e['id'] for e in rows})
        self.assertTrue(can_insert_social([],10))

    def test_policy_rejects_nonfinite_unbounded_and_unknown_settings(self):
        good=load_policy()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'policy.json'
            for key,value in [('urgent_wait_game_minutes',0),('ordinary_wait_game_minutes',1441),
                              ('ordinary_wait_game_minutes',30),('urgent_priority_threshold',float('nan')),
                              ('followup_burst_limit',0),('followup_burst_limit',True),('extra',1)]:
                path.write_text(json.dumps({**good,key:value}),encoding='utf-8')
                with self.subTest(key=key,value=value),patch('dispatch_policy.POLICY_PATH',path):
                    with self.assertRaises(ValueError):load_policy()


if __name__=='__main__':unittest.main()
