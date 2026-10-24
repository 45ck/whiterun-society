"""Finite, save-bound conversations: language proposes, Jev selects, code delivers.

Heard speech is remembered as a claim, never as proof of its contents. No model
can transfer inventory through this interface. Interrupted playback is held.
"""
import copy
import math
import re
import secrets
import time
from agency import distance
from decisions import validate_decision
from routing import dynamic_route
from knowledge import person_view, record_heard_identity
from social import SOCIAL_STAGES, social_candidates, social_context, settle_social, record_appraisal


def validate_candidates(value):
    if not isinstance(value, dict) or set(value) != {'candidates'}:
        raise ValueError('Expected candidate object')
    candidates = value['candidates']
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise ValueError('Exactly two bounded intentions required')
    for i, c in enumerate(candidates):
        if not isinstance(c, dict) or set(c) != {'id', 'intention', 'line', 'tone'}:
            raise ValueError('Invalid candidate fields')
        if c['id'] != f'option_{i+1}':
            raise ValueError('Invalid candidate ID')
        for field, limit in [('intention', 100), ('line', 240)]:
            if not isinstance(c[field], str) or not 1 <= len(c[field]) <= limit or any(ord(x)<32 for x in c[field]):
                raise ValueError('Invalid candidate text')
        if not 3 <= len(c['line'].split()) <= 40 or c['tone'] not in ('calm','worried','hopeful','frustrated'):
            raise ValueError('Invalid spoken length or tone')
    if candidates[0]['line'] == candidates[1]['line']:
        raise ValueError('Two distinct alternatives required')
    return candidates


