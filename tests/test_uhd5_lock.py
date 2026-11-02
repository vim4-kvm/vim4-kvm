"""Guard the source/artifact boundary without requiring hardware or binary blobs."""
import hashlib
import json
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestedRuntimeLockTest(unittest.TestCase):
    def test_complete_package_and_sources_remain_matched(self):
        recipe = ROOT / 'packaging/kernel-edge'
        lock = tomllib.loads((recipe / 'sources.toml').read_text())
        built = lock['tested_build']
        overlays = lock['retained_runtime'].get('module_overlays', {})
        if overlays:
            overlay_revisions = {overlay['revision'] for overlay in overlays.values()}
            self.assertIn(lock['kernel']['revision'], overlay_revisions)
        else:
            self.assertEqual(lock['kernel']['revision'], built['image_source_revision'])
        self.check_build(built, installed=True)

    def test_module_overlay_receipts_match_source_and_artifact_identity(self):
        recipe = ROOT / 'packaging/kernel-edge'
        lock = tomllib.loads((recipe / 'sources.toml').read_text())
        built = lock['tested_build']
        for name, overlay in lock['retained_runtime'].get('module_overlays', {}).items():
            with self.subTest(module=name):
                path = recipe / overlay['receipt_path']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                                 overlay['receipt_sha256'])
                receipt = json.loads(path.read_text())
                for field, built_field in [('image_source_revision', 'image_source_revision'),
                                           ('kernel_build_id', 'build_id'), ('release', 'release')]:
                    self.assertEqual(receipt[field], built[built_field])
                for field, overlay_field in [('module_source_revision', 'revision'),
                                             ('module_sha256', 'sha256'),
                                             ('module_build_id', 'build_id'), ('module_path', 'path')]:
                    self.assertEqual(receipt[field], overlay[overlay_field])

    def test_previous_gpu_build_keeps_its_complete_historical_lock(self):
        lock = tomllib.loads((ROOT / 'packaging/kernel-edge/sources.toml').read_text())
        self.check_build(lock['previous_tested_build'], installed=False)

    def test_qualification_matches_tested_and_installed_identity(self):
        recipe = ROOT / 'packaging/kernel-edge'
        lock = tomllib.loads((recipe / 'sources.toml').read_text())
        built, retained = lock['tested_build'], lock['retained_runtime']
        receipt = recipe / built['validation_path']
        self.assertEqual(hashlib.sha256(receipt.read_bytes()).hexdigest(), built['validation_sha256'])
        qualified = json.loads(receipt.read_text())
        for key, field in [('source', 'image_source_revision'), ('kernel_build_id', 'build_id'),
                           ('package_sha256', 'package_sha256')]:
            self.assertEqual(qualified[key], built[field])
        self.assertEqual(qualified['status'], 'qualified')
        self.assertEqual(len(qualified['regression']), 9)
        self.assertTrue(all(row['status'] == 'passed' for row in qualified['regression']))
        self.assertEqual(qualified['stability']['status'], 'passed')
        modes = json.loads((recipe / 'hdmi-modes.json').read_text())['modes']
        self.assertEqual({(row['mode'], row['codec']) for row in qualified['matrix']},
                         {(mode['id'], codec) for mode in modes for codec in ('h264', 'h265')})
        for key in ('release', 'build_id', 'image_sha256', 'manifest_sha256', 'package_sha256'):
            self.assertEqual(retained[key], built[key])
        self.assertEqual(retained['revision'], built['image_source_revision'])
        self.assertEqual(retained['default_boot'], '5.15')
        proof = recipe / retained['installed_proof_path']
        self.assertEqual(hashlib.sha256(proof.read_bytes()).hexdigest(), retained['live_proof_sha256'])
        installed = json.loads(proof.read_text())
        self.assertEqual(installed['release'], built['release'])
        self.assertEqual(installed['kernel_build_id'], built['build_id'])
        self.assertEqual(installed['manifest_sha256'], built['manifest_sha256'])
        self.assertEqual(installed['module_count'], built['module_count'])
        self.assertEqual(installed['kernels_sha256'], retained['kernels_manifest_sha256'])

    def check_build(self, built, *, installed):
        recipe = ROOT / 'packaging/kernel-edge'
        def checked(relative, digest):
            path = recipe / relative
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, relative)
            return path
        manifest = json.loads(checked(built['manifest_path'], built['manifest_sha256']).read_text())
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
        runtime_path = built.get('runtime_files_path', '../kbase/uhd5-runtime-files.json')
        runtime_files = json.loads(checked(runtime_path, built['runtime_files_sha256']).read_text())
        external_files = json.loads(checked(built.get('external_runtime_files_path', runtime_path),
                                            external['runtimeManifestSha256']).read_text())
        self.assertTrue(external_files)
        for name, digest in external_files.items():
            self.assertEqual(runtime_files[name], digest)
        for name, digest in runtime_files.items():
            self.assertEqual(manifest['files']['runtime/' + name], digest)
        for name, digest in built['external_modules'].items():
            self.assertEqual(manifest['modules']['extra/' + name + '.ko'], digest)
        for name, identity in built['module_build_ids'].items():
            matches = [value for path, value in manifest['module_build_ids'].items()
                       if Path(path).name.split('.ko')[0].replace('-', '_') == name]
            self.assertEqual(matches, [identity])
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
        self.assertEqual(runtime['installed'], installed)
        self.assertEqual(runtime['default_boot'], '5.15')
        self.assertEqual(runtime['profiles']['kbase']['sha256'], built['board_dtb_sha256'])
        self.assertEqual(runtime['profiles']['panfrost']['sha256'], built['panfrost_dtb_sha256'])
        self.assertNotEqual(runtime['profiles']['kbase']['gpu_driver'], runtime['profiles']['panfrost']['gpu_driver'])
        self.assertFalse(runtime['blob']['glvnd_vendor'])
        self.assertFalse(any('libMali' in name for name in manifest['files']))
