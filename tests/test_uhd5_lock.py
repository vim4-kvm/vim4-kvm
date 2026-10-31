"""Guard the source/artifact boundary without requiring hardware or binary blobs."""
import hashlib
import json
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Uhd5LockTest(unittest.TestCase):
    def test_complete_package_and_sources_remain_matched(self):
        recipe = ROOT / 'packaging/kernel-edge'
        lock = tomllib.loads((recipe / 'sources.toml').read_text())
        built = lock['tested_build']
        def checked(relative, digest):
            path = recipe / relative
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, relative)
            return path
        manifest = json.loads(checked(built['manifest_path'], built['manifest_sha256']).read_text())
        self.assertEqual(manifest['source'], lock['kernel']['revision'])
        self.assertEqual(manifest['source'], built['image_source_revision'])
        self.assertEqual(manifest['release'], built['release'])
        self.assertEqual(manifest['kernel_build_id'], built['build_id'])
        checked(built['config_path'], built['config_sha256'])
        self.assertEqual(built['image_sha256'], manifest['files']['Image'])
        self.assertEqual(built['board_dtb_sha256'], manifest['files']['vim4.dtb'])
        self.assertEqual(built['panfrost_dtb_sha256'], manifest['files']['panfrost.dtb'])
        self.assertEqual(built['modules_sha256'], manifest['files']['modules.tar.gz'])
        self.assertEqual(built['module_symvers_sha256'], manifest['files']['Module.symvers'])
        self.assertEqual(built['vmlinux_btf_sha256'], manifest['files']['vmlinux.btf'])
        names = {n for n in manifest['modules'] if n.endswith(('.ko', '.ko.xz'))}
        self.assertEqual(names, set(manifest['module_build_ids']))
        self.assertEqual(len(names), built['module_count'])
        self.assertEqual(sum(n.startswith('kernel/') for n in names), built['base_module_count'])
        self.assertEqual(sum(n.startswith('extra/') for n in names), built['external_module_count'])
        external = json.loads(checked(built['external_manifest_path'], built['external_manifest_sha256']).read_text())
        self.assertEqual(external['kernel'], built['image_source_revision'])
        checked('../kbase/uhd5-runtime-files.json', built['runtime_files_sha256'])
        self.assertEqual(external['runtimeManifestSha256'], built['runtime_files_sha256'])
        package = ROOT / 'packaging/kbase'
        for name, digest in external['patches'].items():
            self.assertEqual(hashlib.sha256((package/name).read_bytes()).hexdigest(), digest, name)
        for folder, key in [('dvfs', 'governorSources'), ('heaps', 'heapSources')]:
            for name, digest in external[key].items():
                self.assertEqual(hashlib.sha256((package/folder/name).read_bytes()).hexdigest(), digest, name)
        runtime = json.loads((recipe/built['runtime_descriptor']).read_text())
        self.assertEqual(runtime['build_id'], built['build_id'])
        self.assertEqual(runtime['image_source_revision'], built['image_source_revision'])
        self.assertEqual(runtime['package_sha256'], built['package_sha256'])
        self.assertFalse(runtime['installed'])
        self.assertEqual(runtime['default_boot'], '5.15')
        self.assertEqual(runtime['profiles']['kbase']['sha256'], built['board_dtb_sha256'])
        self.assertEqual(runtime['profiles']['panfrost']['sha256'], built['panfrost_dtb_sha256'])
        self.assertNotEqual(runtime['profiles']['kbase']['gpu_driver'], runtime['profiles']['panfrost']['gpu_driver'])
        self.assertFalse(runtime['blob']['glvnd_vendor'])
        self.assertFalse(any(n.endswith('.so') or 'libMali' in n for n in manifest['files']))
        previous = lock['previous_tested_build']
        self.assertEqual(hashlib.sha256((recipe/previous['config_path']).read_bytes()).hexdigest(), previous['config_sha256'])
