"""Transparent text heuristics; no semantic or human-realism claim."""
from collections import Counter
import re

PATTERNS={
    'greeting':r'\b(hello|greetings|good (day|morning|afternoon|evening)|well met)\b',
    'courtesy':r'\b(thank|thanks|please|appreciate|pardon)\b',
    'farewell':r'\b(goodbye|farewell|take care|see you|good night)\b',
    'weather':r'\b(weather|rain|sunny|cloud|snow|wind)\b',
    'business':r'\b(gold|loaf|bread|buy|sell|price|work|forge|trade|wage)\b',
    'conflict_cue':r'\b(angry|annoyed|unfair|betray|liar|apologize|sorry)\b'}

def dialogue_metrics(scenes):
    counts=Counter();lines=[];speaker_counts=Counter();pairs=Counter();repeat_greetings=0;duplicate_lines=0
    clock_known=0;timed_greetings=0;time_mismatches=0;closing_turns=0;closing_questions=0;word_counts=[]
    for scene in scenes:
        seen=set();greeted=set()
        if len(scene.get('speakers',[]))==2:pairs[tuple(sorted(scene['speakers']))]+=1
        for turn in scene.get('turns',[]):
            if not turn.get('delivered'):continue
            text=turn.get('selected',{}).get('line');speaker=turn.get('speaker')
            if not isinstance(text,str) or type(speaker) is not int:continue
            normalized=' '.join(text.lower().split())
            word_counts.append(len(text.split()))
            context=turn.get('context') or {};clock=context.get('interaction',{}).get('clock',{})
            clock_known+=int(clock.get('known') is True)
            greeting=re.search(r'\bgood (morning|afternoon|evening|night)\b',text,re.I)
            if greeting and clock.get('known') is True:
                timed_greetings+=1;time_mismatches+=int(greeting.group(1).lower()!=clock.get('period'))
            if context.get('event',{}).get('dialogue_stage')=='closing':
                closing_turns+=1;closing_questions+=int('?' in text)
            lines.append(text);speaker_counts[speaker]+=1;counts['question_mark']+=int('?' in text)
            for category,pattern in PATTERNS.items():
                if re.search(pattern,text,re.I):counts[category]+=1
            if re.search(PATTERNS['greeting'],text,re.I):
                repeat_greetings+=int(speaker in greeted);greeted.add(speaker)
            duplicate_lines+=int(normalized in seen);seen.add(normalized)
    total=len(lines)
    return {'delivered_lines':total,'lexical_cues':dict(counts),'repeated_greeting_turns':repeat_greetings,
        'known_clock_lines':clock_known,'time_checked_greetings':timed_greetings,'time_mismatched_greetings':time_mismatches,
        'closing_turns':closing_turns,'closing_question_marks':closing_questions,
        'mean_words_per_line':round(sum(word_counts)/total,2) if total else None,
        'exact_repeated_lines_within_scene':duplicate_lines,'unique_speakers':len(speaker_counts),'unique_pairs':len(pairs),
        'largest_speaker_share_percent':round(100*max(speaker_counts.values())/total,2) if total else None,
        'question_answer_relevance':None,'topic_coherence':None,'human_smalltalk_rating':None,
        'scope':'Overlapping English keyword cues over delivered social lines, not semantic topics. A question mark is not proof of a question answered; conflict words do not prove drama. Pair counts include refused approaches.'}
