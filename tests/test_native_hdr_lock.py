"""Keep the accepted native candidate separate from the uhd5 binary locks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tomllib
import unittest
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class NativeHdrLockTest(unittest.TestCase):
    def test_runtime_sources_and_complete_modules_match(self):
        recipe = ROOT / 'packaging/kernel'
        sources = tomllib.loads((recipe / 'sources.toml').read_text())
        lock = sources['native_hdr']
        path = recipe / lock['runtime_descriptor']
        runtime = json.loads(path.read_text())

        def checked(name, digest):
            content = (path.parent / name).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), digest, name)
            return json.loads(content)

        manifest = checked(runtime['kernel_manifest'], runtime['kernel_manifest_sha256'])
        self.assertEqual(manifest['source'], runtime['sources']['kernel'])
        self.assertEqual(manifest['release'], runtime['release'])
        self.assertEqual(manifest['kernel_build_id'], runtime['build_id'])
        modules = {name for name in manifest['modules']
                   if name.endswith(('.ko', '.ko.xz', '.ko.zst', '.ko.gz'))}
        self.assertEqual(len(modules), runtime['module_count'])
        self.assertEqual(manifest['module_count'], runtime['module_count'])
        for component in ('kernel', 'capture', 'onekvm'):
            self.assertEqual(runtime['sources'][component], lock[component + '_revision'])
        self.assertEqual(runtime['gstreamer_v4l2_sha256'], sources['gstreamer']['native_hdr_plugin_sha256'])
        self.assertNotEqual(runtime['gstreamer_v4l2_sha256'], sources['gstreamer']['candidate_plugin_sha256'])
        # uhd5 retains its own Image, DTs and BTF-matched module inventory.
        self.assertNotEqual(runtime['build_id'], sources['tested_build']['build_id'])
        self.assertFalse(runtime['installed'])
        self.assertFalse(runtime['native_hdr_default'])
        self.assertEqual(runtime['default_boot'], '5.15')

        smoke = checked(runtime['smoke_summary'], runtime['smoke_summary_sha256'])
        self.assertEqual(smoke['sdp_profile'], smoke['sps_vui']['general_profile_idc'])
        self.assertEqual(smoke['cma']['before'], smoke['cma']['after'])
        self.assertEqual(smoke['cma']['taint'], 0)
        self.assertEqual(smoke['cma']['faults'], [])
        self.assertTrue(smoke['sei_matches_hdmi'])

    def test_packager_rejects_substituted_v4l2_plugin(self):
        path = ROOT / 'packaging/kernel/package-hdr10.py'
        spec = importlib.util.spec_from_file_location('package_hdr10', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / 'plugin.so'
            plugin.write_bytes(b'candidate')
            lock = {'candidate_plugin_sha256': hashlib.sha256(b'candidate').hexdigest(),
                    'native_hdr_plugin_sha256': hashlib.sha256(b'historical').hexdigest()}
            with mock.patch.object(module.tomllib, 'loads', return_value={'gstreamer': lock}):
                module.verify_v4l2_plugin(module.sha(plugin), 'yuv444')
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    module.verify_v4l2_plugin(module.sha(plugin), 'native-hdr')
                plugin.write_bytes(b'historical')
                module.verify_v4l2_plugin(module.sha(plugin), 'native-hdr')
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    module.verify_v4l2_plugin(module.sha(plugin), 'yuv444')
