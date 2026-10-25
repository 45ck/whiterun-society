"""Actual HTTP dispatch and pre-mutation session/effect guards, no listener."""
import copy
import time
import unittest
from unittest.mock import patch
import test_startup_http as startup_fixture


class IndependentReviewHTTPTests(unittest.TestCase):
    setUp=startup_fixture.StartupHTTPTests.setUp
    tearDown=startup_fixture.StartupHTTPTests.tearDown
    bind=startup_fixture.StartupHTTPTests.bind
    post=startup_fixture.StartupHTTPTests.post

    def test_claim_and_result_dispatch_with_current_observation(self):
        with patch.object(self.world,'claim_independent_reviews',return_value={'empty':True},create=True) as claim:
            status,body=self.post('/independent-reviews/claim',{'id':'reviews','limit':4})
            self.assertEqual((status,body),(202,{'empty':True}))
            claim.assert_called_once_with('reviews',self.obs,4)
        with patch.object(self.world,'finish_independent_reviews',return_value={'accepted':[]},create=True) as finish:
            status,body=self.post('/independent-reviews/result',{'id':'reviews','claim_id':'claim','results':[]})
            self.assertEqual((status,body),(202,{'accepted':[]}))
            finish.assert_called_once_with('reviews','claim',[],self.obs)

    def test_wrong_session_cannot_dispatch_model_result(self):
        before=copy.deepcopy(self.world.active)
        with patch.object(self.world,'finish_independent_reviews',create=True) as finish:
            status,body=self.post('/independent-reviews/result',{'id':'reviews','claim_id':'claim','results':[]},session='another-save')
            self.assertEqual(status,409,body);finish.assert_not_called()
        self.assertEqual(self.world.active,before)

    def test_service_shutdown_does_not_abandon_a_live_review_claim(self):
        self.world.active['independent_review_waves']=[{'id':'live-review','phase':'thinking',
            'session':'startup','deadline_at':time.time()+1800,'members':[]}]
        before=copy.deepcopy(self.world.active)
        status,body=self.post('/service/shutdown',{})
        self.assertEqual(status,400,body)
        self.assertIn('independent review claims',body['error'])
        self.assertEqual(self.world.active,before)

    def test_pending_effect_result_conflict_is_certified_before_dispatch(self):
        self.world.active['pending']={'status':'held','command':{'kind':'fixture_unresolved_effect'}}
        before=copy.deepcopy(self.world.active)
        with patch.object(self.world,'finish_independent_reviews',create=True) as finish:
            status,body=self.post('/independent-reviews/result',{'id':'reviews','claim_id':'claim','results':[]})
            self.assertEqual(status,409,body)
            self.assertEqual(body['code'],'independent_review_effect_busy')
            self.assertEqual(body['session'],'startup');finish.assert_not_called()
        self.assertEqual(self.world.active,before)
