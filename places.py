"""Authored public-place knowledge, distinct from knowledge of people or stock."""
import math
import copy
import json
from pathlib import Path
import re
from routing import activity_blocker

MARKET = 0x2BE1B  # Legacy test/save fixture only; current routing uses catalogued observations.


def validate_venue_catalog(value):
    if (not isinstance(value, dict) or not isinstance(value.get('venues'), list) or len(value['venues']) > 512 or
            not isinstance(value.get('version'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value['version']) or
            not isinstance(value.get('knowledge'), str) or not value['knowledge'].strip() or len(value['knowledge']) > 500):
        raise ValueError('Invalid venue catalogue')
    ids = set()
    for venue in value['venues']:
        if (not isinstance(venue, dict) or type(venue.get('id')) is not int or not 0 < venue['id'] <= 0xffffffff or venue['id'] in ids or
                venue.get('kind') not in ('public_place', 'rest_bench') or
                not isinstance(venue.get('name'), str) or not venue['name'].strip() or len(venue['name']) > 120 or
                not isinstance(venue.get('provenance'), str) or not venue['provenance'].strip() or len(venue['provenance']) > 500 or
                venue.get('access') != ('inspected_unowned' if venue['kind'] == 'rest_bench' else 'public') or
                ('editor_id' in venue and (not isinstance(venue['editor_id'], str) or len(venue['editor_id']) > 120))):
            raise ValueError('Invalid venue catalogue entry')
        ids.add(venue['id'])
    return copy.deepcopy(value)


VENUE_CATALOG = validate_venue_catalog(json.loads((Path(__file__).parent / 'config/places.json').read_text(encoding='utf-8')))


def registered_venues(kind):
    """Startup config shared with native JS; no discovery or NPC identity inference."""
    return {v['id']: copy.deepcopy(v) for v in VENUE_CATALOG['venues'] if v['kind'] == kind}


def catalogued_site(site, kind):
    venue = registered_venues(kind).get(site.get('id'))
    if venue is None or ('catalog_version' in site and site['catalog_version'] != VENUE_CATALOG['version']):
        return None
    if any(key in site and site[key] != venue[key] for key in ('kind', 'name', 'access', 'provenance')):
        return None
    return {**site, **venue, 'catalog_version': VENUE_CATALOG['version'], 'knowledge': VENUE_CATALOG['knowledge']}


def same_venue_space(resident, site):
    a, b = resident.get('space'), site.get('space')
    # Explicit compatibility for pre-space synthetic fixtures; one-sided or
    # current-catalog missing geometry is never accepted as a matching space.
    if a is None and b is None and 'catalog_version' not in site:
        return True
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    if type(a.get('cell')) is int and a['cell'] > 0 and a.get('cell') == b.get('cell'):
        return True
    return (a.get('interior') is False and b.get('interior') is False and
            type(a.get('world')) is int and a['world'] > 0 and a['world'] == b.get('world'))


def venue_distance(resident, site):
    if not same_venue_space(resident, site):
        return None
    values = [resident.get(k) for k in ('x', 'y', 'z')]
    position = site.get('position')
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        return None
    if any(type(n) not in (int, float) or not math.isfinite(n) for n in values + list(position)):
        return None
    return math.dist(values, position)


def market_opportunities(state, observation, actor):
    person = state.get('people', {}).get(str(actor), {})
    capability = observation.get('routing') or {}
    if capability.get('available') is not True or capability.get('places') is not True:
        return []
    resident = next((r for r in observation.get('residents', [])
                     if r['id'] == actor and r.get('isPerson') is True), None)
    if not resident or activity_blocker(resident):
        return []
    day = observation.get('gameDays')
    if type(day) not in (int, float) or not math.isfinite(day):
        return []
    # Remember an unsuccessful search rather than buying another model call each tick.
    avoided = {m['place'] for m in person.get('memories', [])
               if m.get('kind') == 'market_seller_not_observed' and type(m.get('day')) in (int, float)
               and type(m.get('place')) is int and math.isfinite(m['day']) and 0 <= day - m['day'] < 4/24}
    result = []
    for site in observation.get('places', []):
        venue = catalogued_site(site, 'public_place')
        if venue is None or site.get('id') in avoided or site.get('available') is not True or actor not in site.get('eligible_actors', []):
            continue
        gap = venue_distance(resident, site)
        if gap is None:
            continue
        result.append({'id': venue['id'], 'name': venue['name'], 'distance': gap,
            'catalog_version': venue['catalog_version'],
            'knowledge': venue['knowledge'] + ' Seller presence, stock and opening hours are unknown.'})
    return sorted(result, key=lambda site: (site['distance'], site['id']))


def market_opportunity(state, observation, actor, target=None):
    sites = market_opportunities(state, observation, actor)
    return next((site for site in sites if target is None or site['id'] == target), None)


def at_market(observation, actor, target=None):
    resident = next((r for r in observation.get('residents', []) if r['id'] == actor), None)
    if not resident:
        return False
    for site in observation.get('places', []):
        if target is not None and site.get('id') != target:
            continue
        if catalogued_site(site, 'public_place') is None or site.get('available') is not True or actor not in site.get('eligible_actors', []):
            continue
        gap = venue_distance(resident, site)
        if gap is not None and gap <= 300:
            return True
    return False
