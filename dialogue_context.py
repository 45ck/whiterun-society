"""Public scene and own-state context for situated dialogue, with narrow hard checks."""
import math
import re
from relationship_metrics import relationship_level

def time_context(game_days):
    if type(game_days) not in (int,float) or not math.isfinite(game_days) or game_days<0:
        return {'known':False,'greeting':'neutral greeting only; time is unknown'}
    # Round away floating-point noise at exact clock-band boundaries.
    hour=round((game_days%1)*24,8)%24
    period='morning' if 5<=hour<12 else 'afternoon' if 12<=hour<17 else 'evening' if 17<=hour<22 else 'night'
    return {'known':True,'hour':round(hour,2),'period':period,'source':'native game clock; authored greeting bands'}

def dialogue_frame(conversation,observation,person,actor):
    turns=[t for t in conversation.get('turns',[]) if t.get('delivered')]
    heard=[t for t in turns if t['listener']==actor]
    last=heard[-1]['selected']['line'] if heard else None
    listener=conversation['speakers'][1-conversation['turn']%2]
    continuity=next((a for a in (observation.get('resident_control') or {}).get('activities',[]) if a.get('actor')==actor),None)
    own_activity={'kind':'not_semantically_observed','source':'A native package ID or occupational role does not establish a current task'}
    if continuity:
        row=next((r for r in observation.get('residents',[]) if r.get('id')==actor),{})
        package=(row.get('activity') or {}).get('package_id')
        if continuity.get('ownedPackage') is True and package and package==continuity.get('expectedPackage'):
            own_activity={'kind':'awaiting_decision','source':'Observed society standby package; not work, patrol, production or a promise to resume them'}
        elif continuity.get('phase')=='interaction_priority':
            own_activity={'kind':'interaction_in_progress','source':'Society interaction temporarily supersedes standby; no other duty is established'}
    return {'clock':time_context(observation.get('gameDays')),
        'delivered_turns':len(turns),'is_refusal':conversation.get('response')=='decline',
        'last_line_heard':last,'last_line_has_question_mark':bool(last and '?' in last),
        'already_spoken':any(t['speaker']==actor for t in turns),'relationship_band':relationship_level(person.get('relationships',{}).get(str(listener),{})),
        'approach_reason':conversation.get('source','Nearby encounter; no prior shared topic'),
        'closing_reason':'The resident declined this approach; no conversation has happened yet' if conversation.get('response')=='decline' else 'The resident selected a polite ending' if conversation.get('end_after_turn') else 'Encounter turn budget is ending' if conversation['turn']>=conversation.get('max_turns',2)-1 else None,
        'own_recorded_commitments':person.get('commitments',[]),
        'own_current_activity':own_activity,
        'physical_capabilities':['talk','listen','end this conversation'],
        'not_observed':['current work orders or deadlines','forge temperature','a promise to sit or execute another task','the other resident private motives or stock'],
        'rules':['Address the latest question or acknowledge uncertainty before changing topic.',
            'Do not restart a greeting after already speaking in this encounter.',
            'A farewell needs no invented excuse or appointment.',
            'Your occupational role is not evidence of a current shift, patrol, work order or task to resume.',
            'Do not propose sitting or another physical task that this social interaction cannot execute.',
            'Use time-of-day greetings only when the clock supports them.']}

def validate_situated_candidates(candidates,frame,closing=False):
    clock=frame['clock'];period=clock.get('period')
    for candidate in candidates:
        line=candidate['line']
        greeting=re.search(r'\bgood (morning|afternoon|evening|night)\b',line,re.I)
        if greeting and (not clock['known'] or greeting.group(1).lower()!=period):
            raise ValueError('Language output greeting contradicts the observed time of day')
        if closing and '?' in line:
            raise ValueError('Language output starts a new question during the closing turn')
        if frame.get('delivered_turns')==0 and re.search(r"\b(?:been (?:pleasant|nice|good|lovely) (?:chatting|talking)|(?:nice|good|pleasant|lovely) (?:chatting|talking) (?:to|with) you)\b",line,re.I):
            raise ValueError('Language output invents a conversation before any speech was heard')
        if closing and not frame.get('own_recorded_commitments') and re.search(r"\bi (?:need|have|must) to (?:tend|attend|finish|complete)\b",line,re.I):
            raise ValueError('Language output introduces an unsupported task as a departure excuse')
