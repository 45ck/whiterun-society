"""Retry only a certified pre-mutation checkpoint conflict, never inference."""
import json
import time
import urllib.error
import urllib.request


MUTATION_PREFIXES=('/agency/','/conversation/','/routines/','/town/','/goals/','/world/','/market-day/')


def checkpoint_rejection(path,expected_session,current_session,transition,native_effect=False):
    """Called synchronously before a mutation by the single-threaded server."""
    if not path.startswith(MUTATION_PREFIXES):return None
    if expected_session is not None and expected_session!=current_session:
        return {'code':'session_changed','error':'Game session changed; request was not applied','session':current_session}
    if transition:
        return {'code':'checkpoint_busy','error':'Checkpoint is binding; request was not applied','session':current_session}
    if path=='/goals/result' and native_effect:
        return {'code':'goal_effect_busy','error':'Native effect is pending; goal result was not applied','session':current_session}
    return None


class CheckpointHTTP:
    def __init__(self,base,token,timeout=30,checkpoint_wait=40):
        self.base=base;self.token=token;self.timeout=timeout;self.checkpoint_wait=checkpoint_wait;self.session=None

    def __call__(self,route,data=None):
        mutation=data is not None and route.startswith(MUTATION_PREFIXES)
        # Bind the worker to the initial game session before any state mutation.
        if mutation and self.session is None:self('/state')
        if mutation and self.session is None:raise ValueError('No game session for checkpoint mutation')
        encoded=None if data is None else json.dumps(data).encode()
        deadline=time.monotonic()+self.checkpoint_wait
        retrying=False
        while True:
            headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'}
            if mutation:headers['X-Society-Session']=self.session
            request=urllib.request.Request(self.base+route,data=encoded,headers=headers)
            # Include the final HTTP attempt in the bounded conflict wait.
            timeout=min(self.timeout,max(.001,deadline-time.monotonic())) if retrying else self.timeout
            try:
                with urllib.request.urlopen(request,timeout=timeout) as response:result=json.load(response)
            except urllib.error.HTTPError as error:
                if error.code!=409 or not mutation:raise
                try:body=json.load(error)
                except (ValueError,TypeError):raise ValueError('Unrecognized checkpoint conflict; no retry') from None
                recognized=isinstance(body,dict) and (body.get('code')=='checkpoint_busy'
                    or route=='/goals/result' and body.get('code')=='goal_effect_busy')
                if not recognized:
                    raise ValueError(body.get('error','Request conflict; no retry') if isinstance(body,dict) else 'Request conflict; no retry') from None
                if body.get('session')!=self.session:raise ValueError('Game session changed; no retry') from None
                if time.monotonic()>=deadline:raise TimeoutError('Checkpoint conflict did not settle; no mutation replay') from None
                retrying=True;time.sleep(min(.1,max(0,deadline-time.monotonic())))
                if time.monotonic()>=deadline:raise TimeoutError('Checkpoint conflict did not settle; no mutation replay')
                continue
            if route=='/state':
                session=result.get('bridge',{}).get('session')
                if self.session is not None and session!=self.session:raise ValueError('Game session changed; worker must stop')
                if isinstance(session,str) and session:self.session=session
            return result
