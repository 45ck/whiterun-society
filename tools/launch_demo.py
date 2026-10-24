"""Start or attach to the isolated observer demo; wait for actual game readiness."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

SOURCE=Path(__file__).resolve().parents[1]


def request(port,path,token=None):
    headers={'Authorization':'Bearer '+token} if token else {}
    with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}{path}',headers=headers),timeout=3) as response:
        return json.load(response)


def game_paths():
    # A fixed read-only command; no shell interpolation of caller-controlled paths.
    result=subprocess.run(['powershell','-NoProfile','-Command',
        "@(Get-CimInstance Win32_Process -Filter \"Name='SkyrimSE.exe'\" | ForEach-Object { $_.ExecutablePath }) | ConvertTo-Json -Compress"],
        capture_output=True,text=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    data=json.loads(result.stdout) if result.stdout.strip() else []
    if isinstance(data,str): data=[data]
    if any(not value for value in data): raise RuntimeError('Cannot identify a running Skyrim process')
    return [Path(value).resolve() for value in data]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=180)
    parser.add_argument('--audio-diagnostic',action='store_true')
    args=parser.parse_args()
    if os.name!='nt': raise RuntimeError('The observer launcher currently requires Windows')
    root=args.root.resolve()
    manifest=json.loads((root/'runtime-manifest.json').read_text())
    game=Path(manifest['game']).resolve()
    original=Path(manifest['source']).resolve()
    if game!=root/'game' or game==original or original in root.parents or root in original.parents:
        raise RuntimeError('Runtime isolation check failed')
    mo=root/'mod-organizer'/'ModOrganizer.exe'
    if not mo.is_file() or not (mo.parent/'portable.txt').exists():
        raise RuntimeError('Complete the portable Mod Organizer setup first')
    existing=game_paths()
    if any(path!=game/'SkyrimSE.exe' for path in existing):
        raise RuntimeError('Another Skyrim installation is running; it has been left untouched')
    runtime=root/'runtime'
    runtime.mkdir(exist_ok=True)
    config_path=runtime/'bridge-config.json'
    port=json.loads(config_path.read_text())['port'] if config_path.exists() else 17841
    if type(port) is not int or not 1024 <= port <= 65535:
        raise RuntimeError('Invalid local service port in runtime configuration')
    started=time.monotonic()
    def progress(message): print(f'[{time.monotonic()-started:5.1f}s] {message}',flush=True)
    try:
        health=request(port,'/health')
    except urllib.error.URLError:
        progress('Starting local society service')
        with (runtime/'service.log').open('a',encoding='utf-8') as log:
            service=subprocess.Popen([sys.executable,str(SOURCE/'server.py'),'--runtime',str(runtime),'--port',str(port)],
                cwd=SOURCE,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+15
        while True:
            if service.poll() is not None: raise RuntimeError('Local service exited; inspect runtime/service.log')
            try:
                health=request(port,'/health');break
            except urllib.error.URLError:
                if time.monotonic()>deadline: raise RuntimeError('Local service startup timed out')
                time.sleep(0.25)
    if health.get('service')!='whiterun-society' or health.get('protocol')!=1:
        raise RuntimeError(f'Port {port} is occupied by another or older service')
    config=json.loads((runtime/'bridge-config.json').read_text())
    initial_session=request(port,'/state',config['token'])['bridge']['session']
    if not existing:
        subprocess.run([sys.executable,str(SOURCE/'tools'/'build_plugin.py'),'--output',str(game/'Data'/'WhiterunSociety.esp')],check=True)
        subprocess.run([sys.executable,str(SOURCE/'tools'/'patch_overlay_save.py'),'--root',str(root)],check=True)
        subprocess.run([sys.executable,str(SOURCE/'tools'/'configure_profile.py'),'--root',str(root),*(['--audio-diagnostic'] if args.audio_diagnostic else [])],check=True)
    elif args.audio_diagnostic and not (runtime/'audio-mode.json').exists():
        raise RuntimeError('Audio diagnostics need a new lab process, not a hot reload')
    mode=json.loads((runtime/'audio-mode.json').read_text()) if (runtime/'audio-mode.json').exists() else {'disabled':False}
    if args.audio_diagnostic and not mode['disabled']:
        raise RuntimeError('Running game has audio enabled; restart is required for this diagnostic')
    if mode['disabled']:progress('Audio disabled for this diagnostic; audio stability is not being validated')
    subprocess.run([sys.executable,str(SOURCE/'tools'/'deploy_bridge.py'),'--root',str(root)],check=True)
    if not existing:
        progress('Launching SKSE through the isolated Mod Organizer profile')
        subprocess.Popen([str(mo),'-p','Default','moshortcut://:SKSE'],cwd=mo.parent)
    else:
        progress('Attached to the already-running lab game')
    deadline=time.monotonic()+args.timeout
    previous=None
    while time.monotonic()<deadline:
        health=request(port,'/health')
        state=request(port,'/state',config['token']) if health['bridge_connected'] else None
        fresh=state is not None and state['bridge']['session']!=initial_session
        ready=health['observer_ready'] and fresh
        stage='observer ready' if ready else ('waiting for loaded residents' if fresh else 'waiting for game and bridge')
        if stage!=previous: progress(stage);previous=stage
        if ready:
            evidence={'elapsed_seconds':round(time.monotonic()-started,2),'health':health,'audio_mode':mode,
                      'observation':state['bridge']['observation']}
            (runtime/'last-launch.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
            progress('Whiterun is ready to observe. No character setup or playthrough required.')
            return
        time.sleep(1)
    raise RuntimeError('Game did not become ready before the timeout. Nothing has been reported as a successful launch.')


if __name__=='__main__':
    try: main()
    except (RuntimeError,OSError,ValueError,subprocess.SubprocessError) as error:
        print('Launch failed: '+str(error),file=sys.stderr)
        sys.exit(1)
