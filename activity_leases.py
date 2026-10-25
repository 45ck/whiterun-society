"""Save-bound actor reservations for overlapping travel and social activity."""

from resident_identity import resident_identity_status


def identity_quarantine_actors(state, observation=None):
    """Exclude unqualified census identities without altering historical records.

    These are admission exclusions, not native leases or authority to release
    an actor. Hand-authored pre-census fixtures retain their separate boundary.
    """
    state=state or {};residents=(state.get('town') or {}).get('residents') or {}
    if not isinstance(residents,dict):return set()
    actors=set()
    for key in residents:
        if (not isinstance(key,str) or not key.isascii() or not key.isdigit()
                or len(key)>10 or str(int(key))!=key or not 0<int(key)<=0xffffffff):continue
        actor=int(key)
        if not resident_identity_status(state,observation or {},actor)['qualified']:actors.add(actor)
    return actors

def _saved_leases(state,fields):
    rows=[]
    for field in fields:
        records=(state or {}).get(field) or {}
        if isinstance(records,dict):
            # /state exposes active leases separately from acknowledged history.
            # Metadata and historical receipts are not additional reservations.
            records=records['jobs'] if isinstance(records.get('jobs'),list) else records.values()
        elif not isinstance(records,list):continue
        rows.extend(job for job in records if isinstance(job,dict)
                    and job.get('receipt_acknowledged') is not True)
    return rows

def activity_leases(state):
    """Rest protocol jobs only; work jobs must never enter rest command emission."""
    return _saved_leases(state,('activity_jobs','activity_orphans'))

def owner_work_leases(state):
    """Work accounts remain reserved through settlement, release and exact ack."""
    return _saved_leases(state,('work_jobs','work_orphans','owner_work_jobs'))

def _native_rows(observation,key):
    native=(observation or {}).get(key) or {}
    return [row for field in ('jobs','receipts') for row in native.get(field,[]) if isinstance(row,dict)]

def _work_rows(state,observation):
    return [*owner_work_leases(state),*_native_rows(observation,'owner_work_jobs')]

def _account_actor(value):
    if not isinstance(value,str) or not value.startswith('native-inventory:'):return None
    suffix=value.removeprefix('native-inventory:')
    return int(suffix) if len(suffix)<=10 and suffix.isascii() and suffix.isdigit() and str(int(suffix))==suffix and int(suffix)>0 else None

def reserved_work_accounts(state,observation=None,*,include_identity=True):
    actors=resource_quarantine_actors(state,observation)|trade_quarantine_actors(state,observation)
    if include_identity:actors.update(identity_quarantine_actors(state,observation))
    for row in _work_rows(state,observation):
        actors.update(row.get(field) for field in ('actor','custodian','account_actor')
                      if type(row.get(field)) is int and row[field]>0)
        account=_account_actor(row.get('resource_account'))
        if account:actors.add(account)
    native=(observation or {}).get('owner_work_jobs') or {}
    actors.update(a for a in native.get('reserved_actors',[]) if type(a) is int and a>0)
    return {'native-inventory:'+str(actor) for actor in actors}

def reserved_work_businesses(state,observation=None):
    return {row['business_id'] for row in _work_rows(state,observation)
            if isinstance(row.get('business_id'),str) and row['business_id']}

def work_account_conflict(state,actors=(),business_ids=(),observation=None):
    accounts={'native-inventory:'+str(actor) for actor in actors if type(actor) is int and actor>0}
    return bool(accounts&reserved_work_accounts(state,observation)
                or set(business_ids)&reserved_work_businesses(state,observation))

def resource_quarantine_actors(state,observation=None):
    """Unsettled imports reserve their recipient even when delivery is held.

    A native arm can survive a service rollback. Missing saved identity cannot
    authorize a different resident to spend an ambiguous inventory account.
    """
    state=state or {};observation=observation or {};actors=set();unknown=False
    valid=lambda value:type(value) is int and 0<value<=0xffffffff
    for record in (state.get('pending'),state.get('resource_delivery')):
        if not isinstance(record,dict):continue
        command=record.get('command')
        if not isinstance(command,dict) or command.get('kind')!='inventory_endowment':continue
        if record.get('status') in ('committed','complete'):continue
        identities=[command.get('actor')]
        if 'actor' in record:identities.append(record['actor'])
        if 'recipient' in record:
            recipient=record['recipient']
            identities.append(recipient.get('actor') if isinstance(recipient,dict) else None)
        actors.update(value for value in identities if valid(value))
        unknown=unknown or not all(valid(value) for value in identities)
    native=observation.get('resource_import') or {}
    if isinstance(native,dict) and 'reserved_actors' in native:
        reserved=native['reserved_actors']
        if isinstance(reserved,list):
            actors.update(value for value in reserved if valid(value))
            unknown=unknown or not all(valid(value) for value in reserved)
        else:unknown=True
    if unknown:
        for people in (state.get('people'),(state.get('town') or {}).get('residents')):
            if isinstance(people,dict):
                actors.update(int(key) for key in people if isinstance(key,str) and key.isascii() and key.isdigit()
                              and len(key)<=10 and str(int(key))==key and valid(int(key)))
        for field in ('residents','inventory_observations'):
            actors.update(row['id'] for row in observation.get(field,[]) if isinstance(row,dict) and valid(row.get('id')))
    return actors

