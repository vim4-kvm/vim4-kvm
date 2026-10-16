import fcntl
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from board import vim4media as media


class MediaTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.data = self.root / 'data'
        self.data.mkdir()
        self.images = self.root / 'images'
        self.images.mkdir()
        self.lun = self.root / 'lun'
        self.lun.write_text('')
        self.enterContext(patch.object(media, 'DATA_DIR', self.data))
        self.enterContext(patch.object(media, 'IMAGE_ROOTS', {'shared': self.images}))
        self.enterContext(patch.object(media, 'LUN_FILE', self.lun))
        self.enterContext(patch.object(media, 'LOCKS', [self.root / 'lock1', self.root / 'lock2']))
        # Production locks must be root-owned; temporary fixtures belong to the test user.
        real_stat = os.fstat

        def lock_stat(fd):
            info = real_stat(fd)
            if info.st_size == 0:
                fields = list(info)
                fields[4] = 0
                return os.stat_result(fields)
            return info

        self.enterContext(patch.object(media.os, 'fstat', side_effect=lock_stat))
        (self.data / 'disk.img').write_bytes(bytes(512))
        (self.data / 'second.img').write_bytes(bytes(512))

    def test_catalog_filters_invalid_files_and_nested_data(self):
        (self.data / 'enabled').write_text('1')
        (self.data / 'nested').mkdir()
        (self.data / 'nested/hidden.img').write_bytes(bytes(512))
        (self.images / 'rescue.iso').write_bytes(bytes(512))
        (self.images / 'link.img').symlink_to(self.data / 'disk.img')
        self.assertEqual([x['id'] for x in media.catalog()],
                         ['data/disk.img', 'data/second.img', 'shared/rescue.iso'])
        self.assertTrue(all(x['disk'] for x in media.catalog(['data'])))

    def test_open_rejects_traversal_links_and_special_files(self):
        (self.images / 'dir').symlink_to(self.data)
        (self.images / 'link.img').symlink_to(self.data / 'disk.img')
        os.link(self.data / 'disk.img', self.images / 'hard.img')
        os.mkfifo(self.images / 'pipe.img')
        (self.images / 'small.img').write_bytes(b'x')
        for identifier in ('data/../second.img', 'data/nested/a.img', 'data/.img',
                           'shared/dir/second.img', 'shared/link.img', 'shared/hard.img',
                           'shared/pipe.img', 'shared/small.img', 'shared//a.img'):
            with self.subTest(identifier=identifier), self.assertRaises((ValueError, OSError)):
                media.open_image(identifier, True)

    def test_edit_blocks_same_disk_but_releases_global_locks(self):
        with media.edit_disk('disk.img'):
            with media.media_locks():
                with self.assertRaisesRegex(ValueError, '管理面板中编辑'):
                    media.open_image('data/disk.img', True)
                fd = media.open_image('data/second.img', False)
                os.close(fd)
            with self.assertRaisesRegex(ValueError, '正在使用'):
                with media.edit_disk('disk.img'):
                    pass
        with media.read_disk('disk.img') as (_, stale):
            self.assertFalse(stale)
            with self.assertRaisesRegex(ValueError, '正在使用'):
                with media.edit_disk('disk.img'):
                    pass

    def test_attached_disk_allows_stale_reads_but_refuses_edits(self):
        self.lun.write_text(str(self.data / 'disk.img'))
        with media.read_disk('disk.img') as (fd, stale):
            self.assertTrue(stale)
            self.assertTrue(media.is_attached(fd))
        with self.assertRaisesRegex(ValueError, '安全弹出'):
            with media.edit_disk('disk.img'):
                pass
        self.lun.unlink()
        self.assertIsNone(media.attached())

    def test_create_is_exclusive_and_global_lock_contention_is_released(self):
        with self.assertRaises(FileExistsError):
            with media.edit_disk('disk.img', create=True):
                pass
        with media.edit_disk('new.img', create=True) as fd:
            os.write(fd, bytes(512))
        self.assertEqual((self.data / 'new.img').stat().st_mode & 0o777, 0o600)
        with media.media_locks():
            with self.assertRaises(BlockingIOError):
                with media.media_locks():
                    pass
        with media.media_locks():
            pass

    def test_unknown_lun_refuses_edit_and_create_without_orphan(self):
        for error in (PermissionError('denied'), OSError('I/O error')):
            with patch.object(Path, 'read_text', side_effect=error):
                with self.assertRaises(OSError), media.edit_disk('disk.img'):
                    pass
                with self.assertRaises(OSError), media.edit_disk('new.img', create=True):
                    pass
            self.assertFalse((self.data / 'new.img').exists())
        self.lun.write_text(str(self.root / 'unresolved.img'))
        with self.assertRaises(FileNotFoundError), media.edit_disk('disk.img'):
            pass
        self.lun.write_text('')
        with patch.object(media, 'is_attached', side_effect=OSError('failed after create')):
            with self.assertRaises(OSError), media.edit_disk('new.img', create=True):
                pass
        self.assertFalse((self.data / 'new.img').exists())

    def test_name_lock_survives_inode_replacement(self):
        with media.edit_disk('disk.img'):
            replacement = self.data / 'replacement'
            replacement.write_bytes(bytes(1024))
            replacement.replace(self.data / 'disk.img')
            with self.assertRaisesRegex(ValueError, '正在使用'), media.edit_disk('disk.img'):
                pass
            with self.assertRaisesRegex(ValueError, '正在使用'), media.read_disk('disk.img'):
                pass
        with media.read_disk('disk.img') as (fd, _):
            self.assertEqual(os.fstat(fd).st_size, 1024)

    def test_reader_opening_old_inode_cannot_attach_after_replacement(self):
        open_original = media._open

        def replace_after_open(identifier, readonly):
            fd = open_original(identifier, readonly)
            replacement = self.data / 'replacement'
            replacement.write_bytes(bytes(1024))
            replacement.replace(self.data / 'disk.img')
            return fd

        with patch.object(media, '_open', side_effect=replace_after_open):
            with self.assertRaisesRegex(ValueError, '已改变'):
                media.open_image('data/disk.img', True)

    def test_application_helpers_wait_for_brief_global_lock(self):
        import threading
        acquired = threading.Event()

        def helper():
            with media.media_locks(wait=True):
                acquired.set()

        with media.media_locks():
            waiter = threading.Thread(target=helper)
            waiter.start()
            waiter.join(0.2)
            self.assertFalse(acquired.is_set(), 'wait=True must block while another helper holds the locks')
        waiter.join(5)
        self.assertTrue(acquired.is_set())


class PackagingTest(unittest.TestCase):
    def test_board_package_installs_importable_module_and_runtime_tools(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('ubuntu_package', root / 'packaging/ubuntu/package.py')
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        stage = Path(self.enterContext(tempfile.TemporaryDirectory()))
        real_copy = package.copy

        def copy(source, destination, path, mode=0o644):
            if source == root / 'build/usb-pd-init':
                package.write(destination, path, 'fixture', mode)
                return destination / path
            return real_copy(source, destination, path, mode)

        with patch.object(package, 'ROOT', root), patch.object(package, 'copy', side_effect=copy):
            package.board(stage)
        module = stage / 'usr/lib/vim4-kvm/python/vim4media.py'
        installed = importlib.util.spec_from_file_location('installed_vim4media', module)
        imported = importlib.util.module_from_spec(installed)
        installed.loader.exec_module(imported)
        self.assertTrue(imported.valid_disk_name('disk.img'))
        self.assertEqual(module.stat().st_mode & 0o777, 0o644)
        depends = next(entry[2] for entry in package.PACKAGES['platform'] if entry[0] == 'vim4-kvm-board')
        self.assertIn('mtools', depends.split(', '))
        self.assertIn('dosfstools', depends.split(', '))
