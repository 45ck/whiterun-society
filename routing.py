"""Current executor capabilities, not a promise that every path is navigable."""
from activity_leases import activity_conflict


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
    """Compatibility API: every newly issued trip uses the observed mailbox."""
    return True


def actor_route_supported(observation,actor):
    """Tri-state executor evidence, independent of a destination or occupancy lease.

    Native census rows classified as isPerson are already adult/dead filtered.
    Explicit conflicting telemetry remains disqualifying; absent capability or
    classification is unknown, never inferred from an actor's identity.
    """
    if not isinstance(observation,dict):return None
    rows=[r for r in observation.get('residents',[]) if isinstance(r,dict) and r.get('id')==actor]
    if len(rows)!=1:return None
    resident=rows[0];capability=observation.get('routing')
    if resident.get('loaded') is False:return None
    if any(resident.get(key) is True for key in ('isChild','isDead')):return False
    if resident.get('isPerson') is False:return False
    if resident.get('isPerson') is not True:return None
    if not isinstance(capability,dict):return None
    if 'session' in capability and capability['session']!=observation.get('session'):return None
    if 'session' in resident and resident['session']!=observation.get('session'):return None
    if capability.get('available') is False:return False
    if isinstance(capability.get('adapter'),str) and capability['adapter']!='papyrus-mailbox-v1':return False
    if capability.get('available') is not True or capability.get('adapter')!='papyrus-mailbox-v1':return None
    blocker=activity_blocker(resident)
    if blocker=='activity_unknown':return None
    return not bool(blocker)


def route_available(observation,first,second,state=None):
    if activity_conflict(state,actors=(first,second),targets=(second,),observation=observation):return False
    if first==second:return False
    return all(actor_route_supported(observation,key) is True for key in (first,second))