def trade_quarantine_actors(state,observation=None):
    """Both sides of an unresolved exchange remain unavailable for new work.

    Native orphan leases survive saved-state rollback. Malformed participants
    cannot be interpreted as a free account; reserve the observed population.
    """
    state=state or {};observation=observation or {};actors=set();unknown=False
    valid=lambda value:type(value) is int and 0<value<=0xffffffff
    for record in (state.get('pending'),state.get('unsettled_effect')):
        if not isinstance(record,dict):continue
        command=record.get('command')
        if not isinstance(command,dict) or command.get('kind')!='inventory_trade':continue
        if record.get('status') in ('committed','complete'):continue
        pair=[command.get('buyer'),command.get('seller')]
        actors.update(value for value in pair if valid(value))
        unknown=unknown or not all(valid(value) for value in pair) or pair[0]==pair[1]
    native=observation.get('trade_execution') or {}
    if isinstance(native,dict) and 'reserved_actors' in native:
        reserved=native['reserved_actors']
        if isinstance(reserved,list):
            actors.update(value for value in reserved if valid(value))
            unknown=unknown or not all(valid(value) for value in reserved)
        else:unknown=True
    if unknown:
        for people in (state.get('people'),(state.get('town') or {}).get('residents')):
            if isinstance(people,dict):
                actors.update(int(key) for key in people if isinstance(key,str) and key.isascii() and key.isdigit()
                              and len(key)<=10 and str(int(key))==key and valid(int(key)))
        for field in ('residents','inventory_observations'):
            actors.update(row['id'] for row in observation.get(field,[]) if isinstance(row,dict) and valid(row.get('id')))
    return actors


def conversation_quarantine_actors(state,observation=None):
    """Reserve ambiguous cleanup participants without choosing a release owner.

    Only terminal-held cleanup is added here. Active/releasing conversations
    retain their existing gates so claims cannot conflict with their own lease.
    """
    state=state or {};conversation=state.get('conversation') or {}
    if not isinstance(conversation,dict) or conversation.get('phase')!='held' or not (
            conversation.get('release_required') is True or conversation.get('cleanup_review_required') is True):return set()
    route=conversation.get('meeting_route');scenario=conversation.get('scenario')
    candidates=[conversation.get('initiator'),conversation.get('partner')]
    if isinstance(route,dict):candidates.extend((route.get('actor'),route.get('target')))
    if isinstance(conversation.get('speakers'),list):candidates.extend(conversation['speakers'])
    if isinstance(scenario,dict) and isinstance(scenario.get('participants'),list):candidates.extend(scenario['participants'])
    valid=lambda value:type(value) is int and 0<value<=0xffffffff
    actors={value for value in candidates if valid(value)}
    pairs=[]
    if 'meeting_route' in conversation:pairs.append([route.get('actor'),route.get('target')] if isinstance(route,dict) else None)
    if 'initiator' in conversation or 'partner' in conversation:pairs.append([conversation.get('initiator'),conversation.get('partner')])
    if 'speakers' in conversation:pairs.append(conversation['speakers'])
    if 'scenario' in conversation:pairs.append(scenario.get('participants') if isinstance(scenario,dict) else None)
    complete=lambda pair:isinstance(pair,list) and len(pair)==2 and all(valid(value) for value in pair) and pair[0]!=pair[1]
    if len(actors)>=2 and all(complete(pair) for pair in pairs):return actors
    for people in (state.get('people'),(state.get('town') or {}).get('residents')):
        if isinstance(people,dict):
            actors.update(int(key) for key in people if isinstance(key,str) and key.isascii() and key.isdigit()
                          and len(key)<=10 and str(int(key))==key and valid(int(key)))
    control=((state.get('town') or {}).get('resident_control') or {}).get('assignments') or {}
    if isinstance(control,dict):actors.update(row.get('actor') for row in control.values() if isinstance(row,dict) and valid(row.get('actor')))
    actors.update(row.get('id') for row in (observation or {}).get('residents',[])
                  if isinstance(row,dict) and valid(row.get('id')))
    return actors


def _reserved_activity(state,observation,field,include_identity=True):
    native=(observation or {}).get('activity_jobs') or {}
    # Native identities can outlive their saved assignment after a rollback.
    # Never discard them merely because their session/epoch is now stale.
    rows=[*activity_leases(state),*_native_rows(observation,'activity_jobs'),*_work_rows(state,observation)]
    ids=[row.get(field) for row in rows]
    ids.extend(native.get('reserved_actors' if field=='actor' else 'reserved_targets',[]))
    if field=='actor':
        # Cleanup may exclude identity admission checks, but must retain every
        # actual work/resource/trade reservation, including unresolved leases.
        ids.extend(_account_actor(account) for account in reserved_work_accounts(state,observation,include_identity=include_identity))
        ids.extend(conversation_quarantine_actors(state,observation))
        ids.extend(resource_quarantine_actors(state,observation))
    return {value for value in ids if type(value) is int and value>0}

def reserved_activity_actors(state,observation=None,*,include_identity=True):
    return _reserved_activity(state,observation,'actor',include_identity=include_identity)

def reserved_activity_targets(state,observation=None):
    return _reserved_activity(state,observation,'target')

def activity_conflict(state,actors=(),targets=(),observation=None,*,include_identity=True):
    return bool(set(actors)&reserved_activity_actors(state,observation,include_identity=include_identity)
                or set(targets)&reserved_activity_targets(state,observation))

def background_cohort(state):
    batches=(state or {}).get('routine_batches',[])
    return batches[-1] if batches else (state or {}).get('routine_batch')

def routine_actors(state):
    batch=background_cohort(state)
    if not batch or batch.get('phase') in ('complete','held') and not batch.get('unverified_release'):return set()
    return {m['actor'] for m in batch['members'] if m['phase'] not in ('complete','held') or
            batch.get('unverified_release') and not m.get('receipt',{}).get('release_verified')}

def background_social_ready(state,existing=False):
    batch=background_cohort(state)
    return bool(batch and batch.get('background') is True and batch.get('launched') is True
                and (batch['phase']=='travelling' or existing and batch.get('unverified_release')))
