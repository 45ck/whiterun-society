"""Current enterprise inputs and public suppliers; no stock omniscience or imports."""
from enterprises import production_policy
from opportunities import commodity_sellers


def grain_procurement(state, observation, actor):
    native=next((r for r in observation.get('residents',[]) if r.get('id')==actor),{})
    inventory=native.get('inventory',{})
    if any(type(inventory.get(k)) is not int or inventory[k]<0 for k in ('gold','bread','grain')):
        return []
    if inventory['gold']<1:return []
    own=[]
    for key,b in sorted((state.get('town') or {}).get('businesses',{}).items()):
        if b.get('active',True) is not True or b.get('custodian')!=actor or 'bread_recipe' not in b.get('capabilities',[]):continue
        policy=production_policy(b)
        # Inputs already held cover the target; another purchase is not required.
        required=max(0,(policy['target_bread']-inventory['bread']+1)//2-inventory['grain'])
        if required:own.append({'business_id':key,'revision':b.get('revision',0),'grain_shortfall':required})
    if not own:return []
    return [{**seller,'own_businesses':own} for seller in commodity_sellers(state,observation,actor,'grain')]