class Conversation:
    def conversation_status(self):
        return copy.deepcopy(self.active.get('conversation')) if self.active else None

    def conversation_busy(self):
        c = self.conversation_status()
        return bool(c and c['phase'] not in ('complete', 'held'))

    def start_conversation(self, event_id, observation, actor=None, max_turns=None):
        self._agency_guard(observation)
        if max_turns is not None and (type(max_turns) is not int or not 2<=max_turns<=6):
            raise ValueError('Conversation turn limit must be an integer from 2 to 6')
        if not isinstance(event_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', event_id):
            raise ValueError('Invalid conversation ID')
        old = self.conversation_status()
        history = self.active.get('conversation_history', []) + ([old] if old else [])
        for item in history:
            if item['id'] == event_id:
                if actor is not None and item.get('initiator')!=actor:raise ValueError('Conversation ID reused for another resident')
                if max_turns is not None and item.get('turn_limit',2)!=max_turns:raise ValueError('Conversation ID reused with another turn limit')
                return {'duplicate': True, 'conversation': item}
        day = self.active.get('market_day')
        if self.agency_busy() or self.conversation_busy() or day and day['status'] != 'complete':
            raise ValueError('Another resident event is active')
        offered = actor is None and bool(self.active.get('town'))
        if offered:
            eligible=[int(key) for key in self.active['town']['residents']
                      if social_candidates(self.active,observation,int(key))]
            if not eligible:raise ValueError('No qualified nearby social participants remain')
            # The operator offers an opportunity, never a required conversation.
            # The resident still chooses a partner or defers, and the partner consents.
            actor=min(eligible,key=lambda aid:(self.active['people'][str(aid)].get('social_clock',0),aid))
            self._social_day(observation)
        elif actor is None:distance(observation, 108186, 108149)
        else:
            event=next((e for e in self.active.get('town',{}).get('daily',{}).get('queue',[]) if e['id']==event_id),None)
            if type(actor) is not int or not event or event['actor']!=actor or event['kind']!='social_review' or event['status']!='pending':
                raise ValueError('A pending scheduled social opportunity is required')
            if not social_candidates(self.active,observation,actor):raise ValueError('No qualified nearby social partner remains')
            self._social_day(observation)
        state = copy.deepcopy(self.active)
        limit=max_turns if max_turns is not None else (6 if actor is not None else 2)
        if offered:
            daily=state['town'].setdefault('daily',{'last_day':observation['gameDays'],'sequence':0,'queue':[],'reviews':[]})
            if any(e['id']==event_id for e in daily['queue']):raise ValueError('Opportunity ID already exists')
            daily['queue'].append({'id':event_id,'actor':actor,'kind':'social_review','status':'pending',
                'created_day':observation['gameDays'],'priority':.45,
                'reason':'Operator offered a nearby social opportunity; residents may decline',
                'source':'operator opportunity, not a claimed autonomous need'})
        if old: state.setdefault('conversation_history', []).append(old)
        state['conversation'] = {'id': event_id, 'phase': 'meeting', 'turn': 0, 'started_at':time.time(),
            'speakers': [108186,108149], 'turns': [], 'claim': None,
            'source': 'Authored two-person encounter; generated intentions and speech',
            'turn_limit':limit,'max_turns':limit,'max_llm_calls':limit,'max_jev_calls':limit}
        if actor is not None:
            state['conversation'].update(phase='choose_partner',initiator=actor,partner=None,mode='autonomous_social',
                speakers=[],social_decisions=[],max_jev_calls=limit+4+(limit-1 if limit>2 else 0),source='Scheduled social need; residents choose partner, consent, speech and appraisal')
            next(e for e in state['town']['daily']['queue'] if e['id']==event_id)['status']='started'
            if offered:state['conversation']['source']='Operator offered opportunity; current residents choose partner, consent, speech and appraisal'
        return {'checkpoint': self._write(state, 'conversation encounter started')}

    def _social_day(self, observation):
        day=observation.get('gameDays')
        if type(day) not in (int,float) or not math.isfinite(day) or day<0:raise ValueError('Finite social event game clock required')
        return day

    def _conversation_guard(self, event_id, observation):
        self._agency_guard(observation)
        c = self.conversation_status()
        if not c or c['id'] != event_id: raise ValueError('Conversation changed')
        return c

    def _speech_context(self, c, observation):
        actor = c['speakers'][c['turn']%2]
        listener = c['speakers'][1-c['turn']%2]
        person = self.active['people'][str(actor)]
        own = next((a for a in observation['residents'] if a['id']==actor), None)
        if not own or distance(observation, actor, listener)>500:
            raise ValueError('Conversation participants are not nearby')
        facts=[]
        for memory in person['memories'][-8:]:
            other=person_view(self.active,actor,memory.get('other'))['name']
            if memory['kind']=='trade_offer_declined':
                facts.append(f"I offered {other} {memory['gold']} gold to BUY one loaf FROM them. {other} REFUSED TO SELL me bread. I was the BUYER, not the seller." if memory['role']=='buyer' else
                    f"{other} offered ME {memory['gold']} gold to BUY one loaf FROM ME. I REFUSED TO SELL them bread. I was the SELLER.")
            elif memory['kind']=='paid_work':
                facts.append(f"I worked for {other}, making their bread using their grain. They paid me {memory['gold']} gold. The bread belonged to them, not me." if memory['role']=='worker' else
                    f"I hired {other} to make bread with my grain. I paid them {memory['gold']} gold. The produced bread belongs to me.")
            elif memory['kind']=='consumed_bread':facts.append('I ate one of my carried loaves.')
        return {'actor_id': actor, 'profile': person['profile'], 'needs': person['needs'],
            'known_facts_in_first_person':facts,
            'own_inventory': own['inventory'], 'own_food_policy': person.get('food_policy'),
            'memories': person['memories'][-8:], 'trust': person['trust'],
            'my_relationship':person.get('relationships',{}).get(str(listener),{}),
            'weather':observation.get('weather'),
            'listener': person_view(self.active,actor,listener),
            'heard_in_this_conversation': [{'speaker':t['speaker'], 'line':t['selected']['line'],
                'epistemic_status':'heard claim, not verified fact'} for t in c['turns'] if t.get('delivered')],
            'event': {'id':c['id'], 'kind':'nearby_conversation',
                'dialogue_stage':'closing' if c.get('end_after_turn') or c['turn']>=c.get('max_turns',2)-1 else 'opening' if c['turn']==0 else 'reply',
                'information':('This is a short polite refusal of a social approach. Say that you cannot chat now without inventing a reason or hostility.' if c.get('response')=='decline' else
                    'You meet a nearby resident. Respond naturally to their latest words, or use your own experiences, observed weather, ordinary courtesy, a question or a remembered disagreement. Do not force economics into every conversation. Do not invent shared history.')+
                    ' The other person\'s private motives, needs and inventory are unknown. An unfamiliar person\'s name is unknown. '
                    'You may introduce yourself or ask their name, but do not invent an acquaintance. Speech cannot itself complete a trade or change a policy.'}}

    def claim_conversation(self, event_id, observation):
        c = self._conversation_guard(event_id, observation)
        phase = c['phase']
        if phase not in ('propose','select')+SOCIAL_STAGES: raise ValueError('A claim already exists or no inference is due')
        context = social_context(self.active,c,observation,phase) if phase in SOCIAL_STAGES else self._speech_context(c, observation)
        if phase=='respond' and distance(observation,c['initiator'],c['partner'])>500:raise ValueError('Social partner left before responding')
        if phase == 'select':
            context['options'] = [{'id':v['id'], 'effect':v['intention']+' Say: '+v['line']+' Tone: '+v['tone']}
                                  for v in c['current']['candidates']]
        claim = {'id':secrets.token_hex(12), 'stage':phase, 'context':context, 'session':self.session}
        c.update(phase='thinking_'+phase, claim=claim)
        state = copy.deepcopy(self.active); state['conversation'] = c
        return {'checkpoint':self._write(state,'conversation inference claimed before call'), 'claim':claim}

    def finish_conversation_inference(self, event_id, claim_id, result, observation):
        c = self._conversation_guard(event_id, observation)
        claim = c.get('claim')
        if not claim or claim['id']!=claim_id or claim.get('session')!=self.session or c['phase']!='thinking_'+claim['stage']:
            raise ValueError('Stale conversation inference')
        if not isinstance(result, dict) or not isinstance(result.get('model'), str):
            raise ValueError('Missing model provenance')
        if claim['stage'] in SOCIAL_STAGES:
            stage=claim['stage'];context=social_context(self.active,c,observation,stage)
            validate_decision(result['decision'],claim['context'])
            if stage=='respond' and distance(observation,c['initiator'],c['partner'])>500:raise ValueError('Social partner left during response')
            decision=validate_decision(result['decision'],context)
            c['social_decisions'].append({'stage':stage,'actor':context['actor_id'],**result})
            state=copy.deepcopy(self.active)
            if stage=='choose_partner':
                if decision['action_id']=='defer':c.update(phase='complete',outcome='continued_quietly')
                else:
                    partner=int(decision['action_id'].split('_')[-1]);c.update(partner=partner,speakers=[c['initiator'],partner],phase='meeting')
                    state['people'][str(c['initiator'])]['agency'].update(state='approaching_resident',reason='Chose to approach '+person_view(state,c['initiator'],partner)['name'])
            elif stage=='respond':
                c['response']=decision['action_id'];c['phase']='propose'
                if c['response']=='chat':c.update(phase='attending',paired_attendance=True)
                for resident in (c['initiator'],c['partner']):state['people'][str(resident)]['agency'].update(state='social_encounter',reason='Partner chose '+c['response'])
                if c['response']=='decline':c['speakers']=[c['partner'],c['initiator']];c['max_turns']=1
            elif stage=='continue_dialogue':
                if decision['action_id']=='leave_quietly':
                    c.update(phase='releasing',final_phase='complete',end_reason='left_quietly')
                else:
                    c['phase']='propose'
                    if decision['action_id']=='close_politely':c.update(end_after_turn=True,end_reason='polite_closure')
            else:
                record_appraisal(state,c,stage,decision)
                c['phase']='reflect_second' if stage=='reflect_first' else 'complete'
                if c['phase']=='complete':c['outcome']='spoke_brief_refusal' if c['response']=='decline' else 'social_exchange_completed'
            c['claim']=None
            if c['phase']=='complete':
                c['finished_at']=time.time();settle_social(state,c,self._social_day(observation))
            state['conversation']=c
            return {'checkpoint':self._write(state,'resident social '+stage+' decision accepted')}
        if claim['stage']=='propose':
            candidates = validate_candidates(result['proposal'])
            c['current'] = {'speaker':claim['context']['actor_id'], 'listener':claim['context']['listener']['id'],
                'candidates':candidates, 'language':result, 'context':claim['context']}
            c['phase']='select'
        else:
            choice = validate_decision(result['decision'], claim['context'])['action_id']
            c['current'].update(selected=next(v for v in c['current']['candidates'] if v['id']==choice), decision=result)
            c['phase']='synthesize'
        c['claim']=None
        state=copy.deepcopy(self.active);state['conversation']=c
        return {'checkpoint':self._write(state,'conversation '+claim['stage']+' result accepted')}

    def prepare_speech(self, event_id, audio, observation):
        c = self._conversation_guard(event_id, observation)
        if c['phase']!='synthesize': raise ValueError('Speech is not awaiting synthesis')
        if not isinstance(audio,dict) or set(audio)!={'file','sha256','seconds','voice','engine'}:
            raise ValueError('Invalid audio metadata')
        if not re.fullmatch(r'[a-f0-9]{64}\.wav',audio['file']) or audio['file']!=audio['sha256']+'.wav':
            raise ValueError('Audio must use a content hash filename')
        if type(audio['seconds']) not in (float,int) or not math.isfinite(audio['seconds']) or not .2<audio['seconds']<=30:
            raise ValueError('Speech duration out of bounds')
        if audio['voice'] not in ('bf_emma','bf_alice','bm_george','bm_lewis') or audio['engine']!='kokoro-onnx-0.6.1':
            raise ValueError('Unknown stock voice')
        if distance(observation,c['current']['speaker'],c['current']['listener'])>500:
            raise ValueError('Listener left before delivery')
        if c.get('paired_attendance') and not self._paired_present(c,observation):
            raise ValueError('Conversation attendance ownership lost before delivery')
        c['current'].update(audio=audio,delivery_id='speech-'+secrets.token_hex(12),delivery_session=self.session,prepared_at=time.time())
        c['phase']='speaking'
        state=copy.deepcopy(self.active);state['conversation']=c
        return {'checkpoint':self._write(state,'speech delivery persisted before playback')}

    def speech_command(self, session):
        c=self.conversation_status()
        if c and c['phase']=='attending':
            return {'id':'attend-'+c['id'],'kind':'conversation_attend','participants':[c['initiator'],c['partner']],
                'session':session,'checkpoint':self.marker}
        if c and c['phase']=='meeting':
            actor=c.get('initiator',108186);target=c.get('partner',108149)
            return {'id':'meet-'+c['id'],'kind':'walk_to','actor':actor,'target':target,'dynamic':dynamic_route(actor,target),
                'method':'package','retain':True,'origin':'resident_decision' if c.get('mode') else 'authored_encounter','session':session,'checkpoint':self.marker}
        if c and c['phase']=='releasing':
            return {'id':'release-chat-'+c['id'],'kind':'release_routine','actor':c.get('initiator',108186),
                **({'participants':[c['initiator'],c['partner']]} if c.get('paired_attendance') else {}),
                'session':session,'checkpoint':self.marker}
        if not c or c['phase']!='speaking' or c['current']['delivery_session']!=session: return None
        t=c['current']
        return {'id':t['delivery_id'],'kind':'speak','session':session,'checkpoint':self.marker,
            'actor':t['speaker'],'target':t['listener'],'line':t['selected']['line'],
            'tone':t['selected']['tone'],'audio':t['audio']}

    @staticmethod
    def _paired_present(c,observation):
        attendance=observation.get('conversationAttendance') or {}
        members=attendance.get('participants',[])
        return (attendance.get('id')=='attend-'+c['id'] and attendance.get('phase')=='attending'
                and len(members)==2 and {r.get('actor') for r in members}=={c['initiator'],c['partner']}
                and all(r.get('ownedPackage') is True and r.get('loaded') is True for r in members))

    def observe_conversation(self, observation):
        c=self.conversation_status()
        if not c:return
        ack=observation.get('ack') or {}
        if c['phase']=='attending' and ack.get('id')=='attend-'+c['id']:
            if ack.get('status')!='applied' or not self._paired_present(c,observation) or distance(observation,c['initiator'],c['partner'])>500:
                return self.hold_conversation(c['id'],'Both conversation attendance leases were not observed',observation)
            c.update(phase='propose',attendance_evidence=ack)
            state=copy.deepcopy(self.active);state['conversation']=c
            self._write(state,'both consenting participants own nearby attendance packages');return
        if c.get('attendance_evidence') and c['phase'] not in ('releasing','reflect_first','thinking_reflect_first','reflect_second','thinking_reflect_second','complete','held') and not self._paired_present(c,observation):
            return self.hold_conversation(c['id'],'Conversation attendance ownership interrupted',observation)
        if c['phase']=='meeting' and ack.get('id')=='meet-'+c['id']:
            if ack.get('status')!='applied':return self.hold_conversation(c['id'],'Meeting route failed',observation)
            if c.get('mode')=='autonomous_social':
                movement=ack.get('movement') or {}
                if (movement.get('actor')!=c['initiator'] or movement.get('target')!=c['partner'] or
                    movement.get('ownedPackage') is not True or distance(observation,c['initiator'],c['partner'])>500):
                    return self.hold_conversation(c['id'],'Social meeting lacks owned nearby attendance',observation)
            c['phase']='respond' if c.get('mode')=='autonomous_social' else 'propose';c['meeting_evidence']=ack
            state=copy.deepcopy(self.active);state['conversation']=c
            self._write(state,'conversation participants met under owned route');return
        if c['phase']=='releasing' and ack.get('id')=='release-chat-'+c['id']:
            c['release_evidence']=ack
            c['phase']=c.pop('final_phase') if ack.get('released') is True else 'held'
            if ack.get('released') is not True:c['error']='Conversation route release was not verified'
            state=copy.deepcopy(self.active);state['conversation']=c
            if c.get('mode')=='autonomous_social' and c['phase']=='complete':c['phase']='reflect_first'
            if c.get('mode')=='autonomous_social' and c['phase']=='held':settle_social(state,c,self._social_day(observation))
            if c['phase'] in ('complete','held'):c['finished_at']=time.time()
            self._write(state,'conversation travel task release observed');return
        if c['phase']!='speaking': return
        t=c['current'];report=observation.get('speech') or {}
        if t['delivery_session']!=self.session:
            return self.hold_conversation(c['id'],'Save/load interrupted speech; no automatic replay',observation)
        if report.get('id')!=t['delivery_id']: return
        if report.get('status')=='failed':
            return self.hold_conversation(c['id'],'Speech playback failed: '+str(report.get('error','unknown'))[:120],observation)
        if report.get('status')!='ended': return
        elapsed=report.get('playedSeconds')
        if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<t['audio']['seconds']-.3 or report.get('nearbyThroughout') is not True:
            return self.hold_conversation(c['id'],'Incomplete playback or listener left hearing range',observation)
        state=copy.deepcopy(self.active)
        t.update(delivered=True,playback=report,ended_at=time.time())
        record_heard_identity(state,t)
        for actor,kind in [(t['speaker'],'said'),(t['listener'],'heard_speech')]:
            p=state['people'][str(actor)]
            p['memories'].append({'event_id':t['delivery_id'],'kind':kind,'speaker':t['speaker'],
                'listener':t['listener'],'quote':t['selected']['line'],
                'epistemic_status':'claim, not verified fact',
                'source':'completed overlay audio playback with nearby listener; not semantic truth or lip-sync proof'})
            p['memories']=p['memories'][-32:]
        c['turns'].append(t);c.pop('current');c['turn']+=1
        at_limit=c['turn']>=c.get('max_turns',len(c['speakers']))
        c['phase']='releasing' if at_limit or c.get('end_after_turn') else 'continue_dialogue' if c.get('mode')=='autonomous_social' and c.get('turn_limit',2)>2 else 'propose'
        if c['phase']=='releasing':
            c['final_phase']='complete';c.setdefault('end_reason','turn_limit' if at_limit else 'polite_closure')
        state['conversation']=c
        self._write(state,'completed speech recorded as witnessed claims')

    def hold_conversation(self,event_id,reason,observation):
        c=self._conversation_guard(event_id,observation)
        if c['phase'] in ('complete','held'): return {'duplicate':True}
        no_route=c['phase'] in ('choose_partner','thinking_choose_partner','reflect_first','thinking_reflect_first','reflect_second','thinking_reflect_second')
        c.update(phase='held' if no_route else 'releasing',final_phase='held',error=str(reason)[:200])
        if no_route:c['finished_at']=time.time()
        state=copy.deepcopy(self.active);state['conversation']=c
        if c.get('mode')=='autonomous_social' and no_route:settle_social(state,c,self._social_day(observation))
        return {'checkpoint':self._write(state,'conversation held without retry')}
