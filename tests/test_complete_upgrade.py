"""Exercise the installed uhd7 -> complete candidate -> uhd7 boundary offline."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_register_runtime import runtime, boot


class CompleteUpgradeTest(unittest.TestCase):
    def fixture(self, root, bad_hash=False):
        boot_root = root / 'boot'
        edge = boot_root / 'edge'
        edge.mkdir(parents=True)
        for name in runtime.BOOT_FILES:
            (edge / name).write_text('qualified ' + name)
        (edge / 'Image').write_text('Linux version ' + runtime.UHD7 + ' (builder)')
        config = boot_root / 'extlinux.conf'
        config.write_text('DEFAULT FullKvm\nLABEL FullKvm\n LINUX /edge/Image\n FDT /edge/vim4.dtb\n')
        manifest = root / 'kernels.json'
        manifest.write_text('original registry')
        usr = root / 'usr'
        old_modules = usr / 'lib/modules' / runtime.UHD7
        old_modules.mkdir(parents=True)
        for name in ('hdmirx.ko.xz', 'vdin.ko.xz', 'wave5.ko.xz', 'kbase.ko', 'modules.dep'):
            (old_modules / name).write_text('qualified overlay ' + name)
        (root / 'lib').symlink_to(usr / 'lib', target_is_directory=True)
        helper = usr / 'libexec/vim4-board-runtime'
        helper.parent.mkdir(parents=True)
        helper.write_text('old launcher')
        firmware = usr / 'lib/firmware/updates' / runtime.UHD7 / 'brcm/brcmfmac43752-sdio.khadas,vim4.bin'
        firmware.parent.mkdir(parents=True)
        firmware.write_text('qualified firmware')
        payload = root / 'payload'
        payload.mkdir()
        for name in runtime.BOOT_FILES:
            (payload / name).write_text('candidate ' + name)
        (payload / 'Image').write_text('Linux version ' + runtime.CANDIDATE + ' (builder)')
        files = {'kernel/wave5.ko': b'new matched module', 'modules.dep': b'kernel/wave5.ko:\n'}
        hashes = {name: runtime.hashlib.sha256(data).hexdigest() for name, data in files.items()}
        with tarfile.open(payload / 'modules.tar.gz', 'w:gz') as archive:
            for name, data in files.items():
                member = tarfile.TarInfo(runtime.CANDIDATE + '/' + name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        (payload / 'manifest.json').write_text(json.dumps(dict(release=runtime.CANDIDATE, modules=hashes)))
        (payload / 'runtime-proof.json').write_text('{}')
        new_helper = payload / 'runtime/usr/libexec/vim4-board-runtime'
        new_helper.parent.mkdir(parents=True)
        new_helper.write_text('candidate launcher')
        inventory = {str(p.relative_to(payload)): runtime.digest(p) for p in payload.rglob('*') if p.is_file()}
        if bad_hash:
            inventory['Image'] = '0'*64
        (payload / 'candidate.json').write_text(json.dumps(dict(sha256=inventory)))
        package = root / 'package.tar.gz'
        with tarfile.open(package, 'w:gz') as archive:
            archive.add(payload, arcname='.')
        board = SimpleNamespace(BOOT=boot_root, CONFIG=config, MANIFEST=manifest,
                                boot_entries=boot.boot_entries, default_label=boot.default_label)
        return board, package, old_modules, helper

    def run_install(self, root, board, package, **options):
        def board_path(*parts):
            value = str(Path(*parts))
            return root / value.lstrip('/') if value == '/lib' or value.startswith(('/lib/', '/usr')) else Path(value)
        digest = runtime.digest
        def firmware_digest(path):
            return '3ff292ab216c13ce3019f6b4cc4234a15a81c8b553014b122f748efd9465676d' if str(path).endswith('.bin') else digest(path)
        def register(args):
            board.MANIFEST.write_text('new registry')
        run = runtime.subprocess.run
        def extract(command, **kwargs):
            # BSD tar lacks the GNU option; this fixture archives only RELEASE,
            # so extraction still exercises the Ubuntu-style /lib symlink.
            if runtime.sys.platform == 'darwin':
                command = [part for part in command if part != '--keep-directory-symlink']
            return run(command, **kwargs)
        with patch.dict(runtime.sys.modules, {'vim4boot': board}), patch.object(
                runtime, 'Path', side_effect=board_path), patch.object(runtime, 'digest', side_effect=firmware_digest), patch.object(
                runtime.os, 'geteuid', return_value=0), patch.object(runtime.os, 'sync', create=True), patch.object(
                runtime, 'register', side_effect=register), patch.object(runtime.subprocess, 'run', side_effect=extract):
            runtime.install(SimpleNamespace(archive=package, backup=root/'backup', source_label='FullKvm'))

    def test_complete_install_and_explicit_rollback_preserve_original_default_and_overlays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board, package, modules, helper = self.fixture(root)
            default = board.CONFIG.read_bytes()
            previous = {p.name: p.read_bytes() for p in modules.iterdir()}
            self.run_install(root, board, package)
            self.assertEqual(board.CONFIG.read_bytes(), default)
            self.assertEqual({p.name: p.read_bytes() for p in modules.iterdir()}, previous)
            self.assertEqual(helper.read_text(), 'candidate launcher')
            self.assertEqual(board.MANIFEST.read_text(), 'new registry')
            with patch.object(runtime.os, 'sync', create=True):
                runtime.restore_rollback(root / 'backup')
            self.assertEqual(board.CONFIG.read_bytes(), default)
            self.assertEqual(board.MANIFEST.read_text(), 'original registry')
            self.assertEqual(helper.read_text(), 'old launcher')
            self.assertEqual({p.name: p.read_bytes() for p in modules.iterdir()}, previous)
            self.assertIn(runtime.UHD7, (board.BOOT/'edge/Image').read_text())

    def test_bad_package_hash_and_low_space_do_not_change_baseline(self):
        for bad_hash in (True, False):
            with self.subTest(bad_hash=bad_hash), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                board, package, modules, helper = self.fixture(root, bad_hash)
                before = (board.BOOT/'edge/Image').read_bytes()
                with patch.object(runtime.shutil, 'disk_usage', return_value=SimpleNamespace(free=0)):
                    with self.assertRaisesRegex(ValueError, 'hash mismatch|Insufficient /boot'):
                        self.run_install(root, board, package)
                self.assertFalse((root/'backup').exists())
                self.assertEqual((board.BOOT/'edge/Image').read_bytes(), before)
                self.assertEqual(helper.read_text(), 'old launcher')

    def test_preexisting_candidate_modules_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board, package, modules, helper = self.fixture(root)
            existing = modules.with_name(runtime.CANDIDATE)
            existing.mkdir()
            (existing/'other.ko').write_text('owned by previous task')
            with self.assertRaisesRegex(ValueError, 'existing module set'):
                self.run_install(root, board, package)
            self.assertEqual((existing/'other.ko').read_text(), 'owned by previous task')
            self.assertEqual(helper.read_text(), 'old launcher')
