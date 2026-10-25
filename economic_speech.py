"""Audible, grounded trade acts; speech never substitutes for a physical transfer."""
import copy
import math
import secrets
import time
from agency import distance
from enterprises import plan_work_policy, current_work_terms
from employment import remember_unavailable, accept_contract
from economic_language import economic_context, validate_wording, qualify_wording, wording_receipt, trade_terms, TERMS
from decisions import validate_decision
from trade_memory import remember_refusal_decision, remember_refusal_heard


def attendance_id(plan):
    return plan.get('economic_attendance_id', 'economic-attend-' + plan['id'])


class EconomicSpeech:
    def queue_trade_speech(self, state, plan, act):
        if not plan.get('voiced_trade'):return
        buyer,seller=plan.get('economic_pair',[plan['actor'],plan['target']])
        terms=None;lines={}
        if act=='leave':
            lines={'leave':(buyer,seller,'All right. I will leave it there. Goodbye.')}
        elif not act.startswith('work_'):
            terms=trade_terms(plan);quantity=terms['quantity'];price=terms['unit_price'];total=terms['cost']
            goods=f"{quantity} {'unit' if quantity==1 else 'units'} of {terms['label']}"
            quote=f'{goods} at {price} gold each, {total} gold total'
            lines={
                'offer':(buyer,seller,f'Would you sell me {quote}?'),
                'counteroffer':(buyer,seller,f'My final offer is {quote}. Would that suit you?'),
                'seller_counteroffer':(seller,buyer,f'I can sell you {quote}. Would that suit you?'),
                'buyer_accept':(buyer,seller,f'Agreed. I will buy {quote}.'),
                'accept':(seller,buyer,f'Agreed. I will sell you {quote}.'),
                'refuse':(seller,buyer,f'No, I will not sell {quote}.'),
                'receipt':(buyer,seller,f'Thank you. I received {goods} at {price} gold each and paid {total} gold total.')}
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
        plan.setdefault('economic_pair',[buyer,seller])
        if not plan.get('economic_attendance'):
            generation=plan.get('economic_attendance_generation',0)+1
            plan['economic_attendance_generation']=generation
            plan['economic_attendance_id']='economic-attend-'+plan['id']+('-'+str(generation) if generation>1 else '')
        plan['economic_speech']={'actor':actor,'listener':listener,'act':act,'line':line,'canonical_line':line,
            'source':'Deterministic wording of accepted economic terms; not generated dialogue',
            'origin_session':self.session,'resume_phase':plan['phase']}
        if terms:plan['economic_speech']['terms']=terms
        if act=='refuse':plan['economic_speech']['refusal_event_id']=remember_refusal_decision(state,plan)
        plan['phase']=('economic_propose' if plan.get('natural_trade') else 'economic_synthesize') if plan.get('economic_attendance') else 'economic_attending'
        plan['release_required']=True

    def economic_present(self, plan, observation):
        from activity_leases import identity_quarantine_actors
        if identity_quarantine_actors(self.active,observation).intersection(plan['economic_pair']):return False
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

    def claim_economic_wording(self,event_id,observation):
        self._agency_guard(observation)
        plan=self.agency_plan()
        if not plan or plan['id']!=event_id or plan['phase'] not in ('economic_propose','economic_select'):
            raise ValueError('No economic wording decision available')
        if not self.economic_present(plan,observation) or distance(observation,*plan['economic_pair'])>300:
            raise ValueError('Economic speakers must be attending nearby')
        stage=plan['phase'].removeprefix('economic_');context=economic_context(self.active,plan,observation)
        if stage=='select':
            context['options']=[{'id':c['id'],'effect':c['line'].replace(TERMS,context['event']['canonical_terms']),
                                 'intention':c['intention'],'tone':c['tone']} for c in plan['economic_speech']['candidates']]
        claim={'id':'wording-'+secrets.token_hex(12),'stage':stage,'session':self.session,'context':context}
        state=copy.deepcopy(self.active);updated=state['plans'][-1]
        updated['economic_speech']['claim']=claim;updated['phase']='economic_thinking_'+stage
        return {'checkpoint':self._write(state,'economic wording claim persisted before inference'),'claim':claim}

    def finish_economic_wording(self,event_id,claim_id,result,observation):
        self._agency_guard(observation)
        plan=self.agency_plan();turn=(plan or {}).get('economic_speech') or {};claim=turn.get('claim')
        if (not plan or plan['id']!=event_id or not claim or claim['id']!=claim_id
                or claim['session']!=self.session or plan['phase']!='economic_thinking_'+claim['stage']):
            raise ValueError('Economic wording claim does not match current session and phase')
        if not self.economic_present(plan,observation) or distance(observation,*plan['economic_pair'])>300:
            raise ValueError('Economic speakers left during inference')
        if not isinstance(result,dict):raise ValueError('Expected economic wording result')
        state=copy.deepcopy(self.active);updated=state['plans'][-1];speech=updated['economic_speech']
        receipt=wording_receipt(result);receipt.update(stage=claim['stage'],claim_id=claim_id)
        context=economic_context(self.active,plan,observation)
        rejected=None
        try:
            if result.get('failure'):
                if result['failure'] not in ('provider_error','transport_error','invalid_output'):raise ValueError('invalid_failure_category')
                raise ValueError(result['failure'])
            if claim['stage']=='propose':
                candidates,rejections=qualify_wording(result.get('proposal'),context)
                receipt['candidate_rejections']=rejections
                if len(rejections)==2:raise ValueError('no_qualified_options')
                speech.update(candidates=candidates,direct_wording_ids=list(rejections))
                updated['phase']='economic_select'
            else:
                validate_wording({'candidates':turn['candidates']},context,turn.get('direct_wording_ids',[]))
                decision=validate_decision(result.get('decision'),claim['context'])
                candidate=next(c for c in turn['candidates'] if c['id']==decision['action_id'])
                speech.update(selected=copy.deepcopy(candidate),line=candidate['line'].replace(TERMS,speech['canonical_line']),
                    source='Model-selected courtesy phrasing from a bounded grammar around exact economic terms')
                receipt['selected_id']=candidate['id']
                if candidate['id'] in turn.get('direct_wording_ids',[]):
                    speech.update(wording_fallback='selected_direct_terms',source='Jev selected deterministic terms instead of the qualified generated alternative')
                updated['phase']='economic_synthesize'
        except ValueError as error:
            known={'terms_marker','extra_terms','incomplete_sentence','no_qualified_options','repeated_greeting','unsupported_weather','provider_error','transport_error','invalid_output'}
            rejected=str(error) if str(error) in known else 'candidate_validation'
            speech.update(line=speech['canonical_line'],wording_fallback=rejected,
                          source='Deterministic economic terms after rejected or unavailable generated wording')
            updated['phase']='economic_synthesize'
        receipt.update(accepted=rejected is None,validation_failure=rejected)
        speech.setdefault('wording_results',[]).append(receipt);speech.pop('claim',None)
        return {'checkpoint':self._write(state,'economic wording resolved without changing the economic act'),
                'fallback':rejected}

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
                    state=copy.deepcopy(self.active);state['plans'][-1].update(phase='economic_propose' if plan.get('natural_trade') else 'economic_synthesize',economic_attendance=copy.deepcopy(ack))
                    self._write(state,'buyer and seller attended for voiced terms')
            return True
        if plan['phase'] in ('economic_synthesize','economic_propose','economic_select','economic_thinking_propose','economic_thinking_select'):return True
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
        if turn['act']=='refuse':remember_refusal_heard(state,updated,turn)
        if updated['phase']=='travelling':updated.update(phase='economic_departing',economic_resume='travelling')
        for actor,kind in ((turn['actor'],'said'),(turn['listener'],'heard_speech')):
            person=state['people'][str(actor)]
            person['memories'].append({'event_id':turn['delivery_id'],'kind':kind,'speaker':turn['actor'],
                'listener':turn['listener'],'quote':turn['line'],'economic_act':turn['act'],
                'terms':copy.deepcopy(turn.get('terms')),
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
            'line':turn['line'],'tone':turn.get('selected',{}).get('tone','calm'),'audio':turn['audio'],'session':session,'checkpoint':self.marker}
