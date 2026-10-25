"""Save-bound event plans. Models select allowed intentions, never native commands.

This mixin shares TimelineEconomy's immutable checkpoint protocol. Inference runs
in a separate worker; a persisted claim prevents automatic duplicate model calls.
"""
import copy
import hashlib
import json
import math
import secrets
from decisions import validate_decision
from food import allocation
from production import work_inventory
from market_day import event_for
from routing import route_available, dynamic_route, activity_blocker
from labour import work_opportunities, settle_contract
from rest import rest_opportunities
from places import market_opportunity, market_opportunities, at_market
from opportunities import food_sellers
from knowledge import person_view
from social import social_candidates
from enterprises import plan_work_policy, current_work_terms
from owner_production import owner_work_opportunities
from procurement import input_procurement, validate_procurement, PINS as PROCUREMENT_PINS
from market_policy import goods_policy, policy_hash
import economy_catalog
from bargaining import PRICING_POLICY, own_prices, price_choices, record_quote, accept_quote, quote_valid
from employment import approach_employer, accept_contract, REVIEW_AFTER_REFUSAL_MINUTES
from entrepreneurship import enterprise_choices, apply_resident_enterprise, recipe_knowledge
from context_window import (bounded_economic_context, purchase_attention_context, purchase_attention_policy,
    purchase_catalogue_hash, check_purchase_decision_budget, frozen_purchase_choices)
from trade_memory import remember_refusal_decision
from activity_leases import reserved_activity_actors, identity_quarantine_actors
from economy_catalog import recipe_spec, require_native_catalog, MAX_STOCK, commodity_ids, native_catalog_matches, catalog_hash

TERMINAL = ('complete', 'held')


def owner_work_choice_id(job):
    identity=json.dumps([job['business_id'],job['recipe_id']],separators=(',',':'))
    return 'work_own_'+hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]


