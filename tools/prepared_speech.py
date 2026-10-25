"""Silent candidate synthesis scoped to one exact economic turn and game session."""
import time
from economic_language import TERMS


def turn_key(plan,session):
    turn=plan['economic_speech']
    return (session,plan['id'],len(plan.get('economic_turns',[])),
            turn['actor'],turn['listener'],turn['canonical_line'])


class PreparedSpeech:
    def __init__(self):
        self.key=None;self.clips={}

    def prepare(self,worker,plan,session,voice):
        key=turn_key(plan,session)
        if self.key==key:return 0
        self.key=key;self.clips={}
        turn=plan['economic_speech']
        for candidate in turn['candidates']:
            line=candidate['line'].replace(TERMS,turn['canonical_line'])
            if (line,voice) not in self.clips:
                self.clips[line,voice]={'id':worker.submit(line,voice),'submitted_at':time.monotonic()}
        return len(self.clips)

    def selected(self,worker,plan,session,voice):
        """A stale or changed line misses; never substitute another candidate."""
        if self.key!=turn_key(plan,session):return None
        clip=self.clips.get((plan['economic_speech']['line'],voice))
        if clip is None:return None
        began=time.monotonic();result=worker.result(clip['id'])
        return result,{'mode':'prepared_candidate','wait_seconds':round(time.monotonic()-began,3),
                       'lead_seconds':round(began-clip['submitted_at'],3)}
