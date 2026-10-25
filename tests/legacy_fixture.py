"""Explicit authored historical people used only by legacy protocol unit tests.

This is not population discovery and must never be called by production startup.
Fresh-bootstrap tests bypass this fixture and start with no residents.
"""
import copy
from decisions import PROFILES


def historical_people():
    return {str(actor): {'profile':copy.deepcopy(profile),'memories':[],'trust':{},'needs':{'hunger':.4}}
            for actor,profile in PROFILES.items()}


def install_legacy_people(world):
    """Persist a separate historical test checkpoint after empty bootstrap binds."""
    if (not world.active or world.transition or world.active.get('pending')
            or world.active.get('people')):
        raise ValueError('Legacy test people require an empty, bound test timeline')
    state=copy.deepcopy(world.active);state['people']=historical_people()
    return world._write(state,'Explicit authored historical population fixture; not bootstrap discovery')
