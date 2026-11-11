import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = 'fpga-rtl-standards'


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dest = Path(self.temp.name) / 'skills'

    def run_install(self, *extra):
        return subprocess.run(
            [sys.executable, str(ROOT / 'install.py'), '--dest', str(self.dest), *extra],
            capture_output=True, text=True,
        )

    def test_install_all_skill_files_and_record_source(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        source = ROOT / 'skills' / NAME
        target = self.dest / NAME
        for file in source.rglob('*'):
            if file.is_file():
                self.assertEqual(file.read_bytes(), (target / file.relative_to(source)).read_bytes())
        receipt = json.loads((target / '.install-source.json').read_text())
        self.assertEqual(receipt['repository'], 'https://github.com/black-pigeon/fpga_skills_for_codex')
        self.assertEqual(receipt['path'], 'skills/' + NAME)

    def test_select_debug_skill_and_record_source(self):
        result = self.run_install('--skill', 'xilinx-jtag-debug')
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.dest / 'xilinx-jtag-debug'
        self.assertTrue((target / 'SKILL.md').is_file())
        receipt = json.loads((target / '.install-source.json').read_text())
        self.assertEqual(receipt['path'], 'skills/xilinx-jtag-debug')
        self.assertFalse((self.dest / NAME).exists())

    def test_install_both_skills(self):
        result = self.run_install('--skill', NAME, 'xilinx-jtag-debug')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in [NAME, 'xilinx-jtag-debug']:
            self.assertTrue((self.dest / name / 'SKILL.md').is_file())

    def test_invalid_skill_name_cannot_escape_repository(self):
        result = self.run_install('--skill', '../elsewhere')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.dest.exists())

    def test_existing_install_not_overwritten_without_update(self):
        target = self.dest / NAME
        target.mkdir(parents=True)
        sentinel = target / 'personal-notes.txt'
        sentinel.write_text('keep me')
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(), 'keep me')
        self.assertFalse((target / 'SKILL.md').exists())

    def test_update_replaces_install_and_preserves_backup(self):
        self.assertEqual(self.run_install().returncode, 0)
        target = self.dest / NAME
        (target / 'SKILL.md').write_text('local changes')
        (target / 'obsolete.txt').write_text('old file')
        result = self.run_install('--update')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((target / 'SKILL.md').read_bytes(), (ROOT / 'skills' / NAME / 'SKILL.md').read_bytes())
        self.assertFalse((target / 'obsolete.txt').exists())
        backups = list((self.dest.parent / 'skill-backups').glob(NAME + '-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / 'SKILL.md').read_text(), 'local changes')
        self.assertEqual((backups[0] / 'obsolete.txt').read_text(), 'old file')

    def test_destination_symlink_is_not_replaced(self):
        source = Path(self.temp.name) / 'managed-elsewhere'
        source.mkdir()
        self.dest.mkdir()
        try:
            (self.dest / NAME).symlink_to(source, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable on this platform')
        result = self.run_install('--update')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.dest / NAME).is_symlink())
        self.assertEqual(list(source.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
