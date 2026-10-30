"""Exercise the real launcher without applications, sysfs or board hardware."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class KVMRunTests(unittest.TestCase):
    def test_capture_selection_is_shared_and_does_not_leak_across_kernels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = (ROOT / 'board/vim4-kvm-run').read_text()
            script = re.sub(r'/(?:sys|usr|opt|var)/', lambda match: str(root) + match[0], script)
            launcher = root / 'run'
            launcher.write_text(script)
            binaries = ('opt/vim4-nanokvm/NanoKVM-Server', 'opt/vim4-jetkvm/jetkvm',
                        'opt/vim4-onekvm/one-kvm', 'usr/libexec/vim4-pikvm-run')
            for binary in binaries:
                path = root / binary
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f'#!{sys.executable}\nimport json, os\nprint(json.dumps(dict(os.environ)))\n')
                path.chmod(0o755)
            for plugin in ('usr/lib/vim4-kvm/vendor-gstreamer-1.0/libgstvideo4linux2.so',
                           'opt/vim4-onekvm/lib/gstreamer-1.0/libgstvideo4linux2.so',
                           'usr/lib/vim4-kvm/gpu/mali.json'):
                path = root / plugin
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            native = root / 'sys/module/aml_media/parameters/vdin0_native_hdr'
            native.parent.mkdir(parents=True)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            for name, command in (('uname', 'echo "$TEST_KERNEL"'), ('taskset', 'exit 0')):
                path = bin_dir / name
                path.write_text('#!/bin/sh\n' + command + '\n')
                path.chmod(0o755)
            for kernel, enabled, secondary in (
                ('5.15.137-vim4kvm-hdrdual6', 'Y', True),
                ('5.15.137-vim4kvm', 'N', False),
                ('7.3.0-vim4kvm-uhd1+', 'Y', False),
                ('7.3.0-vim4kvm-uhd2+', 'Y', False),
                ('7.3.0-vim4kvm-npu1+', 'Y', False),
                ('7.3.0-vim4kvm-npu2+', 'Y', False),
                ('7.3.0-rc7-vim4kvm-uhd1+', 'Y', False),
            ):
                native.write_text(enabled)
                for app in ('nanokvm', 'jetkvm', 'pikvm', 'onekvm'):
                    with self.subTest(kernel=kernel, app=app):
                        result = subprocess.run(['sh', str(launcher), app], capture_output=True, text=True,
                            env={**os.environ, 'PATH': str(bin_dir) + os.pathsep + os.environ['PATH'],
                                 'TEST_KERNEL': kernel, 'VIM4_SECONDARY_HDMI_CAPTURE': '1',
                                 'GST_V4L2_PREFER_CONTIGUOUS': '0',
                                 'VK_ICD_FILENAMES': '/usr/lib/vim4-kvm/gpu/mali.json'})
                        self.assertEqual(result.returncode, 0, result.stderr)
                        actual = json.loads(result.stdout)
                        self.assertEqual(actual.get('VIM4_SECONDARY_HDMI_CAPTURE'), '1' if secondary else None)
                        self.assertEqual(actual['VIM4_VIDEO_BACKEND'], 'wave5' if kernel.startswith('7.') else 'vendor')
                        self.assertEqual(actual.get('GST_V4L2_PREFER_CONTIGUOUS'),
                                         None if kernel.startswith('7.') else '1')
                        if kernel.startswith('7.'):
                            self.assertNotIn('VK_ICD_FILENAMES', actual)
                        elif app == 'onekvm':
                            self.assertEqual(actual['VK_ICD_FILENAMES'], str(root / 'usr/lib/vim4-kvm/gpu/mali.json'))
                        if secondary:
                            self.assertIn('/vendor-gstreamer-1.0:', actual['GST_PLUGIN_PATH'])

    @unittest.skipUnless((ROOT / 'NanoKVM').is_dir(), 'NanoKVM is not checked out')
    def test_nanokvm_scaling_preserves_the_native_display(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = (ROOT / 'NanoKVM/deploy/vim4/vim4-video').read_text()
            for prefix in ('/sys/', '/run/lock/', '/etc/default/'):
                script = script.replace(prefix, str(root) + prefix)
            for path in ('run/lock', 'etc/default', 'sys/module/aml_media/parameters'):
                (root / path).mkdir(parents=True, exist_ok=True)
            (root / 'sys/module/aml_media/parameters/vdin0_native_hdr').write_text('Y')
            config = root / 'etc/default/vim4-kvm-hdmi'
            config.write_text('HDMI_WIDTH=3840\nHDMI_HEIGHT=2160\nHDMI_DISPLAY_TEE=1\n')
            previous = config.read_bytes()
            for name, command in (('uname', 'echo 5.15.137-test'), ('flock', 'exit 0'),
                                  ('systemctl', 'echo Unexpected HDMI restart >&2; exit 1')):
                path = root / name
                path.write_text('#!/bin/sh\n' + command + '\n')
                path.chmod(0o755)
            launcher = root / 'video'
            launcher.write_text(script)
            result = subprocess.run(['sh', str(launcher), '1920', '1080'], capture_output=True, text=True,
                                    env={**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH']})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, '')
            self.assertEqual(config.read_bytes(), previous)
