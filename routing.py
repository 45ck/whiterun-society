"""Current executor capabilities, not a promise that every path is navigable."""
from activity_leases import activity_conflict
FIXED_RESIDENTS={108149,108186,108156}


def activity_blocker(resident):
    """Current engine occupancy; missing legacy telemetry is not a busy claim."""
    if 'activity' not in resident:return None
    activity=resident.get('activity')
    if not isinstance(activity,dict):return 'activity_unknown'
    scene=activity.get('scene_id');combat=activity.get('in_combat');sleep=activity.get('sleep_state')
    if type(scene) is not int or scene<0 or type(combat) is not bool or type(sleep) is not int or not 0<=sleep<=4:
        return 'activity_unknown'
    if scene:return 'native_scene'
    if combat:return 'combat'
    if sleep:return 'sleep_transition'
    return None


def dynamic_route(first,second):
    return first not in FIXED_RESIDENTS or second not in FIXED_RESIDENTS


def route_available(observation,first,second,state=None):
    if activity_conflict(state,actors=(first,second),targets=(second,),observation=observation):return False
    actors={a['id']:a for a in observation.get('residents',[])}
    if first==second or first not in actors or second not in actors:return False
    if any(activity_blocker(actors[key]) for key in (first,second)):return False
    if not dynamic_route(first,second):return True
    capability=observation.get('routing') or {}
    return (capability.get('adapter')=='papyrus-mailbox-v1' and capability.get('available') is True
            and all(actors[key].get('isPerson') is True for key in (first,second)))
