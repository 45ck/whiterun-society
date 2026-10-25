import copy
import unittest
import test_activity_jobs as job_fixture
import test_social as social_fixture
import test_goal_scheduler as scheduler_fixture
from activity_leases import activity_leases,reserved_activity_actors,reserved_activity_targets
from resident_goals import occupied
from rest import rest_opportunities
from social import social_candidates
from opportunities import food_sellers
from goal_opportunities import focus_opportunities
from tools.goal_scheduler import due_residents
from tools.run_daily_life import event_available,routine_dispatch_prefix
from legacy_fixture import author_fixture_identities


def job(actor,target,**extra):
    return {'id':'job-'+str(actor),'actor':actor,'target':target,'slot':0,'session':'s','epoch':'e',
        'phase':'held','receipt_acknowledged':False,'policy':{'rest_minutes':30},**extra}


class ActivityProjectionTests(unittest.TestCase):
    def test_public_status_jobs_and_orphans_match_internal_reservations(self):
        state={'activity_jobs':{'one':job(1,101),'old':job(2,102,receipt_acknowledged=True)},
               'activity_orphans':{'orphan':job(3,103,orphan=True)}}
        status=job_fixture.SavedJobs(state).activity_status()
        self.assertEqual(set(status),{'epoch','capacity','jobs','history'})
        projection={'activity_jobs':status}
        self.assertEqual(reserved_activity_actors(projection),{1,3})
        self.assertEqual(reserved_activity_targets(projection),{101,103})
        self.assertEqual(reserved_activity_actors(state),reserved_activity_actors(projection))
        self.assertEqual(occupied(projection),{1,3})

    def test_history_is_not_a_lease_even_if_legacy_ack_marker_is_missing(self):
        projection={'activity_jobs':{'epoch':'e','capacity':2,'jobs':[],
                                    'history':[job(1,101),job(2,102,receipt_acknowledged=True)]}}
        self.assertEqual(activity_leases(projection),[])

    def test_completed_active_lease_stays_reserved_until_acknowledged(self):
        active=job(1,101,phase='complete',release_verified=True)
        projection={'activity_jobs':{'epoch':'e','capacity':2,'jobs':[active],'history':[]}}
        self.assertEqual(reserved_activity_actors(projection),{1})
        active['receipt_acknowledged']=True
        self.assertEqual(reserved_activity_actors(projection),set())

    def test_native_quarantine_is_union_with_projected_active_leases(self):
        projection={'activity_jobs':{'epoch':'new','capacity':2,'jobs':[job(1,101)],'history':[]}}
        obs={'activity_jobs':{'epoch':'old','jobs':[job(2,102)],'receipts':[job(3,103)]}}
        before=copy.deepcopy((projection,obs))
        self.assertEqual(reserved_activity_actors(projection,obs),{1,2,3})
        self.assertEqual(reserved_activity_targets(projection,obs),{101,102,103})
        self.assertEqual((projection,obs),before)

    def test_goal_scheduler_excludes_projection_and_native_only_quarantine(self):
        snapshot=scheduler_fixture.snapshot(3)
        snapshot['society']['activity_jobs']={'epoch':'e','capacity':2,'jobs':[job(1,101)],'history':[]}
        snapshot['bridge']['observation']['activity_jobs']={'receipts':[job(2,102)]}
        self.assertEqual(due_residents(snapshot),[3])

    def test_director_rejects_native_only_queued_actor_without_model_dispatch(self):
        event={'id':'need','actor':1,'kind':'need_review','status':'pending'}
        society={'people':{'1':{}},'town':{'residents':{'1':{'id':1}},'daily':{'queue':[event]}},
                 'activity_jobs':{'epoch':'e','capacity':2,'jobs':[],'history':[]}}
        observation={'session':'fixture','checkpoint':0,'ready':True,'residents':[{'id':1,'baseId':101,'isPerson':True}],
                     'activity_jobs':{'jobs':[job(1,101)]}}
        author_fixture_identities(society,observation)
        snapshot={'society':society,'bridge':{'observation':observation}}
        self.assertFalse(event_available(snapshot,event))
        self.assertEqual(routine_dispatch_prefix(society,observation,[event]),[])
        observation['activity_jobs']['jobs']=[]
        self.assertTrue(event_available(snapshot,event))


class RestProjectionTests(unittest.TestCase):
    setUp=job_fixture.ActivityJobsTests.setUp

    def test_rest_menu_accepts_actual_status_shape_and_preserves_other_seats(self):
        state=copy.deepcopy(self.world.active)
        state['activity_jobs']={'j':job(1,self.seats[0])}
        projection={**state,'activity_jobs':job_fixture.SavedJobs(state).activity_status()}
        self.assertEqual(rest_opportunities(projection,self.obs,1),[])
        sites={s['id'] for s in rest_opportunities(projection,self.obs,2)}
        self.assertNotIn(self.seats[0],sites);self.assertIn(self.seats[1],sites)


class SocialProjectionTests(unittest.TestCase):
    setUp=social_fixture.SocialTests.setUp
    tearDown=social_fixture.SocialTests.tearDown
    sync=social_fixture.SocialTests.sync
    census=social_fixture.SocialTests.census
    review=social_fixture.SocialTests.review

    def test_social_seller_and_focus_menus_read_projection_without_flattening(self):
        state=copy.deepcopy(self.world.active)
        state['activity_jobs']={'j':job(108149,700),'old':job(99,701,receipt_acknowledged=True)}
        projection={**state,'activity_jobs':job_fixture.SavedJobs(state).activity_status()}
        candidates=social_candidates(projection,self.obs,99)
        self.assertNotIn(108149,[c['id'] for c in candidates])
        self.assertEqual(food_sellers(projection,self.obs,99),[])
        self.assertEqual(social_candidates(projection,self.obs,108149),[])
        focus=focus_opportunities(projection,self.obs,108149)
        self.assertFalse(any(focus[k] for k in ('food','rest','work','social')))
