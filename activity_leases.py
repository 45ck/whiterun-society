"""Save-bound actor reservations for overlapping travel and social activity."""

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
