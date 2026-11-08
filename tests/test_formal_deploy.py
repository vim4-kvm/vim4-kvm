"""Offline contracts at the package, boot registration and published receipt boundaries."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('formal_deploy', ROOT/'packaging/kernel/formal-deploy.py')
formal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(formal)


class FormalDeployTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest = self.root/'manifest.json'
        self.manifest.write_text(json.dumps(dict(release='new',kernel_build_id='new-id',source='source')))
        self.baseline = self.root/'baseline.json'
        self.baseline.write_text(json.dumps(dict(release='old',build_id='old-id',files={'/protected':'a'*64})))
        self.package = self.root/'package.tar'
        with tarfile.open(self.package,'w') as archive:
            archive.add(self.manifest,arcname='manifest.json')
        self.rollback = self.root/'rollback.tar'
        self.rollback.write_bytes(b'rollback')
        self.new = dict(release='new',build_id='new-id',image_source_revision='source',
                        manifest_path='manifest.json',manifest_sha256=formal.sha(self.manifest),
                        package_sha256=formal.sha(self.package),image_sha256='image',
                        board_dtb_sha256='dtb',module_count=3)
        self.old = dict(release='old',build_id='old-id',package_sha256=formal.sha(self.rollback),
                        baseline_proof_path='baseline.json',baseline_proof_sha256=formal.sha(self.baseline))
        self.write_lock()
        self.args = formal.parser().parse_args(['plan','--sources',str(self.root/'sources.toml'),
            '--package',str(self.package),'--rollback',str(self.rollback),'--gates','audio',
            '--record','docs/record.md','--logs',str(self.root/'logs'),'--output',str(self.root/'output')])

    def write_lock(self):
        (self.root/'sources.toml').write_text(''.join(
            '['+section+']\n'+''.join(k+' = '+json.dumps(v)+'\n' for k,v in values.items())
            for section,values in (('tested_build',self.new),('retained_runtime',self.old))))

    def test_plan_seals_inputs_without_ssh(self):
        path = formal.prepare_plan(self.args)
        plan = json.loads(path.read_text())
        self.assertEqual(plan['gates'],['audio'])
        self.assertEqual(plan['files'][str(self.package.resolve())],formal.sha(self.package))
        self.package.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
            formal.configure(plan)

    def test_rejects_package_rollback_manifest_and_baseline_corruption(self):
        for path in (self.package,self.rollback,self.manifest,self.baseline):
            with self.subTest(path=path.name):
                original=path.read_bytes()
                path.write_bytes(b'corrupt')
                with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
                    formal.prepare_plan(self.args)
                path.write_bytes(original)

    def test_source_identity_and_same_release_are_rejected(self):
        self.new['build_id']='other'
        self.write_lock()
        with self.assertRaisesRegex(ValueError,'identity differs'):
            formal.prepare_plan(self.args)
        self.new['release']='old'
        self.write_lock()
        with self.assertRaisesRegex(ValueError,'same release'):
            formal.prepare_plan(self.args)

    def test_overlay_only_replaces_known_protected_paths(self):
        baseline=json.loads(self.baseline.read_text())
        updated=formal.baseline_overlay(baseline,{'/protected':'b'*64})
        self.assertEqual(updated['files']['/protected'],'b'*64)
        self.assertEqual(baseline['files']['/protected'],'a'*64)
        for overlay in ({'/unknown':'b'*64},{'/protected':'invalid'}):
            with self.assertRaises(ValueError):
                formal.baseline_overlay(baseline,overlay)

    def test_registration_preserves_append_other_entries_and_records(self):
        before='DEFAULT Mainline\nLABEL Mainline\n  LINUX /kernels/old/Image\n  FDT /kernels/old/vim4.dtb\n  APPEND root=old quiet\nLABEL Vendor\n  LINUX /vendor/Image\n  APPEND root=vendor\n'
        after=before.replace('/kernels/old/','/kernels/new/')
        records=[dict(label='Mainline',release='old'),dict(label='Vendor',release='vendor')]
        updated=copy.deepcopy(records);updated[0]['release']='new'
        formal.check_registration(before,after,records,updated,'new')
        for changed in (after.replace('root=old','root=new'),
                        after.replace('/vendor/Image','/vendor/Changed'),
                        after.replace('DEFAULT Mainline','DEFAULT Vendor')):
            with self.assertRaises(ValueError):
                formal.check_registration(before,changed,records,updated,'new')
        updated[1]['release']='changed'
        with self.assertRaisesRegex(ValueError,'kernels.json'):
            formal.check_registration(before,after,records,updated,'new')

    def test_publish_copies_receipts_and_updates_only_retained_section(self):
        plan=json.loads(formal.prepare_plan(self.args).read_text())
        logs=Path(plan['logs']);logs.mkdir()
        values={
            'result.json':dict(retained_default=True,release='new',gates=['audio'],package_sha256=self.new['package_sha256']),
            'new-baseline.json':dict(release='new',build_id='new-id',files={
                '/new':'c'*64,
                '/etc/vim4-kvm/runtime-build.json':hashlib.sha256(json.dumps(dict(running='new')).encode()).hexdigest()}),
            'runtime-build.json':dict(running='new'),
        }
        for name,value in values.items():
            (logs/name).write_text(json.dumps(value))
        proof=dict(release='new',build_id='new-id',source='source',manifest_sha256=self.new['manifest_sha256'],
                   baseline_proof_sha256=formal.sha(logs/'new-baseline.json'),kernels_sha256='registry')
        (logs/'installed-proof.json').write_text(json.dumps(proof))
        # SSH stdout must preserve the receipt bytes, including its final newline.
        runtime_path = logs/'runtime-build.json'
        original = runtime_path.read_bytes()
        runtime_path.write_bytes(original+b'\n')
        with self.assertRaisesRegex(ValueError,'Runtime receipt hash'):
            formal.publish(plan,logs,self.root)
        self.assertFalse((self.root/'releases/new').exists())
        runtime_path.write_bytes(original)
        formal.publish(plan,logs,self.root)
        lock=formal.tomllib.loads((self.root/'sources.toml').read_text())
        self.assertEqual(lock['tested_build'],self.new)
        self.assertEqual(lock['retained_runtime']['release'],'new')
        for source,target in (('installed-proof.json','installed-proof.json'),
                              ('new-baseline.json','baseline.json'),('runtime-build.json','runtime-build.json')):
            self.assertEqual((logs/source).read_bytes(),(self.root/'releases/new'/target).read_bytes())
        self.assertEqual(lock['retained_runtime']['baseline_proof_sha256'],formal.sha(logs/'new-baseline.json'))
        proof['baseline_proof_sha256']='bad'
        (logs/'installed-proof.json').write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            formal.publish(plan,logs,self.root)

    def test_gate_order_and_invalid_selections(self):
        self.assertEqual(formal.gates_list('pd,audio,cleanup'),['pd','audio','cleanup'])
        for names in ('','audio,audio','unknown','audio,'):
            with self.assertRaises(argparse.ArgumentTypeError):
                formal.gates_list(names)

    def test_retained_capture_lock_uses_old_complete_inventory(self):
        from unittest.mock import patch
        proof=dict(release='old',build_id='old-id',
                   files={'/boot/kernels/old/'+name:'a'*64 for name in
                          ('Image','vim4.dtb','panfrost.dtb','config','Module.symvers','vmlinux.btf','manifest.json')},
                   loaded_modules={'wave5':'old-wave5-id'})
        proof['files']['/lib/modules/old/kernel/wave5.ko']='b'*64
        self.baseline.write_text(json.dumps(proof))
        with patch.multiple(formal,BASELINE=self.baseline,LOG=self.root,OLD='old',OVERLAY={},create=True):
            previous=formal.bw.once.SOURCES
            self.addCleanup(setattr,formal.bw.once,'SOURCES',previous)
            formal.configure_baseline_identity()
            lock=formal.tomllib.loads(formal.bw.once.SOURCES.read_text())
            manifest=json.loads((self.root/lock['tested_build']['manifest_path']).read_text())
        self.assertEqual(lock['retained_runtime']['build_id'],'old-id')
        self.assertEqual(lock['tested_build']['module_build_ids']['wave5'],'old-wave5-id')
        self.assertEqual(manifest['modules'],{'kernel/wave5.ko':'b'*64})

    def test_dedicated_media_is_reproducible_and_readable(self):
        first,second=self.root/'a.img',self.root/'b.img'
        formal.prepare_media(first);formal.prepare_media(second)
        self.assertEqual(formal.sha(first),formal.sha(second))
        # The existing host checks require a FAT volume with this label and marker.
        import shutil
        import subprocess
        if shutil.which('mtype'):
            result=subprocess.check_output(['mtype','-i',str(first),'::marker.txt'])
            self.assertEqual(result,b'VIM4 edge USB transfer validation\n')


if __name__ == '__main__':
    unittest.main()
