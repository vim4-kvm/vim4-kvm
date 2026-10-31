import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class KbaseRuntimeTest(unittest.TestCase):
    def test_candidate_platform_uses_mainline_services_and_rejects_unknown_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = (ROOT / 'board/vim4-board-runtime').read_text()
            script = script.replace('/usr/libexec/', str(root) + '/')
            launcher = root / 'runtime'
            launcher.write_text(script)
            for name in ('vim4-mainline-gadget-prepare', 'vim4-mainline-prepare',
                         'vim4-edid', 'systemd-notify', 'sleep'):
                path = root / name
                path.write_text('#!/bin/sh\necho ' + name + '\n')
                path.chmod(0o755)
            uname = root / 'uname'
            uname.write_text('#!/bin/sh\necho 7.3.0-vim4kvm-uhd3+\n')
            uname.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'])
            for action, expected in (('gadget-start', 'vim4-mainline-gadget-prepare'),
                                     ('hdmi', 'vim4-mainline-prepare')):
                result = subprocess.run(['sh', str(launcher), action], env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout)
            rejected = subprocess.run(['sh', str(launcher), 'check-kernel', '7.3.0-unregistered'],
                                      env=env, text=True, capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertNotIn('prepare', rejected.stdout)

    def test_gpu_binding_selects_blob_without_changing_wave5(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = (ROOT / 'board/vim4-kvm-run').read_text()
            script = re.sub(r'/(?:sys|usr|opt|var)/', lambda m: str(root) + m[0], script)
            launcher = root / 'launcher'
            launcher.write_text(script)
            executable = root / 'opt/vim4-nanokvm/NanoKVM-Server'
            executable.parent.mkdir(parents=True)
            executable.write_text('#!' + sys.executable + '\nimport os\nprint(os.environ["VIM4_VIDEO_BACKEND"])\n')
            executable.chmod(0o755)
            python = root / 'usr/bin/python3'
            python.parent.mkdir(parents=True)
            python.symlink_to(sys.executable)
            wrapper = root / 'usr/lib/vim4-kvm/python/vim4gpu.py'
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text('import os,sys\nprint("blob-direct",flush=True)\na=sys.argv.index("--")+1\nos.execv(sys.argv[a],sys.argv[a:])\n')
            driver = root / 'sys/bus/platform/devices/fe400000.gpu/driver'
            driver.parent.mkdir(parents=True)
            for name, contents in (('uname', 'echo 7.3.0-vim4kvm-uhd3+'), ('taskset', 'exit 0')):
                path = root / name
                path.write_text('#!/bin/sh\n' + contents + '\n')
                path.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'])
            for bound in ('panfrost', 'mali'):
                driver.symlink_to('/sys/bus/platform/drivers/' + bound)
                result = subprocess.run(['sh', str(launcher), 'nanokvm'], env=env, text=True, capture_output=True)
                driver.unlink()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('wave5', result.stdout)
                self.assertEqual('blob-direct' in result.stdout, bound == 'mali')
