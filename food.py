"""Resident-owned reserves and save-bound, inventory-verified food use."""
import copy
import math
from daily_life import HUNGER_PER_GAME_HOUR
from activity_leases import activity_conflict
from economy_catalog import commodity_ids, require_native_catalog, native_catalog_matches, catalog_hash, MAX_STOCK


def allocation(person, inventory):
    count = inventory['bread']
    policy = person.get('food_policy')
    if not policy:
        return {'allocated': False, 'unallocated': count}
    reserve = count if policy['mode'] == 'household_all' else min(count, policy['reserve_target'])
    return {'allocated': True, 'household': reserve, 'for_sale': count-reserve,
            'policy': copy.deepcopy(policy), 'source': 'allocation of observed carried bread; not additional stock'}


def own_inventory(observation, actor):
    resident = next((a for a in observation.get('residents', []) if a.get('id') == actor), None)
    if not resident:
        raise ValueError('Resident is not observed')
    inventory = resident.get('inventory', {})
    if any(type(inventory.get(k)) is not int or not 0 <= inventory[k] <= MAX_STOCK for k in commodity_ids()):
        raise ValueError('Complete observed inventory required')
    return {k: inventory[k] for k in commodity_ids()}


class FoodEconomy:
    def plan_consumption(self, event_id, observation, actor, agency_plan):
        self._agency_guard(observation)
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 128:
            raise ValueError('Invalid consumption event ID')
        for old in self.active.get('consumptions', []):
            if old['id'] == event_id:
                if old['command']['actor'] != actor:
                    raise ValueError('Consumption ID reused for another resident')
                return old
        plan = self.agency_plan()
        if not plan or plan['id'] != agency_plan or plan['actor'] != actor or plan['phase'] != 'ready_to_eat':
            raise ValueError('Consumption needs a current resident decision')
        if activity_conflict(self.active,actors=(actor,),observation=observation):
            raise ValueError('An independent activity owns the consuming resident')
        bound_catalog=require_native_catalog(observation)
        if 'bread' not in commodity_ids():raise ValueError('Catalog has no supported bread consumption commodity')
        before = own_inventory(observation, actor)
        if before['bread'] < 1:
            raise ValueError('No carried loaf to consume')
        command = {'id': event_id, 'kind': 'inventory_consume', 'actor': actor,
                   'catalog_hash':bound_catalog,
                   'before': before, 'after': {**before, 'bread': before['bread']-1}}
        record = {'id': event_id, 'command': command, 'status': 'pending', 'evidence': None}
        state = copy.deepcopy(self.active)
        state['pending'] = record
        state['plans'][-1]['phase'] = 'consuming'
        return {'checkpoint': self._write(state, 'food-use intent persisted before native consumption')}

    def observe_consumption(self, observation):
        pending = self.active['pending']
        if pending.get('status')=='held':return
        if pending['command'].get('catalog_hash')!=catalog_hash() or not native_catalog_matches(observation):
            state=copy.deepcopy(self.active);state['pending'].update(status='held',error='Consumption catalog proof is missing or changed; do not replay')
            state['plans'][-1].update(phase='held',error=state['pending']['error'])
            self._write(state,'unbound consumption held without recertifying a legacy effect');return
        ack = observation.get('ack') or {}
        if ack.get('id') != pending['id']:
            return
        command = pending['command']
        try:
            actual = own_inventory(observation, command['actor'])
        except ValueError:
            return
        state = copy.deepcopy(self.active)
        state['pending']['evidence'] = {'actual': actual, 'ack': ack, 'session': self.session}
        if (ack.get('status') == 'applied' and ack.get('catalog_hash') == command['catalog_hash']
            and actual == command['after']):
            record = state['pending']
            record['status'] = 'committed'
            state.setdefault('consumptions', []).append(record)
            state['pending'] = None
            person = state['people'][str(command['actor'])]
            # Authored nutrition parameter, not vanilla Skyrim hunger physiology.
            day=observation.get('gameDays')
            before_hunger = person['needs']['hunger']
            if type(day) in (int,float) and math.isfinite(day) and day>=0:
                resident=state.get('town',{}).get('residents',{}).get(str(command['actor']))
                if resident:
                    baseline=max(person.get('needs_clock',resident['observed_game_day']),person.get('hunger_clock',0))
                    before_hunger=min(1,before_hunger+max(0,day-baseline)*24*HUNGER_PER_GAME_HOUR)
                person['hunger_clock']=day
            person['needs']['hunger'] = round(max(0, before_hunger-.6), 6)
            person['memories'].append({'event_id': pending['id'], 'kind': 'consumed_bread',
                'bread': 1, 'hunger_before': before_hunger, 'hunger_after': person['needs']['hunger'],
                'source': 'native food-use command and observed inventory; animation not verified'})
            person['memories'] = person['memories'][-32:]
            state['plans'][-1].update(phase='complete', outcome='ate_bread')
            self._write(state, 'native food use observed; hunger and memory updated')
        else:
            state['pending']['status'] = 'held'
            state['plans'][-1].update(phase='held', error='Consumption requires reconciliation')
            self._write(state, 'unexpected food-use effect held for reconciliation')
