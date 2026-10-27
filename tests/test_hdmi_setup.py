"""Exercise native capture memory policy without touching a live HDMI source."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HDMISetupTests(unittest.TestCase):
    def test_native_pool_limit_preserves_legacy_and_smaller_admin_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = (ROOT / 'tools/hdmi-setup.sh').read_text()
            for prefix in ('/sys/', '/usr/libexec/'):
                script = script.replace(prefix, str(root) + prefix)
            setup = root / 'hdmi-setup.sh'
            setup.write_text(script)
            params = root / 'sys/module/aml_media/parameters'
            params.mkdir(parents=True)
            native, maximum = params / 'vdin0_native_hdr', params / 'max_buf_num'
            attr = root / 'sys/class/vdin/vdin0/attr'
            attr.parent.mkdir(parents=True)
            attr.touch()
            mapping = root / 'sys/class/vfm/map'
            mapping.parent.mkdir(parents=True)
            mapping.write_text('tvpath { vdin0(0) vfm_cap}\n')
            for name, command in (('modprobe', 'exit 0'), ('pkill', 'exit 1'),
                                  ('vim4-hdr-curve', 'exit 0'),
                                  ('hdmiin-demo', 'echo HDMI-open')):
                stub = root / name
                stub.write_text('#!/bin/sh\n' + command + '\n')
                stub.chmod(0o755)
            for enabled, before, expected in (
                ('Y', '12', '6'), ('Y', '4', '4'), ('N', '12', '12'),
                (None, '12', '12'), ('Y', None, None),
            ):
                with self.subTest(native=enabled, maximum=before):
                    for path, value in ((native, enabled), (maximum, before)):
                        if value is None:
                            path.unlink(missing_ok=True)
                        else:
                            path.write_text(value + '\n')
                    result = subprocess.run(['sh', str(setup)], capture_output=True, text=True,
                        env={**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                             'HDMI_WIDTH': '3840', 'HDMI_HEIGHT': '2160',
                             'HDMI_CAPTURE_FORMAT': 'NV21', 'HDMI_LOW_LATENCY': '1',
                             'HDMI_DISPLAY_TEE': '0', 'VIM4_HDMI_NOTIFY': '0'})
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), 'HDMI-open')
                    self.assertEqual(maximum.read_text().strip() if maximum.exists() else None, expected)
