"""Preview an observed adult census; --apply seeds state without minting stock."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.startup_checkpoint import client_for,fresh_state,observed_cohort,apply_checkpoint,definition_hash


def initialize(client,event_id,seed,runtime,apply=False,actor_ids=None,wait_seconds=30):
    if any(not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',value) for value in (event_id,seed)):
        raise ValueError('Explicit bounded census ID and seed required')
    before=fresh_state(client);cohort=observed_cohort(before)
    if actor_ids is not None and observed_cohort(before,actor_ids)!=cohort:
        raise ValueError('Census initializes every observed adult; selected cohort must match the full preview')
    body={'id':event_id,'seed':seed,'expected_cohort':cohort}
    preview={'status':'preview','confirmed':False,'request_session':before['bridge']['session'],
        'request_checkpoint':before['society']['checkpoint'],'definition':body,'definition_hash':definition_hash(body),
        'cohort':cohort,'provenance':'Explicit seed over the current observed adult census; authored starting state, not witnessed history.',
        'scope':'No stock minted, no occupation assigned, and no routine ownership proven by this census.'}
    if not apply:return preview
    def confirms(after,result):
        town=after['society'].get('town') or {}
        event=next((row for row in town.get('census_events',[]) if row.get('id')==event_id),None)
        if (town.get('seed')==seed and event
            and all(str(row['actor']) in town.get('residents',{}) for row in cohort)):
            return {'census_event':event,'seed':seed,'managed_actor_ids':[row['actor'] for row in cohort]}
    return {**preview,**apply_checkpoint(client,'/town/initialize',body,before,cohort,confirms,runtime,'population',wait_seconds)}


def parser():
    result=argparse.ArgumentParser(description=__doc__)
    result.add_argument('--root',type=Path,required=True);result.add_argument('--id',required=True)
    result.add_argument('--seed',required=True);result.add_argument('--actors',type=int,nargs='+')
    result.add_argument('--apply',action='store_true',help='Apply this explicit census after a fresh session/checkpoint preflight')
    return result


def main(argv=None):
    args=parser().parse_args(argv);runtime=args.root/'runtime'
    result=initialize(client_for(runtime),args.id,args.seed,runtime,args.apply,args.actors)
    print(json.dumps(result));return 0 if not args.apply or result['confirmed'] else 2


if __name__=='__main__':raise SystemExit(main())
