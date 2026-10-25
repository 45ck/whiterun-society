"""Save-bound actor reservations for overlapping travel and social activity."""

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

def reserved_work_accounts(state,observation=None):
    actors=set()
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

def _reserved_activity(state,observation,field):
    native=(observation or {}).get('activity_jobs') or {}
    # Native identities can outlive their saved assignment after a rollback.
    # Never discard them merely because their session/epoch is now stale.
    rows=[*activity_leases(state),*_native_rows(observation,'activity_jobs'),*_work_rows(state,observation)]
    ids=[row.get(field) for row in rows]
    ids.extend(native.get('reserved_actors' if field=='actor' else 'reserved_targets',[]))
    if field=='actor':ids.extend(_account_actor(account) for account in reserved_work_accounts(state,observation))
    return {value for value in ids if type(value) is int and value>0}

def reserved_activity_actors(state,observation=None):
    return _reserved_activity(state,observation,'actor')

def reserved_activity_targets(state,observation=None):
    return _reserved_activity(state,observation,'target')

def activity_conflict(state,actors=(),targets=(),observation=None):
    return bool(set(actors)&reserved_activity_actors(state,observation)
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
