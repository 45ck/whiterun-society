import copy
import unittest
from agency_metrics import account_cashflow,economic_network
from metrics import simulation_metrics


def receipt(id,kind,**fields):
    return {'id':id,'status':'committed','command':{'id':id,'kind':kind,**fields}}


def trade(id,buyer,seller,cost):
    return receipt(id,'inventory_trade',buyer=buyer,seller=seller,cost=cost,
        before={'buyer':{'gold':10},'seller':{'gold':10}},after={'buyer':{'gold':10-cost},'seller':{'gold':10+cost}})


class AccountCashflowTests(unittest.TestCase):
    def test_known_paid_cycle_reconciles_accounts_without_claiming_profit(self):
        state={'trades':[trade('grain',2,1,3),trade('bread-a',4,2,4),trade('bread-b',4,2,4)],
            'production':[receipt('work','inventory_produce',worker=3,employer=2,wage_gold=2,
                before={'worker':{'gold':0},'employer':{'gold':7}},after={'worker':{'gold':2},'employer':{'gold':5}})]}
        before=copy.deepcopy(state);m=account_cashflow(state);rows={r['actor']:r for r in m['accounts']}
        self.assertEqual(rows[2]['sales_receipts'],8);self.assertEqual(rows[2]['purchases_paid'],3)
        self.assertEqual(rows[2]['wages_paid'],2);self.assertEqual(rows[2]['net_operating_cashflow'],3)
        self.assertEqual(rows[3]['wages_received'],2);self.assertEqual(rows[4]['net_operating_cashflow'],-8)
        self.assertEqual(m['observed_transfer_balance_septims'],0);self.assertEqual(m['record_coverage'],{'success':4,'n':4,'percent':100})
        self.assertIsNone(m['profit']);self.assertIsNone(m['accounting_period']);self.assertEqual(state,before)
        self.assertEqual(economic_network(state)['cashflow'],m)

    def test_external_grant_is_separate_from_earned_cash_and_owner_work_pays_no_wage(self):
        grant=receipt('grant','inventory_endowment',actor=2,grant={'gold':20},before={'gold':3},after={'gold':23})
        own=receipt('own','inventory_self_produce',actor=2,before={'owner':{'gold':23}},after={'owner':{'gold':23}})
        m=account_cashflow({'town':{'resource_program':{'grants':{'2':grant}}},'production':[own]})
        row=m['accounts'][0];self.assertEqual(row['net_operating_cashflow'],0);self.assertEqual(row['net_including_recorded_grants'],20)
        self.assertEqual(row['wages_received'],0);self.assertEqual(row['production_events'],1)
        self.assertEqual(m['external_grants_received_septims'],20)

    def test_uncommitted_and_malformed_receipts_cannot_mint_cashflow(self):
        valid=trade('valid',1,2,3);bad=trade('bad',1,2,3);bad['command']['after']['seller']['gold']=16
        held=trade('held',1,2,99);held['status']='held'
        m=account_cashflow({'trades':[valid,bad,held]})
        self.assertEqual(m['record_coverage'],{'success':1,'n':2,'percent':50})
        self.assertEqual(m['rejected_records'],{'invalid_trade_cash_leg':1})
        self.assertEqual(m['accounts'][0]['purchases_paid'],3)
        self.assertIsNone(account_cashflow({})['observed_transfer_balance_septims'])

    def test_duplicate_event_id_never_doubles_money_and_conflict_excludes_both(self):
        r=trade('same',1,2,3)
        m=account_cashflow({'trades':[r,copy.deepcopy(r)]})
        self.assertEqual(m['duplicate_records_excluded'],1);self.assertEqual(m['accounts'][0]['purchases_paid'],3)
        other=trade('same',1,2,4);m=account_cashflow({'trades':[r,other]})
        self.assertEqual(m['accounts'],[]);self.assertEqual(m['rejected_records'],{'conflicting_duplicate_id':1})

    def test_invalid_ids_and_disagreeing_wage_contract_stay_outside_coverage(self):
        wage=receipt('wage','inventory_produce',worker=3,employer=2,wage_gold=4,
            before={'worker':{'gold':0},'employer':{'gold':7}},after={'worker':{'gold':2},'employer':{'gold':5}})
        m=account_cashflow({'trades':[trade('bool',True,2,3)],'production':[wage]})
        self.assertEqual(m['record_coverage'],{'success':0,'n':2,'percent':0});self.assertEqual(m['accounts'],[])
        self.assertEqual(m['rejected_records'],{'invalid_trade_cash_leg':1,'invalid_wage_cash_leg':1})

    def test_independent_owner_recipe_counts_only_committed_zero_gold_exact_recipe(self):
        command=receipt('owner-commit','inventory_self_produce_commit',actor=2,
            before={'owner':{'gold':3,'bread':4,'grain':1}},after={'owner':{'gold':3,'bread':6,'grain':0}})
        state={'production':[command,copy.deepcopy(command)],'work_jobs':{'attendance':{'phase':'ready','actor':2}}}
        result=account_cashflow(state);row=result['accounts'][0]
        self.assertEqual(row['production_events'],1);self.assertEqual(row['net_operating_cashflow'],0)
        self.assertEqual(row['cash_leg_events'],0);self.assertEqual(result['duplicate_records_excluded'],1)
        self.assertEqual(result['recognized_record_kinds'],{'inventory_self_produce_commit':1})
        self.assertIsNone(result['profit'])
        self.assertEqual(account_cashflow({'work_jobs':state['work_jobs']})['accounts'],[])
        for label,alter in [('gold',lambda c:c['after']['owner'].update(gold=4)),
                            ('bread',lambda c:c['after']['owner'].update(bread=7)),
                            ('grain',lambda c:c['after']['owner'].update(grain=1)),
                            ('wage',lambda c:c.update(wage_gold=1)),
                            ('account',lambda c:c.update(custodian=3)),
                            ('missing',lambda c:c['before']['owner'].pop('grain')),
                            ('bool',lambda c:c['after']['owner'].update(gold=True))]:
            with self.subTest(label=label):
                broken=copy.deepcopy(command);alter(broken['command'])
                rejected=account_cashflow({'production':[broken]})
                self.assertEqual(rejected['accounts'],[])
                self.assertEqual(rejected['rejected_records'],{'invalid_owner_recipe_cash_leg':1})

    def test_simulation_owner_metrics_count_both_committed_protocols_not_attendance(self):
        legacy=receipt('legacy','inventory_self_produce',actor=2,
            before={'owner':{'gold':3,'bread':0,'grain':2}},after={'owner':{'gold':3,'bread':2,'grain':1}})
        modern=receipt('modern','inventory_self_produce_commit',actor=3,
            before={'owner':{'gold':4,'bread':1,'grain':1}},after={'owner':{'gold':4,'bread':3,'grain':0}})
        held=copy.deepcopy(modern);held.update(id='held',status='held')
        economy=simulation_metrics({'production':[legacy,modern,held],
            'work_jobs':{'attending':{'actor':4,'phase':'attendance_verified'}}})['economy']
        self.assertEqual(economy['owner_production_batches'],2)
        self.assertEqual(economy['gold_conservation'],{'success':2,'n':2,'percent':100.0})
