"""Run inside the isolated Kokoro environment; output stock-voice speech only."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--input',type=Path,required=True)
    args=p.parse_args();data=json.loads(args.input.read_text(encoding='utf-8'))
    text=data['text'];voice=data['voice']
    if not isinstance(text,str) or not 1<=len(text)<=240 or voice not in ('bf_emma','bf_alice'):
        raise ValueError('Invalid bounded stock-voice request')
    import onnxruntime as rt
    import soundfile as sf
    from kokoro_onnx import Kokoro
    options=rt.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
    models=args.root/'models/kokoro'
    session=rt.InferenceSession(str(models/'kokoro-v1.0.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
    kokoro=Kokoro.from_session(session,str(models/'voices-v1.0.bin'))
    samples,rate=kokoro.create(text,voice=voice,speed=1.0,lang='en-gb')
    seconds=len(samples)/rate
    if not .2<seconds<=30:raise ValueError('Speech too long or empty')
    target=args.root/'game/Data/Platform/UI/audio';target.mkdir(exist_ok=True)
    import io
    wav=io.BytesIO();sf.write(wav,samples,rate,format='WAV',subtype='PCM_16');encoded=wav.getvalue()
    digest=hashlib.sha256(encoded).hexdigest();name=digest+'.wav'
    (target/name).write_bytes(encoded)
    metadata={'file':name,'sha256':digest,'seconds':round(seconds,4),'voice':voice,'engine':'kokoro-onnx-0.6.1'}
    args.input.with_suffix('.audio.json').write_text(json.dumps(metadata),encoding='utf-8')
    print(json.dumps(metadata))


if __name__=='__main__':main()
