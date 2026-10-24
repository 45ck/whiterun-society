import tempfile
import unittest
from pathlib import Path
from tools.verify_plan_save import plugin_manifest

class SavePluginTests(unittest.TestCase):
    def test_order_enabled_state_and_generated_bytes_are_part_of_save_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);profile=root/'mod-organizer/profiles/Default';profile.mkdir(parents=True)
            data=root/'game/Data';data.mkdir(parents=True)
            (data/'WhiterunRouter.esp').write_bytes(b'route')
            (data/'WhiterunRest.esp').write_bytes(b'rest')
            p=profile/'plugins.txt';p.write_text('*WhiterunRouter.esp\n*WhiterunRest.esp\n')
            original=plugin_manifest(root)
            p.write_text('*WhiterunRest.esp\n*WhiterunRouter.esp\n')
            self.assertNotEqual(plugin_manifest(root),original)
            p.write_text('*WhiterunRouter.esp\nWhiterunRest.esp\n')
            self.assertNotEqual(plugin_manifest(root),original)
            p.write_text('*WhiterunRouter.esp\n*WhiterunRest.esp\n');(data/'WhiterunRest.esp').write_bytes(b'changed')
            self.assertNotEqual(plugin_manifest(root),original)

    def test_missing_generated_plugin_cannot_be_recorded_as_qualified(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);profile=root/'mod-organizer/profiles/Default';profile.mkdir(parents=True)
            (profile/'plugins.txt').write_text('*WhiterunRest.esp\n')
            with self.assertRaises(FileNotFoundError):plugin_manifest(root)

if __name__=='__main__':unittest.main()
