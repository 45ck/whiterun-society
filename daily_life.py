"""Game-clock needs and a bounded, save-bound queue of resident opportunities.

Rates are authored gameplay parameters. A queued opportunity is not a completed
activity. Unsupported rest, social and travel actions remain explicitly unmet.
"""
import copy
import math
from routing import route_available
from labour import work_opportunities
from rest import rest_opportunities, FATIGUE_PER_GAME_HOUR
from social import social_candidates
from places import market_opportunity
from opportunities import food_sellers
from procurement import grain_procurement
from resident_control import sync_resident_assignments
from owner_production import owner_work_opportunities

INTERVAL = 15 / 1440
HUNGER_PER_GAME_HOUR = .055


class DailyLife:
    def review_population(self, observation):
        self._agency_guard(observation)
        if self.agency_busy() or self.conversation_busy():
            raise ValueError('Finish the active resident activity before reviewing the town')
        town = self.active.get('town')
        if not town:
            raise ValueError('Initialize the town first')
        day = observation.get('gameDays')
        if type(day) not in (int, float) or not math.isfinite(day) or day < 0:
            raise ValueError('A finite observed game clock is required')
        daily = town.get('daily')
        if daily and day < daily['last_day'] - 1e-7:
            raise ValueError('Game time moved backwards without loading the matching society checkpoint')
        if daily and day - daily['last_day'] < INTERVAL:
            return {'duplicate': True, 'next_review_day': daily['last_day'] + INTERVAL}
        state = copy.deepcopy(self.active)
        town = state['town']
        sync_resident_assignments(town)
        daily = town.setdefault('daily', {'last_day': day, 'sequence': 0, 'queue': [], 'reviews': []})
        daily['sequence'] += 1
        actors = {str(a['id']): a for a in observation.get('residents', []) if a.get('isPerson') is True}
        plans = {p['id']: p for p in state.get('plans', [])}
        for event in daily['queue']:
            plan = plans.get(event['id'])
            if plan and plan['phase'] in ('complete', 'held') and not plan.get('release_required'):
                event.update(status=plan['phase'], outcome=plan.get('outcome'), settled_day=day)
        outstanding = {str(e['actor']) for e in daily['queue'] if e['status'] in ('pending', 'started')}
        added = []
        for key, resident in town['residents'].items():
            person = state['people'][key]
            last_day = person.get('needs_clock', resident['observed_game_day'])
            if day < last_day - 1e-7:
                raise ValueError('Resident needs belong to a later game time')
            hours = max(0, day - last_day) * 24
            rates = {'hunger': HUNGER_PER_GAME_HOUR, 'fatigue': FATIGUE_PER_GAME_HOUR,
                     'social_contact': .018 + .025 * person['profile']['big_five']['extraversion']}
            for need, rate in rates.items():
                recovery_clock={'hunger':'hunger_clock','fatigue':'fatigue_clock','social_contact':'social_clock'}.get(need)
                elapsed = max(0, day-max(last_day,person.get(recovery_clock,last_day))) * 24 if recovery_clock else hours
                person['needs'][need] = round(min(1, person['needs'][need] + rate * elapsed), 6)
            person['needs_clock'] = day
            actor = actors.get(key)
            agency = person['agency']
            supported=bool(actor) and (any(route_available(observation,int(key),int(other)) for other in actors if other!=key) or bool(market_opportunity(state,observation,int(key))))
            resident['native_route_supported']=supported
            agency['native_route_supported']=supported
            # An unaccepted invitation is not an obligation. Reassess it after
            # aging needs, so old low-priority work cannot starve a resident's
            # queue. Never interrupt a started event or manufacture acceptance.
            pending = [e for e in daily['queue'] if str(e['actor']) == key and e['status'] == 'pending']
            inventory = actor.get('inventory', {}) if actor else {}
            urgent_food = person['needs']['hunger'] >= .6 and actor and (
                type(inventory.get('bread')) is int and inventory['bread'] > 0 or
                type(inventory.get('gold')) is int and inventory['gold'] >= 1 and (
                    food_sellers(state, observation, int(key)) or market_opportunity(state, observation, int(key))))
            urgent_rest = person['needs']['fatigue'] >= .8 and actor and rest_opportunities(state, observation, int(key))
            interrupted = False
            for queued in pending:
                if queued['kind'] == 'need_review':
                    queued['priority'] = max(person['needs']['hunger'], person['needs']['fatigue'])
                    queued['priority_reviewed_day'] = day
                elif queued['kind'] in ('social_review', 'stock_review') and (urgent_food or urgent_rest):
                    queued.update(status='superseded', settled_day=day,
                        outcome='urgent_needs_review', reason_before_interruption=queued.get('reason'),
                        interruption_reason='An executable personal need took priority before this activity started')
                    interrupted = True
            if interrupted and not any(str(e['actor']) == key and e['status'] in ('pending', 'started') for e in daily['queue']):
                outstanding.discard(key)
                agency['next_review_day'] = day
            if key in outstanding:
                continue
            if day < agency['next_review_day']:
                continue
            agency['next_review_day'] = day + 1 / 24
            agency['last_review_day'] = day
            agency['state'] = 'quiet_interval'
            agency['reason'] = 'No executable urgent opportunity; no inference requested'
            if not actor:
                agency.update(state='unloaded', reason='Needs progressed abstractly; no native action inferred')
                continue
            weather = observation.get('weather') or {}
            agency['weather_observation'] = {'classification': weather.get('classification'),
                'outdoors': actor.get('outdoors'), 'day': day}
            if actor.get('outdoors') is True and weather.get('classification') in (2, 3):
                agency['shelter_need'] = 'Current precipitation observed outdoors; shelter routing not implemented'
            else:
                agency.pop('shelter_need', None)
            inventory = actor.get('inventory', {})
            if any(type(inventory.get(k)) is not int or inventory[k] < 0 for k in ('bread', 'gold')):
                agency.update(state='awaiting_observation', reason='Current inventory is incomplete')
                continue
            if person['needs']['hunger'] >= .6:
                can_eat = inventory['bread'] > 0
                can_seek = (food_sellers(state,observation,int(key)) or market_opportunity(state,observation,int(key))) and inventory['gold'] >= 1
                can_rest = person['needs']['fatigue']>=.8 and bool(rest_opportunities(state,observation,int(key)))
                can_work = bool(work_opportunities(state,observation,int(key)) or owner_work_opportunities(state,observation,int(key)) or grain_procurement(state,observation,int(key)))
                if not any((can_eat,can_seek,can_rest,can_work)):
                    agency.update(state='unmet_food_need', reason='No carried bread or qualified affordable seller route')
                    continue
                event = {'id': f"daily-{daily['sequence']}-{key}", 'actor': int(key),
                    'kind': 'need_review', 'status': 'pending', 'created_day': day,
                    'priority': person['needs']['hunger'],
                    'reason': ('Simulated hunger crossed the meal-review threshold' if can_eat or can_seek else
                               'Food is unavailable; consider an available break or livelihood without claiming hunger relief'),
                    'observed_inventory': copy.deepcopy(inventory)}
                daily['queue'].append(event)
                added.append(event['id'])
                agency.update(state='decision_pending', reason=event['reason'], event_id=event['id'])
            elif person['needs']['fatigue'] >= .8:
                if rest_opportunities(state,observation,int(key)):
                    event={'id':f"daily-{daily['sequence']}-{key}",'actor':int(key),'kind':'need_review','status':'pending',
                        'created_day':day,'priority':person['needs']['fatigue'],'reason':'Fatigue is high and an observed bench is available',
                        'observed_inventory':copy.deepcopy(inventory)}
                    daily['queue'].append(event);added.append(event['id'])
                    agency.update(state='decision_pending',reason=event['reason'],event_id=event['id'])
                else:agency.update(state='unmet_rest_need',reason='No qualified available bench or an existing commitment prevents a break')
            elif (any(b.get('active',True) is True and b['custodian']==int(key) and 'retail_food' in b['capabilities'] for b in town['businesses'].values())
                  and (person.get('food_policy',{}).get('reviewed_day') is None
                       or day-person['food_policy']['reviewed_day'] >= 4/24-1e-7
                       or abs(inventory['bread']-person['food_policy'].get('observed_bread',inventory['bread'])) >= 2)):
                event = {'id': f"daily-{daily['sequence']}-{key}", 'actor':int(key),
                    'kind':'stock_review', 'status':'pending', 'created_day':day, 'priority':.55,
                    'reason':'Business reserve policy is due for review after time or stock changes',
                    'observed_inventory':copy.deepcopy(inventory)}
                daily['queue'].append(event);added.append(event['id'])
                agency.update(state='decision_pending', reason=event['reason'], event_id=event['id'])
            elif work_opportunities(state, observation, int(key)) or owner_work_opportunities(state,observation,int(key)) or grain_procurement(state,observation,int(key)):
                event = {'id': f"daily-{daily['sequence']}-{key}", 'actor': int(key),
                    'kind':'need_review', 'status':'pending', 'created_day':day,
                    'priority':.5, 'reason':'An executable enterprise opportunity can replenish stock through labour or buying inputs',
                    'observed_inventory':copy.deepcopy(inventory)}
                daily['queue'].append(event);added.append(event['id'])
                agency.update(state='decision_pending', reason=event['reason'], event_id=event['id'])
            elif person['needs']['social_contact'] >= .7:
                agency.update(state='unmet_social_need', reason='No qualified nearby partner is available')
            # A light social opportunity remains possible when the rest executor
            # is unavailable. The model can defer because of fatigue; no forced chat.
            if (agency['state'] in ('quiet_interval','unmet_social_need','unmet_rest_need')
                    and person['needs']['social_contact']>=.7 and social_candidates(state,observation,int(key))):
                event={'id':f"social-{daily['sequence']}-{key}",'actor':int(key),'kind':'social_review','status':'pending',
                    'created_day':day,'priority':.45,'reason':'Social need and a nearby eligible person; either resident may decline'}
                daily['queue'].append(event);added.append(event['id'])
                agency.update(state='decision_pending',reason=event['reason'],event_id=event['id'])
        # Keep current work; retain a bounded terminal audit tail in each snapshot.
        live = [e for e in daily['queue'] if e['status'] in ('pending', 'started')]
        settled = [e for e in daily['queue'] if e['status'] not in ('pending', 'started')][-128:]
        daily['queue'] = settled + live
        daily['last_day'] = day
        daily['reviews'] = (daily['reviews'] + [{'sequence': daily['sequence'], 'day': day,
            'residents': len(town['residents']), 'new_events': added, 'model_calls': 0}])[-32:]
        return {'checkpoint': self._write(state, 'game-clock needs reviewed; feasible resident opportunities queued'),
                'new_events': added, 'next_review_day': day + INTERVAL}
