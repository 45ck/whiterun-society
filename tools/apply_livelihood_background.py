"""Preview explicit starting recipe knowledge; --apply freezes it in this save."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from livelihood_backgrounds import load_livelihood_manifest,validate_livelihood_manifest,livelihood_manifest_hash
from tools.startup_checkpoint import client_for,fresh_state,observed_cohort,apply_checkpoint,frozen


def apply_background(client,event_id,seed,manifest,actor_ids,runtime,apply=False,wait_seconds=30):
    manifest=validate_livelihood_manifest(frozen(manifest));digest=livelihood_manifest_hash(manifest)
    before=fresh_state(client);cohort=observed_cohort(before,actor_ids)
    body={'id':event_id,'seed':seed,'scenario_id':manifest['id'],'scenario_hash':digest,
        'actor_ids':[row['actor'] for row in cohort],'expected_checkpoint':before['society']['checkpoint']}
    proposed=client('/town/livelihood-background/preview',frozen(body))
    background=frozen(proposed.get('background'))
    expected_request={'event_id':event_id,**{key:body[key] for key in ('seed','scenario_id','scenario_hash','actor_ids')}}
    if (not isinstance(background,dict) or background.get('manifest')!=manifest
        or background.get('request')!=expected_request or background.get('cohort')!=cohort
        or background.get('scenario_hash')!=digest):
        raise ValueError('Preview does not match the reviewed manifest, exact request and observed cohort')
    preview={'status':'preview','confirmed':False,'scenario_id':manifest['id'],'scenario_hash':digest,
        'cohort':cohort,'background':background,'provenance':background.get('provenance'),
        'request_session':before['bridge']['session'],'request_checkpoint':before['society']['checkpoint'],
        'scope':background.get('scope')}
    if not apply:return preview
    def matches(value):
        return isinstance(value,dict) and all(value.get(key)==item for key,item in background.items())
    def confirms(after,result):
        if not matches(result.get('background')):return None
        row=next((row for row in (after['society'].get('town') or {}).get('livelihood_backgrounds',[]) if matches(row)),None)
        if row:return {'livelihood_background':row}
    return {**preview,**apply_checkpoint(client,'/town/livelihood-background',body,before,cohort,confirms,
        runtime,'livelihood-background',wait_seconds)}


def parser():
    result=argparse.ArgumentParser(description=__doc__)
    result.add_argument('--root',type=Path,required=True);result.add_argument('--id',required=True)
    result.add_argument('--seed',required=True);result.add_argument('--scenario',type=Path,required=True)
    result.add_argument('--actors',type=int,nargs='+',required=True,help='Explicit currently observed adult reference IDs')
    result.add_argument('--apply',action='store_true',help='Apply the reviewed manifest/cohort after a fresh save preflight')
    return result


def main(argv=None):
    args=parser().parse_args(argv);runtime=args.root/'runtime';manifest=load_livelihood_manifest(args.scenario)
    result=apply_background(client_for(runtime),args.id,args.seed,manifest,args.actors,runtime,args.apply)
    print(json.dumps(result));return 0 if not args.apply or result['confirmed'] else 2


if __name__=='__main__':raise SystemExit(main())
