"""Save-bound standing activity under transient travel/conversation packages.

This layer prevents an unassigned resident from silently reverting to vanilla
schedules. A continuity hold is explicitly deterministic standby, not a model
choice, work, rest, production, or a completed personal goal.
"""
import copy
import re

CAPACITY=128


def sync_resident_assignments(town):
    control=town.get('resident_control')
    if not control:return
    managed=town['residents']
    if len(managed)>CAPACITY:raise ValueError('Resident control capacity exceeded')
    assignments=control['assignments']
    for key in list(assignments):
        if key not in managed:del assignments[key]
    used={v['slot'] for v in assignments.values()};free=iter(i for i in range(CAPACITY) if i not in used)
    for key in sorted(managed,key=int):
        if key not in assignments:
            assignments[key]={'actor':int(key),'slot':next(free),'mode':'await_decision',
                'source':'deterministic continuity; no claimed personal decision or economic effect'}

class ResidentControl:
    def configure_resident_control(self,event_id,enabled,observation):
        self._agency_guard(observation)
        if not isinstance(event_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',event_id):raise ValueError('Invalid resident control event')
        if type(enabled) is not bool:raise ValueError('Enabled must be boolean')
        if self.agency_busy() or self.conversation_busy() or self.routines_busy():raise ValueError('Finish current resident activity before changing control')
        town=self.active.get('town')
        if not town:raise ValueError('Initialize residents first')
        old=town.get('resident_control') or {}
        for item in old.get('changes',[]):
            if item['id']==event_id:
                if item['enabled']!=enabled:raise ValueError('Control event ID reused')
                return {'duplicate':True,'control':copy.deepcopy(old)}
        if len(town['residents'])>CAPACITY:raise ValueError('Resident control capacity exceeded; no partial enrollment')
        if enabled and (observation.get('resident_control') or {}).get('available') is not True:
            raise ValueError('Native resident-control plugin is unavailable')
        state=copy.deepcopy(self.active);control=state['town'].setdefault('resident_control',{'revision':0,'assignments':{},'changes':[]})
        sync_resident_assignments(state['town'])
        control['revision']+=1;control['enabled']=enabled;control['changes'].append({'id':event_id,'enabled':enabled,'revision':control['revision']})
        return {'checkpoint':self._write(state,'resident continuity policy changed'),'control':copy.deepcopy(control)}
