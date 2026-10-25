"""Offline service faults with explicitly authored claim and native-receipt fixtures."""
import copy
import time
import unittest
from catalog_fixture import native_catalog
from economy_catalog import catalog_hash,recipe_hash
from employment import work_terms_hash,accept_contract
from enterprises import production_policy
from entrepreneurship import learn_recipe
from legacy_fixture import author_fixture_identities
from paid_employment import PaidEmployment,paid_identity,paid_stages,paid_effect_evidence


class SavedPaidWorld(PaidEmployment):
    def __init__(self):
        self.session='paid-unit';self.marker=1;self.transition=None;self.error=None;self.writes=[]
        self.active={'pending':None,'people':{'17':{'memories':[]},'29':{'memories':[]}},'plans':[],
            'town':{'residents':{'17':{'id':17},'29':{'id':29}},'daily':{'queue':[]},'businesses':{
                'fixture-shop':{'id':'fixture-shop','owner':29,'custodian':29,'active':True,'revision':1,
                    'capabilities':['bread_recipe'],'contracts':[],'workers':[]}}}}
        self.obs={'session':self.session,'checkpoint':1,'ready':True,'gameDays':3.,'economy_catalog':native_catalog(),
            'paid_employment':{'available':True,'protocol':2,'epoch':'native-unit','capacity':4,'jobs':[],'receipts':[]},
            'resident_control':{'activities':[{'actor':17,'slot':0,'expectedPackage':9000}]},
            'residents':[{'id':a,'baseId':a+1000,'isPerson':True,'x':i*50,'y':0,'z':0,'cell_id':77,
                'inventory':{'gold':5 if a==17 else 20,'grain':0 if a==17 else 3,'bread':0}}
                for i,a in enumerate((17,29))]}
        author_fixture_identities(self.active,self.obs)
        learn_recipe(self.active['people']['29'],'explicit-unit-prior','bread_recipe')
        terms={'protocol':2,'worker':17,'worker_base_id':1017,'employer':29,'employer_base_id':1029,
            'business_id':'fixture-shop','revision':1,'recipe_id':'bread_recipe','catalog_hash':catalog_hash(),
            'recipe_hash':recipe_hash('bread_recipe'),'currency':'gold','policy':production_policy(self.active['town']['businesses']['fixture-shop'])}
        terms['terms_hash']=work_terms_hash(terms)
        self.plan={'id':'fixture-plan','actor':17,'target':29,'phase':'ready_to_paid_work','work_terms':terms,
            'paid_work_release':{'id':'release-fixture-plan','status':'applied','released':True},'release_required':False,'decisions':[]}
        for action,actor in [('offer_shift',29),('take_shift',17)]:
            self.plan['decisions'].append({'claim_id':'unit-'+action,'actor_id':actor,'decision':{'action_id':action},
                'context':{'actor_id':actor,'session':self.session,'event':{'id':self.plan['id']},'terms_hash':terms['terms_hash'],
                    'work_terms':copy.deepcopy(terms),'options':[{'id':action}]}})
        self.active['plans']=[self.plan];accept_contract(self.active,self.plan,self.obs)
        self.latest_observation=self.obs
    def _agency_guard(self,observation):
        if self.transition or self.active.get('pending'):raise ValueError('Unsettled fixture writer')
    def agency_plan(self):return self.active['plans'][-1]
    def agency_busy(self):return False
    def conversation_busy(self):return False
    def agency_command(self,session):return None
    def speech_command(self,session):return None
    def _write(self,state,reason):self.active=state;self.writes.append(reason);return len(self.writes)
    def start(self):
        self.delegate_paid_work(self.agency_plan(),self.obs);job=next(iter(self.active['paid_work_jobs'].values()))
        c=self.paid_work_pending_command();self.obs['ack']={**paid_identity(job),'id':c['id'],'status':'applied','accepted':True,'effects_issued':False}
        self.observe_paid_employment(self.obs);return self.active['paid_work_jobs'][job['id']]
    def attend(self,job=None):
        job=self.start() if job is None else job
        self.obs['gameDays']+=job['work_minutes']/1440+.00001;now=time.time()*1000
        receipt={**paid_identity(job),'phase':'attendance_verified','effects_issued':False,'attendance':{
            'token':'authored-unit-attendance','token_valid':True,'slot':job['slot'],'serial':2,'expected_package':job['expected_package'],
            'anchor':job['anchor'],'cell_id':job['cell_id'],'worked_minutes':job['work_minutes'],'samples':100,'ready_at':now-10,'expires_at':now+120000}}
        self.obs['paid_employment']['receipts']=[receipt];self.observe_paid_employment(self.obs)
        return self.active['paid_work_jobs'][job['id']]
    def prepare(self):
        job=self.attend();self.prepare_paid_work_commit(self.obs);return self.active['paid_work_jobs'][job['id']],self.active['pending']['command']
    def effect(self,command,count=4,issued_next=False):
        stages=paid_stages(command);legs=[]
        for i,stage in enumerate(stages):
            issued=i<count or issued_next and i==count
            legs.append({**stage,'issued':issued,'observed':i<count,**({'issued_at':time.time()*1000} if issued else {})})
        inventory=copy.deepcopy(command['before'] if count==0 else stages[count-1]['after'])
        return {**paid_identity(command),'id':command['id'],'status':'applied' if count==4 else 'held',
            'phase':'effects_verified' if count==4 else 'held','commit_id':command['id'],'attendance_token':command['attendance_token'],
            'legs':legs,'effects_issued':count>0 or issued_next,'effects_verified':count==4,'output_verified':count>=2,
            'wage_debit_verified':count>=3,'wages_verified':count==4,'inventory':inventory,'release_verified':False}
    def inventory(self,accounts):
        for row in self.obs['residents']:row['inventory']=copy.deepcopy(accounts['worker' if row['id']==17 else 'employer'])


