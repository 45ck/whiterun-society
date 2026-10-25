"""A resident may release one household loaf for one explicitly agreed sale.

This is not a new standing allocation policy. The consent is bound to the current
plan, buyer, seller, price, quantity, policy and observed inventory, then retained
on the physical trade receipt. A spoken acceptance alone is not this authority.
"""


def reserved_sale_consent(state, event_id, buyer, seller, quantity, unit_price, agency_plan, inventory):
    plans=state.get('plans') or []
    if not agency_plan or not plans:return None
    plan=plans[-1];consent=plan.get('reserve_release')
    if not consent or plan.get('id')!=agency_plan or plan.get('phase')!='ready_to_trade':return None
    if (plan.get('trade_id')!=event_id or plan.get('actor')!=buyer or plan.get('target')!=seller
            or plan.get('unit_price',3)!=unit_price or quantity!=1):return None
    decisions=plan.get('decisions') or []
    if not decisions or decisions[-1].get('actor_id')!=seller or decisions[-1].get('decision',{}).get('action_id')!='sell_reserved_bread':return None
    expected={'plan_id':agency_plan,'trade_id':event_id,'buyer':buyer,'seller':seller,
              'quantity':1,'unit_price':unit_price,
              'policy':state.get('people',{}).get(str(seller),{}).get('food_policy'),
              'inventory':inventory,'decision_claim_id':decisions[-1].get('claim_id')}
    return consent if consent==expected else None
