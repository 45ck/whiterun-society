"""A finite, explicitly authored paid bread-making contract in the physical world."""
import copy
from labour import settle_contract
from enterprises import plan_work_policy, current_work_terms

ITEMS = ('gold', 'bread', 'grain')


def work_inventory(observation, worker, employer):
    actors = {a['id']: a for a in observation.get('residents', [])}
    result = {}
    for role, actor in [('worker', worker), ('employer', employer)]:
        inventory = actors.get(actor, {}).get('inventory', {})
        if any(type(inventory.get(k)) is not int or inventory[k] < 0 for k in ITEMS):
            raise ValueError('Work requires complete observed inventories')
        result[role] = {k: inventory[k] for k in ITEMS}
    return result


class Production:
    def setup_production(self, observation):
        self._agency_guard(observation)
        if self.agency_busy():
            raise ValueError('Finish the resident plan before scenario setup')
        if self.active.get('imports'):
            return {'duplicate': True, 'import': self.active['imports'][0]}
        before = work_inventory(observation, 108186, 108149)
        after = copy.deepcopy(before)
        after['employer']['grain'] += 2
        command = {'id':'demo-grain-import-v1', 'kind':'inventory_supply',
                   'worker':108186, 'employer':108149, 'before':before, 'after':after}
        state = copy.deepcopy(self.active)
        state['pending'] = {'id':command['id'], 'command':command, 'status':'pending',
                           'source':'Explicit demo import: two grain, no gold; not resident production', 'evidence':None}
        return {'checkpoint': self._write(state, 'explicit finite scenario grain endowment')}

    def plan_production(self, observation, plan):
        self._agency_guard(observation)
        if plan is not self.agency_plan() or plan['phase'] != 'ready_to_work':
            raise ValueError('Work requires a current agreed plan and arrival')
        current_work_terms(self.active, plan)
        terms = plan_work_policy(plan)
        wage = terms['wage_gold']
        before = work_inventory(observation, plan['actor'], plan['target'])
        if before['employer']['grain'] < 1 or before['employer']['gold'] < wage:
            raise ValueError('Employer no longer has the agreed input or wage')
        after = copy.deepcopy(before)
        after['employer']['grain'] -= 1
        after['employer']['bread'] += 2
        after['employer']['gold'] -= wage
        after['worker']['gold'] += wage
        command = {'id': 'produce-'+plan['id'], 'kind': 'inventory_produce',
                   'worker': plan['actor'], 'employer': plan['target'],
                   'expected_package': plan['travel']['movement']['expectedPackage'],
                   'work_minutes': terms['work_minutes'], 'wage_gold': wage, 'before': before, 'after': after}
        state = copy.deepcopy(self.active)
        state['pending'] = {'id': command['id'], 'command': command, 'status': 'pending', 'evidence': None}
        state['plans'][-1]['phase'] = 'working'
        return self._write(state, 'agreed production intent persisted before labour and inventory effects')

    def observe_production(self, observation):
        pending = self.active['pending']
        ack = observation.get('ack') or {}
        if ack.get('id') != pending['id']:
            return
        command = pending['command']
        try:
            actual = work_inventory(observation, command['worker'], command['employer'])
        except ValueError:
            return
        state = copy.deepcopy(self.active)
        state['pending']['evidence'] = {'actual': actual, 'ack': ack, 'session': self.session}
        if ack.get('status') == 'applied' and actual == command['after']:
            record = state['pending']
            record['status'] = 'committed'
            field = 'imports' if command['kind']=='inventory_supply' else 'production'
            state.setdefault(field, []).append(record)
            state['pending'] = None
            if field == 'imports':
                self._write(state, 'explicit imported grain observed; no wage or production claimed')
                return
            state['plans'][-1].update(phase='complete', outcome='paid_work_completed')
            settle_contract(state, state['plans'][-1], 'paid_work_completed')
            for role, other in [('worker', 'employer'), ('employer', 'worker')]:
                person = state['people'][str(command[role])]
                person['memories'].append({'event_id': pending['id'], 'kind': 'paid_work',
                    'role': role, 'other': command[other], 'gold': command.get('wage_gold', 2),
                    'work_minutes': command['work_minutes'], 'grain_used': 1, 'bread_made': 2,
                    'source': 'observed native inventory conversion and wage; work animation unverified'})
                person['memories'] = person['memories'][-32:]
            self._write(state, 'production and conserved wage observed; both residents remember')
        elif (command['kind']=='inventory_produce' and ack.get('status')=='held'
              and ack.get('no_effects_issued') is True and actual==command['before']):
            record=state['pending']
            record.update(status='cancelled',outcome='interrupted_before_effects')
            state.setdefault('cancelled_production',[]).append(record)
            state['pending']=None
            state['plans'][-1].update(phase='complete',outcome='work_interrupted',
                interruption=ack.get('error','Work stopped before inventory effects'))
            settle_contract(state,state['plans'][-1],'work_interrupted')
            for role, other in [('worker','employer'),('employer','worker')]:
                person=state['people'][str(command[role])]
                person['memories'].append({'event_id':pending['id'],'kind':'interrupted_work',
                    'role':role,'other':command[other],'gold_paid':0,'bread_made':0,
                    'source':'Native no-effect attestation and unchanged observed inventories'})
                person['memories']=person['memories'][-32:]
            self._write(state,'interrupted work recorded with no native effects; no wage or output claimed')
        else:
            state['pending']['status'] = 'held'
            if command['kind']=='inventory_produce':
                state['plans'][-1].update(phase='held', error='Work requires reconciliation; do not retry blindly')
                settle_contract(state, state['plans'][-1], 'reconciliation_required')
            self._write(state, 'unexpected production effect held for reconciliation')
