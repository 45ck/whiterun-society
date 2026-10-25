import tempfile
from pathlib import Path
import unittest
from metrics import simulation_metrics
from relationship_metrics import relationship_level,relationship_metrics
from dialogue_metrics import dialogue_metrics
from doc_assets import documentation_asset

class QualityGoalTests(unittest.TestCase):
    def test_friendship_requires_affinity_familiarity_and_heard_history(self):
        self.assertEqual(relationship_level({'affinity':1}),'stranger')
        self.assertEqual(relationship_level({'affinity':.25,'familiarity':.25,'heard_turns':6}),'friend')
        self.assertEqual(relationship_level({'affinity':.6,'familiarity':.6,'heard_turns':12}),'close_friend')
        self.assertEqual(relationship_level({'affinity':-.25}),'strained')
        self.assertEqual(relationship_level({'affinity':0,'heard_turns':1}),'acquaintance')

    def test_one_sided_friendship_is_not_reported_as_mutual(self):
        f={'affinity':.3,'familiarity':.4,'heard_turns':8};people={'1':{'relationships':{'2':f}},'2':{}}
        self.assertEqual(relationship_metrics(people)['mutual_friend_pairs'],0)
        self.assertEqual(relationship_metrics(people)['one_sided_friendships'],1)
        people['2']['relationships']={'1':f}
        self.assertEqual(relationship_metrics(people)['mutual_friend_pairs'],1)
        self.assertEqual(relationship_metrics(people)['one_sided_friendships'],0)

    def test_smalltalk_heuristics_ignore_undelivered_and_keep_semantics_unknown(self):
        turn=lambda s,t,ok=True:{'speaker':s,'selected':{'line':t},'delivered':ok}
        m=dialogue_metrics([{'speakers':[1,2],'turns':[turn(1,'Hello. How are you?'),turn(2,'Thank you.'),turn(1,'Hello. How are you?'),turn(2,'Goodbye.',False)]}])
        self.assertEqual(m['delivered_lines'],3);self.assertEqual(m['lexical_cues']['question_mark'],2)
        self.assertEqual(m['repeated_greeting_turns'],1);self.assertEqual(m['exact_repeated_lines_within_scene'],1)
        self.assertNotIn('farewell',m['lexical_cues']);self.assertIsNone(m['question_answer_relevance'])

    def test_unknown_metrics_cannot_meet_targets_and_small_samples_cannot_pass(self):
        m=simulation_metrics({});items={i['id']:i for i in m['quality_goals']['items']}
        self.assertGreaterEqual(len(items),25);self.assertEqual(items['SOC-01']['status'],'unmeasured')
        self.assertEqual(items['SOC-03']['status'],'insufficient_sample')
        self.assertEqual(items['ECO-02']['status'],'below_target')
        self.assertEqual(items['EVO-02']['status'],'unmeasured')

    def test_deliberate_interruption_is_separate_from_technical_failure(self):
        c={'id':'c','mode':'autonomous_social','phase':'held','started_at':1,'finished_at':12,
            'interruption':{'kind':'observer','stage':'speaking','requested_at':10},'release_evidence':{'released':True},'turns':[]}
        e=simulation_metrics({'conversation':c})['encounters']
        self.assertEqual(e['observer_interruptions'],1);self.assertEqual(e['technical_failures'],0)
        self.assertEqual(e['interruption_cleanup']['percent'],100);self.assertEqual(e['interruption_settle_seconds']['median'],2)

    def test_public_asset_route_does_not_read_sibling_files_or_encoded_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'docs/images').mkdir(parents=True);(root/'docs/index.html').write_text('Gallery')
            (root/'docs/images/test.png').write_bytes(b'public-image');(root/'private.env').write_text('private')
            self.assertEqual(documentation_asset(root,'/docs/')[1],b'Gallery')
            self.assertEqual(documentation_asset(root,'/docs/images/test.png')[1],b'public-image')
            (root/'docs/audio').mkdir();(root/'docs/audio/line.wav').write_bytes(b'public-audio')
            self.assertEqual(documentation_asset(root,'/docs/audio/line.wav'),('audio/wav',b'public-audio'))
            self.assertIsNone(documentation_asset(root,'/docs/audio/../../private.env'))
            self.assertIsNone(documentation_asset(root,'/docs/audio/catalog.json'))
            for route in ('/docs/../private.env','/docs/images/../../private.env','/docs/images/%2e%2e/private.env','/docs/images/x.svg','/docs/images/missing.png'):
                self.assertIsNone(documentation_asset(root,route))
