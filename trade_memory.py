"""Refusal knowledge follows private decisions and qualified public delivery."""
import hashlib
import json
import math


def _append(state, actor, offer, role, source, delivery_id=None):
    commodity = offer['commodity']
    memory = {'event_id':offer['plan_id'], 'refusal_event_id':offer['id'],
        'kind':'trade_offer_declined', 'other':offer['seller'] if role=='buyer' else offer['buyer'],
        'role':role, commodity:1, 'commodity':commodity, 'gold':offer['unit_price'],
        'offer_round':offer['offer_round'], 'source':source,
        'epistemic_status':'refused offer only; seller reason and stock are unknown' if role=='buyer' else 'own refusal decision'}
    if delivery_id:memory['delivery_id']=delivery_id
    person=state['people'][str(actor)]
    person['memories']=(person.get('memories',[])+[memory])[-32:]


def remember_refusal_decision(state, plan):
    """Return a stable offer-event ID; never reveal private rationale or stock."""
    offer={'plan_id':plan['id'], 'buyer':plan['actor'], 'seller':plan['target'],
        'commodity':plan.get('commodity','bread'), 'unit_price':plan.get('unit_price',3),
        'offer_round':plan.get('offer_round',0)}
    decisions=plan.get('decisions') or []
    claim=decisions[-1].get('claim_id') if decisions else None
    identity=json.dumps([offer,claim],sort_keys=True,separators=(',',':'))
    event='refusal-'+hashlib.sha256(identity.encode()).hexdigest()[:24]
    records=plan.setdefault('refusal_events',{})
    if event not in records:
        offer.update(id=event, heard=False)
        records[event]=offer
        _append(state,offer['seller'],offer,'seller','Own consent decision; no spoken delivery implied')
        if not plan.get('voiced_trade'):
            _append(state,offer['buyer'],offer,'buyer','Legacy non-spoken trade protocol feedback; not heard dialogue')
        plan['refusals_recorded']=plan.get('refusals_recorded',0)+1
    return event


def remember_refusal_heard(state, plan, turn):
    """Attach buyer knowledge once, using the queued offer rather than live terms."""
    offer=plan.get('refusal_events',{}).get(turn.get('refusal_event_id'))
    playback=turn.get('playback') or {};audio=turn.get('audio') or {}
    elapsed,duration=playback.get('playedSeconds'),audio.get('seconds')
    finite=lambda x:type(x) in (int,float) and math.isfinite(x)
    if (not plan.get('voiced_trade') or not offer or offer['heard'] or turn.get('act')!='refuse'
            or turn.get('delivered') is not True or not turn.get('delivery_id')
            or playback.get('id')!=turn['delivery_id'] or playback.get('status')!='ended'
            or playback.get('nearbyThroughout') is not True
            or not finite(elapsed) or not finite(duration) or duration<=0 or elapsed<duration-.3
            or turn.get('actor')!=offer['seller'] or turn.get('listener')!=offer['buyer']):
        return False
    _append(state,offer['buyer'],offer,'buyer','Completed nearby refusal speech; seller reason and stock are unknown',turn['delivery_id'])
    offer.update(heard=True,delivery_id=turn['delivery_id'])
    return True
