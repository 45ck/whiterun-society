"""Current public business capabilities, not another resident's private stock."""
import math
from knowledge import person_view
from routing import route_available


def commodity_sellers(state, observation, buyer, commodity):
    if commodity not in ('bread','grain'):raise ValueError('Unsupported sale commodity')
    capability='retail_food' if commodity=='bread' else 'retail_grain'
    town = state.get('town')
    if town is None:
        # Compatibility for explicitly authored pre-census demonstrations only.
        ids = [108149] if commodity=='bread' else []
    else:
        ids = sorted({b['custodian'] for b in town.get('businesses', {}).values()
                      if b.get('active', True) is True and capability in b.get('capabilities', [])})
    actors = {r['id']: r for r in observation.get('residents', [])}
    own = actors.get(buyer, {})
    result = []
    for seller in ids:
        if seller==buyer or str(seller) not in state.get('people', {}) or not route_available(observation, buyer, seller,state):
            continue
        if town is not None and (str(seller) not in town.get('residents', {}) or
                actors[seller].get('isPerson') is not True):
            continue
        try:
            gap = math.dist([own[k] for k in ('x', 'y', 'z')], [actors[seller][k] for k in ('x', 'y', 'z')])
        except KeyError:
            gap = None  # A route capability is known; range is not yet observed.
        except (TypeError, ValueError):
            continue
        if gap is not None and not math.isfinite(gap):
            continue
        result.append({**person_view(state, buyer, seller), 'distance': round(gap, 1) if gap is not None else None,
                       'capability_source': 'public '+commodity+'-enterprise charter; stock and consent unknown'})
    return sorted(result, key=lambda row: (row['distance'] if row['distance'] is not None else float('inf'), row['id']))


def food_sellers(state, observation, buyer):
    return commodity_sellers(state, observation, buyer, 'bread')
