"""Explicit authored historical people used only by legacy protocol unit tests.

This is not population discovery and must never be called by production startup.
Fresh-bootstrap tests bypass this fixture and start with no residents.
"""
import copy
from decisions import PROFILES
from resident_identity import resident_identity_status,valid_binding,valid_actor_id


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


def author_fixture_identities(state,observation,actor_ids=None,event_id='authored-fixture-identity'):
    """Opt-in positive test identities; never repair or create legacy people.

    The test must supply observed base IDs. Existing conflicting bindings fail.
    Before census, only existing people are bound; no town/cohort is invented.
    A later real census binds newly created people using its own source event.
    """
    rows=observation.get('residents',[])
    if not isinstance(rows,list):raise ValueError('Fixture needs explicit observed residents')
    selected=([row['id'] for row in rows if isinstance(row,dict) and str(row.get('id')) in state.get('people',{})]
              if actor_ids is None else list(actor_ids))
    if any(not valid_actor_id(actor) for actor in selected) or len(set(selected))!=len(selected):
        raise ValueError('Fixture identity cohort must be distinct valid actor IDs')
    changes={}
    for actor in selected:
        observed=[row for row in rows if isinstance(row,dict) and row.get('id')==actor]
        if len(observed)!=1:raise ValueError('Fixture identity needs one explicit actor observation')
        base=observed[0].get('baseId')
        if not valid_actor_id(base):raise ValueError('Fixture identity requires an authored observed base ID')
        person=state.get('people',{}).get(str(actor))
        if person is None:continue  # Census owns creation and binding of new people.
        if not isinstance(person,dict):raise ValueError('Fixture person is malformed')
        resident=((state.get('town') or {}).get('residents') or {}).get(str(actor))
        existing=[row.get('identity_binding') for row in (person,resident) if isinstance(row,dict) and row.get('identity_binding') is not None]
        if any(not valid_binding(binding,actor) or binding['base_id']!=base for binding in existing):
            raise ValueError('Fixture cannot overwrite an existing identity conflict')
        if existing and any(binding!=existing[0] for binding in existing):
            raise ValueError('Fixture cannot reconcile conflicting saved identity evidence')
        binding=copy.deepcopy(existing[0]) if existing else {'schema_version':1,'actor':actor,'base_id':base,'event_id':event_id}
        candidate={'people':{str(actor):{**person,'identity_binding':binding}},
                   'town':{'residents':{str(actor):{**(resident or {'id':actor}),'identity_binding':binding}}}}
        status=resident_identity_status(candidate,observation,actor)
        if not status['qualified']:raise ValueError('Unqualified positive identity fixture: '+status['reason'])
        changes[str(actor)]=binding
    for key,binding in changes.items():
        state['people'][key]['identity_binding']=copy.deepcopy(binding)
        resident=((state.get('town') or {}).get('residents') or {}).get(key)
        if resident is not None:resident['identity_binding']=copy.deepcopy(binding)
    return sorted(int(key) for key in changes)
