"""Service proof tests use authored witnesses, separately from actual JS interop."""
import copy
import unittest
from unittest.mock import patch
import test_lineage
import economy_catalog
import market_policy
from catalog_fixture import native_catalog
from trade_execution_fixture import trade_ack, arm_trade, native_trade_status
from trade_execution import IDENTITY


class TradeProtocolServiceTests(unittest.TestCase):
    setUp=test_lineage.LineageTests.setUp
    tearDown=test_lineage.LineageTests.tearDown
    bind=test_lineage.LineageTests.bind
    prepare=test_lineage.LineageTests.prepare
    finish=test_lineage.LineageTests.finish

    def armed(self):
        self.prepare();return arm_trade(self.world,self.obs,self.bind)

    def after(self,command):
        for role in ('buyer','seller'):
            for row in self.obs['residents']+self.obs.get('inventory_observations',[]):
                if row['id']==command[role]:row['inventory']=command['after'][role].copy()

    def held(self):
        if self.world.transition:self.bind()
        self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertEqual(self.world.active['trades'],[])
        self.assertEqual(self.world.active['people']['108186']['memories'],[])
        self.assertEqual(self.world.active['people']['108149']['memories'],[])
        self.assertIsNone(self.world.pending(self.obs['session']))

    def test_operator_provenance_is_explicit_and_not_resident_decisions(self):
        self.prepare();self.finish();record=self.world.active['trades'][0]
        self.assertEqual(record['consent']['payload']['source_kind'],'operator')
        self.assertEqual(record['id'],'bread-1')
        self.assertEqual(record['command']['id'],'bread-1-deliver')
        self.assertEqual(self.world.active['people']['108186']['memories'][0]['source_kind'],'operator')

    def test_arm_permit_checkpoint_precedes_any_delivery(self):
        self.prepare();arm=self.world.pending('a');self.assertEqual(arm['phase'],'arm')
        self.obs['ack']=trade_ack(arm);self.world.observe(self.obs)
        self.assertEqual(self.world.pending('a')['kind'],'bind_checkpoint')
        self.bind();delivery=self.world.pending('a')
        self.assertEqual(delivery['phase'],'deliver');self.assertNotEqual(delivery['id'],arm['id'])
        self.assertEqual(delivery['permit'],self.world.active['pending']['arm_receipt']['permit'])

    def test_inventory_after_without_receipt_cannot_credit(self):
        command=self.armed();self.after(command);self.obs.pop('ack',None);self.world.observe(self.obs)
        self.assertEqual(self.world.active['trades'],[])
        self.assertEqual(self.world.active['pending']['status'],'pending')

    def test_cold_epoch_after_both_effects_holds_without_credit(self):
        command=self.armed();self.after(command);self.obs['ack']=trade_ack(command)
        self.obs['trade_execution']['epoch']='cold';self.world.observe(self.obs);self.held()

    def test_missing_arm_witness_cannot_dispatch_or_credit(self):
        command=self.armed();self.world.active['pending'].pop('arm_receipt')
        self.assertIsNone(self.world.pending('a'));self.after(command);self.obs['ack']=trade_ack(command)
        self.world.observe(self.obs);self.held()

    def test_changed_consent_hash_holds(self):
        self.prepare();self.world.active['pending']['consent']['payload']['source_kind']='resident_decisions'
        self.world.observe(self.obs);self.held()

    def test_changed_policy_holds_original_intent(self):
        self.prepare();changed=copy.deepcopy(market_policy.MARKET_POLICY);changed['id']='different-market'
        with patch.object(market_policy,'MARKET_POLICY',changed):
            self.assertIsNone(self.world.pending('a'));self.world.observe(self.obs)
        self.held()

    def test_legacy_pending_not_rebound_or_stamped(self):
        self.prepare();record=self.world.active['pending'];record['command']={'id':'old','kind':'inventory_trade','buyer':108186,'seller':108149}
        before=copy.deepcopy(record['command']);self.assertIsNone(self.world.pending('a'))
        self.world.observe(self.obs);self.held();self.assertEqual(self.world.active['pending']['command'],before)

    def test_bad_event_id_never_reserves_accounts(self):
        for event in ('spaces disallowed','slash/id','dot.id','colon:id'):
            with self.subTest(event=event),self.assertRaises(ValueError):self.world.plan_trade(event,self.obs,108186,108149)
        self.assertIsNone(self.world.active['pending']);self.assertIsNone(self.world.transition)

    def test_currency_cannot_be_the_sale_good(self):
        with self.assertRaises(ValueError):self.world.plan_trade('gold-sale',self.obs,108186,108149,commodity='gold')
        self.assertIsNone(self.world.active['pending'])

    def test_missing_base_identity_rejects_before_reserving(self):
        self.obs['residents'][1].pop('baseId')
        with self.assertRaises(ValueError):self.prepare()
        self.assertIsNone(self.world.active['pending'])

    def test_duplicate_observed_identity_rejects_before_reserving(self):
        self.obs['residents'].append(copy.deepcopy(self.obs['residents'][1]))
        with self.assertRaises(ValueError):self.prepare()
        self.assertIsNone(self.world.active['pending'])

    def test_stale_accounting_waits_across_both_bindings(self):
        self.obs['inventory_observations']=copy.deepcopy(self.obs['residents'])
        self.obs['inventory_checkpoint']=self.obs['checkpoint']
        self.prepare();self.assertEqual(self.world.active['pending']['status'],'pending')
        arm=self.world.pending('a');self.obs['ack']=trade_ack(arm);self.world.observe(self.obs)
        self.assertIsNone(self.world.transition)
        self.obs['inventory_checkpoint']=self.obs['checkpoint'];self.world.observe(self.obs);self.bind()
        command=self.world.pending('a');self.assertEqual(command['phase'],'deliver')
        self.after(command);self.obs['ack']=trade_ack(command);self.world.observe(self.obs)
        self.assertIsNone(self.world.transition);self.assertEqual(self.world.active['trades'],[])
        self.obs['inventory_checkpoint']=self.obs['checkpoint'];self.world.observe(self.obs);self.bind()
        self.assertEqual(len(self.world.active['trades']),1)

    def test_stale_buyer_account_does_not_hide_wrong_seller_base(self):
        self.prepare();self.obs['inventory_observations']=[copy.deepcopy(self.obs['residents'][0])]
        self.obs['inventory_checkpoint']=self.obs['checkpoint']-1;self.obs['residents'][1]['baseId']+=1
        self.world.observe(self.obs);self.held()

    def test_stale_accounts_do_not_hide_bad_leg(self):
        command=self.armed();self.after(command);self.obs['inventory_observations']=copy.deepcopy(self.obs['residents'])
        self.obs['inventory_checkpoint']=self.obs['checkpoint']-1;ack=trade_ack(command);ack['legs'][1]['credit_observed']=False
        self.obs['ack']=ack;self.world.observe(self.obs);self.held()

    def test_held_receipt_retains_partial_debit_proof(self):
        command=self.armed();ack=trade_ack(command)
        ack.update(status='held',phase='held',accepted=False);ack['legs']=ack['legs'][:1]
        ack['legs'][0].update(observed=False,credit_observed=False)
        self.obs['ack']=ack;self.world.observe(self.obs);self.held()
        self.assertTrue(self.world.active['pending']['evidence']['ack']['legs'][0]['debit_observed'])
        self.assertFalse(self.world.active['pending']['evidence']['ack']['legs'][0]['credit_observed'])

    def test_fourth_commodity_variable_quantity_conserves_every_account_key(self):
        catalog=copy.deepcopy(economy_catalog.ECONOMY_CATALOG)
        catalog['commodities'].append({'id':'iron','label':'Iron','native':{'plugin':'Skyrim.esm','local_form_id':388,'record_type':'MISC'},'currency':False,'provenance':'Authored integration fixture only'})
        with patch.object(economy_catalog,'ECONOMY_CATALOG',economy_catalog.validate_catalog(catalog)):
            policy=copy.deepcopy(market_policy.MARKET_POLICY);policy['catalog_hash']=economy_catalog.catalog_hash()
            row=copy.deepcopy(policy['goods'][1]);row.update(commodity='iron',legacy_retail_capability=None,reserve_mode='seller_choice');policy['goods'].append(row)
            with patch.object(market_policy,'MARKET_POLICY',market_policy.validate_policy(policy)):
                self.obs['economy_catalog']=native_catalog();self.obs['trade_execution']=native_trade_status()
                self.obs['residents'][0]['inventory']['iron']=0;self.obs['residents'][1]['inventory']['iron']=5
                self.world.plan_trade('iron-sale',self.obs,108186,108149,quantity=2,unit_price=2,commodity='iron');self.bind()
                command=arm_trade(self.world,self.obs,self.bind);self.after(command);self.obs['ack']=trade_ack(command)
                self.world.observe(self.obs);self.bind();record=self.world.active['trades'][0]
                self.assertEqual(record['command']['after']['buyer'],{'gold':5,'bread':0,'grain':0,'iron':2})
                for key in economy_catalog.commodity_ids():
                    self.assertEqual(sum(a[key] for a in command['before'].values()),sum(a[key] for a in command['after'].values()))
                memory=self.world.active['people']['108186']['memories'][0]
                self.assertEqual((memory['commodity'],memory['quantity'],memory['gold']),('iron',2,4))
                self.assertNotIn('bread',memory)


def missing_identity(field):
    def test(self):
        command=self.armed();self.after(command);ack=trade_ack(command);ack.pop(field)
        self.obs['ack']=ack;self.world.observe(self.obs);self.held()
    return test
for field in IDENTITY:setattr(TradeProtocolServiceTests,'test_final_receipt_requires_'+field,missing_identity(field))


def missing_leg_flag(index,field):
    def test(self):
        command=self.armed();self.after(command);ack=trade_ack(command);ack['legs'][index].pop(field)
        self.obs['ack']=ack;self.world.observe(self.obs);self.held()
    return test
for index in (0,1):
    for field in ('issued','observed','debit_observed','credit_observed'):
        setattr(TradeProtocolServiceTests,'test_leg_'+str(index)+'_requires_'+field,missing_leg_flag(index,field))


def bad_arm(field,value):
    def test(self):
        self.prepare();command=self.world.pending('a');ack=trade_ack(command);ack[field]=value
        self.obs['ack']=ack;self.world.observe(self.obs);self.held()
    return test
for field,value in [('protocol',None),('accepted',False),('inventory',{}),('permit',''),('effects_issued',True),('legs',[{}])]:
    setattr(TradeProtocolServiceTests,'test_arm_requires_'+field,bad_arm(field,value))
