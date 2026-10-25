"""Versioned turn choices; old saved encounters retain their original protocol."""
POLICIES=('separate_choice','combined_choice')
MAX_COMBINED_CALLS=16  # Six proposals, six utterance choices, four social decisions.


def candidate_roles(conversation):
    if conversation.get('reply_policy','separate_choice')!='combined_choice':return {}
    if conversation.get('response')=='decline':roles=('refusal','refusal')
    elif conversation.get('end_after_turn') or conversation['turn']>=conversation.get('max_turns',2)-1:
        roles=('close_politely','close_politely')
    elif conversation['turn']==0:roles=('opening','opening')
    else:roles=('reply','close_politely')
    return dict(zip(('option_1','option_2'),roles))


def recorded_model_results(conversation):
    """Count accepted and rejected inference once, including unspoken replies."""
    results=list(conversation.get('social_decisions',[]))+[r['receipt'] for r in conversation.get('rejected_inferences',[])]
    turns=conversation.get('turns',[])+conversation.get('unspoken_turns',[])
    if conversation.get('current'):turns=turns+[conversation['current']]
    return results+[r for turn in turns for r in (turn.get('language'),turn.get('decision')) if r]
