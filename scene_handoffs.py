"""Explicit scene interruption, persisted before the engine receives it.

Stopping a scene may run its scripts and affect every participant. It is not
quest completion, a resident decision, or proof of ownership of their next task.
"""
import copy
from routing import activity_blocker


def scene_candidates(society, observation):
    """Do not automatically repeat a stop against a previously attempted scene."""
    attempted={r['scene_id'] for r in society.get('scene_handoffs',[])}
    managed=(society.get('town') or {}).get('residents',{})
    return [r for r in observation.get('residents',[]) if r.get('isPerson') is True
            and str(r['id']) in managed and activity_blocker(r)=='native_scene'
            and r['activity']['in_combat'] is False and r['activity']['sleep_state']==0
            and r['activity']['scene_id'] not in attempted]


class SceneHandoffs:
    def request_scene_handoff(self, event_id, actor, scene_id, observation):
        self._agency_guard(observation)
        if self.agency_busy() or self.conversation_busy():
            raise ValueError('Settle the active resident activity before a scene handoff')
        if not isinstance(event_id,str) or not 1<=len(event_id)<=64 or event_id.startswith('checkpoint-'):
            raise ValueError('A bounded handoff ID is required')
        if type(actor) is not int or type(scene_id) is not int or actor<=0 or scene_id<=0:
            raise ValueError('Positive integer actor and observed scene IDs required')
        for old in self.active.get('scene_handoffs',[]):
            if old['id']==event_id:
                if (old['actor'],old['scene_id'])!=(actor,scene_id):raise ValueError('Handoff ID reused')
                return {'duplicate':True,'handoff':old}
        row=next((r for r in observation.get('residents',[]) if r['id']==actor),None)
        if not row or str(actor) not in (self.active.get('town') or {}).get('residents',{}) or row.get('isPerson') is not True:
            raise ValueError('An observed initialized adult resident is required')
        if (activity_blocker(row)!='native_scene' or row['activity']['scene_id']!=scene_id
                or row['activity']['in_combat'] is not False or row['activity']['sleep_state']!=0):
            raise ValueError('The exact scene must still occupy an awake resident outside combat')
        state=copy.deepcopy(self.active)
        command={'id':event_id,'kind':'scene_handoff','actor':actor,'scene_id':scene_id}
        record={**command,'session':self.session,'status':'pending',
                'created_day':observation.get('gameDays'),
                'observed_participants':[r['id'] for r in observation['residents']
                    if (r.get('activity') or {}).get('scene_id')==scene_id]}
        state.setdefault('scene_handoffs',[]).append(record)
        state['pending']={'id':event_id,'status':'pending','command':command}
        return {'checkpoint':self._write(state,'explicit native scene handoff prepared'),'handoff':record}

    def observe_scene_handoff(self, observation):
        pending=self.active['pending'];record=self.active['scene_handoffs'][-1]
        ack=observation.get('ack') or {}
        changed=observation['session']!=record['session']
        if not changed and ack.get('id')!=pending['id']:return
        row=next((r for r in observation.get('residents',[]) if r['id']==record['actor']),None)
        released=bool(not changed and ack.get('status')=='applied' and ack.get('actor')==record['actor']
            and ack.get('scene_id')==record['scene_id'] and ack.get('release_observed') is True
            and row and row.get('isPerson') is True and activity_blocker(row) is None)
        state=copy.deepcopy(self.active);item=state['scene_handoffs'][-1]
        item.update(status='released' if released else 'held',
            outcome='scene_released' if released else 'session_changed' if changed else 'release_not_verified',
            receipt=copy.deepcopy(ack) if not changed else None,settled_day=observation.get('gameDays'))
        state['pending']=None
        if released:
            person=state['people'][str(record['actor'])]
            person['agency'].update(next_review_day=observation.get('gameDays',0),state='decision_pending',
                reason='Native scene released; current needs and opportunities must be reconsidered')
        self._write(state,'scene handoff result observed; no inventory or relationship effects')
