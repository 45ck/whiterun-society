"""Save-bound event plans. Models select allowed intentions, never native commands.

This mixin shares TimelineEconomy's immutable checkpoint protocol. Inference runs
in a separate worker; a persisted claim prevents automatic duplicate model calls.
"""
import copy
import math
import secrets
from decisions import validate_decision
from food import allocation

TERMINAL = ('complete', 'held')


def distance(observation, first, second):
    actors = {a['id']: a for a in observation.get('residents', [])}
    try:
        result = math.dist([actors[first][k] for k in ('x', 'y', 'z')],
                           [actors[second][k] for k in ('x', 'y', 'z')])
    except (KeyError, TypeError, ValueError):
        raise ValueError('Both residents must have observed positions')
    if not math.isfinite(result):
        raise ValueError('Invalid observed positions')
    return result


class Agency:
    def agency_plan(self):
        plans = self.active.get('plans', []) if self.active else []
        return plans[-1] if plans else None

    def agency_busy(self):
        plan = self.agency_plan()
        return bool(plan and (plan['phase'] not in TERMINAL or plan.get('release_required')))

    def _agency_guard(self, observation):
        if self.error or not self.active or self.transition or self.active['pending']:
            raise ValueError('Society must be synchronized without an unsettled trade')
        if observation.get('session') != self.session or observation.get('checkpoint') != self.marker:
            raise ValueError('Observation belongs to another save checkpoint')

    def begin_plan(self, event_id, observation, actor=108186, kind='meal_time'):
        self._agency_guard(observation)
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 64:
            raise ValueError('A bounded event ID is required')
        if kind not in ('meal_time','stock_review') or type(actor) is not int or str(actor) not in self.active['people']:
            raise ValueError('Unsupported resident or event kind')
        for plan in self.active.get('plans', []):
            if plan['id'] == event_id:
                if plan['actor'] != actor or plan['kind'] != kind:
                    raise ValueError('Event ID reused for another resident or kind')
                return {'duplicate': True, 'plan': plan}
        if self.agency_busy():
            raise ValueError('Another resident plan is active')
        state = copy.deepcopy(self.active)
        person = state['people'][str(actor)]
        # Authored meal-time simulation event, explicitly not a Skyrim hunger reading.
        if kind=='meal_time':
            person['needs']['hunger'] = min(1, person['needs']['hunger'] + .35)
        plan = {'id': event_id, 'kind': kind, 'actor': actor, 'phase': 'allocate' if kind=='stock_review' else 'choose',
                'decisions': [], 'claim': None, 'travel': None, 'trade_id': 'meal-' + event_id,
                'unit_price': 3, 'refusals_recorded': 0, 'food_actions': True}
        state.setdefault('plans', []).append(plan)
        return {'checkpoint': self._write(state, kind+' triggered resident planning'), 'plan': plan}

    def _plan_context(self, observation, plan):
        seller_turn = plan['phase'] == 'consent'
        reconsidering = plan['phase'] == 'reconsider'
        price = plan.get('unit_price', 3)
        actor = plan['target'] if seller_turn else plan['actor']
        actors = {a['id']: a for a in observation.get('residents', [])}
        if actor not in actors or plan['actor'] not in actors:
            raise ValueError('Decision participants are not observed')
        person = self.active['people'][str(actor)]
        inventory = actors[actor]['inventory']
        if any(type(inventory.get(k)) is not int or inventory[k] < 0 for k in ('gold', 'bread')):
            raise ValueError('Invalid observed inventory')
        stock = allocation(person, inventory)
        if plan['phase']=='allocate':
            options = [{'id':'reserve_all','effect':'Keep all carried bread for your household. None is offered for sale until you review this policy again.'},
                       {'id':'reserve_one','effect':'Keep up to one carried loaf for your household; earmark any surplus for sale. You may still refuse individual offers.'},
                       {'id':'reserve_two','effect':'Keep up to two carried loaves for your household; earmark any surplus for sale. You may still refuse individual offers.'}]
            information = 'Review how to use your currently carried bread, balancing your household and livelihood. This allocates existing goods only; no unobserved food at home is invented.'
        elif plan['phase']=='after_purchase':
            options = [{'id':'keep_food','effect':'Keep the purchased loaf for later; hunger does not improve just by owning food.'}]
            if inventory['bread']>0:
                options.append({'id':'eat_bread','effect':'Consume one carried loaf now; it leaves inventory and reduces your simulated hunger.'})
            information = 'Your purchase was verified. Decide whether to eat now or save the food for later.'
        elif seller_turn:
            if distance(observation, actor, plan['actor']) > 300:
                raise ValueError('Buyer is no longer within interaction range')
            options = [{'id': 'decline', 'effect': 'Decline the request; keep your goods.'}]
            if inventory['bread'] > 0 and (not stock['allocated'] or stock['for_sale']>0):
                options.append({'id': 'sell_bread', 'effect': f'Agree to sell one carried loaf for {price} gold to the nearby buyer.'})
            buyer_name=self.active['people'][str(plan['actor'])]['profile']['name']
            information = f'{buyer_name} is nearby and offers {price} gold for one loaf. Choose freely whether to sell. Refusal does not reveal your motive to the buyer.'
        elif reconsidering:
            options = [{'id': 'leave_without_food', 'effect': 'End this negotiation without buying food; preserve your money and leave the seller alone.'}]
            if actor!=108156:
                options.append({'id': 'visit_adrianne', 'effect': 'End this negotiation and visit Adrianne instead; travel only, no purchase or conversation yet.'})
            if price == 3 and inventory['gold'] >= 5 and distance(observation, actor, plan['target']) <= 300:
                options.append({'id': 'raise_offer', 'effect': 'Make one final offer of 5 gold for one loaf instead of 3. Pay only if the seller agrees; she may refuse again.'})
            information = 'Carlotta just declined your 3-gold offer. Her reason is unknown. Reconsider your plan using this outcome, your needs, resources and priorities; repeating the unchanged request is not an available action in this bounded negotiation.'
        else:
            options = [{'id': 'defer', 'effect': 'Postpone this errand; no travel or purchase.'}]
            if inventory['bread'] > 0:
                options.append({'id':'eat_bread','effect':'Consume one carried loaf now; it leaves inventory and reduces your simulated hunger.'})
            if actor!=108156:
                options.append({'id': 'visit_adrianne', 'effect': 'Visit Adrianne instead; travel only, no purchase or conversation yet.'})
            if actor!=108149 and inventory['gold'] >= 3 and inventory['bread'] == 0:
                options.append({'id': 'seek_bread', 'effect': 'Walk to Carlotta and ask to buy one loaf for 3 gold. She may refuse.'})
            information = 'Meal time: consider your hunger, carried food, money, priorities and past experiences. This does not prove what food you have at home.'
        return {'actor_id': actor, 'profile': person['profile'], 'session': self.session,
                'event': {'id': plan['id'], 'kind': plan['kind'], 'information': information},
                'observed_inventory': copy.deepcopy(inventory),
                'own_food_allocation': stock,
                'scenario_state': {'needs': person['needs'], 'source': 'authored society simulation, not Skyrim hunger'},
                'perception': self._resident_perception(observation, actor),
                'prior_knowledge': 'Authored starting knowledge: Carlotta is a produce merchant; Adrianne is a blacksmith. The 3-gold initial offer and 5-gold final offer are demo assumptions, not discovered market prices. Other residents\' private inventories are not known.',
                'memories': person['memories'][-8:], 'trust': person['trust'], 'options': options}

    @staticmethod
    def _resident_perception(observation, actor):
        sensor = observation.get('perception', {}).get(str(actor), {})
        if not sensor.get('available'):
            return {'available': False, 'information': 'Vision is unavailable; this does not mean nobody is nearby.'}
        return {'available': True, 'visible': copy.deepcopy(sensor.get('visible', []))}

    def claim_plan_decision(self, event_id, observation):
        self._agency_guard(observation)
        plan = self.agency_plan()
        if not plan or plan['id'] != event_id or plan['phase'] not in ('choose', 'consent', 'reconsider', 'allocate', 'after_purchase'):
            raise ValueError('No unclaimed decision is ready')
        context = self._plan_context(observation, plan)
        state = copy.deepcopy(self.active)
        updated = state['plans'][-1]
        updated['claim'] = {'id': secrets.token_hex(12), 'stage': plan['phase'], 'context': context}
        updated['phase'] = 'thinking'
        return {'checkpoint': self._write(state, 'model call claimed before inference'), 'claim': updated['claim']}

    def finish_plan_decision(self, event_id, claim_id, result, observation):
        self._agency_guard(observation)
        plan = self.agency_plan()
        if not plan or plan['id'] != event_id or plan['phase'] != 'thinking' or plan['claim']['id'] != claim_id:
            raise ValueError('Decision claim is not current')
        claim = plan['claim']
        if claim['context']['session'] != self.session:
            raise ValueError('Decision belongs to an earlier game session')
        context_plan = {**plan, 'phase': claim['stage']}
        current = self._plan_context(observation, context_plan)
        decision = validate_decision(result['decision'], current)
        if current['observed_inventory'] != claim['context']['observed_inventory']:
            raise ValueError('Inventory changed while deciding')
        state = copy.deepcopy(self.active)
        updated = state['plans'][-1]
        updated['decisions'].append({'actor_id': current['actor_id'], 'context': claim['context'],
            'decision': decision, 'model': str(result.get('model', 'unknown'))[:100],
            'elapsed_seconds': result.get('elapsed_seconds'), 'claim_id': claim_id,
            'rationale_kind': result.get('rationale_kind','model_public_rationale'),
            'probabilities': result.get('probabilities',{}), 'usage': result.get('usage',{})})
        updated['claim'] = None
        action = decision['action_id']
        if action in ('seek_bread', 'visit_adrianne'):
            travel_id = 'travel-' + event_id
            if updated.get('travel'):
                updated.setdefault('travel_history', []).append(updated['travel'])
                updated['travel'] = None
                travel_id += '-replan-' + str(len(updated['decisions']))
            updated.update(phase='travelling', target=108149 if action == 'seek_bread' else 108156,
                           intent=action, travel_id=travel_id, release_required=True)
        elif action == 'raise_offer':
            updated.update(phase='consent', unit_price=5)
        elif action == 'sell_bread':
            updated['phase'] = 'ready_to_trade'
        elif action == 'decline':
            self._remember_refusal(state, updated)
            if updated.get('unit_price', 3) == 3:
                updated['phase'] = 'reconsider'
            else:
                updated.update(phase='complete', outcome='seller_declined')
        elif action == 'leave_without_food':
            updated.update(phase='complete', outcome='left_without_food')
        elif action in ('reserve_all','reserve_one','reserve_two'):
            state['people'][str(plan['actor'])]['food_policy'] = {
                'mode':'household_all' if action=='reserve_all' else 'fixed_reserve',
                'reserve_target':{'reserve_all':0,'reserve_one':1,'reserve_two':2}[action],
                'source_event':event_id, 'source':'resident selected among authored allocation policies'}
            updated.update(phase='complete',outcome='allocated_stock')
        elif action == 'eat_bread':
            updated['phase']='ready_to_eat'
        elif action == 'keep_food':
            updated.update(phase='complete',outcome='bought_bread')
        else:
            updated.update(phase='complete', outcome='deferred')
        return {'checkpoint': self._write(state, 'resident decision accepted'), 'plan': updated}

    @staticmethod
    def _remember_refusal(state, plan):
        for actor, other, role in [(plan['actor'], plan['target'], 'buyer'),
                                   (plan['target'], plan['actor'], 'seller')]:
            person = state['people'][str(actor)]
            person['memories'].append({'event_id': plan['id'], 'kind': 'trade_offer_declined',
                'other': other, 'role': role, 'bread': 1, 'gold': plan.get('unit_price', 3),
                'source': 'agent consent decision, not spoken dialogue'})
            person['memories'] = person['memories'][-32:]
        plan['refusals_recorded'] = plan.get('refusals_recorded', 0) + 1

    def hold_plan(self, event_id, reason, observation):
        self._agency_guard(observation)
        plan = self.agency_plan()
        if not plan or plan['id'] != event_id or plan['phase'] in TERMINAL:
            raise ValueError('No active matching plan')
        state = copy.deepcopy(self.active)
        state['plans'][-1].update(phase='held', error=str(reason)[:240])
        return {'checkpoint': self._write(state, 'resident plan held for review')}

    def _agency_observe(self, observation):
        plan = self.agency_plan()
        ack = observation.get('ack') or {}
        if plan and plan['phase'] in TERMINAL and plan.get('release_required'):
            if ack.get('id') == 'release-' + plan['id'] and ack.get('status') == 'applied':
                state = copy.deepcopy(self.active)
                state['plans'][-1]['release_required'] = False
                self._write(state, 'resident task release observed')
            return
        if plan and plan['phase'] in TERMINAL and not plan.get('remembered'):
            state=copy.deepcopy(self.active)
            updated=state['plans'][-1]
            if plan.get('outcome')=='seller_declined' and not plan.get('refusals_recorded'):
                self._remember_refusal(state, updated)
            elif plan.get('outcome') in ('deferred','visited_only','left_without_food'):
                person=state['people'][str(plan['actor'])]
                person['memories'].append({'event_id':plan['id'],'kind':plan['outcome'],
                    'other':plan.get('target'),'source':'observed arrival, not conversation' if plan['outcome']=='visited_only' else 'own decision'})
                person['memories']=person['memories'][-32:]
            elif plan.get('outcome')=='allocated_stock':
                person=state['people'][str(plan['actor'])]
                person['memories'].append({'event_id':plan['id'],'kind':'allocated_food',
                    'policy':copy.deepcopy(person['food_policy']),'source':'own allocation decision; no inventory change'})
                person['memories']=person['memories'][-32:]
            updated['remembered']=True
            self._write(state,'resident remembers the observed plan outcome')
            return
        if not plan or plan['phase'] in TERMINAL:
            return
        if plan['phase'] == 'thinking' and plan['claim']['context']['session'] != self.session:
            self.hold_plan(plan['id'], 'Game session changed during inference; do not repeat the claimed call', observation)
        elif plan['phase'] == 'travelling':
            ack = observation.get('ack') or {}
            if ack.get('id') != plan['travel_id']:
                return
            movement = ack.get('movement') or {}
            try:
                arrived = distance(observation, plan['actor'], plan['target']) <= 300
            except ValueError:
                arrived = False
            state = copy.deepcopy(self.active)
            updated = state['plans'][-1]
            updated['travel'] = copy.deepcopy(ack)
            if ack.get('status') == 'applied' and movement.get('hasOwnedPackage') and arrived:
                updated['phase'] = 'consent' if plan['intent'] == 'seek_bread' else 'complete'
                if updated['phase'] == 'complete':
                    updated['outcome'] = 'visited_only'
            else:
                updated.update(phase='held', error='Travel did not establish owned arrival')
            self._write(state, 'resident travel outcome observed')
        elif plan['phase'] == 'ready_to_trade':
            try:
                if distance(observation, plan['actor'], plan['target']) > 300:
                    raise ValueError('Participants separated before exchange')
                self.plan_trade(plan['trade_id'], observation, plan['actor'], plan['target'],
                                unit_price=plan.get('unit_price', 3), agency_plan=plan['id'])
            except ValueError as error:
                self.hold_plan(plan['id'], str(error), observation)
        elif plan['phase'] == 'ready_to_eat':
            try:
                self.plan_consumption('consume-'+plan['id'], observation, plan['actor'], plan['id'])
            except ValueError as error:
                self.hold_plan(plan['id'], str(error), observation)

    def agency_command(self, session):
        plan = self.agency_plan()
        if plan and plan['phase'] in TERMINAL and plan.get('release_required'):
            return {'id': 'release-' + plan['id'], 'kind': 'release_routine', 'actor': plan['actor'],
                    'session': session, 'checkpoint': self.marker}
        if not plan or plan['phase'] != 'travelling':
            return None
        return {'id': plan['travel_id'], 'kind': 'walk_to', 'actor': plan['actor'], 'target': plan['target'],
                'method': 'package', 'origin': 'resident_decision', 'plan_id': plan['id'], 'retain': True,
                'session': session, 'checkpoint': self.marker}