class PaidEmploymentTests(unittest.TestCase):
    def test_moving_employer_social_activity_defers_commit_then_completes_original_job_only(self):
        w=SavedPaidWorld();job=w.start();source_id=job['source_plan']
        employer=w.obs['residents'][1]
        employer.update(x=9000,y=2500,z=450,cell_id=88,loaded=True,
            activity={'package_id':12345,'moving':True})
        # Authored foreground fixture: the employer's newer social plan must not
        # become the paid job's consent source or completion target.
        social={'id':'employer-social','actor':29,'phase':'talking','decisions':[]}
        w.active['plans'].append(social);w.conversation_busy=lambda:True
        job=w.attend(job)
        self.assertEqual(job['phase'],'attendance_verified')
        before=copy.deepcopy(w.active);self.assertFalse(w.prepare_paid_work_commit(w.obs))
        self.assertEqual(w.active,before);self.assertIsNone(w.active['pending'])
        self.assertNotIn('known_recipes',w.active['people']['17'])
        w.active['plans'][-1]['phase']='complete';social_before=copy.deepcopy(w.active['plans'][-1])
        w.conversation_busy=lambda:False
        self.assertTrue(w.prepare_paid_work_commit(w.obs));command=w.active['pending']['command']
        self.assertEqual(command['anchor'],job['anchor']);self.assertEqual(command['cell_id'],77)
        self.assertEqual(command['consent_hash'],job['consent_hash'])
        self.assertEqual(w.paid_work_commit_command(w.session),command)
        ack=w.effect(command);w.inventory(ack['inventory']);w.obs['ack']=ack
        self.assertTrue(w.observe_paid_production(w.obs))
        self.assertNotIn('known_recipes',w.active['people']['17'])
        employer.update(x=10000,cell_id=99)
        w.obs['paid_employment']['receipts']=[{**ack,'phase':'complete','release_verified':True}]
        self.assertTrue(w.observe_paid_employment(w.obs))
        self.assertEqual(next(p for p in w.active['plans'] if p['id']==source_id)['phase'],'complete')
        self.assertEqual(w.active['plans'][-1],social_before)
        self.assertIn('bread_recipe',w.active['people']['17']['known_recipes'])
        self.assertEqual(len(w.active['production']),1)

    def test_employer_social_ack_and_matching_balances_never_complete_paid_work(self):
        w=SavedPaidWorld();job,command=w.prepare();w.obs['residents'][1].update(x=9000,cell_id=88)
        w.inventory(command['after'])
        w.obs['ack']={'id':'employer-social','status':'applied','released':True}
        before=copy.deepcopy(w.active)
        self.assertFalse(w.observe_paid_production(w.obs));self.assertFalse(w.observe_paid_employment(w.obs))
        self.assertEqual(w.active,before);self.assertEqual(w.active['pending']['status'],'pending')
        self.assertNotIn('production',w.active);self.assertNotIn('known_recipes',w.active['people']['17'])

    def test_employer_freedom_does_not_relax_worker_attendance_or_reserved_account_proof(self):
        changes=[lambda w:w.obs['paid_employment']['receipts'][0]['attendance'].update(anchor=[9000,0,0]),
            lambda w:w.obs['paid_employment']['receipts'][0]['attendance'].update(cell_id=88),
            lambda w:w.obs['paid_employment']['receipts'][0]['attendance'].update(expected_package=12345),
            lambda w:w.obs['residents'][1]['inventory'].update(gold=19),
            lambda w:w.obs['residents'][1].update(loaded=False)]
        for index,change in enumerate(changes):
            with self.subTest(invalid_evidence=index):
                w=SavedPaidWorld();job=w.attend();w.obs['residents'][1].update(x=9000,cell_id=88)
                change(w);self.assertTrue(w.prepare_paid_work_commit(w.obs))
                self.assertIsNone(w.active['pending']);self.assertEqual(w.active['paid_work_jobs'][job['id']]['phase'],'held')
                self.assertNotIn('production',w.active);self.assertNotIn('known_recipes',w.active['people']['17'])

    def test_success_keeps_learning_and_completion_separate_from_inventory_then_releases_once(self):
        w=SavedPaidWorld();job,c=w.prepare();ack=w.effect(c);w.inventory(ack['inventory']);w.obs['ack']=ack
        self.assertTrue(w.observe_paid_production(w.obs));job=w.active['paid_work_jobs'][job['id']]
        self.assertEqual(job['phase'],'effects_verified');self.assertNotIn('known_recipes',w.active['people']['17'])
        self.assertEqual(w.agency_plan()['phase'],'delegated');self.assertEqual(len(w.active['production']),1)
        w.obs['paid_employment']['receipts']=[{**ack,'phase':'complete','release_verified':True}]
        w.observe_paid_employment(w.obs);self.assertEqual(w.agency_plan()['phase'],'complete')
        self.assertIn('bread_recipe',w.active['people']['17']['known_recipes'])
        c=w.paid_work_pending_command();w.obs['ack']={**paid_identity(job),'id':c['id'],'status':'applied','acknowledged':True}
        w.obs['paid_employment']['receipts']=[];w.observe_paid_employment(w.obs)
        self.assertEqual(w.paid_employment_status()['jobs'],[]);self.assertEqual(len(w.paid_employment_status()['history']),1)
        before=copy.deepcopy(w.active);self.assertFalse(w.observe_paid_employment(w.obs));self.assertEqual(w.active,before)

    def test_each_partial_leg_stays_quarantined_with_distinct_output_and_wage_axes(self):
        for count in range(4):
            with self.subTest(observed=count):
                w=SavedPaidWorld();job,c=w.prepare();ack=w.effect(c,count,True);w.inventory(ack['inventory']);w.obs['ack']=ack
                w.observe_paid_production(w.obs);job=w.active['paid_work_jobs'][job['id']]
                self.assertEqual(w.active['pending']['status'],'held');self.assertTrue(job['effect_unreconciled'])
                self.assertEqual(job['settlement']['output_verified'],count>=2)
                self.assertEqual(job['settlement']['wage_debit_verified'],count>=3)
                self.assertFalse(job['settlement']['wages_verified']);self.assertNotIn('production',w.active)
                self.assertNotIn('known_recipes',w.active['people']['17']);self.assertIsNone(w.paid_work_commit_command(w.session))

    def test_receipt_flags_after_balances_or_later_legs_cannot_replace_issued_proof(self):
        w=SavedPaidWorld();_,c=w.prepare();good=w.effect(c)
        changes=[lambda a:a['legs'][0].update(issued=False),lambda a:a['legs'][0].update(observed=False),
            lambda a:a['legs'][2]['before']['employer'].update(grain=500),lambda a:a['legs'][3].update(amount=99),
            lambda a:a.update(attendance_token='other'),lambda a:a.update(terms_hash='0'*64),
            lambda a:a.update(worker_base_id=9999),lambda a:a['legs'][0].pop('issued_at'),
            lambda a:a.update(output_verified=False),lambda a:a.update(effects_issued=None)]
        for change in changes:
            ack=copy.deepcopy(good);change(ack)
            self.assertFalse(paid_effect_evidence(c,ack,c['after'])['valid'])

    def test_missing_or_reversed_consent_and_unreleased_travel_cannot_admit(self):
        for change in [lambda w:w.plan['decisions'].pop(),lambda w:w.plan['decisions'].reverse(),
            lambda w:w.plan['paid_work_release'].update(released=False),lambda w:w.plan.update(release_required=True),
            lambda w:w.obs['paid_employment'].update(protocol=1),lambda w:w.obs['residents'][0].update(baseId=9999)]:
            w=SavedPaidWorld();change(w);before=copy.deepcopy(w.active)
            with self.assertRaises(ValueError):w.delegate_paid_work(w.agency_plan(),w.obs)
            self.assertEqual(w.active,before);self.assertEqual(w.writes,[])

    def test_expired_or_changed_attendance_never_prepares_inventory(self):
        for change in [lambda w:w.obs['paid_employment']['receipts'][0]['attendance'].update(expires_at=0),
            lambda w:w.obs['paid_employment']['receipts'][0]['attendance'].update(serial=0),
            lambda w:w.obs['residents'][1]['inventory'].update(grain=0),
            lambda w:w.active['town']['businesses']['fixture-shop'].update(revision=2)]:
            w=SavedPaidWorld();job=w.attend();change(w);w.prepare_paid_work_commit(w.obs)
            self.assertIsNone(w.active['pending']);self.assertEqual(w.active['paid_work_jobs'][job['id']]['phase'],'held')

    def test_session_epoch_catalog_and_base_changes_never_reissue_prepared_commit(self):
        for change in [lambda w:setattr(w,'session','new-session'),lambda w:w.obs['paid_employment'].update(epoch='new-epoch'),
            lambda w:w.obs['residents'][1].update(baseId=9999),lambda w:w.active['paid_work_jobs'][next(iter(w.active['paid_work_jobs']))].update(recipe_id='missing_recipe')]:
            w=SavedPaidWorld();job,c=w.prepare();w.inventory(c['after']);change(w)
            self.assertIsNone(w.paid_work_commit_command(w.session));w.observe_paid_production(w.obs)
            self.assertEqual(w.active['pending']['status'],'held');self.assertNotIn('production',w.active)
            self.assertNotIn('known_recipes',w.active['people']['17'])

    def test_lost_ack_uses_exact_retained_live_journal_not_final_balances(self):
        w=SavedPaidWorld();job,c=w.prepare();receipt=w.effect(c);receipt.pop('id');receipt.pop('status');w.inventory(receipt['inventory'])
        w.obs.pop('ack',None);w.obs['paid_employment']['receipts']=[receipt];w.observe_paid_production(w.obs)
        self.assertEqual(len(w.active['production']),1)
        self.assertEqual(w.active['production'][0]['evidence']['receipt_source'],'retained_native_journal')
        self.assertNotIn('known_recipes',w.active['people']['17'])

    def test_pending_with_no_saved_job_is_held_without_adopting_it(self):
        w=SavedPaidWorld();_,c=w.prepare();w.active['paid_work_jobs']={};w.obs['ack']=w.effect(c);w.inventory(c['after'])
        w.observe_paid_production(w.obs);self.assertEqual(w.active['pending']['status'],'held');self.assertNotIn('production',w.active)

    def test_unbound_start_rejection_is_held_instead_of_retrying_forever(self):
        w=SavedPaidWorld();w.delegate_paid_work(w.agency_plan(),w.obs);c=w.paid_work_pending_command()
        w.obs['ack']={'id':c['id'],'status':'held','error':'unavailable'};w.observe_paid_employment(w.obs)
        self.assertIsNone(w.paid_work_pending_command());job=next(iter(w.active['paid_work_jobs'].values()))
        self.assertEqual(job['phase'],'held');self.assertTrue(job['effect_unreconciled'])

    def test_verified_no_effect_commit_rejection_cancels_intent_but_waits_for_cleanup(self):
        for consumed in (False,True):
            w=SavedPaidWorld();job,c=w.prepare();ack=w.effect(c,0)
            ack.update(no_effects_issued=True,legs=ack['legs'] if consumed else [],commit_id=c['id'] if consumed else None)
            w.obs['ack']=ack;w.observe_paid_production(w.obs)
            current=w.active['paid_work_jobs'][job['id']]
            self.assertIsNone(w.active['pending']);self.assertEqual(current['phase'],'held')
            self.assertFalse(current['effect_unreconciled']);self.assertFalse(current['receipt_acknowledged'])
            self.assertNotIn('production',w.active);self.assertNotIn('known_recipes',w.active['people']['17'])

    def test_lost_no_effect_ack_uses_exact_retained_journal_without_releasing_lease(self):
        for tampered in (False,True):
            w=SavedPaidWorld();job,c=w.prepare();receipt=w.effect(c,0)
            receipt.update(no_effects_issued=True);receipt.pop('id');receipt.pop('status')
            if tampered:receipt['attendance_token']='unrelated-token'
            w.obs.pop('ack',None);w.obs['paid_employment']['receipts']=[receipt]
            w.observe_paid_production(w.obs);current=w.active['paid_work_jobs'][job['id']]
            self.assertEqual(current['phase'],'held');self.assertFalse(current['receipt_acknowledged'])
            self.assertFalse(current['release_verified']);self.assertEqual(current['effect_unreconciled'],tampered)
            if tampered:self.assertEqual(w.active['pending']['status'],'held')
            else:
                self.assertIsNone(w.active['pending'])
                self.assertEqual(w.active['cancelled_production'][0]['evidence']['receipt_source'],'retained_native_journal')
            self.assertNotIn('production',w.active);self.assertNotIn('known_recipes',w.active['people']['17'])

    def test_changed_saved_terms_after_inventory_cannot_grant_learning_at_release(self):
        w=SavedPaidWorld();job,c=w.prepare();ack=w.effect(c);w.inventory(ack['inventory']);w.obs['ack']=ack;w.observe_paid_production(w.obs)
        w.active['town']['businesses']['fixture-shop']['revision']=2
        w.obs['paid_employment']['receipts']=[{**ack,'phase':'complete','release_verified':True}];w.observe_paid_employment(w.obs)
        self.assertEqual(w.active['paid_work_jobs'][job['id']]['phase'],'held')
        self.assertNotIn('known_recipes',w.active['people']['17']);self.assertEqual(len(w.active['production']),1)

    def test_rollback_orphan_receipt_never_adopts_output_or_learning(self):
        w=SavedPaidWorld();_,c=w.prepare();receipt=w.effect(c,2,True);w.inventory(receipt['inventory'])
        w.active['paid_work_jobs']={};w.active['pending']=None;w.obs['paid_employment']['receipts']=[receipt];w.obs.pop('ack',None)
        self.assertTrue(w.observe_paid_employment(w.obs));orphan=next(iter(w.active['paid_work_orphans'].values()))
        self.assertTrue(orphan['effect_unreconciled']);self.assertEqual(orphan['settlement']['phase'],'not_admitted')
        self.assertNotIn('production',w.active);self.assertNotIn('known_recipes',w.active['people']['17']);self.assertIsNone(w.paid_work_pending_command())
        before=copy.deepcopy(w.active);self.assertFalse(w.observe_paid_employment(w.obs));self.assertEqual(w.active,before)

    def test_no_effect_orphan_can_only_acknowledge_verified_cleanup(self):
        w=SavedPaidWorld();job=w.start();receipt={**paid_identity(job),'phase':'held','effects_issued':False,'legs':[],'release_verified':False}
        w.active['paid_work_jobs']={};w.obs['paid_employment']['receipts']=[receipt];w.obs.pop('ack',None);w.observe_paid_employment(w.obs)
        self.assertIsNone(w.paid_work_pending_command());receipt['release_verified']=True;w.observe_paid_employment(w.obs)
        c=w.paid_work_pending_command();self.assertEqual(c['kind'],'paid_work_ack_receipt')
        w.obs['ack']={**paid_identity(job),'id':c['id'],'status':'applied','acknowledged':True};w.obs['paid_employment']['receipts']=[]
        w.observe_paid_employment(w.obs);self.assertEqual(w.paid_employment_status()['jobs'],[])
        self.assertNotIn('production',w.active);self.assertNotIn('known_recipes',w.active['people']['17'])
