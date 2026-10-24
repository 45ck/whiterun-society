"""Sims-style gameplay bands, not psychological or biological measurements."""
from collections import Counter

def relationship_level(relation):
    affinity=relation.get('affinity',0);familiarity=relation.get('familiarity',0)
    heard=relation.get('heard_turns',0)
    if affinity<=-.25:return 'strained'
    if affinity>=.6 and familiarity>=.6 and heard>=12:return 'close_friend'
    if affinity>=.25 and familiarity>=.25 and heard>=6:return 'friend'
    if heard>0 or familiarity>0:return 'acquaintance'
    return 'stranger'

def relationship_metrics(people):
    edges=[];levels={}
    for actor,person in people.items():
        for other,relation in person.get('relationships',{}).items():
            if actor==other:continue
            level=relationship_level(relation);levels[(actor,other)]=level
            edges.append({'actor':int(actor),'other':int(other),'level':level,'affinity_points':round(100*relation.get('affinity',0),1),
                'familiarity_percent':round(100*relation.get('familiarity',0),1),'heard_turns':relation.get('heard_turns',0),
                'background':relation.get('background')})
    friends={'friend','close_friend'}
    mutual={tuple(sorted((a,b))) for (a,b),level in levels.items() if level in friends and levels.get((b,a)) in friends}
    return {'directed_levels':dict(Counter(e['level'] for e in edges)),'edges':edges,'mutual_friend_pairs':len(mutual),
        'authored_background_edges':sum(bool(e['background']) for e in edges),
        'one_sided_friendships':sum(level in friends and levels.get((b,a)) not in friends for (a,b),level in levels.items()),
        'scope':'Only recorded directed relationships. Missing edges mean no relationship evidence, not hostility. Bands are authored gameplay rules; there is no forced friend quota.',
        'rules':{'friend':'affinity >= 0.25, familiarity >= 0.25, heard turns >= 6',
            'close_friend':'affinity >= 0.60, familiarity >= 0.60, heard turns >= 12','strained':'affinity <= -0.25'}}
