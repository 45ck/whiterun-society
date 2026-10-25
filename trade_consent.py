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
    if not decisions:return None
    source_decision=decisions[-1]
    if plan.get('counter_quote_accepted'):
        quote=plan.get('counter_quote') or {}
        if (source_decision.get('actor_id')!=buyer or source_decision.get('decision',{}).get('action_id')!='accept_counterprice'
                or quote.get('inventory')!=inventory or quote.get('release_reserved') is not True):return None
        source_decision=next((d for d in decisions if d.get('claim_id')==quote.get('claim_id')), {})
        if source_decision.get('actor_id')!=seller or source_decision.get('decision',{}).get('action_id')!='ask_price_'+str(unit_price):return None
    elif source_decision.get('actor_id')!=seller or source_decision.get('decision',{}).get('action_id')!='sell_reserved_bread':return None
    expected={'plan_id':agency_plan,'trade_id':event_id,'buyer':buyer,'seller':seller,
              'quantity':1,'unit_price':unit_price,
              'policy':state.get('people',{}).get(str(seller),{}).get('food_policy'),
              'inventory':inventory,'decision_claim_id':source_decision.get('claim_id')}
    return consent if consent==expected else None
