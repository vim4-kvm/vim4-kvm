"""An unsupported kernel or unverified firmware must not touch video hardware."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EdgeLauncherTest(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.bin = Path(self.directory)
        self.trace = self.bin / 'hardware-calls'
        for name, body in {
            'uname': 'printf "%s\\n" "$EDGE_TEST_RELEASE"',
            'sha256sum': 'cat >/dev/null; exit 1',
            'modprobe': 'printf "modprobe\\n" >> "$EDGE_TEST_TRACE"',
            'udevadm': 'printf "udevadm\\n" >> "$EDGE_TEST_TRACE"',
            'systemctl': 'case "$3" in SubState) echo exited ;; ExecMainStatus) echo 0 ;; esac',
        }.items():
            path = self.bin / name
            path.write_text('#!/bin/sh\n' + body + '\n')
            path.chmod(0o755)

    def run_script(self, name, release):
        env = dict(os.environ, PATH=f'{self.bin}:/usr/bin:/bin',
                   EDGE_TEST_RELEASE=release, EDGE_TEST_TRACE=str(self.trace))
        return subprocess.run(['sh', str(ROOT / 'packaging/kernel-edge' / name)],
                              env=env, capture_output=True, text=True, timeout=5)

    def test_prepare_refuses_production_and_unknown_kernels_before_hardware_access(self):
        for release in ['5.15.137-vim4kvm', '7.3.0-unmatched']:
            with self.subTest(release=release):
                result = self.run_script('one-kvm-edge-prepare', release)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.trace.exists())

    def test_invalid_firmware_prevents_module_loading(self):
        result = self.run_script('one-kvm-edge-prepare', '7.3.0-rc7-vim4kvm-uhd1+')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.trace.exists())

    def test_npu_candidate_still_requires_verified_video_firmware(self):
        result = self.run_script('one-kvm-edge-prepare', '7.3.0-vim4kvm-npu2+')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('firmware is missing or has changed', result.stderr)
        self.assertFalse(self.trace.exists())

    def test_failed_secure_preloader_prevents_module_loading(self):
        (self.bin / 'systemctl').write_text(
            '#!/bin/sh\ncase "$3" in SubState) echo exited ;; ExecMainStatus) echo 1 ;; esac\n')
        result = self.run_script('one-kvm-edge-prepare', '7.3.0-rc7-vim4kvm-uhd1+')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('preloader failed', result.stderr)
        self.assertFalse(self.trace.exists())

    def test_final_release_enters_the_same_guarded_preparation_path(self):
        (self.bin / 'systemctl').write_text(
            '#!/bin/sh\ncase "$3" in SubState) echo exited ;; ExecMainStatus) echo 1 ;; esac\n')
        result = self.run_script('one-kvm-edge-prepare', '7.3.0-vim4kvm-uhd1+')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('preloader failed', result.stderr)
        self.assertFalse(self.trace.exists())

    def test_unfinished_secure_preloader_has_bounded_wait_and_no_hardware_access(self):
        (self.bin / 'systemctl').write_text('#!/bin/sh\necho running\n')
        sleep = self.bin / 'sleep'
        sleep.write_text('#!/bin/sh\nexit 0\n')
        sleep.chmod(0o755)
        result = self.run_script('one-kvm-edge-prepare', '7.3.0-rc7-vim4kvm-uhd1+')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('preloader did not finish', result.stderr)
        self.assertFalse(self.trace.exists())

    def test_unmatched_kernel_cannot_launch_either_application(self):
        result = self.run_script('one-kvm-edge', '7.3.0-unmatched')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No validated One-KVM backend', result.stderr)

    def test_prepare_rejects_preloaded_copy_mode_before_application_start(self):
        (self.bin / 'sha256sum').write_text('#!/bin/sh\n/bin/cat >/dev/null; exit 0\n')
        cat = self.bin / 'cat'
        cat.write_text('#!/bin/sh\ncase "$1" in\n'
                       '  */t7_vdin_test/parameters/direct_dma) echo N ;;\n'
                       '  /sys/module/*/parameters/*) echo Y ;;\n'
                       '  *) exec /bin/cat "$@" ;;\nesac\n')
        cat.chmod(0o755)
        result = self.run_script('one-kvm-edge-prepare', '7.3.0-rc7-vim4kvm-uhd1+')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('leased direct DMA', result.stderr)
        self.assertNotIn('udevadm', self.trace.read_text())

    def test_prepare_rejects_preloaded_fixed_geometry_before_application_start(self):
        (self.bin / 'sha256sum').write_text('#!/bin/sh\n/bin/cat >/dev/null; exit 0\n')
        cat = self.bin / 'cat'
        cat.write_text('#!/bin/sh\ncase "$1" in\n'
                       '  */t7_hdmirx/parameters/dynamic_modes) echo N ;;\n'
                       '  /sys/module/*/parameters/*) echo Y ;;\n'
                       '  *) exec /bin/cat "$@" ;;\nesac\n')
        cat.chmod(0o755)
        result = self.run_script('one-kvm-edge-prepare', '7.3.0-rc7-vim4kvm-uhd1+')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('HDMI receiver is already loaded', result.stderr)
        self.assertNotIn('udevadm', self.trace.read_text())


if __name__ == '__main__':
    unittest.main()
