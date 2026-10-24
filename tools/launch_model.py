"""Launch the prepared, local CPU model. No tools, remote access, or idle prompts."""
import argparse
import json
import secrets
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / 'runtime/model-manifest.json').read_text())
    engine = root / 'vendor/llama-b11849/llama-server.exe'
    model = root / manifest['files'][1]['path']
    key_file = root / 'runtime/model-key.txt'
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
    config = {'url': 'http://127.0.0.1:17842', 'key_file': str(key_file),
              'model': manifest['model'], 'engine': manifest['engine']}
    (root / 'runtime/model-config.json').write_text(json.dumps(config, indent=2))
    with (root / 'runtime/model.stdout.log').open('w') as out, (root / 'runtime/model.stderr.log').open('w') as err:
        process = subprocess.Popen([str(engine), '-m', str(model), '--host', '127.0.0.1',
            '--port', '17842', '--threads', '4', '--ctx-size', '4096', '--parallel', '1',
            '--gpu-layers', '0', '--reasoning', 'off', '--offline', '--no-webui',
            '--no-agent', '--cors-origins', 'http://127.0.0.1:17842', '--no-cors-credentials',
            '--api-key-file', str(key_file)], stdout=out, stderr=err,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    print(json.dumps({'pid': process.pid, 'url': config['url'], 'status': 'starting'}))


if __name__ == '__main__':
    main()
