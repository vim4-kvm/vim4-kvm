import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'preflight', ROOT / 'packaging/kernel-edge/passthrough-preflight.py')
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


@unittest.skipUnless(shutil.which('dtc') and shutil.which('fdtget'), 'dtc/fdtget required')
class PreflightTests(unittest.TestCase):
    def check_tree(self, extra='', split=True, display_start=0xff006840):
        dts = '''/dts-v1/;
        / {
            #address-cells = <2>; #size-cells = <2>;
            display {
                compatible = "amlogic,t7-display";
                amlogic,video-planes;
                reg = <0 START 0 0x80>;
            };
            capture {
                compatible = "amlogic,t7-vdin-test";
                reg = <0 0xff000000 0 0x40000>;
                SPLIT
            };
            tx { compatible = "amlogic,t7-hdmi-tx"; amlogic,enc2-modeset; };
            sound { compatible = "amlogic,axg-sound-card"; model = "VIM4HDMITX"; };
            gpu { compatible = "arm,mali-bifrost"; };
            EXTRA
        };'''.replace('START', hex(display_start)).replace(
            'SPLIT', 'amlogic,split-vcbus;' if split else '').replace('EXTRA', extra)
        with tempfile.TemporaryDirectory() as directory:
            dtb = Path(directory) / 'test.dtb'
            subprocess.run(['dtc', '-q', '-I', 'dts', '-O', 'dtb', '-o', str(dtb)],
                           input=dts, text=True, check=True)
            return preflight.audit(preflight.DeviceTree(dtb), [(0xff004800, 0x400)])

    def test_whole_window_lease_rejects_capture_display_coexistence(self):
        self.assertTrue(self.check_tree()['offline_resource_gate'])
        report = self.check_tree(split=False)
        self.assertFalse(report['offline_resource_gate'])
        self.assertTrue(any('overlap' in error for error in report['errors']))

    def test_hdr_window_boundary_and_overlap(self):
        self.assertTrue(self.check_tree(display_start=0xff004c00)['offline_resource_gate'])
        report = self.check_tree(display_start=0xff004bfc)
        self.assertFalse(report['offline_resource_gate'])

    def test_disabled_ancestor_excludes_gpu_but_enabled_duplicate_fails(self):
        extra = '''bus { status = "disabled";
            gpu { compatible = "arm,mali-midgard"; }; };'''
        self.assertTrue(self.check_tree(extra)['offline_resource_gate'])
        self.assertFalse(self.check_tree(extra.replace('disabled', 'okay'))['offline_resource_gate'])

    def test_simplefb_is_a_conflicting_owner(self):
        extra = 'framebuffer { compatible = "simple-framebuffer"; };'
        self.assertFalse(self.check_tree(extra)['offline_resource_gate'])

    def test_no_runtime_qualification_from_static_pass(self):
        report = self.check_tree()
        self.assertTrue(report['offline_resource_gate'])
        self.assertFalse(report['runtime_verified'])

    def test_corrupt_dtb_is_not_treated_as_missing_optional_property(self):
        with tempfile.TemporaryDirectory() as directory:
            dtb = Path(directory) / 'bad.dtb'
            dtb.write_bytes(b'not a dtb')
            with self.assertRaises(subprocess.CalledProcessError):
                preflight.DeviceTree(dtb)
