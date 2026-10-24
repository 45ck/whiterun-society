import configparser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ProfileAudioTests(unittest.TestCase):
    def test_audio_diagnostic_is_explicit_and_normal_reconfiguration_restores_default(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);game=root/'game';game.mkdir()
            (root/'runtime').mkdir()
            profile=root/'mod-organizer/profiles/Default';profile.mkdir(parents=True)
            source='[General]\nsLanguage=ENGLISH\n[Audio]\nfMusicDuckingSeconds=6.0\n'
            (game/'Skyrim_Default.ini').write_text(source)
            (profile/'settings.ini').write_text('[General]\nLocalSaves=true\nLocalSettings=true\n')
            (profile/'skyrimprefs.ini').write_text('[Display]\niSize W=1280\n')
            (game/'Data').mkdir()
            (game/'Data/WhiterunAgents.esp').write_bytes(b'fixture')
            (game/'Data/WhiterunRouter.esp').write_bytes(b'fixture')
            existing=['*Skyrim.esm','*WhiterunSociety.esp','*WhiterunAgents.esp','*Unrelated.esp']
            (profile/'plugins.txt').write_text('\n'.join(existing)+'\n')
            script=Path(__file__).resolve().parents[1]/'tools/configure_profile.py'
            for diagnostic in (False,True,False):
                subprocess.run([sys.executable,str(script),'--root',str(root),*(['--audio-diagnostic'] if diagnostic else [])],check=True,capture_output=True)
                ini=configparser.ConfigParser();ini.read(profile/'skyrim.ini')
                self.assertEqual(ini.getboolean('Audio','bEnableAudio',fallback=True),not diagnostic)
                self.assertEqual(json.loads((root/'runtime/audio-mode.json').read_text())['disabled'],diagnostic)
                self.assertEqual((game/'Skyrim_Default.ini').read_text(),source)
                self.assertEqual((profile/'plugins.txt').read_text().splitlines(),existing+['*WhiterunRouter.esp'])
            (game/'Data/WhiterunRest.esp').write_bytes(b'fixture')
            subprocess.run([sys.executable,str(script),'--root',str(root),'--experimental-rest'],check=True,capture_output=True)
            self.assertIn('*WhiterunRest.esp',(profile/'plugins.txt').read_text().splitlines())
            subprocess.run([sys.executable,str(script),'--root',str(root)],check=True,capture_output=True)
            self.assertEqual((profile/'plugins.txt').read_text().splitlines(),existing+['*WhiterunRouter.esp','WhiterunRest.esp'])
