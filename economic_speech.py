"""Audible, grounded trade acts; speech never substitutes for a physical transfer."""
import copy
import math
import secrets
import time
from agency import distance
from enterprises import plan_work_policy, current_work_terms
from employment import remember_unavailable, accept_contract


def attendance_id(plan):
    return plan.get('economic_attendance_id', 'economic-attend-' + plan['id'])


class EconomicSpeech:
    def queue_trade_speech(self, state, plan, act):
        if not plan.get('voiced_trade'):return
        buyer,seller=plan.setdefault('economic_pair',[plan['actor'],plan['target']]);price=plan.get('unit_price',3)
        unit='loaf' if plan.get('commodity','bread')=='bread' else 'unit of grain'
        lines={
            'offer':(buyer,seller,f'Would you sell me one {unit} for {price} gold?'),
            'counteroffer':(buyer,seller,f'Would {price} gold change your mind? That is my final offer for one {unit}.'),
            'seller_counteroffer':(seller,buyer,f'I can sell you one {unit} for {price} gold. Would that suit you?'),
            'buyer_accept':(buyer,seller,f'Agreed. I will pay {price} gold for one {unit}.'),
            'accept':(seller,buyer,f'Agreed. One {unit} for {price} gold.'),
            'refuse':(seller,buyer,f'No, I will not sell a {unit} on those terms.'),
            'leave':(buyer,seller,'All right. I will leave it there. Goodbye.'),
            'receipt':(buyer,seller,f'Thank you. I have received one {unit} and paid {price} gold.')}
        if act.startswith('work_'):
            policy=plan_work_policy(plan);wage=policy['wage_gold'];minutes=policy['work_minutes']
            lines.update({
                'work_request':(buyer,seller,f'Are you hiring for that {minutes}-minute bread-making shift?'),
                'work_offer':(seller,buyer,f'I can offer {wage} gold for {minutes} minutes of bread-making. I supply the grain and pay after the work is done.'),
                'work_unavailable':(seller,buyer,'I am not offering you a shift right now.'),
                'work_accept':(buyer,seller,f'I accept. {minutes} minutes of bread-making for {wage} gold, paid after the work.'),
                'work_decline':(buyer,seller,'Thank you, but I will not take that shift.'),
                'work_receipt':(buyer,seller,f'The bread is made and I have received {wage} gold. Thank you.')})
        actor,listener,line=lines[act]
        if len(plan.get('economic_turns',[]))>=5:raise ValueError('Trade speech budget exhausted')
        if not plan.get('economic_attendance'):
            generation=plan.get('economic_attendance_generation',0)+1
            plan['economic_attendance_generation']=generation
            plan['economic_attendance_id']='economic-attend-'+plan['id']+('-'+str(generation) if generation>1 else '')
        plan['economic_speech']={'actor':actor,'listener':listener,'act':act,'line':line,
            'source':'Deterministic wording of accepted economic terms; not generated dialogue',
            'origin_session':self.session,'resume_phase':plan['phase']}
        plan['phase']='economic_synthesize' if plan.get('economic_attendance') else 'economic_attending'
        plan['release_required']=True

    @staticmethod
    def economic_present(plan, observation):
        attendance=observation.get('conversationAttendance') or {}
        members=attendance.get('participants',[])
        return (attendance.get('id')==attendance_id(plan) and attendance.get('phase')=='attending'
            and len(members)==2 and {r.get('actor') for r in members}==set(plan['economic_pair'])
            and all(r.get('ownedPackage') is True and r.get('loaded') is True for r in members))

    def prepare_trade_speech(self,event_id,audio,observation):
        self._agency_guard(observation)
        plan=self.agency_plan()
        if not plan or plan['id']!=event_id or plan['phase']!='economic_synthesize':raise ValueError('No trade speech awaiting synthesis')
        self.validate_audio_metadata(audio)
        if not self.economic_present(plan,observation) or distance(observation,*plan['economic_pair'])>300:
            raise ValueError('Trade participants are no longer attending nearby')
        if plan['economic_speech']['origin_session']!=self.session:raise ValueError('Trade speech belongs to another session')
        state=copy.deepcopy(self.active);updated=state['plans'][-1]
        updated['economic_speech'].update(audio=audio,delivery_id='speech-'+secrets.token_hex(12),prepared_at=time.time())
        updated['phase']='economic_speaking'
        return {'checkpoint':self._write(state,'economic speech persisted before delivery')}

    def observe_trade_speech(self,observation):
        plan=self.agency_plan()
        if not plan or not plan.get('voiced_trade') or plan['phase'] in ('complete','held'):return False
        current=plan.get('economic_speech');ack=observation.get('ack') or {}
        if plan['phase']=='economic_departing':
            if ack.get('id')=='economic-depart-'+plan['id']:
                if ack.get('status')!='applied' or ack.get('released') is not True:
                    self.hold_plan(plan['id'],'Economic departure release failed',observation)
                else:
                    state=copy.deepcopy(self.active);updated=state['plans'][-1]
                    updated['economic_release']=copy.deepcopy(ack);updated.pop('economic_attendance',None)
                    updated.pop('economic_pair',None);updated['phase']=updated.pop('economic_resume')
                    self._write(state,'old trade partners released before a new journey')
            return True
        if current and current['origin_session']!=self.session:
            self.hold_plan(plan['id'],'Save/load interrupted economic speech; no automatic replay',observation);return True
        if plan.get('economic_attendance') and not self.economic_present(plan,observation):
            self.hold_plan(plan['id'],'Economic attendance ownership interrupted',observation);return True
        if plan['phase']=='economic_attending':
            if ack.get('id')==attendance_id(plan):
                if ack.get('status')!='applied' or not self.economic_present(plan,observation) or distance(observation,*plan['economic_pair'])>300:
                    self.hold_plan(plan['id'],'Economic attendance was not established',observation)
                else:
                    state=copy.deepcopy(self.active);state['plans'][-1].update(phase='economic_synthesize',economic_attendance=copy.deepcopy(ack))
                    self._write(state,'buyer and seller attended for voiced terms')
            return True
        if plan['phase']=='economic_synthesize':return True
        if plan['phase']!='economic_speaking':return False
        report=observation.get('speech') or {}
        if report.get('id')!=current['delivery_id']:return True
        if report.get('status')=='failed':
            self.hold_plan(plan['id'],'Economic speech playback failed',observation);return True
        if report.get('status')!='ended':return True
        elapsed=report.get('playedSeconds')
        if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<current['audio']['seconds']-.3 or report.get('nearbyThroughout') is not True:
            self.hold_plan(plan['id'],'Economic playback incomplete or listener departed',observation);return True
        if current['act']=='work_accept':
            try:current_work_terms(self.active,plan)
            except ValueError as error:
                self.hold_plan(plan['id'],str(error),observation);return True
        state=copy.deepcopy(self.active);updated=state['plans'][-1];turn=updated.pop('economic_speech')
        turn.update(delivered=True,playback=copy.deepcopy(report),ended_at=time.time())
        updated.setdefault('economic_turns',[]).append(turn);updated['phase']=turn['resume_phase']
        if turn['act']=='work_accept':accept_contract(state,updated)
        if turn['act']=='work_unavailable':remember_unavailable(state,updated,observation.get('gameDays'),turn['delivery_id'])
        if updated['phase']=='travelling':updated.update(phase='economic_departing',economic_resume='travelling')
        for actor,kind in ((turn['actor'],'said'),(turn['listener'],'heard_speech')):
            person=state['people'][str(actor)]
            person['memories'].append({'event_id':turn['delivery_id'],'kind':kind,'speaker':turn['actor'],
                'listener':turn['listener'],'quote':turn['line'],'economic_act':turn['act'],
                'source':'Completed nearby economic speech; physical ledger separately verifies transfers',
                'epistemic_status':'heard terms; receipt act refers to a separately committed transfer'})
            person['memories']=person['memories'][-32:]
        self._write(state,'economic terms heard before continuing transaction');return True

    def trade_speech_command(self,session):
        plan=self.agency_plan()
        if not plan:return None
        if plan['phase']=='economic_departing':
            return {'id':'economic-depart-'+plan['id'],'kind':'release_routine','actor':plan['actor'],'participants':plan['economic_pair'],
                'session':session,'checkpoint':self.marker}
        if plan['phase']=='economic_attending':
            return {'id':attendance_id(plan),'kind':'conversation_attend','participants':plan['economic_pair'],
                'session':session,'checkpoint':self.marker}
        if plan['phase']!='economic_speaking':return None
        turn=plan['economic_speech']
        if turn['origin_session']!=session:return None
        return {'id':turn['delivery_id'],'kind':'speak','actor':turn['actor'],'target':turn['listener'],
            'line':turn['line'],'tone':'calm','audio':turn['audio'],'session':session,'checkpoint':self.marker}
