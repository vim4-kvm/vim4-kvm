"""Shared USB media validation and cross-application locking (root helpers only)."""
from contextlib import ExitStack, contextmanager
import fcntl
import os
from pathlib import Path
import re
import stat

LUN_FILE = Path('/sys/kernel/config/usb_gadget/kvm/functions/mass_storage.disk0/lun.0/file')
GADGET_ROOT = Path('/sys/kernel/config/usb_gadget')
IMAGE_ROOTS: dict[str, Path] = {
    'shared': Path('/var/lib/vim4-kvm/images'),
    'jetkvm': Path('/var/lib/jetkvm/images'),
    'onekvm': Path('/var/lib/one-kvm/msd'),
    'pikvm': Path('/var/lib/kvmd/msd'),
}
DATA_DIR = Path('/var/lib/vim4-kvm/usb')
LOCKS = ('/run/lock/vim4-media.lock', '/run/lock/vim4-jetkvm-media.lock')
SNAPSHOT_DIR = Path('/var/lib/vim4-kvm/usb-snapshots')
DISK_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}\.img')


def valid_disk_name(name):
    return isinstance(name, str) and DISK_NAME.fullmatch(name) is not None


@contextmanager
def media_locks(wait=False):
    # Application helpers wait like their previous private locks; web requests fail fast.
    with ExitStack() as stack:
        for path in LOCKS:
            fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            stack.callback(os.close, fd)
            if os.fstat(fd).st_uid != 0:
                raise ValueError('Invalid media lock owner')
            fcntl.flock(fd, fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


@contextmanager
def _directory(source, parts=()):
    root = DATA_DIR if source == 'data' else IMAGE_ROOTS[source]
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _open(identifier, readonly, create=False, allow_empty=False):
    parts = identifier.split('/')
    if (len(parts) < 2 or len(parts) > 10 or
            parts[0] not in (*IMAGE_ROOTS, 'data') or
            any(p in ('', '.', '..') or '\0' in p for p in parts) or
            Path(parts[-1]).suffix.lower() not in ('.iso', '.img') or
            (parts[0] == 'data' and (len(parts) != 2 or not valid_disk_name(parts[1])))):
        raise ValueError('请选择镜像列表中的文件')
    flags = (os.O_RDONLY if readonly else os.O_RDWR) | os.O_NOFOLLOW | os.O_NONBLOCK
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    with _directory(parts[0], parts[1:-1]) as directory:
        fd = os.open(parts[-1], flags, 0o600, dir_fd=directory)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                (not create and not allow_empty and info.st_size < 512)):
            raise ValueError('镜像必须是至少 512 字节、无硬链接的普通文件')
        return fd
    except BaseException:
        os.close(fd)
        if create:
            with _directory(parts[0], parts[1:-1]) as directory:
                os.unlink(parts[-1], dir_fd=directory)
        raise


def open_image(identifier, readonly):
    fd = _open(identifier, readonly)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            if identifier.startswith('data/'):
                raise ValueError('数据盘正在管理面板中编辑，请稍后再挂载') from None
            raise ValueError('镜像正在文件传输中，请稍后再挂载') from None
        if identifier.startswith('data/'):
            # A reader may have opened the old inode just before atomic replacement.
            with _directory('data') as directory:
                current = os.stat(identifier.split('/')[1], dir_fd=directory, follow_symlinks=False)
            info = os.fstat(fd)
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError('数据盘已改变，请重试')
        return fd
    except BaseException:
        os.close(fd)
        raise


def check_image_transfer(identifier):
    """Called after the application holds an exclusive flock, before any writes.

    Mount helpers take shared file locks under these same global locks. Checking
    every live LUN here closes the race with a mount that completed just before
    the writer acquired its file lock; configfs does not retain advisory locks.
    """
    if not identifier.startswith('onekvm/images/'):
        raise ValueError('Only One-KVM image files may be transferred')
    with media_locks(wait=True):
        fd = _open(identifier, True, allow_empty=True)
        try:
            image = os.fstat(fd)
            for lun in GADGET_ROOT.glob('*/functions/mass_storage*/lun.*/file'):
                path = lun.read_text().strip()
                if not path:
                    continue
                mounted = os.stat(path)
                if (mounted.st_dev, mounted.st_ino) == (image.st_dev, image.st_ino):
                    raise ValueError('镜像已挂载，请先在被控机安全弹出，再在管理面板卸载')
        finally:
            os.close(fd)


def catalog(sources=None):
    images = []
    remaining = 10000

    def scan(source, directory, parents=()):
        nonlocal remaining
        with os.scandir(directory) as entries:
            for entry in entries:
                remaining -= 1
                if remaining < 0:
                    raise ValueError('镜像目录条目过多，请先整理目录')
                parts = (*parents, entry.name)
                if source == 'data' and (parents or not valid_disk_name(entry.name)):
                    continue
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode) and len(parts) < 8:
                    child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=directory)
                    try:
                        scan(source, child, parts)
                    finally:
                        os.close(child)
                elif (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size >= 512
                      and Path(entry.name).suffix.lower() in ('.iso', '.img')):
                    item = dict(id='/'.join((source, *parts)), name='/'.join(parts),
                                source=source, size=info.st_size,
                                cdrom=Path(entry.name).suffix.lower() == '.iso')
                    if source == 'data':
                        item['disk'] = True
                    images.append(item)

    for source in (*IMAGE_ROOTS, 'data'):
        if sources is not None and source not in sources:
            continue
        try:
            with _directory(source) as directory:
                scan(source, directory)
        except FileNotFoundError:
            continue
    return sorted(images, key=lambda item: item['id'])


def attached():
    try:
        path = LUN_FILE.read_text().strip()
    except FileNotFoundError:
        # No LUN cannot hold media. All other read errors are unknown, not empty.
        # A dangling symlink is not an absent configfs attribute.
        if LUN_FILE.is_symlink():
            raise
        return None
    # A nonempty but unresolvable backing path may still be open in the kernel.
    return os.stat(path) if path else None


@contextmanager
def disk_name_lock(name, exclusive):
    if not valid_disk_name(name):
        raise ValueError('数据盘名称无效')
    with _directory('data') as directory:
        fd = os.open('.' + name + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600,
                     dir_fd=directory)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_nlink != 1:
            raise ValueError('Invalid disk lock')
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('数据盘正在使用') from None
        yield
    finally:
        os.close(fd)


def is_attached(fd):
    current = attached()
    info = os.fstat(fd)
    return current is not None and (current.st_dev, current.st_ino) == (info.st_dev, info.st_ino)


@contextmanager
def edit_disk(name, create=False):
    with ExitStack() as stack:
        stack.enter_context(disk_name_lock(name, True))
        with media_locks():
            # Check unknown attachment state before creating a visible empty file.
            attached()
            fd = _open('data/' + name, False, create)
            stack.callback(os.close, fd)
            try:
                if is_attached(fd):
                    raise ValueError('数据盘已挂载到被控电脑，请先安全弹出')
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                if create:
                    (DATA_DIR / name).unlink()
                raise ValueError('数据盘正在使用') from None
            except BaseException:
                if create:
                    (DATA_DIR / name).unlink()
                raise
        yield fd


@contextmanager
def read_disk(name):
    with disk_name_lock(name, False):
        fd = open_image('data/' + name, True)
        try:
            yield fd, is_attached(fd)
        finally:
            os.close(fd)
