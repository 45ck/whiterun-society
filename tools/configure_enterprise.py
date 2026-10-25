"""Preview an exact enterprise specification; --apply writes a save-bound charter."""
import argparse
import copy
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from enterprises import apply_enterprise_change
from tools.startup_checkpoint import client_for,fresh_state,observed_cohort,apply_checkpoint,definition_hash,frozen


PROVENANCE='Explicit operator-authored charter; assets stay in each physical custodian inventory'


def configure(client,event_id,specification,runtime,apply=False,wait_seconds=30):
    if not isinstance(event_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',event_id):raise ValueError('Invalid enterprise event ID')
    specification=frozen(specification)
    if not isinstance(specification,dict):raise ValueError('Expected enterprise specification')
    before=fresh_state(client);cohort=observed_cohort(before,[specification.get('custodian')])
    town=before['society'].get('town') or {}
    if not town:raise ValueError('Initialize the population before registering enterprises')
    previous=next((row for row in town.get('enterprise_events',[]) if row.get('id')==event_id),None)
    if previous:
        if previous.get('request')!=specification:raise ValueError('Enterprise event ID reused with different terms')
        business=town.get('businesses',{}).get(specification['id'])
    else:
        business,_=apply_enterprise_change(copy.deepcopy(before['society']),event_id,specification,
            before['bridge']['observation'],PROVENANCE)
    preview={'status':'preview','confirmed':False,'definition':specification,'definition_hash':definition_hash(specification),
        'cohort':cohort,'business_preview':business,'provenance':PROVENANCE,
        'request_session':before['bridge']['session'],'request_checkpoint':before['society']['checkpoint'],
        'scope':'An authored charter is not observed work, inventory transfer, a sale or profit.'}
    if not apply:return preview
    def confirms(after,result):
        row=next((row for row in (after['society'].get('town') or {}).get('enterprise_events',[])
            if row.get('id')==event_id and row.get('request')==specification),None)
        if row:return {'enterprise_event':row}
    body={'id':event_id,'enterprise':specification}
    return {**preview,**apply_checkpoint(client,'/town/enterprise',body,before,cohort,confirms,runtime,'enterprise',wait_seconds)}


def parser():
    result=argparse.ArgumentParser(description=__doc__)
    result.add_argument('--runtime',type=Path,required=True);result.add_argument('--id',required=True)
    result.add_argument('--spec',type=Path,required=True);result.add_argument('--apply',action='store_true')
    return result


def main(argv=None):
    args=parser().parse_args(argv);specification=json.loads(args.spec.read_text(encoding='utf-8-sig'))
    result=configure(client_for(args.runtime),args.id,specification,args.runtime,args.apply)
    print(json.dumps(result));return 0 if not args.apply or result['confirmed'] else 2


if __name__=='__main__':raise SystemExit(main())
