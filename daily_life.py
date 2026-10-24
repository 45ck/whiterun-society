"""Game-clock needs and a bounded, save-bound queue of resident opportunities.

Rates are authored gameplay parameters. A queued opportunity is not a completed
activity. Unsupported rest, social and travel actions remain explicitly unmet.
"""
import copy
import math

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
            rates = {'hunger': HUNGER_PER_GAME_HOUR, 'fatigue': .025,
                     'social_contact': .018 + .025 * person['profile']['big_five']['extraversion']}
            for need, rate in rates.items():
                elapsed = max(0, day-max(last_day, person.get('hunger_clock',last_day))) * 24 if need=='hunger' else hours
                person['needs'][need] = round(min(1, person['needs'][need] + rate * elapsed), 6)
            person['needs_clock'] = day
            actor = actors.get(key)
            agency = person['agency']
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
                can_seek = int(key) in (108186, 108156) and '108149' in actors and inventory['gold'] >= 3
                if not can_eat and not can_seek:
                    agency.update(state='unmet_food_need', reason='No carried bread or qualified affordable seller route')
                    continue
                event = {'id': f"daily-{daily['sequence']}-{key}", 'actor': int(key),
                    'kind': 'need_review', 'status': 'pending', 'created_day': day,
                    'priority': person['needs']['hunger'],
                    'reason': 'Simulated hunger crossed the meal-review threshold',
                    'observed_inventory': copy.deepcopy(inventory)}
                daily['queue'].append(event)
                added.append(event['id'])
                agency.update(state='decision_pending', reason=event['reason'], event_id=event['id'])
            elif person['needs']['fatigue'] >= .8:
                agency.update(state='unmet_rest_need', reason='A verified sleep/rest executor is not implemented')
            elif person['needs']['social_contact'] >= .7:
                agency.update(state='unmet_social_need', reason='An autonomous social encounter selector is not implemented')
        # Keep current work; retain a bounded terminal audit tail in each snapshot.
        live = [e for e in daily['queue'] if e['status'] in ('pending', 'started')]
        settled = [e for e in daily['queue'] if e['status'] not in ('pending', 'started')][-128:]
        daily['queue'] = settled + live
        daily['last_day'] = day
        daily['reviews'] = (daily['reviews'] + [{'sequence': daily['sequence'], 'day': day,
            'residents': len(town['residents']), 'new_events': added, 'model_calls': 0}])[-32:]
        return {'checkpoint': self._write(state, 'game-clock needs reviewed; feasible resident opportunities queued'),
                'new_events': added, 'next_review_day': day + INTERVAL}
