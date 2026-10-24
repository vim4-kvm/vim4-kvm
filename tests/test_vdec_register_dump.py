"""Invalid dump plans cannot reach a physical read or a vendor address-cache write."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('cc'), 'requires a C compiler')
class RegisterReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.reader = Path(cls.directory.name) / 'reader'
        subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-Werror',
                        str(ROOT / 'packaging/kernel-edge/vdec-register-dump.c'),
                        '-o', str(cls.reader)], check=True)

    def test_entire_plan_validated_before_either_hardware_interface_is_opened(self):
        for backend in ('--devmem', '--vendor-paddr'):
            for invalid in ('0xfe32260c', '0xfe322638', '0xfe32fc08',
                            '0xfe0102a0', '0xfe010380',
                            '0xfe000001', '0xfe000004 0xdeadbeef'):
                with self.subTest(backend=backend, invalid=invalid):
                    plan = Path(self.directory.name) / 'addresses'
                    plan.write_text('0xfe000044\n' + invalid + '\n')
                    result = subprocess.run([str(self.reader), backend, str(plan)],
                                            text=True, capture_output=True, timeout=3)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn('refusing address', result.stderr)
                    self.assertEqual(result.stdout, '')
