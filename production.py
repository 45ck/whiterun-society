"""A finite, explicitly authored paid bread-making contract in the physical world."""
import copy
from entrepreneurship import learn_recipe
from labour import settle_contract
from enterprises import plan_work_policy, current_work_terms, paid_bread_recipe
from activity_leases import activity_conflict
from paid_work_policy import paid_work_capability, PAID_WORK_BLOCK_REASON

from economy_catalog import commodity_ids, recipe_spec, recipe_hash, catalog_hash, apply_recipe, require_native_catalog, MAX_STOCK


def work_inventory(observation, worker, employer):
    actors = {a['id']: a for a in observation.get('residents', [])}
    result = {}
    for role, actor in [('worker', worker), ('employer', employer)]:
        inventory = actors.get(actor, {}).get('inventory', {})
        if any(type(inventory.get(k)) is not int or not 0 <= inventory[k] <= MAX_STOCK for k in commodity_ids()):
            raise ValueError('Work requires complete observed inventories')
        result[role] = {k: inventory[k] for k in commodity_ids()}
    return result


def production_receipt_matches(command, receipt):
    """A matching inventory alone cannot certify which recipe actually ran."""
    fields = ('catalog_hash',) if command.get('kind') == 'inventory_supply' else ('catalog_hash', 'recipe_id', 'recipe_hash')
    return all(isinstance(command.get(key), str) and bool(command[key]) and receipt.get(key) == command[key]
               for key in fields)


