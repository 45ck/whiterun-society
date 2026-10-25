"""Authored protocol receipts for service unit tests; not native evidence."""
import copy
from endowments import IDENTITY
from resource_manifest import load_manifest, manifest_hash


def resource_status(epoch='resource-test'):
    manifest=load_manifest()
    return {'available':True,'protocol':2,'epoch':epoch,'manifest_hash':manifest_hash(manifest),'catalog_hash':manifest['catalog_hash']}


def resource_ack(command):
    ack={'id':command['id'],'protocol':2,'accepted':True,**{key:copy.deepcopy(command[key]) for key in IDENTITY},'status':'applied'}
    if command['phase']=='arm':
        ack.update(accepted=True,phase='armed',permit='permit-'+command['grant_id'],effects_issued=False,no_effects_issued=True,legs=[],inventory=copy.deepcopy(command['before']))
    else:
        ack.update(phase='complete',permit=command['permit'],effects_issued=True,no_effects_issued=False,
            inventory=copy.deepcopy(command['after']),legs=[{'item':key,'amount':amount,'issued':True,'observed':True}
                for key,amount in command['grant'].items() if amount>0])
    return ack
