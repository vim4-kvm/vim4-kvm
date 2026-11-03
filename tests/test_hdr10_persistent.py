import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('persistent',ROOT/'packaging/hdr10/persistent-r14e.py')
persistent=importlib.util.module_from_spec(spec);spec.loader.exec_module(persistent)


class PersistentTests(unittest.TestCase):
    def test_kbase_wrapper_main_pid_is_not_mistaken_for_application(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);group=root/'group';group.mkdir()
            (group/'cgroup.procs').write_text('900\n951\n1075\n')
            program=root/'candidate/one-kvm';program.parent.mkdir();program.touch()
            for pid,target in (('900','/usr/bin/python3'),('951',str(program)),('1075','/usr/bin/ttyd')):
                directory=root/'proc'/pid;directory.mkdir(parents=True)
                (directory/'exe').symlink_to(target)
            with patch.object(persistent,'PREFIX',str(program.parent)):
                self.assertEqual(persistent.one_kvm_pid(group,root/'proc'),951)

    def test_kernel_specific_launcher_preserves_vendor_and_routes_all_four_apps(self):
        original=(ROOT/'tests/fixtures/uhd6-installed-kvm-run').read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(),
                         '5f6a038eea357cd12cc8c8b544b755c34b471db67537123fa5b900b0ff9d22be')
        generated=persistent.launcher(original).decode()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);bin=root/'bin';bin.mkdir()
            (bin/'uname').write_text('#!/bin/sh\nprintf "%s\\n" "$TEST_RELEASE"\n')
            (bin/'readlink').write_text('#!/bin/sh\nexit 0\n')
            (bin/'taskset').write_text('#!/bin/sh\nexit 0\n')
            for file in bin.iterdir():file.chmod(0o755)
            text=generated.replace('/var/lib/',temp+'/state/').replace('/opt/',temp+'/opt/')
            old_pi='/usr/libexec/vim4-pikvm-run'
            text=text.replace(old_pi,temp+'/vendor-pikvm')
            wrapper=root/'run';wrapper.write_text(text)
            for release in ('5.15.137-vim4kvm-hdrdual6',persistent.RELEASE):
                for app,old,new in (
                    ('onekvm','vim4-onekvm/one-kvm','one-kvm'),
                    ('nanokvm','vim4-nanokvm/NanoKVM-Server','nanokvm'),
                    ('jetkvm','vim4-jetkvm/jetkvm','jetkvm'),
                    ('pikvm',None,'pikvm-run')):
                    with self.subTest(release=release,app=app):
                        native=root/'opt/vim4-kvm/hdr10-r14e'/new
                        vendor=root/'opt'/old if old else root/'vendor-pikvm'
                        for file,label in ((native,'native'),(vendor,'vendor')):
                            file.parent.mkdir(parents=True,exist_ok=True)
                            file.write_text('#!/bin/sh\nprintf \'%s\\n\' '+label+' "$GST_PLUGIN_PATH"\n')
                            file.chmod(0o755)
                        out=subprocess.check_output(['sh',str(wrapper),app],env=dict(os.environ,
                            PATH=str(bin)+':'+os.environ['PATH'],TEST_RELEASE=release),text=True).splitlines()
                        self.assertEqual(out[0],'native' if release==persistent.RELEASE else 'vendor')
                        if release==persistent.RELEASE:self.assertTrue(out[1].endswith('/hdr10-r14e/gstreamer-1.0'))

    def test_package_identity_and_duplicate_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'bundle.tar.gz'
            with tarfile.open(path,'w:gz') as archive:
                for _ in range(2):
                    member=tarfile.TarInfo('app');member.size=1
                    archive.addfile(member,io.BytesIO(b'x'))
            with self.assertRaisesRegex(ValueError,'hash differs'):
                persistent.read_archive(path,'0'*64)
            with self.assertRaisesRegex(ValueError,'duplicate'):
                persistent.read_archive(path,hashlib.sha256(path.read_bytes()).hexdigest())