def recipe_quantities(recipe_id):
    recipe=recipe_spec(recipe_id)
    describe=lambda side:', '.join(str(n)+' '+key for key,n in sorted(recipe[side].items()))
    return describe('inputs'),describe('outputs')



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
        return bool(plan and (plan['phase'] not in (*TERMINAL, 'delegated') or plan.get('release_required')))

    def _agency_guard(self, observation, allow_routines=False):
        if not allow_routines and self.routines_busy():
            raise ValueError('An independent routine cohort owns these daily opportunities')
        if self.error or not self.active or self.transition or self.active['pending']:
            raise ValueError('Society must be synchronized without an unsettled trade')
        if observation.get('session') != self.session or observation.get('checkpoint') != self.marker:
            raise ValueError('Observation belongs to another save checkpoint')

    def begin_plan(self, event_id, observation, actor=None, kind='meal_time', voiced_trade=False, natural_trade=False):
        self._agency_guard(observation)
        if type(actor) is not int or not 0 < actor <= 0xffffffff or str(actor) not in self.active['people']:
            raise ValueError('An explicit valid resident actor is required')
        if type(voiced_trade) is not bool:raise ValueError('Voiced trade must be boolean')
        if type(natural_trade) is not bool or natural_trade and not voiced_trade:raise ValueError('Natural wording requires voiced trade')
        if self.conversation_busy():
            raise ValueError('A conversation owns the participants')
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 64:
            raise ValueError('A bounded event ID is required')
        if kind not in ('meal_time','stock_review','work_shift','need_review'):
            raise ValueError('Unsupported resident or event kind')
        for plan in self.active.get('plans', []):
            if plan['id'] == event_id:
                if plan['actor'] != actor or plan['kind'] != kind or plan.get('voiced_trade',False)!=voiced_trade or plan.get('natural_trade',False)!=natural_trade:
                    raise ValueError('Event ID reused for another resident or kind')
                return {'duplicate': True, 'plan': plan}
        if actor in reserved_activity_actors(self.active, observation):
            raise ValueError('Resident owns an independent activity lease')
        native=next((r for r in observation.get('residents',[]) if r['id']==actor),None)
        if native and activity_blocker(native):raise ValueError('Resident currently occupied: '+activity_blocker(native))
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
                'unit_price': 3, 'quantity':1, 'commodity':'bread', 'purpose':'food',
                'market_policy_hash':policy_hash(), 'catalog_hash':catalog_hash(), 'refusals_recorded': 0, 'food_actions': True}
        if state.get('town') is not None:
            plan.update(pricing_policy=PRICING_POLICY, offer_round=0)
        handoff=next((h for h in reversed(state.get('scene_handoffs',[]))
                      if h['actor']==actor and h['status']=='released' and not h.get('resumed_by')),None)
        if handoff:
            plan['scene_handoff']={'id':handoff['id'],'scene_id':handoff['scene_id']}
            handoff['resumed_by']=event_id
        if voiced_trade:plan['voiced_trade']=True
        if natural_trade:plan['natural_trade']=True
        if scheduled:
            plan['scheduled']=True
            if event.get('conversation_followups'):plan['conversation_followups']=copy.deepcopy(event['conversation_followups'])
            if event.get('goal_followups'):plan['goal_followups']=copy.deepcopy(event['goal_followups'])
        state.setdefault('plans', []).append(plan)
        if kind == 'work_shift':
            jobs = work_opportunities(state, observation, actor)
            if jobs:
                plan.update(phase='job_offer', target=jobs[0]['employer'], work_terms=jobs[0])
                if voiced_trade:approach_employer(plan)
            else:
                raise ValueError('No feasible paid-work opportunity for this resident')
        return {'checkpoint': self._write(state, kind+' triggered resident planning'), 'plan': plan}

    def _plan_context(self, observation, plan):
        participants={plan.get('actor')}
        if plan.get('target_kind','resident')=='resident':participants.add(plan.get('target'))
        if participants.intersection(identity_quarantine_actors(self.active,observation)):
            raise ValueError('Resident identity changed or is unqualified; hold the plan before another decision')
        seller_turn = plan['phase'] == 'consent'
        reconsidering = plan['phase'] == 'reconsider'
        price = plan.get('unit_price', 3)
        commodity=plan.get('commodity','bread');quantity=plan.get('quantity',1);cost=price*quantity
        label=next((r['label'] for r in economy_catalog.ECONOMY_CATALOG['commodities'] if r['id']==commodity),None)
        if label is None:raise ValueError('Unknown trade commodity')
        policy=goods_policy(commodity)
        if type(quantity) is not int or quantity not in policy['quantity_choices']:
            raise ValueError('Trade quantity is not enabled by the market policy')
        unit='loaf' if commodity=='bread' and quantity==1 else label
        goods=f'{quantity} {unit}'
        leave_action='leave_without_purchase' if plan.get('purpose')=='production_input' else 'leave_without_food'
        if plan.get('market_policy_hash')!=policy_hash() or plan.get('catalog_hash')!=catalog_hash():
            raise ValueError('Economic policy changed or is unbound; a fresh review is required')
        if plan.get('procurement') and not validate_procurement(self.active,observation,plan['actor'],plan['procurement']):
            raise ValueError('Selected input purchase is no longer valid')
        bargaining = plan.get('pricing_policy') == PRICING_POLICY
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
        owner_work_actions = []
        price_options = {}
        business_options = {}
        market_options = {}
        purchase_options = {}
        if plan['phase'] in ('job_offer', 'job_accept'):
            require_native_catalog(observation,'bread_recipe')
            current_work_terms(self.active, plan)
            policy = plan_work_policy(plan)
            wage, minutes = policy['wage_gold'], policy['work_minutes']
        def visits():
            if self.active.get('town') is None:
                rows=[]  # No implicit authored acquaintance in a world without a census.
            else:
                rows=[{**r,'action':'visit_person_'+str(r['id'])} for r in social_candidates(self.active,observation,actor)]
            for row in rows:
                targets[row['action']]=row['id']
            return [{'id':r['action'],'effect':'Visit '+r['name']+'; travel only, no purchase or conversation is implied.'} for r in rows]
        if plan['phase']=='job_offer':
            options = [{'id':'defer','effect':'Do not offer this job; keep your resources.'}]
            resources = work_inventory(observation, plan['actor'], plan['target'])
            if (resources['employer']['grain'] >= policy['grain_per_shift'] and resources['employer']['gold'] >= wage
                    and resources['employer']['bread'] <= MAX_STOCK-policy['bread_per_shift']
                    and resources['worker']['gold'] <= MAX_STOCK-wage):
                worker_name = person_view(self.active,actor,plan['actor'])['name']
                options.append({'id':'offer_shift','effect':f'Offer {worker_name} {wage} gold from your purse to convert {policy["grain_per_shift"]} of your grain into {policy["bread_per_shift"]} bread. They may refuse. Pay only after {minutes} game minutes of qualified work and observed production.'})
            information = f'Consider paid bread-making to replenish your stock toward your enterprise target of {policy["target_bread"]} loaves. The recipe is authored; no oven animation is implemented. Your household reserve applies to output. Sale prices and sales are not guaranteed, wages cost {wage} gold and grain has an opportunity cost. Use your own remembered trades when judging whether replenishing is worthwhile.'
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
        elif bargaining and plan['phase']=='quote':
            if distance(observation, actor, plan['target']) > 300:
                raise ValueError('Seller is no longer within interaction range')
            options = [{'id':leave_action,'effect':'Leave without making an offer; keep your money.'}]
            for value in price_choices(person, inventory['gold']//quantity,commodity=commodity):
                action='bid_price_'+str(value);price_options[action]=value
                options.append({'id':action,'effect':f'Offer {value} septims per unit for {goods}: {value*quantity} septims total; pay only if accepted.'})
            information = f'You reached a registered {commodity} seller. Choose your own opening bid using your money, hunger, priorities and remembered prices, or leave. Their stock, finances and reservation price are unknown. A low bid may be refused; a high bid leaves you less money. No market price is supplied.'
        elif seller_turn:
            if distance(observation, actor, plan['actor']) > 300:
                raise ValueError('Buyer is no longer within interaction range')
            options = [{'id': 'decline', 'effect': 'Decline the request; keep your goods.'}]
            if type(inventory.get(commodity)) is int and inventory[commodity]>=quantity:
                reserved=policy['reserve_mode']=='existing_food_policy' and stock['allocated'] and stock['for_sale']<quantity
                if reserved:
                    options.append({'id':'sell_reserved_bread','effect':f'Release {goods} from your household allocation for this sale only at {price} septims each, {cost} total. Your household keeps less food; the standing reserve policy remains unchanged. You may refuse.'})
                else:
                    action='sell_bread' if commodity=='bread' and plan.get('purpose')=='food' else 'sell_goods'
                    options.append({'id':action,'effect':f'Agree to sell {goods} for {price} septims each, {cost} total. Consider your own needs and productive uses; you may refuse.'})
            if bargaining and plan.get('offer_round',0)==1 and inventory.get(commodity,0)>=quantity:
                reserved=policy['reserve_mode']=='existing_food_policy' and stock['allocated'] and stock['for_sale']<quantity
                for value in price_choices(person, above=price,commodity=commodity):
                    action='ask_price_'+str(value);price_options[action]=value
                    options.append({'id':action,'effect':f'Offer {goods} for {value} septims each, {value*quantity} total instead. Commit to this sale if the buyer agrees; keep your reserve policy for remaining stock.'})
            buyer_name=person_view(self.active,actor,plan['actor'])['name']
            information = f'{buyer_name} is nearby and offers {price} septims each for {goods}, {cost} total. Choose freely whether to sell. Refusal does not reveal your motive to the buyer. Consider your own needs, productive uses, remaining stock, money and memories. Only a bread sale can reconsider your household food allocation. Your stock and motives are not disclosed to the buyer. Their total money is unknown.'
        elif reconsidering and bargaining:
            options = [{'id':leave_action,'effect':'End this negotiation and keep your money.'}]
            options += visits()
            if plan.get('counter_quote'):
                if not quote_valid(self.active,plan,observation):
                    raise ValueError('Seller quote changed while awaiting acceptance')
                if inventory['gold']>=cost and distance(observation,actor,plan['target'])<=300:
                    options.append({'id':'accept_counterprice','effect':f'Accept {goods} for {price} septims each, {cost} total. Pay after spoken terms and native verification.'})
                information=f'The seller offered {goods} for {price} septims each, {cost} total instead. Accept if worthwhile and affordable, or leave. Their finances, remaining stock and motives remain private. No further counteroffer is available in this bounded encounter.'
            else:
                if distance(observation,actor,plan['target'])<=300:
                    for value in price_choices(person,inventory['gold']//quantity,above=price,commodity=commodity):
                        action='bid_price_'+str(value);price_options[action]=value
                        options.append({'id':action,'effect':f'Make a final offer of {value} septims each for {goods}, {value*quantity} total; pay only if accepted.'})
                information=f'The seller declined your offer of {price} septims each for {goods}, {cost} total. Their reason is unknown. You can make one higher final bid or leave. Repeating the unchanged bid is unavailable.'
        elif reconsidering:
            options = [{'id': 'leave_without_food', 'effect': 'End this negotiation without buying food; preserve your money and leave the seller alone.'}]
            options += visits()
            if price == 3 and inventory['gold'] >= 5 and distance(observation, actor, plan['target']) <= 300:
                price_options['raise_offer']=5
                options.append({'id': 'raise_offer', 'effect': 'Make one final offer of 5 gold for one loaf instead of 3. Pay only if the seller agrees; she may refuse again.'})
            information = 'The seller just declined your 3-gold offer. Their reason is unknown. Reconsider your plan using this outcome, your needs, resources and priorities; repeating the unchanged request is not an available action in this bounded negotiation.'
        else:
            options = [{'id': 'defer', 'effect': 'Postpone this errand; no travel or purchase.'}]
            if inventory['bread'] > 0:
                options.append({'id':'eat_bread','effect':'Consume one carried loaf now; it leaves inventory and reduces your simulated hunger.'})
            options += visits()
            sellers=food_sellers(self.active,observation,actor)
            if sellers and inventory['gold'] >= (1 if bargaining else 3) and inventory['bread'] == 0:
                for i,seller in enumerate(sellers):
                    action='seek_bread' if i==0 else 'seek_bread_'+str(seller['id'])
                    targets[action]=seller['id']
                    purpose='choose an affordable bid on arrival' if bargaining else 'offer 3 gold for one loaf'
                    options.append({'id':action,'effect':'Walk to '+seller['name']+', a publicly registered food seller, and '+purpose+'. Stock is unknown and they may refuse.'})
            elif inventory['gold'] >= (1 if bargaining else 3) and inventory['bread'] == 0 and market_opportunity(self.active,observation,actor):
                purpose='choose an affordable bid for a loaf' if bargaining else 'offer 3 gold for a loaf'
                for i,site in enumerate(market_opportunities(self.active,observation,actor)):
                    action='check_market' if i==0 else 'check_market_'+str(site['id'])
                    market_options[action]=site
                    options.append({'id':action,'effect':'Walk to '+site['name']+' to look for a food seller. Presence and stock are unknown. If a registered food seller is nearby on arrival, '+purpose+'; otherwise remember the unsuccessful visit. No food or wage is guaranteed.'})
            if plan['kind']=='need_review':
                if any(b.get('active',True) is True and b.get('custodian')==actor and 'retail_food' in b.get('capabilities',[])
                       for b in (self.active.get('town') or {}).get('businesses',{}).values()):
                    options.append({'id':'review_food_reserve','effect':'Reconsider how much of your carried bread to keep for your household and how much to offer for sale. This changes only your reserve policy; it does not consume, sell or create food.'})
                for option in enterprise_choices(self.active,observation,actor):
                    business_options[option['id']]=option['specification']
                    options.append({'id':option['id'],'effect':option['effect']})
                for purchase in input_procurement(self.active,observation,actor):
                    action=purchase['id']
                    if action in purchase_options:raise ValueError('Duplicate input purchase choice identity')
                    purchase_options[action]=copy.deepcopy(purchase);targets[action]=purchase['supplier']
                    name=person_view(self.active,actor,purchase['supplier'])['name']
                    product=next(row['label'] for row in economy_catalog.ECONOMY_CATALOG['commodities'] if row['id']==purchase['commodity'])
                    options.append({'id':action,'effect':f'Visit {name}, a publicly registered supplier, to bid for {purchase["quantity"]} {product} for your production inputs. Your own business has an input shortfall. Supplier stock and consent are unknown; no purchase or production is guaranteed.'})
                for job in owner_work_opportunities(self.active,observation,actor):
                    action=owner_work_choice_id(job)
                    if action in work_options:raise ValueError('Duplicate owner work choice identity')
                    work_options[action]=job;owner_work_actions.append(action)
                    inputs,outputs=recipe_quantities(job['recipe_id'])
                    options.append({'id':action,'effect':f'Spend {job["policy"]["work_minutes"]} game minutes working your own stock where you are. Use {inputs} to produce {outputs}. No wage or gold is created or transferred. Output stays yours; household food policy applies to food only. Consider fatigue and other needs; the productive animation is not implemented.'})
                for i, job in enumerate(work_opportunities(self.active, observation, actor)):
                    action = 'seek_work' if i == 0 else 'seek_work_' + job['business_id']
                    work_options[action] = job
                    targets[action] = job['employer']
                    terms = job['policy']
                    options.append({'id': action, 'effect': f'Ask {job["employer_name"]} about an advertised {terms["work_minutes"]}-game-minute bread-making shift paying {terms["wage_gold"]} gold. The employer must offer and you must accept. No wage is guaranteed.'})
            if plan['kind']=='need_review' and rest_opportunities(self.active,observation,actor):
                options.append({'id':'rest_at_bench','effect':'Take a 30-game-minute seated break at an available nearby bench. Walk there and recover some simulated fatigue only after verified sitting. This interrupts your ordinary routine; consider duties and other needs. It is a short break, not sleep.'})
            information = 'Consider your hunger, fatigue, carried food, money, priorities and past experiences. You may defer, eat, seek food or explore an available livelihood opportunity. This does not prove what food you have at home.'
        own_followups=[f for f in plan.get('conversation_followups',[]) if f.get('actor')==actor]
        if own_followups:
            information+=' You chose this review after a conversation. Consider the recorded focus and heard words, but recheck current resources and duties. A heard claim is not a verified fact or binding promise. You may change your mind.'
        own_goals=[f for f in plan.get('goal_followups',[]) if f.get('actor')==actor]
        if own_goals:
            information+=' You chose this review as a personal goal. Consider its focus, recheck current resources and duties, and change your mind if appropriate. No need relief or economic effect has happened merely by choosing or arriving.'
        other=plan.get('target') if actor==plan['actor'] else plan['actor']
        counterparty=person_view(self.active,actor,other) if other!=actor and str(other) in self.active['people'] else None
        context={'actor_id': actor, 'profile': person['profile'], 'session': self.session,
                'event': {'id': plan['id'], 'kind': plan['kind'], 'information': information},
                'conversation_followups':copy.deepcopy(own_followups),
                'own_goal_followups':copy.deepcopy(own_goals),
                'economic_counterparty':counterparty,
                'own_commitments':copy.deepcopy(person.get('commitments',[])),
                'observed_inventory': copy.deepcopy(inventory),
                'inventory_catalog_hash':catalog_hash() if native_catalog_matches(observation) else None,
                'own_food_allocation': stock,
                'scenario_state': {'needs': person['needs'], 'source': 'authored society simulation, not Skyrim hunger'},
                'perception': self._resident_perception(observation, actor),
                'prior_knowledge': 'Public enterprise charters identify advertised services, not personal names, private stock or willingness. Names require personal knowledge. '+('Prices are chosen from an authored bounded search space, not a supplied market equilibrium.' if bargaining else 'The 3-gold initial offer and 5-gold final offer are authored starting assumptions, not discovered market prices.'),
                'own_price_history':own_prices(person,commodity), 'commodity':commodity, 'quantity':quantity, 'unit_price':price, 'cost':cost,
                'purpose':plan.get('purpose'),'market_policy_hash':plan['market_policy_hash'],'price_options':price_options,
                'memories': person['memories'][-8:], 'trust': person['trust'],
                'my_relationships':person.get('relationships',{}), 'option_targets':targets,
                'purchase_options':purchase_options,'work_options':work_options, 'owner_work_actions':owner_work_actions, 'enterprise_options':business_options, 'market_options':market_options,
                'own_recipe_knowledge':recipe_knowledge(person,state=self.active,observation=observation,actor_id=actor),
                'options': options}
        return purchase_attention_context(context,plan,{row['supplier']:person_view(self.active,actor,row['supplier'])['name']
            for row in purchase_options.values()})

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
        if not plan or plan['id'] != event_id or plan['phase'] not in ('choose', 'purchase_select', 'quote', 'consent', 'reconsider', 'allocate', 'after_purchase', 'job_offer', 'job_accept'):
            raise ValueError('No unclaimed decision is ready')
        check_purchase_decision_budget(plan)
        context = bounded_economic_context(self._plan_context(observation, plan),self.active['people'][str(
            plan['target'] if plan['phase'] in ('consent','job_offer') else plan['actor'])]['memories'])
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
        if any(current.get(key)!=claim['context'].get(key) for key in ('commodity','quantity','unit_price','cost','purpose')):
            raise ValueError('Negotiation terms changed while deciding')
        purchase=current.get('purchase_options',{}).get(chosen)
        claimed_purchase=claim['context'].get('purchase_options',{}).get(chosen)
        if purchase is not None or claimed_purchase is not None:
            if (not purchase or not claimed_purchase or any(purchase.get(k)!=claimed_purchase.get(k) for k in (*PROCUREMENT_PINS,'id'))
                    or not validate_procurement(self.active,observation,plan['actor'],claimed_purchase)):
                raise ValueError('The chosen input purchase terms changed while deciding')
        if current.get('purchase_navigation',{}).get(chosen)!=claim['context'].get('purchase_navigation',{}).get(chosen):
            raise ValueError('Purchase inspection group changed while deciding')
        if chosen=='review_input_purchases' and current.get('purchase_attention')!=claim['context'].get('purchase_attention'):
            raise ValueError('Input purchase catalogue changed while deciding')
        if current.get('market_policy_hash')!=claim['context'].get('market_policy_hash'):
            raise ValueError('Market policy changed while deciding')
        if current.get('price_options',{}).get(chosen)!=claim['context'].get('price_options',{}).get(chosen):
            raise ValueError('The chosen price changed while deciding')
        if current.get('enterprise_options',{}).get(chosen)!=claim['context'].get('enterprise_options',{}).get(chosen):
            raise ValueError('The chosen enterprise revision changed while deciding')
        if chosen in claim['context'].get('market_options',{}):
            selected=claim['context']['market_options'][chosen]
            if not market_opportunity(self.active,observation,plan['actor'],selected['id']):
                raise ValueError('The selected public venue is no longer executable')
        if current['observed_inventory'] != claim['context']['observed_inventory']:
            raise ValueError('Inventory changed while deciding')
        if current.get('inventory_catalog_hash')!=claim['context'].get('inventory_catalog_hash'):
            raise ValueError('Inventory catalog changed while deciding')
        if goods_policy(plan.get('commodity','bread'))['reserve_mode']=='existing_food_policy' and (chosen in ('sell_bread','sell_reserved_bread') or chosen.startswith('ask_price_')) and current['own_food_allocation']!=claim['context']['own_food_allocation']:
            raise ValueError('Household allocation changed while deciding')
        state = copy.deepcopy(self.active)
        updated = state['plans'][-1]
        updated['decisions'].append({'actor_id': current['actor_id'], 'context': claim['context'],
            'decision': decision, 'model': str(result.get('model', 'unknown'))[:100],
            'elapsed_seconds': result.get('elapsed_seconds'), 'claim_id': claim_id,
            'rationale_kind': result.get('rationale_kind','model_public_rationale'),
            'call_lane':'purchase_navigation' if claim['stage']=='purchase_select' else 'economic',
            'probabilities': result.get('probabilities',{}), 'usage': result.get('usage',{})})
        updated['claim'] = None
        action = decision['action_id']
        if action=='review_input_purchases':
            choices=frozen_purchase_choices(input_procurement(self.active,observation,updated['actor']))
            if purchase_catalogue_hash(choices)!=claim['context']['purchase_attention']['catalogue_hash']:
                raise ValueError('Input purchase catalogue changed before inspection')
            updated.update(phase='purchase_select',purchase_menu={'choices':choices,'range':[0,len(choices)],'trail':[],
                'catalogue_hash':purchase_catalogue_hash(choices),'policy':purchase_attention_policy()})
        elif action in current.get('purchase_navigation',{}):
            navigation=current['purchase_navigation'][action];menu=updated['purchase_menu']
            if navigation['kind']=='cancel':
                updated['phase']='choose';updated.pop('purchase_menu',None)
            elif navigation['kind']=='back':
                menu['range']=menu['trail'].pop();updated['phase']='purchase_select'
            else:
                menu['trail'].append(menu['range']);menu['range']=copy.deepcopy(navigation['range']);updated['phase']='purchase_select'
        elif action in current['enterprise_options']:
            apply_resident_enterprise(state,updated,current['enterprise_options'][action],observation)
        elif action=='review_food_reserve':
            updated.update(phase='allocate',intent='review_food_reserve')
        elif action == 'check_market' or action.startswith('check_market_'):
            selected=claim['context'].get('market_options',{}).get(action)
            site=market_opportunity(self.active,observation,updated['actor'],selected['id'] if selected else None)
            if not site:raise ValueError('The known public destination is no longer executable')
            updated.update(phase='travelling',target=site['id'],target_kind='place',destination=site,
                intent='check_market',travel_id='travel-'+event_id,dynamic_route=True,release_required=True)
        elif action == 'rest_at_bench':
            sites=rest_opportunities(self.active,observation,updated['actor'])
            if not sites:raise ValueError('No available rest site remains')
            updated.update(phase='ready_to_rest',rest_target=sites[0]['id'])
        elif action == 'seek_work' or action.startswith('seek_work_'):
            job = current['work_options'][action]
            updated.update(phase='job_offer', target=job['employer'], work_terms=job)
            if updated.get('voiced_trade'):approach_employer(updated)
        elif action in current['owner_work_actions']:
            updated.update(phase='ready_to_self_work',intent='owner_production',own_work_terms=current['work_options'][action])
        elif action in current['purchase_options']:
            purchase=copy.deepcopy(claim['context']['purchase_options'][action])
            updated.update(procurement=purchase,procurement_claim_id=claim_id,commodity=purchase['commodity'],quantity=purchase['quantity'],
                purpose='production_input',market_policy_hash=purchase['market_policy_hash'],catalog_hash=purchase['catalog_hash'],
                trade_id='input-'+event_id,phase='travelling',target=purchase['supplier'],intent='procure_input',
                travel_id='travel-'+event_id,release_required=True,food_actions=False,
                dynamic_route=dynamic_route(updated['actor'],purchase['supplier']))
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
            if action == 'take_shift' and not updated.get('employment_dialogue'):
                accept_contract(state, updated)
            updated.update(phase='travelling', target=target,
                           intent='seek_bread' if action.startswith('seek_bread') else action, travel_id=travel_id, release_required=True)
            updated['dynamic_route']=dynamic_route(updated['actor'],updated['target'])
        elif action.startswith('bid_price_'):
            updated.update(phase='consent',unit_price=current['price_options'][action],offer_round=updated.get('offer_round',0)+1)
        elif action.startswith('ask_price_'):
            updated.update(phase='reconsider',unit_price=current['price_options'][action])
            record_quote(state,updated,current,updated['unit_price'],claim_id)
        elif action=='accept_counterprice':
            accept_quote(state,updated,observation)
            updated['phase']='ready_to_trade'
        elif action == 'raise_offer':
            updated.update(phase='consent', unit_price=5)
        elif action in ('sell_bread','sell_reserved_bread','sell_goods'):
            updated['phase'] = 'ready_to_trade'
            if action=='sell_reserved_bread':
                updated['reserve_release']={'plan_id':event_id,'trade_id':updated['trade_id'],
                    'buyer':updated['actor'],'seller':updated['target'],'quantity':updated['quantity'],'commodity':updated['commodity'],
                    'unit_price':updated.get('unit_price',3),
                    'policy':copy.deepcopy(state['people'][str(updated['target'])].get('food_policy')),
                    'inventory':{k:current['observed_inventory'][k] for k in commodity_ids()},
                    'catalog_hash':current['inventory_catalog_hash'],'market_policy_hash':current['market_policy_hash'],
                    'decision_claim_id':claim_id}
        elif action == 'decline':
            self._remember_refusal(state, updated)
            if (updated.get('offer_round',0)<2 if updated.get('pricing_policy')==PRICING_POLICY else updated.get('unit_price',3)==3):
                updated['phase'] = 'reconsider'
            else:
                updated.update(phase='complete', outcome='seller_declined')
        elif action in ('leave_without_food','leave_without_purchase'):
            updated.update(phase='complete', outcome='left_without_purchase' if action=='leave_without_purchase' else 'left_without_food')
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
        elif action == 'defer' and claim['stage']=='job_offer' and updated.get('employment_dialogue'):
            updated.update(phase='complete', outcome='employer_declined')
        else:
            updated.update(phase='complete', outcome='deferred')
        if action in ('sell_bread','sell_reserved_bread','sell_goods','accept_counterprice'):
            seller_claim=updated.get('counter_quote',{}).get('claim_id') if action=='accept_counterprice' else claim_id
            buyer_claim=claim_id if action=='accept_counterprice' else next((d['claim_id'] for d in reversed(updated['decisions'][:-1])
                if d['actor_id']==updated['actor'] and (d['decision']['action_id'].startswith('bid_price_') or d['decision']['action_id']=='raise_offer' or d['decision']['action_id'].startswith('seek_bread'))),None)
            updated['accepted_trade']={'buyer':updated['actor'],'seller':updated['target'],
                'commodity':updated['commodity'],'quantity':updated['quantity'],'unit_price':updated['unit_price'],
                'cost':updated['quantity']*updated['unit_price'],'catalog_hash':updated['catalog_hash'],
                'market_policy_hash':updated['market_policy_hash'],'purpose':updated['purpose'],
                'buyer_claim_id':buyer_claim,'seller_claim_id':seller_claim}
        speech_act={'raise_offer':'counteroffer','sell_goods':'accept','sell_bread':'accept','sell_reserved_bread':'accept','decline':'refuse','leave_without_food':'leave','leave_without_purchase':'leave'}.get(action)
        if action.startswith('bid_price_'):speech_act='offer' if updated['offer_round']==1 else 'counteroffer'
        if action.startswith('ask_price_'):speech_act='seller_counteroffer'
        if action=='accept_counterprice':speech_act='buyer_accept'
        if updated.get('employment_dialogue'):
            if claim['stage']=='job_offer':speech_act='work_offer' if action=='offer_shift' else 'work_unavailable'
            elif claim['stage']=='job_accept':speech_act='work_accept' if action=='take_shift' else 'work_decline'
        if claim['stage']=='reconsider' and action.startswith(('visit_','visit_person_')) and updated.get('economic_attendance'):speech_act='leave'
        if speech_act:self.queue_trade_speech(state,updated,speech_act)
        return {'checkpoint': self._write(state, 'resident decision accepted'), 'plan': updated}

    @staticmethod
    def _remember_refusal(state, plan):
        return remember_refusal_decision(state, plan)

    def hold_plan(self, event_id, reason, observation):
        self._agency_guard(observation)
        plan = self.agency_plan()
        if not plan or plan['id'] != event_id or plan['phase'] in (*TERMINAL, 'delegated'):
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
            if ack.get('id') == 'release-' + plan['id'] and ack.get('status') == 'applied' and (not plan.get('economic_pair') or ack.get('released') is True):
                state = copy.deepcopy(self.active)
                state['plans'][-1]['release_required'] = False
                if plan.get('voiced_trade'):state['plans'][-1]['economic_release']=copy.deepcopy(ack)
                self._write(state, 'resident task release observed')
            return
        if plan and plan['phase'] not in (*TERMINAL,'delegated'):
            participants={plan.get('actor')}
            if plan.get('target_kind','resident')=='resident':participants.add(plan.get('target'))
            if participants.intersection(identity_quarantine_actors(self.active,observation)):
                state=copy.deepcopy(self.active)
                state['plans'][-1].update(phase='held',identity_held=True,
                    error='Resident identity changed or is unqualified; no further decisions or activity credit')
                self._write(state,'resident plan held on identity conflict; historical state preserved')
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
                    'place':plan.get('market_visit',{}).get('place',plan.get('destination',{}).get('id')),'day':observation.get('gameDays'),
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
                if type(day) in (int,float) and math.isfinite(day):
                    minutes=REVIEW_AFTER_REFUSAL_MINUTES if plan.get('outcome')=='employer_declined' else 60
                    person['agency']['next_review_day']=day+minutes/1440
            self._write(state,'resident remembers the observed plan outcome')
            return
        if not plan or plan['phase'] in (*TERMINAL, 'delegated'):
            return
        if self.observe_trade_speech(observation):return
        if plan['phase'] == 'thinking' and plan['claim']['context']['session'] != self.session:
            self.hold_plan(plan['id'], 'Game session changed during inference; do not repeat the claimed call', observation)
        elif plan['phase'] == 'travelling':
            if plan.get('dynamic_route') is not True:
                state = copy.deepcopy(self.active)
                state['plans'][-1].update(phase='held', release_required=True,
                    error='Saved travel lacks the dynamic mailbox contract; release and review required')
                self._write(state, 'legacy resident travel held without arrival credit')
                return
            ack = observation.get('ack') or {}
            if ack.get('id') != plan['travel_id']:
                return
            movement = ack.get('movement') or {}
            try:
                arrived = at_market(observation,plan['actor'],plan['target']) if plan.get('target_kind')=='place' else distance(observation, plan['actor'], plan['target']) <= 300
            except ValueError:
                arrived = False
            state = copy.deepcopy(self.active)
            updated = state['plans'][-1]
            updated['travel'] = copy.deepcopy(ack)
            binding_ok=(movement.get('aliasesConfirmed') is True
                and movement.get('adapter')=='papyrus-mailbox' and movement.get('actor')==plan['actor']
                and movement.get('target')==plan['target']
                and (plan.get('target_kind')!='place' or movement.get('target_kind')=='place'))
            if ack.get('status') == 'applied' and movement.get('hasOwnedPackage') and arrived and binding_ok:
                if plan['intent']=='check_market':
                    sellers=[r for r in food_sellers(state,observation,plan['actor']) if r['distance'] is not None and r['distance']<=300 and at_market(observation,r['id'],plan['target'])]
                    nearby=bool(sellers)
                    updated['market_visit']={'place':plan['target'],'seller_nearby':nearby,'day':observation.get('gameDays')}
                    if nearby:updated.update(phase='consent',target=sellers[0]['id'],target_kind='resident')
                    else:updated.update(phase='complete',outcome='market_seller_not_observed')
                else:
                    updated['phase'] = {'seek_bread':'consent','procure_input':'consent','take_shift':'ready_to_work','ask_work':'job_offer'}.get(plan['intent'], 'complete')
                    if updated['phase'] == 'complete':updated['outcome'] = 'visited_only'
            else:
                updated.update(phase='held', error='Travel did not establish owned arrival')
            if plan.get('procurement') and not validate_procurement(state,observation,plan['actor'],plan['procurement']):
                updated.update(phase='held',error='Selected input purchase changed before arrival')
            if updated['phase']=='consent':
                if updated.get('pricing_policy')==PRICING_POLICY:updated['phase']='quote'
                else:self.queue_trade_speech(state,updated,'offer')
            elif updated['phase']=='job_offer' and updated.get('employment_dialogue'):
                self.queue_trade_speech(state,updated,'work_request')
            self._write(state, 'resident travel outcome observed')
        elif plan['phase'] == 'ready_to_trade':
            try:
                if plan.get('procurement') and not validate_procurement(self.active,observation,plan['actor'],plan['procurement']):
                    raise ValueError('Selected input purchase changed before exchange')
                if distance(observation, plan['actor'], plan['target']) > 300:
                    raise ValueError('Participants separated before exchange')
                if plan.get('counter_quote_accepted') and not quote_valid(self.active,plan,observation):
                    raise ValueError('Seller quote changed before physical exchange')
                self.plan_trade(plan['trade_id'], observation, plan['actor'], plan['target'],
                                quantity=plan.get('quantity',1), unit_price=plan.get('unit_price', 3), agency_plan=plan['id'],commodity=plan.get('commodity','bread'))
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
        elif plan['phase'] == 'ready_to_self_work':
            try:self.plan_owner_production(observation,plan)
            except ValueError as error:self.hold_plan(plan['id'],str(error),observation)

    def agency_command(self, session):
        plan = self.agency_plan()
        if plan and plan['phase'] in TERMINAL and plan.get('release_required'):
            return {'id': 'release-' + plan['id'], 'kind': 'release_routine', 'actor': plan['actor'],
                    **({'participants':plan['economic_pair']} if plan.get('economic_pair') else {}),
                    'session': session, 'checkpoint': self.marker}
        speech=self.trade_speech_command(session)
        if speech:return speech
        if not plan or plan['phase'] != 'travelling':
            return None
        return {'id': plan['travel_id'], 'kind': 'walk_to', 'actor': plan['actor'], 'target': plan['target'],
                'method': 'package', 'origin': 'resident_decision', 'plan_id': plan['id'], 'retain': True,
                'dynamic':plan.get('dynamic_route',False),
                'target_kind':plan.get('target_kind','resident'),
                'session': session, 'checkpoint': self.marker}
