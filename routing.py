"""Current executor capabilities, not a promise that every path is navigable."""
FIXED_RESIDENTS={108149,108186,108156}


def dynamic_route(first,second):
    return first not in FIXED_RESIDENTS or second not in FIXED_RESIDENTS


def route_available(observation,first,second):
    actors={a['id']:a for a in observation.get('residents',[])}
    if first==second or first not in actors or second not in actors:return False
    if not dynamic_route(first,second):return True
    capability=observation.get('routing') or {}
    return (capability.get('adapter')=='papyrus-mailbox-v1' and capability.get('available') is True
            and all(actors[key].get('isPerson') is True for key in (first,second)))
