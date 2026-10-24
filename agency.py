"""Save-bound event plans. Models select allowed intentions, never native commands.

This mixin shares TimelineEconomy's immutable checkpoint protocol. Inference runs
in a separate worker; a persisted claim prevents automatic duplicate model calls.
"""
import copy
import math
import secrets
from decisions import validate_decision
from food import allocation
from production import work_inventory
from market_day import event_for
from routing import route_available, dynamic_route
from labour import work_opportunities, settle_contract
from rest import rest_opportunities
from places import MARKET, market_opportunity, at_market
from opportunities import food_sellers
from knowledge import person_view
from social import social_candidates
from enterprises import plan_work_policy, current_work_terms

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

    def _agency_guard(self, observation, allow_routines=False):
        if not allow_routines and self.routines_busy():
            raise ValueError('An independent routine cohort owns these daily opportunities')
        if self.error or not self.active or self.transition or self.active['pending']:
            raise ValueError('Society must be synchronized without an unsettled trade')
        if observation.get('session') != self.session or observation.get('checkpoint') != self.marker:
            raise ValueError('Observation belongs to another save checkpoint')

    def begin_plan(self, event_id, observation, actor=108186, kind='meal_time'):
        self._agency_guard(observation)
        if self.conversation_busy():
            raise ValueError('A conversation owns the participants')
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 64:
            raise ValueError('A bounded event ID is required')
        if kind not in ('meal_time','stock_review','work_shift','need_review') or type(actor) is not int or str(actor) not in self.active['people']:
            raise ValueError('Unsupported resident or event kind')
        for plan in self.active.get('plans', []):
            if plan['id'] == event_id:
                if plan['actor'] != actor or plan['kind'] != kind:
                    raise ValueError('Event ID reused for another resident or kind')
                return {'duplicate': True, 'plan': plan}
        scenario=self.active.get('market_day')
        if scenario and scenario['status']!='complete':
            expected=event_for(scenario)
            if not expected or (event_id,actor,kind)!=(expected['id'],expected['actor'],expected['kind']):
                raise ValueError('The market-day sequence owns the next resident event')
        if self.agency_busy():
            raise ValueError('Another resident plan is active')
        state = copy.deepcopy(self.active)
        person = state['people'][str(actor)]
        event=next((e for e in state.get('town',{}).get('daily',{}).get('queue',[]) if e['id']==event_id),None)
        scheduled = kind=='need_review' or event is not None
        if scheduled:
            if not event or event['actor']!=actor or event['kind']!=kind or event['status']!='pending':
                raise ValueError('A matching pending daily opportunity is required')
            if not any(a.get('id')==actor and a.get('isPerson') is True for a in observation.get('residents',[])):
                raise ValueError('Scheduled resident is no longer observed')
            event['status']='started'
            person['agency']['state']='deciding'
        # Authored meal-time simulation event, explicitly not a Skyrim hunger reading.
        if kind=='meal_time':
            person['needs']['hunger'] = min(1, person['needs']['hunger'] + .35)
        plan = {'id': event_id, 'kind': kind, 'actor': actor, 'phase': 'allocate' if kind=='stock_review' else 'choose',
                'decisions': [], 'claim': None, 'travel': None, 'trade_id': 'meal-' + event_id,
                'unit_price': 3, 'refusals_recorded': 0, 'food_actions': True}
        if scheduled:plan['scheduled']=True
        state.setdefault('plans', []).append(plan)
        if kind == 'work_shift':
            jobs = work_opportunities(state, observation, actor)
            if jobs:
                plan.update(phase='job_offer', target=jobs[0]['employer'], work_terms=jobs[0])
            elif actor == 108186 and not state.get('town'):
                plan.update(phase='job_offer', target=108149)  # Original standalone demo.
            else:
                raise ValueError('No feasible paid-work opportunity for this resident')
        return {'checkpoint': self._write(state, kind+' triggered resident planning'), 'plan': plan}

    def _plan_context(self, observation, plan):
        seller_turn = plan['phase'] == 'consent'
        reconsidering = plan['phase'] == 'reconsider'
        price = plan.get('unit_price', 3)
        actor = plan['target'] if seller_turn or plan['phase']=='job_offer' else plan['actor']
        actors = {a['id']: a for a in observation.get('residents', [])}
        if actor not in actors or plan['actor'] not in actors:
            raise ValueError('Decision participants are not observed')
        person = self.active['people'][str(actor)]
        inventory = actors[actor]['inventory']
        if any(type(inventory.get(k)) is not int or inventory[k] < 0 for k in ('gold', 'bread')):
            raise ValueError('Invalid observed inventory')
        stock = allocation(person, inventory)
        targets = {}
        work_options = {}
        if plan['phase'] in ('job_offer', 'job_accept'):
            current_work_terms(self.active, plan)
        policy = plan_work_policy(plan)
        wage, minutes = policy['wage_gold'], policy['work_minutes']
        def visits():
            if self.active.get('town') is None:
                rows=[{'id':108156,'name':'Adrianne','action':'visit_adrianne'}] if route_available(observation,actor,108156) else []
            else:
                rows=[{**r,'action':'visit_person_'+str(r['id'])} for r in social_candidates(self.active,observation,actor)]
            for row in rows:
                targets[row['action']]=row['id']
            return [{'id':r['action'],'effect':'Visit '+r['name']+'; travel only, no purchase or conversation is implied.'} for r in rows]
        if plan['phase']=='job_offer':
            options = [{'id':'defer','effect':'Do not offer this job; keep your resources.'}]
            resources = work_inventory(observation, plan['actor'], plan['target'])
            if resources['employer']['grain'] >= 1 and resources['employer']['gold'] >= wage:
                worker_name = person_view(self.active,actor,plan['actor'])['name']
                options.append({'id':'offer_shift','effect':f'Offer {worker_name} {wage} gold from your purse to convert one of your grain into two loaves. They may refuse. Pay only after {minutes} game minutes of qualified work and observed production.'})
            information = f'Consider paid bread-making to replenish your stock toward your enterprise target of {policy["target_bread"]} loaves. The recipe is authored; no oven animation is implemented. Your household reserve applies to output. Two loaves might bring six gold at the initial asking price, but sales are not guaranteed, wages cost {wage} gold and grain has an opportunity cost. Keep your money if replenishing is not worthwhile.'
        elif plan['phase']=='job_accept':
            employer_name = person_view(self.active,actor,plan['target'])['name']
            options = [{'id':'decline_work','effect':'Decline the job. No goods or wages change hands.'},
                       {'id':'take_shift','effect':f'Accept {employer_name}\'s offer: walk to the employer, spend {minutes} game minutes on simulated bread-making work and receive {wage} gold after the output is verified. You supply labour, not grain or money.'}]
            information = f'{employer_name} offers you a paid job: {wage} gold for {minutes} game minutes of bread-making work at their location. Consider fatigue, food, other priorities and your memories. You can refuse; the employer\'s private inventory is not known.'
        elif plan['phase']=='allocate':
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
            buyer_name=person_view(self.active,actor,plan['actor'])['name']
            information = f'{buyer_name} is nearby and offers {price} gold for one loaf. Choose freely whether to sell. Refusal does not reveal your motive to the buyer.'
        elif reconsidering:
            options = [{'id': 'leave_without_food', 'effect': 'End this negotiation without buying food; preserve your money and leave the seller alone.'}]
            options += visits()
            if price == 3 and inventory['gold'] >= 5 and distance(observation, actor, plan['target']) <= 300:
                options.append({'id': 'raise_offer', 'effect': 'Make one final offer of 5 gold for one loaf instead of 3. Pay only if the seller agrees; she may refuse again.'})
            information = 'The seller just declined your 3-gold offer. Their reason is unknown. Reconsider your plan using this outcome, your needs, resources and priorities; repeating the unchanged request is not an available action in this bounded negotiation.'
        else:
            options = [{'id': 'defer', 'effect': 'Postpone this errand; no travel or purchase.'}]
            if inventory['bread'] > 0:
                options.append({'id':'eat_bread','effect':'Consume one carried loaf now; it leaves inventory and reduces your simulated hunger.'})
            options += visits()
            sellers=food_sellers(self.active,observation,actor)
            if sellers and inventory['gold'] >= 3 and inventory['bread'] == 0:
                for i,seller in enumerate(sellers[:6]):
                    action='seek_bread' if i==0 else 'seek_bread_'+str(seller['id'])
                    targets[action]=seller['id']
                    options.append({'id':action,'effect':'Walk to '+seller['name']+', a publicly registered food seller, and offer 3 gold for one loaf. Stock is unknown and they may refuse.'})
            elif inventory['gold'] >= 3 and inventory['bread'] == 0 and market_opportunity(self.active,observation,actor):
                options.append({'id':'check_market','effect':'Walk to the known public market to look for a food seller. Presence and stock are unknown. If a registered food seller is nearby on arrival, offer 3 gold for a loaf; otherwise remember the unsuccessful visit. No food or wage is guaranteed.'})
            if plan['kind']=='need_review':
                for i, job in enumerate(work_opportunities(self.active, observation, actor)[:6]):
                    action = 'seek_work' if i == 0 else 'seek_work_' + job['business_id']
                    work_options[action] = job
                    targets[action] = job['employer']
                    terms = job['policy']
                    options.append({'id': action, 'effect': f'Ask {job["employer_name"]} about an advertised {terms["work_minutes"]}-game-minute bread-making shift paying {terms["wage_gold"]} gold. The employer must offer and you must accept. No wage is guaranteed.'})
            if plan['kind']=='need_review' and person['needs'].get('fatigue',0)>=.6 and rest_opportunities(self.active,observation,actor):
                options.append({'id':'rest_at_bench','effect':'Take a 30-game-minute seated break at an available nearby bench. Walk there and recover some simulated fatigue only after verified sitting. This interrupts your ordinary routine; consider duties and other needs. It is a short break, not sleep.'})
            information = 'Consider your hunger, fatigue, carried food, money, priorities and past experiences. You may defer, eat, seek food or explore an available livelihood opportunity. This does not prove what food you have at home.'
        return {'actor_id': actor, 'profile': person['profile'], 'session': self.session,
                'event': {'id': plan['id'], 'kind': plan['kind'], 'information': information},
                'observed_inventory': copy.deepcopy(inventory),
                'own_food_allocation': stock,
                'scenario_state': {'needs': person['needs'], 'source': 'authored society simulation, not Skyrim hunger'},
                'perception': self._resident_perception(observation, actor),
                'prior_knowledge': 'Public enterprise charters identify advertised services, not personal names, private stock or willingness. Names require personal knowledge. The 3-gold initial offer and 5-gold final offer are authored starting assumptions, not discovered market prices.',
                'memories': person['memories'][-8:], 'trust': person['trust'],
                'my_relationships':person.get('relationships',{}), 'option_targets':targets,
                'work_options':work_options, 'options': options}

    def _resident_perception(self, observation, actor):
        sensor = observation.get('perception', {}).get(str(actor), {})
        if not sensor.get('available'):
            return {'available': False, 'information': 'Vision is unavailable; this does not mean nobody is nearby.'}
        return {'available': True, 'visible': [
            {**person_view(self.active,actor,row['id']), 'distance':row.get('distance')}
            for row in sensor.get('visible',[]) if type(row.get('id')) is int]}

    def claim_plan_decision(self, event_id, observation):
        self._agency_guard(observation)
        plan = self.agency_plan()
        if not plan or plan['id'] != event_id or plan['phase'] not in ('choose', 'consent', 'reconsider', 'allocate', 'after_purchase', 'job_offer', 'job_accept'):
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
        chosen=decision['action_id']
        if current.get('option_targets',{}).get(chosen)!=claim['context'].get('option_targets',{}).get(chosen):
            raise ValueError('The chosen destination changed while deciding')
        if current.get('work_options',{}).get(chosen)!=claim['context'].get('work_options',{}).get(chosen):
            raise ValueError('The chosen employment terms changed while deciding')
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
        if action == 'check_market':
            site=market_opportunity(self.active,observation,updated['actor'])
            if not site:raise ValueError('The known public destination is no longer executable')
            updated.update(phase='travelling',target=MARKET,target_kind='place',destination=site,
                intent=action,travel_id='travel-'+event_id,dynamic_route=True,release_required=True)
        elif action == 'rest_at_bench':
            sites=rest_opportunities(self.active,observation,updated['actor'])
            if not sites:raise ValueError('No available rest site remains')
            updated.update(phase='ready_to_rest',rest_target=sites[0]['id'])
        elif action == 'seek_work' or action.startswith('seek_work_'):
            job = current['work_options'][action]
            updated.update(phase='job_offer', target=job['employer'], work_terms=job)
        elif action == 'offer_shift':
            updated['phase'] = 'job_accept'
        elif action == 'decline_work':
            updated.update(phase='complete', outcome='work_declined')
        elif action in ('seek_bread', 'visit_adrianne', 'take_shift') or action.startswith(('seek_bread_', 'visit_person_')):
            travel_id = 'travel-' + event_id
            if updated.get('travel'):
                updated.setdefault('travel_history', []).append(updated['travel'])
                updated['travel'] = None
                travel_id += '-replan-' + str(len(updated['decisions']))
            target = updated['target'] if action == 'take_shift' else current['option_targets'][action]
            if action == 'take_shift' and updated.get('work_terms'):
                terms = updated['work_terms']
                state['town']['businesses'][terms['business_id']]['contracts'].append({
                    'id':event_id,'worker':updated['actor'],'employer':target,'status':'accepted',
                    'terms':copy.deepcopy(terms['policy']), 'source':'Employer offer and worker consent; no completed work yet'})
            updated.update(phase='travelling', target=target,
                           intent='seek_bread' if action.startswith('seek_bread') else action, travel_id=travel_id, release_required=True)
            updated['dynamic_route']=dynamic_route(updated['actor'],updated['target'])
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
                'reviewed_day':observation.get('gameDays'), 'observed_bread':current['observed_inventory']['bread'],
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
        if not plan['decisions'] and not plan.get('travel') and not plan.get('release_required'):
            state['plans'][-1].update(outcome='interrupted_before_action', effect_free_hold=True)
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
            elif plan.get('outcome') in ('deferred','visited_only','left_without_food','work_declined'):
                decision_actor=plan['decisions'][-1]['actor_id'] if plan.get('decisions') else plan['actor']
                person=state['people'][str(decision_actor)]
                other=plan['actor'] if decision_actor==plan.get('target') else plan.get('target')
                person['memories'].append({'event_id':plan['id'],'kind':plan['outcome'],
                    'other':other,'source':'observed arrival, not conversation' if plan['outcome']=='visited_only' else 'own decision'})
                person['memories']=person['memories'][-32:]
            elif plan.get('outcome')=='market_seller_not_observed':
                person=state['people'][str(plan['actor'])]
                person['memories'].append({'event_id':plan['id'],'kind':plan['outcome'],
                    'place':MARKET,'day':observation.get('gameDays'),
                    'source':'Owned arrival; seller not observed within interaction range. This does not prove the business is closed.'})
                person['memories']=person['memories'][-32:]
            elif plan.get('outcome')=='allocated_stock':
                person=state['people'][str(plan['actor'])]
                person['memories'].append({'event_id':plan['id'],'kind':'allocated_food',
                    'policy':copy.deepcopy(person['food_policy']),'source':'own allocation decision; no inventory change'})
                person['memories']=person['memories'][-32:]
            updated['remembered']=True
            settle_contract(state, updated, plan.get('outcome') or 'held')
            if plan['kind']=='need_review' or plan.get('scheduled'):
                event=next(e for e in state['town']['daily']['queue'] if e['id']==plan['id'])
                event.update(status=plan['phase'],outcome=plan.get('outcome'),settled_day=observation.get('gameDays'))
                person=state['people'][str(plan['actor'])]
                person['agency'].update(state='quiet_interval' if plan['phase']=='complete' else 'held',
                    reason='Last scheduled outcome: '+str(plan.get('outcome') or plan.get('error','held')))
                day=observation.get('gameDays')
                if type(day) in (int,float) and math.isfinite(day):person['agency']['next_review_day']=day+1/24
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
                arrived = at_market(observation,plan['actor']) if plan.get('target_kind')=='place' else distance(observation, plan['actor'], plan['target']) <= 300
            except ValueError:
                arrived = False
            state = copy.deepcopy(self.active)
            updated = state['plans'][-1]
            updated['travel'] = copy.deepcopy(ack)
            binding_ok=not plan.get('dynamic_route') or (movement.get('aliasesConfirmed') is True
                and movement.get('adapter')=='papyrus-mailbox' and movement.get('actor')==plan['actor']
                and movement.get('target')==plan['target']
                and (plan.get('target_kind')!='place' or movement.get('target_kind')=='place'))
            if ack.get('status') == 'applied' and movement.get('hasOwnedPackage') and arrived and binding_ok:
                if plan['intent']=='check_market':
                    sellers=[r for r in food_sellers(state,observation,plan['actor']) if r['distance'] is not None and r['distance']<=300 and at_market(observation,r['id'])]
                    nearby=bool(sellers)
                    updated['market_visit']={'place':MARKET,'seller_nearby':nearby,'day':observation.get('gameDays')}
                    if nearby:updated.update(phase='consent',target=sellers[0]['id'],target_kind='resident')
                    else:updated.update(phase='complete',outcome='market_seller_not_observed')
                else:
                    updated['phase'] = {'seek_bread':'consent','take_shift':'ready_to_work'}.get(plan['intent'], 'complete')
                    if updated['phase'] == 'complete':updated['outcome'] = 'visited_only'
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
        elif plan['phase'] == 'ready_to_work':
            try:
                if distance(observation, plan['actor'], plan['target']) > 300:
                    raise ValueError('Participants separated before work')
                self.plan_production(observation, plan)
            except ValueError as error:
                self.hold_plan(plan['id'], str(error), observation)
        elif plan['phase'] == 'ready_to_rest':
            try:self.plan_rest(observation,plan)
            except ValueError as error:self.hold_plan(plan['id'],str(error),observation)

    def agency_command(self, session):
        plan = self.agency_plan()
        if plan and plan['phase'] in TERMINAL and plan.get('release_required'):
            return {'id': 'release-' + plan['id'], 'kind': 'release_routine', 'actor': plan['actor'],
                    'session': session, 'checkpoint': self.marker}
        if not plan or plan['phase'] != 'travelling':
            return None
        return {'id': plan['travel_id'], 'kind': 'walk_to', 'actor': plan['actor'], 'target': plan['target'],
                'method': 'package', 'origin': 'resident_decision', 'plan_id': plan['id'], 'retain': True,
                'dynamic':plan.get('dynamic_route',False),
                'target_kind':plan.get('target_kind','resident'),
                'session': session, 'checkpoint': self.marker}
