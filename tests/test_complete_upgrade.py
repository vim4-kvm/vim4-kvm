"""Exercise complete installation and interrupted staging without board access."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import os
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_register_runtime import runtime, boot, CURRENT

CANDIDATE = "7.3.1-vim4-20261104"


class CompleteUpgradeTest(unittest.TestCase):
    def test_process_death_at_each_install_stage_retains_a_bootable_current_kernel(self):
        phases = ['firmware', 'modules', *runtime.BOOT_FILES, 'runtime', 'registry', 'boot-commit', 'boot-rename', 'committed']
        for phase in phases:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                board, package, old_modules, helper = self.fixture(root)
                other_entries = {label: fields for label, fields in boot.boot_entries(board.CONFIG.read_text()).items()
                                 if label != 'Mainline'}
                previous = {str(p.relative_to(board.BOOT/'kernels'/CURRENT)): p.read_bytes()
                            for p in (board.BOOT/'kernels'/CURRENT).rglob('*') if p.is_file()}
                module_state = {p.name: p.read_bytes() for p in old_modules.iterdir()}
                script = '''import sys
from pathlib import Path
from test_complete_upgrade import CompleteUpgradeTest
test=CompleteUpgradeTest()
root=Path(sys.argv[1])
test.run_install(root,test.board(root),root/'package.tar.gz',die=sys.argv[2])
'''
                result = subprocess.run([sys.executable, '-c', script, str(root), phase],
                                        env=dict(os.environ, PYTHONPATH=str(Path(__file__).parent)), timeout=30)
                self.assertEqual(result.returncode, 92 if phase == 'committed' else 91)
                fields = boot.boot_entries(board.CONFIG.read_text())['Mainline']
                self.assertEqual(other_entries, {label: values for label, values in boot.boot_entries(board.CONFIG.read_text()).items()
                                                if label != 'Mainline'})
                selected = board.BOOT / fields['LINUX'].lstrip('/')
                self.assertEqual(runtime.release(selected), CANDIDATE if phase == 'committed' else CURRENT)
                self.assertEqual(previous, {str(p.relative_to(board.BOOT/'kernels'/CURRENT)): p.read_bytes()
                                           for p in (board.BOOT/'kernels'/CURRENT).rglob('*') if p.is_file()})
                self.assertEqual(module_state, {p.name: p.read_bytes() for p in old_modules.iterdir()})
                # Every visible launcher remains whole, executable and accepts
                # the old kernel, including a death halfway through its copy.
                check = subprocess.run(['sh', str(helper), 'check-kernel', CURRENT], text=True, capture_output=True)
                self.assertEqual(check.returncode, 0, check.stderr)
                self.assertEqual(check.stdout.strip(), '1')
                self.assertTrue(helper.stat().st_mode & 0o111)

    def test_missing_inventory_entry_and_extra_runtime_file_are_rejected(self):
        for alteration in ('missing', 'extra'):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                board, package, modules, helper = self.fixture(root)
                payload = root/'payload'
                if alteration == 'missing':
                    path = payload/'candidate.json'
                    descriptor = json.loads(path.read_text())
                    descriptor['sha256'].pop('runtime/usr/libexec/vim4-board-runtime')
                    path.write_text(json.dumps(descriptor))
                else:
                    (payload/'runtime/usr/libexec/extra-helper').write_text('unchecked')
                with tarfile.open(package, 'w:gz') as archive:
                    archive.add(payload, arcname='.')
                with self.assertRaisesRegex(ValueError, 'file inventory'):
                    self.run_install(root, board, package)
                self.assertFalse((board.BOOT/'kernels'/CANDIDATE).exists())
                self.assertNotIn('# candidate copy', helper.read_text())

    def test_insufficient_root_space_is_rejected_before_persistent_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            board, package, modules, helper = self.fixture(root)
            def free(path):
                return SimpleNamespace(free=10**9 if Path(path) == board.BOOT else 0)
            with patch.object(runtime.shutil, 'disk_usage', side_effect=free):
                with self.assertRaisesRegex(ValueError, 'Insufficient root'):
                    self.run_install(root, board, package)
            self.assertFalse((board.BOOT/'kernels'/CANDIDATE).exists())
            self.assertFalse(modules.with_name(CANDIDATE).exists())
            self.assertNotIn('# candidate copy', helper.read_text())

    def test_root_and_boot_budgets_are_combined_when_they_share_a_filesystem(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            boot_root = root/'boot'
            boot_root.mkdir()
            firmware = root/'firmware'
            firmware.write_bytes(b'x')
            def board_path(value):
                return root if str(value) == '/' else Path(value)
            # Either allocation alone fits; the combined installation does not.
            with patch.object(runtime, 'Path', side_effect=board_path), patch.object(
                    runtime.shutil, 'disk_usage', return_value=SimpleNamespace(free=60000)):
                with self.assertRaisesRegex(ValueError, 'Insufficient root'):
                    runtime.preflight_root_space(boot_root, 1, [], firmware, 50000)

    def board(self, root):
        def validate(entry, text, *, hashes):
            if boot.boot_entries(text)[entry['label']] != entry['boot']:
                raise ValueError('registry boot mismatch')
            for name, value in entry['artifacts'].items():
                if runtime.digest(Path(name)) != value:
                    raise ValueError('installed artifact mismatch: ' + name)
        return SimpleNamespace(BOOT=root/'boot', CONFIG=root/'boot/extlinux.conf', MANIFEST=root/'kernels.json',
                               boot_entries=boot.boot_entries, default_label=boot.default_label,
                               atomic_write=boot.atomic_write, validate_entry=validate)

    def fixture(self, root, bad_hash=False):
        boot_root = root / 'boot'
        edge = boot_root / 'kernels' / CURRENT
        edge.mkdir(parents=True)
        for name in runtime.BOOT_FILES:
            (edge / name).write_text('qualified ' + name)
        (edge / 'Image').write_text('Linux version ' + CURRENT + ' (builder)')
        config = boot_root / 'extlinux.conf'
        config.write_text('DEFAULT Mainline\nLABEL Vendor\n LINUX /vendor/Image\n APPEND root=vendor\n'
                          'LABEL Stock\n LINUX /stock/Image\n APPEND root=stock\n'
                          f'LABEL Mainline\n LINUX /kernels/{CURRENT}/Image\n FDT /kernels/{CURRENT}/vim4.dtb\n APPEND root=mainline\n')
        manifest = root / 'kernels.json'
        manifest.write_text(json.dumps([dict(id='mainline', label='Mainline', release=CURRENT,
                                            boot=boot.boot_entries(config.read_text())['Mainline'], artifacts={})]))
        usr = root / 'usr'
        old_modules = usr / 'lib/modules' / CURRENT
        old_modules.mkdir(parents=True)
        for name in ('hdmirx.ko.xz', 'vdin.ko.xz', 'wave5.ko.xz', 'kbase.ko', 'modules.dep'):
            (old_modules / name).write_text('qualified module ' + name)
        (root / 'lib').symlink_to(usr / 'lib', target_is_directory=True)
        helper = usr / 'libexec/vim4-board-runtime'
        helper.parent.mkdir(parents=True)
        source = Path(runtime.__file__).parents[2] / 'board'
        helper.write_text((source / 'vim4-board-runtime').read_text().replace(
            '/usr/lib/vim4-kvm/python/vim4boot.py', str(usr / 'lib/vim4-kvm/python/vim4boot.py')))
        module = usr / 'lib/vim4-kvm/python/vim4boot.py'
        module.parent.mkdir(parents=True)
        module.write_bytes((source / 'vim4boot.py').read_bytes())
        helper.chmod(0o755)
        firmware = usr / 'lib/firmware/updates' / CURRENT / 'brcm/brcmfmac43752-sdio.khadas,vim4.bin'
        firmware.parent.mkdir(parents=True)
        firmware.write_text('qualified firmware')
        payload = root / 'payload'
        payload.mkdir()
        for name in runtime.BOOT_FILES:
            (payload / name).write_text('candidate ' + name)
        (payload / 'Image').write_text('Linux version ' + CANDIDATE + ' (builder)')
        files = {'kernel/wave5.ko': b'new matched module', 'modules.dep': b'kernel/wave5.ko:\n',
                 'modules.dep.bin': b'depmod binary metadata'}
        hashes = {name: runtime.hashlib.sha256(data).hexdigest() for name, data in files.items()}
        with tarfile.open(payload / 'modules.tar.gz', 'w:gz') as archive:
            for name, data in files.items():
                member = tarfile.TarInfo(CANDIDATE + '/' + name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        (payload / 'manifest.json').write_text(json.dumps(dict(release=CANDIDATE, modules=hashes)))
        (payload / 'runtime-proof.json').write_text('{}')
        new_helper = payload / 'runtime/usr/libexec/vim4-board-runtime'
        new_helper.parent.mkdir(parents=True)
        new_helper.write_text(helper.read_text() + '\n# candidate copy\n')
        new_helper.chmod(0o755)
        new_module = payload / 'runtime/usr/lib/vim4-kvm/python/vim4boot.py'
        new_module.parent.mkdir(parents=True)
        new_module.write_bytes(module.read_bytes())
        inventory = {str(p.relative_to(payload)): runtime.digest(p) for p in payload.rglob('*') if p.is_file()}
        if bad_hash:
            inventory['Image'] = '0'*64
        (payload / 'candidate.json').write_text(json.dumps(dict(sha256=inventory)))
        package = root / 'package.tar.gz'
        with tarfile.open(package, 'w:gz') as archive:
            archive.add(payload, arcname='.')
        return self.board(root), package, old_modules, helper

    def run_install(self, root, board, package, **options):
        def board_path(*parts):
            value = str(Path(*parts))
            return root / value.lstrip('/') if value in ('/', '/lib') or value.startswith(('/lib/', '/usr')) else Path(value)
        digest = runtime.digest
        def firmware_digest(path):
            return '3ff292ab216c13ce3019f6b4cc4234a15a81c8b553014b122f748efd9465676d' if path.name == 'brcmfmac43752-sdio.khadas,vim4.bin' else digest(path)
        copyfile = runtime.shutil.copyfile
        def copy(source, destination, **kwargs):
            phase = options.get('die')
            destination = Path(destination)
            die = (phase == 'firmware' and destination.suffix == '.bin' or
                   phase == 'runtime' and destination.parent == root/'usr/libexec' or
                   phase == destination.name and destination.parent == board.BOOT/'kernels'/CANDIDATE)
            if die:
                with destination.open('wb') as stream:
                    stream.write(Path(source).read_bytes()[:1])
                    stream.flush()
                    os.fsync(stream.fileno())
                os._exit(91)  # Deliberately bypass finally and atexit.
            return copyfile(source, destination, **kwargs)
        atomic_write = board.atomic_write
        replace = runtime.os.replace
        def rename(source, destination):
            if options.get('die') == 'boot-rename' and destination == board.CONFIG:
                os._exit(91)
            return replace(source, destination)
        def write(path, content):
            if options.get('die') == 'registry' and path == board.MANIFEST:
                os._exit(91)
            if options.get('die') == 'boot-commit' and path == board.CONFIG:
                os._exit(91)
            atomic_write(path, content)
            if options.get('die') == 'committed' and path == board.CONFIG:
                os._exit(92)
        run = runtime.subprocess.run
        def extract(command, **kwargs):
            # BSD tar lacks the GNU option; this fixture archives only RELEASE,
            # so extraction still exercises the Ubuntu-style /lib symlink.
            if runtime.sys.platform == 'darwin':
                command = [part for part in command if part != '--keep-directory-symlink']
            result = run(command, **kwargs)
            if options.get('die') == 'modules':
                os._exit(91)
            return result
        with patch.dict(runtime.sys.modules, {'vim4boot': board}), patch.object(
                runtime, 'Path', side_effect=board_path), patch.object(runtime, 'digest', side_effect=firmware_digest), patch.object(
                runtime.os, 'geteuid', return_value=0), patch.object(runtime.os, 'sync', create=True), patch.object(
                runtime.shutil, 'copyfile', side_effect=copy), patch.object(runtime.subprocess, 'run', side_effect=extract), patch.object(
                board, 'atomic_write', side_effect=write), patch.object(runtime.os, 'replace', side_effect=rename):
            runtime.install(SimpleNamespace(archive=package, source_label='Mainline'))

    def test_complete_install_switches_paths_and_preserves_old_modules_and_boot_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board, package, modules, helper = self.fixture(root)
            default = board.CONFIG.read_bytes()
            others = {label: fields for label, fields in boot.boot_entries(default.decode()).items() if label != 'Mainline'}
            previous = {p.name: p.read_bytes() for p in modules.iterdir()}
            self.run_install(root, board, package)
            self.assertEqual(boot.default_label(board.CONFIG.read_text()), 'Mainline')
            fields = boot.boot_entries(board.CONFIG.read_text())['Mainline']
            self.assertEqual(others, {label: values for label, values in boot.boot_entries(board.CONFIG.read_text()).items()
                                     if label != 'Mainline'})
            self.assertEqual(runtime.release(board.BOOT/fields['LINUX'].lstrip('/')), CANDIDATE)
            self.assertEqual({p.name: p.read_bytes() for p in modules.iterdir()}, previous)
            self.assertIn('# candidate copy', helper.read_text())
            self.assertEqual(json.loads(board.MANIFEST.read_text())[0]['release'], CANDIDATE)
            self.assertIn(CURRENT, (board.BOOT/'kernels'/CURRENT/'Image').read_text())

    def test_bad_package_hash_and_low_space_do_not_change_baseline(self):
        for bad_hash in (True, False):
            with self.subTest(bad_hash=bad_hash), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                board, package, modules, helper = self.fixture(root, bad_hash)
                before = (board.BOOT/'kernels'/CURRENT/'Image').read_bytes()
                with patch.object(runtime.shutil, 'disk_usage', return_value=SimpleNamespace(free=0)):
                    with self.assertRaisesRegex(ValueError, 'hash mismatch|Insufficient /boot'):
                        self.run_install(root, board, package)
                self.assertEqual((board.BOOT/'kernels'/CURRENT/'Image').read_bytes(), before)
                self.assertNotIn('# candidate copy', helper.read_text())

    def test_preexisting_candidate_modules_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board, package, modules, helper = self.fixture(root)
            existing = modules.with_name(CANDIDATE)
            existing.mkdir()
            (existing/'other.ko').write_text('owned by previous task')
            with self.assertRaisesRegex(ValueError, 'existing module set'):
                self.run_install(root, board, package)
            self.assertEqual((existing/'other.ko').read_text(), 'owned by previous task')
            self.assertNotIn('# candidate copy', helper.read_text())