class Production:
    def setup_production(self, observation):
        self._agency_guard(observation)
        if self.agency_busy():
            raise ValueError('Finish the resident plan before scenario setup')
        if self.active.get('imports'):
            return {'duplicate': True, 'import': self.active['imports'][0]}
        if activity_conflict(self.active,actors=(108186,108149),observation=observation):
            raise ValueError('An independent activity owns a scenario supply participant')
        require_native_catalog(observation)
        before = work_inventory(observation, 108186, 108149)
        if before['employer']['grain'] > MAX_STOCK-2:raise ValueError('Scenario grain import would overflow inventory')
        after = copy.deepcopy(before)
        after['employer']['grain'] += 2
        command = {'id':'demo-grain-import-v1', 'kind':'inventory_supply',
                   'worker':108186, 'employer':108149, 'before':before, 'after':after, 'catalog_hash':catalog_hash()}
        state = copy.deepcopy(self.active)
        state['pending'] = {'id':command['id'], 'command':command, 'status':'pending',
                           'source':'Explicit demo import: two grain, no gold; not resident production', 'evidence':None}
        return {'checkpoint': self._write(state, 'explicit finite scenario grain endowment')}

    def plan_production(self, observation, plan):
        if not paid_work_capability()['available']:
            raise ValueError(PAID_WORK_BLOCK_REASON + ': paid production is unavailable pending witnessed execution')
        self._agency_guard(observation)
        if plan is not self.agency_plan() or plan['phase'] != 'ready_to_work':
            raise ValueError('Work requires a current agreed plan and arrival')
        if activity_conflict(self.active,actors=(plan['actor'],plan['target']),observation=observation):
            raise ValueError('An independent activity owns a production participant')
        require_native_catalog(observation, 'bread_recipe')
        paid_bread_recipe()
        current_work_terms(self.active, plan)
        terms = plan_work_policy(plan)
        wage = terms['wage_gold']
        before = work_inventory(observation, plan['actor'], plan['target'])
        if before['employer']['gold'] < wage or before['worker']['gold'] > MAX_STOCK-wage:
            raise ValueError('Employer no longer has the agreed input or wage')
        after = copy.deepcopy(before)
        after['employer'] = apply_recipe(before['employer'], 'bread_recipe')
        after['employer']['gold'] -= wage
        after['worker']['gold'] += wage
        command = {'id': 'produce-'+plan['id'], 'kind': 'inventory_produce',
                   'worker': plan['actor'], 'employer': plan['target'],
                   'recipe_id':'bread_recipe','catalog_hash':catalog_hash(),'recipe_hash':recipe_hash('bread_recipe'),
                   'expected_package': plan['travel']['movement']['expectedPackage'],
                   'work_minutes': terms['work_minutes'], 'wage_gold': wage, 'before': before, 'after': after}
        state = copy.deepcopy(self.active)
        state['pending'] = {'id': command['id'], 'command': command, 'status': 'pending', 'evidence': None}
        state['plans'][-1]['phase'] = 'working'
        return self._write(state, 'agreed production intent persisted before labour and inventory effects')

    def observe_production(self, observation):
        pending = self.active['pending']
        command = pending['command']
        # Inventory snapshots and cached legacy acknowledgements cannot establish
        # whether this process issued attendance, output, or wage effects.
        if command.get('kind') == 'inventory_produce':
            if pending.get('hold_reason') == PAID_WORK_BLOCK_REASON and pending.get('status') == 'held':
                return
            state = copy.deepcopy(self.active)
            state['pending'].update(status='held', hold_reason=PAID_WORK_BLOCK_REASON,
                error='Legacy paid effects are unknown; reconciliation required. Do not replay.',
                effects_issued=None, no_effects_issued=False)
            for plan in state.get('plans', []):
                if (command.get('id') == 'produce-' + str(plan.get('id'))
                        and command.get('worker') == plan.get('actor')
                        and command.get('employer') == plan.get('target')
                        and plan.get('phase') != 'complete'):
                    plan.update(phase='held', error=PAID_WORK_BLOCK_REASON)
                    terms = plan.get('work_terms') or {}
                    business = (state.get('town') or {}).get('businesses', {}).get(terms.get('business_id'))
                    if isinstance(business, dict) and isinstance(business.get('contracts'), list):
                        settle_contract(state, plan, 'reconciliation_required')
            self._write(state, 'legacy paid production quarantined without inferring inventory effects')
            return
        ack = observation.get('ack') or {}
        if ack.get('id') != pending['id']:
            return
        command = pending['command']
        try:
            if not production_receipt_matches(command, ack):
                raise ValueError('Production receipt catalog or recipe binding is missing or mismatched')
            require_native_catalog(observation, 'bread_recipe' if command['kind']=='inventory_produce' else None)
            if command.get('catalog_hash') != catalog_hash():raise ValueError('Historical production intent lacks matching catalog proof')
            if command['kind']=='inventory_produce' and (command.get('recipe_id') != 'bread_recipe' or command.get('recipe_hash') != recipe_hash('bread_recipe')):
                raise ValueError('Production recipe proof is absent or stale')
            if command['kind']=='inventory_produce':paid_bread_recipe()
            actual = work_inventory(observation, command['worker'], command['employer'])
        except ValueError as error:
            if pending.get('status')!='held':
                state=copy.deepcopy(self.active);state['pending'].update(status='held',error=str(error))
                if command['kind']=='inventory_produce':
                    state['plans'][-1].update(phase='held',error='Production catalog requires reconciliation')
                    settle_contract(state,state['plans'][-1],'reconciliation_required')
                self._write(state,'production held: catalog or inventory proof is unavailable')
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
            if state['plans'][-1].get('employment_dialogue'):
                self.queue_trade_speech(state,state['plans'][-1],'work_receipt')
            for role, other in [('worker', 'employer'), ('employer', 'worker')]:
                person = state['people'][str(command[role])]
                learn_recipe(person,pending['id'],command['recipe_id'])
                recipe=recipe_spec(command['recipe_id'])
                person['memories'].append({'event_id': pending['id'], 'kind': 'paid_work',
                    'role': role, 'other': command[other], 'gold': command.get('wage_gold', 2),
                    'work_minutes': command['work_minutes'], 'recipe_id':command['recipe_id'],
                    'inputs':recipe['inputs'],'outputs':recipe['outputs'],
                    'grain_used':recipe['inputs']['grain'],'bread_made':recipe['outputs']['bread'],
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
