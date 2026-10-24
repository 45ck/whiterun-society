"""Authored public-place knowledge, distinct from knowledge of people or stock."""
import math

MARKET = 0x2BE1B  # Owned Skyrim.esm: WhiterunMarketplaceMarker.


def market_opportunity(state, observation, actor):
    person = state.get('people', {}).get(str(actor), {})
    if actor == 108149 or person.get('commitments'):
        return None
    capability = observation.get('routing') or {}
    if capability.get('available') is not True or capability.get('places') is not True:
        return None
    resident = next((r for r in observation.get('residents', [])
                     if r['id'] == actor and r.get('isPerson') is True and r.get('isGuard') is False), None)
    if not resident:
        return None
    day = observation.get('gameDays')
    if type(day) not in (int, float) or not math.isfinite(day):
        return None
    # Remember an unsuccessful search rather than buying another model call each tick.
    if any(m.get('kind') == 'market_seller_not_observed' and
           type(m.get('day')) in (int, float) and day - m['day'] < 4/24
           for m in person.get('memories', [])):
        return None
    for site in observation.get('places', []):
        if site.get('id') == MARKET and site.get('available') is True and actor in site.get('eligible_actors', []):
            return {'id': MARKET, 'name': 'Whiterun market',
                    'knowledge': 'Authored starting knowledge of a public market; seller presence, stock and opening hours are unknown.'}
    return None


def at_market(observation, actor):
    resident = next((r for r in observation.get('residents', []) if r['id'] == actor), None)
    site = next((p for p in observation.get('places', []) if p.get('id') == MARKET), None)
    if not resident or not site or site.get('available') is not True or actor not in site.get('eligible_actors', []):
        return False
    try:
        gap = math.dist([resident[k] for k in ('x', 'y', 'z')], site['position'])
        return math.isfinite(gap) and gap <= 300
    except (KeyError, TypeError, ValueError):
        return False
