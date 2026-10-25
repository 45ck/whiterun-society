"""Run inside the isolated Kokoro environment; output stock-voice speech only."""
import argparse
import hashlib
import json
import contextlib
import sys
import time
from pathlib import Path


def validate_request(data):
    text=data['text'];voice=data['voice']
    if not isinstance(text,str) or not 1<=len(text)<=240 or voice not in ('bf_emma','bf_alice','bm_george','bm_lewis'):
        raise ValueError('Invalid bounded stock-voice request')
    return text,voice


def load_voice(root):
    import onnxruntime as rt
    from kokoro_onnx import Kokoro
    options=rt.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
    models=root/'models/kokoro'
    session=rt.InferenceSession(str(models/'kokoro-v1.0.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
    return Kokoro.from_session(session,str(models/'voices-v1.0.bin'))


def synthesize(kokoro,root,data):
    import soundfile as sf
    text,voice=validate_request(data)
    samples,rate=kokoro.create(text,voice=voice,speed=1.0,lang='en-gb')
    seconds=len(samples)/rate
    if not .2<seconds<=30:raise ValueError('Speech too long or empty')
    target=root/'game/Data/Platform/UI/audio';target.mkdir(exist_ok=True)
    import io
    wav=io.BytesIO();sf.write(wav,samples,rate,format='WAV',subtype='PCM_16');encoded=wav.getvalue()
    digest=hashlib.sha256(encoded).hexdigest();name=digest+'.wav'
    (target/name).write_bytes(encoded)
    metadata={'file':name,'sha256':digest,'seconds':round(seconds,4),'voice':voice,'engine':'kokoro-onnx-0.6.1'}
    return metadata


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--input',type=Path);mode.add_argument('--serve',action='store_true')
    p.add_argument('--max-requests',type=int,default=6);args=p.parse_args()
    if not 1<=args.max_requests<=16:raise ValueError('Voice request limit must be 1 to 16')
    started=time.monotonic()
    with contextlib.redirect_stdout(sys.stderr):kokoro=load_voice(args.root)
    if args.input:
        data=json.loads(args.input.read_text(encoding='utf-8'))
        with contextlib.redirect_stdout(sys.stderr):metadata=synthesize(kokoro,args.root,data)
        args.input.with_suffix('.audio.json').write_text(json.dumps(metadata),encoding='utf-8')
        print(json.dumps(metadata));return
    print(json.dumps({'ready':True,'load_seconds':round(time.monotonic()-started,3)}),flush=True)
    for _ in range(args.max_requests):
        raw=sys.stdin.buffer.readline(4097)
        if not raw:return
        if len(raw)>4096:raise ValueError('Oversized voice request')
        data=json.loads(raw);request_id=data['id'];started=time.monotonic()
        try:
            with contextlib.redirect_stdout(sys.stderr):metadata=synthesize(kokoro,args.root,data)
            result={'id':request_id,'audio':metadata,'synthesis_seconds':round(time.monotonic()-started,3)}
        except Exception as error:result={'id':request_id,'error':type(error).__name__+': voice synthesis failed'}
        print(json.dumps(result),flush=True)
        if 'error' in result:return


if __name__=='__main__':main()
