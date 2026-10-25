"""Exact private decision evidence authorizes one trade, never standing access."""
import copy
import hashlib
from economy_catalog import catalog_hash, canonical_json
from market_policy import policy_hash, goods_policy
from food import allocation


def consent_envelope(payload, prefix='resident'):
    digest=hashlib.sha256(canonical_json(payload).encode('utf-8')).hexdigest()
    return {'consent_id':prefix+'-'+digest[:40],'consent_hash':digest,'payload':copy.deepcopy(payload),
            'purpose':payload.get('purpose','other')}


def reserved_sale_consent(state,event_id,buyer,seller,quantity,unit_price,agency_plan,inventory,commodity='bread'):
    plans=state.get('plans') or []
    if not agency_plan or not plans:return None
    plan=plans[-1];consent=plan.get('reserve_release')
    if not consent or plan.get('id')!=agency_plan or plan.get('phase') not in ('ready_to_trade','trading'):return None
    if (plan.get('trade_id')!=event_id or plan.get('actor')!=buyer or plan.get('target')!=seller
        or plan.get('unit_price',3)!=unit_price or plan.get('quantity',1)!=quantity
        or plan.get('commodity','bread')!=commodity):return None
    decisions=plan.get('decisions') or []
    if not decisions:return None
    source=decisions[-1]
    if plan.get('counter_quote_accepted'):
        quote=plan.get('counter_quote') or {}
        if (source.get('actor_id')!=buyer or source.get('decision',{}).get('action_id')!='accept_counterprice'
            or quote.get('inventory')!=inventory or quote.get('release_reserved') is not True):return None
        source=next((d for d in decisions if d.get('claim_id')==quote.get('claim_id')), {})
        if source.get('actor_id')!=seller or source.get('decision',{}).get('action_id')!='ask_price_'+str(unit_price):return None
    elif source.get('actor_id')!=seller or source.get('decision',{}).get('action_id')!='sell_reserved_bread':return None
    expected={'plan_id':agency_plan,'trade_id':event_id,'buyer':buyer,'seller':seller,'commodity':commodity,
        'quantity':quantity,'unit_price':unit_price,'policy':state.get('people',{}).get(str(seller),{}).get('food_policy'),
        'catalog_hash':catalog_hash(),'market_policy_hash':policy_hash(),
        'inventory':inventory,'decision_claim_id':source.get('claim_id')}
    return copy.deepcopy(consent) if consent==expected else None


