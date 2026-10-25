"""Current public business capabilities, not another resident's private stock."""
import math
from knowledge import person_view
from routing import route_available
from market_policy import goods_policy, advertised_goods


def commodity_sellers(state, observation, buyer, commodity):
    goods_policy(commodity)
    town = state.get('town') or {}
    listings = [(key, b) for key, b in sorted(town.get('businesses', {}).items())
                if commodity in advertised_goods(b)]
    actors = {r['id']: r for r in observation.get('residents', [])}
    own = actors.get(buyer, {})
    result = []
    for key, business in listings:
        seller = business.get('custodian')
        if seller==buyer or str(seller) not in state.get('people', {}) or not route_available(observation, buyer, seller,state):
            continue
        if (str(seller) not in town.get('residents', {}) or
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
                       'listing_business_id': key, 'listing_revision': business.get('revision', 0),
                       'commodity': commodity,
                       'capability_source': 'public '+commodity+'-enterprise charter; stock and consent unknown'})
    return sorted(result, key=lambda row: (row['distance'] if row['distance'] is not None else float('inf'), row['id']))


def food_sellers(state, observation, buyer):
    result = {}
    for row in commodity_sellers(state, observation, buyer, 'bread'):result.setdefault(row['id'], row)
    return list(result.values())
