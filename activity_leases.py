"""Save-bound actor reservations for overlapping travel and social activity."""

def activity_leases(state):
    """Terminal/held jobs retain ownership until their durable receipt is acknowledged."""
    rows=[]
    for field in ('activity_jobs','activity_orphans'):
        records=(state or {}).get(field) or {}
        if isinstance(records,dict):
            # /state exposes active leases separately from acknowledged history.
            # Metadata and historical receipts are not additional reservations.
            records=records['jobs'] if isinstance(records.get('jobs'),list) else records.values()
        elif not isinstance(records,list):continue
        rows.extend(job for job in records if isinstance(job,dict)
                    and job.get('receipt_acknowledged') is not True)
    return rows

def _reserved_activity(state,observation,field):
    native=(observation or {}).get('activity_jobs') or {}
    # Native identities can outlive their saved assignment after a rollback.
    # Never discard them merely because their session/epoch is now stale.
    rows=[*activity_leases(state),*native.get('jobs',[]),*native.get('receipts',[])]
    ids=[row.get(field) for row in rows]
    ids.extend(native.get('reserved_actors' if field=='actor' else 'reserved_targets',[]))
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