def accepted_trade_consent(state,event_id,buyer,seller,quantity,unit_price,agency_plan,inventory,commodity='bread'):
    plans=state.get('plans') or []
    if not plans or plans[-1].get('id')!=agency_plan:raise ValueError('Trade has no matching resident plan')
    plan=plans[-1];accepted=plan.get('accepted_trade') or {}
    purpose=plan.get('purpose','food' if plan.get('intent')=='seek_bread' else 'other')
    if purpose not in ('food','production_input','other'):raise ValueError('Unknown trade purpose')
    terms={'buyer':buyer,'seller':seller,'commodity':commodity,'quantity':quantity,'unit_price':unit_price,
           'cost':quantity*unit_price,'catalog_hash':catalog_hash(),'market_policy_hash':policy_hash(),'purpose':purpose}
    if (plan.get('phase') not in ('ready_to_trade','trading') or plan.get('trade_id')!=event_id
        or plan.get('actor')!=buyer or plan.get('target')!=seller
        or plan.get('commodity','bread')!=commodity or plan.get('quantity',1)!=quantity
        or plan.get('unit_price',3)!=unit_price
        or set(accepted)!=set(terms)|{'buyer_claim_id','seller_claim_id'}
        or any(accepted.get(k)!=v or type(accepted.get(k)) is not type(v) for k,v in terms.items())):
        raise ValueError('Accepted resident trade terms are missing or changed')
    decisions=plan.get('decisions') or [];proof=[]
    for role,actor in (('buyer',buyer),('seller',seller)):
        claim_id=accepted[role+'_claim_id'];matches=[d for d in decisions if d.get('claim_id')==claim_id]
        if not isinstance(claim_id,str) or not claim_id or len(matches)!=1:raise ValueError('Accepted trade claim provenance is missing')
        decision=matches[0];context=decision.get('context') or {};action=decision.get('decision',{}).get('action_id')
        if (decision.get('actor_id')!=actor or context.get('actor_id')!=actor
            or context.get('commodity','bread')!=commodity or context.get('quantity',1)!=quantity
            or context.get('inventory_catalog_hash')!=terms['catalog_hash']
            or context.get('market_policy_hash')!=terms['market_policy_hash']
            or context.get('observed_inventory')!=inventory[role]
            or action not in [o.get('id') for o in context.get('options',[]) if isinstance(o,dict)]):
            raise ValueError('Accepted trade decision does not match its qualified context')
        other=seller if role=='buyer' else buyer
        partner=(context.get('economic_counterparty') or {}).get('id')
        if role=='buyer' and isinstance(action,str) and action.startswith('seek_bread'):
            partner=context.get('option_targets',{}).get(action)
        if (context.get('event',{}).get('id')!=agency_plan or partner!=other
            or context.get('purpose')!=purpose):
            raise ValueError('Accepted trade decision belongs to another encounter or purpose')
        priced_action=action in context.get('price_options',{})
        if not priced_action and (context.get('unit_price')!=unit_price
            or context.get('cost')!=quantity*unit_price):
            raise ValueError('Accepted trade decision price or total changed')
        if role=='seller':
            expected='ask_price_'+str(unit_price) if plan.get('counter_quote_accepted') else None
            if action!=expected and not (expected is None and action in ('sell_goods','sell_bread','sell_grain','sell_reserved_bread')):
                raise ValueError('Seller did not accept these trade terms')
        elif plan.get('counter_quote_accepted'):
            if action!='accept_counterprice':raise ValueError('Buyer did not accept this counteroffer')
        elif action!='bid_price_'+str(unit_price) and not (
            unit_price==3 and action.startswith('seek_bread') or unit_price==5 and action=='raise_offer'):
            raise ValueError('Buyer did not offer this price')
        if (action.startswith(('bid_price_','ask_price_')) or action=='raise_offer' or priced_action) and context.get('price_options',{}).get(action)!=unit_price:
            raise ValueError('Accepted price lacks a qualified choice')
        proof.append({'role':role,'actor':actor,'claim_id':claim_id,'action_id':action})
    if plan.get('counter_quote_accepted'):
        quote=plan.get('counter_quote') or {}
        if (quote.get('buyer')!=buyer or quote.get('seller')!=seller or quote.get('commodity','bread')!=commodity
            or quote.get('quantity',1)!=quantity or quote.get('unit_price')!=unit_price
            or quote.get('cost')!=quantity*unit_price or quote.get('purpose')!=purpose
            or quote.get('catalog_hash')!=catalog_hash() or quote.get('market_policy_hash')!=policy_hash()
            or quote.get('inventory')!=inventory['seller'] or quote.get('claim_id')!=accepted['seller_claim_id']):
            raise ValueError('Accepted seller quote changed before physical trade')
    release=None
    if goods_policy(commodity)['reserve_mode']=='existing_food_policy':
        stock=allocation(state['people'].get(str(seller),{}),inventory['seller'])
        if stock['allocated'] and stock['for_sale']<quantity:
            release=reserved_sale_consent(state,event_id,buyer,seller,quantity,unit_price,agency_plan,inventory['seller'],commodity)
            if not release:raise ValueError('This trade would spend the resident household reserve without exact consent')
    procurement=None
    if purpose=='production_input':
        from procurement import PINS, validate_procurement_terms
        selected=plan.get('procurement');claim_id=plan.get('procurement_claim_id')
        if not validate_procurement_terms(state,buyer,selected):raise ValueError('Procurement enterprise or listing terms changed')
        matches=[d for d in decisions if d.get('claim_id')==claim_id]
        if not isinstance(claim_id,str) or len(matches)!=1:raise ValueError('Procurement choice provenance is missing')
        choice=matches[0];action=choice.get('decision',{}).get('action_id');context=choice.get('context') or {}
        retained=context.get('purchase_options',{}).get(action) or {}
        if (choice.get('actor_id')!=buyer or context.get('actor_id')!=buyer or context.get('event',{}).get('id')!=agency_plan
            or action!=selected['id'] or any(retained.get(k)!=selected[k] for k in ('id',*PINS))
            or selected['supplier']!=seller or selected['commodity']!=commodity or selected['quantity']!=quantity):
            raise ValueError('Procurement choice does not authorize these trade terms')
        procurement={k:copy.deepcopy(selected[k]) for k in ('id',*PINS)}
        procurement['decision_claim_id']=claim_id
    payload={**terms,'source_kind':'resident_decisions','plan_id':agency_plan,'trade_id':event_id,
             'decision_proof':proof,'reserve_release':release,'procurement':procurement}
    result=consent_envelope(payload)
    if release:result['reserve_release']=release
    return result
