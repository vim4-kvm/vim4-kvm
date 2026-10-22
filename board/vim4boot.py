"""Select installed VIM4 kernels without changing their boot arguments or data."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import tempfile

BOOT = Path('/boot')
CONFIG = BOOT / 'extlinux/extlinux.conf'
MANIFEST = Path('/etc/vim4-kvm/kernels.json')


def installed():
    info = MANIFEST.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('内核清单必须由 root 管理且不可被其他用户写入')
    entries = json.loads(MANIFEST.read_text())
    if not isinstance(entries, list) or len(entries) != 2:
        raise ValueError('需要已安装的 5.15 和 7.x 内核清单')
    if {entry['id'] for entry in entries} != {'vendor', 'mainline'}:
        raise ValueError('内核清单标识无效')
    for entry in entries:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', entry['label']):
            raise ValueError('启动标签无效')
        if not entry.get('artifacts'):
            raise ValueError('内核文件校验清单为空')
    return entries


def boot_entries(text):
    entries = {}
    current = None
    for line in text.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) != 2:
            continue
        key, value = fields[0].upper(), fields[1]
        if key == 'LABEL':
            if value in entries:
                raise ValueError('启动标签重复')
            current = entries[value] = {}
        elif current is not None and key in ('LINUX', 'FDT', 'FDTDIR', 'INITRD', 'APPEND'):
            if key in current:
                raise ValueError('启动配置字段重复')
            current[key] = value
    return entries


def default_label(text):
    values = re.findall(r'^\s*default\s+(\S+)\s*$', text, flags=re.I | re.M)
    if len(values) != 1:
        raise ValueError('启动配置需要唯一的默认项')
    return values[0]


def validate_entry(entry, text, *, hashes):
    configured = boot_entries(text).get(entry['label'])
    if configured is None:
        raise ValueError('已安装内核缺少启动项')
    # Match every boot field against the deployment record, including masks.
    # A stale manifest cannot enable an experimental or mismatched entry.
    if configured != entry['boot']:
        raise ValueError('启动参数已改变，请先重新验证内核部署')
    for filename, expected in entry['artifacts'].items():
        path = Path(filename)
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('内核文件路径无效')
        if not (path.is_relative_to(BOOT) or path.is_relative_to('/lib/modules')):
            raise ValueError('内核文件不在启动或模块目录')
        if not re.fullmatch(r'[a-f0-9]{64}', expected) or not path.is_file():
            raise ValueError('内核文件缺失或校验值无效')
        if hashes:
            with path.open('rb') as source:
                digest = hashlib.file_digest(source, 'sha256').hexdigest()
            if digest != expected:
                raise ValueError(f'内核文件校验失败：{path.name}')


def status():
    if not MANIFEST.exists():
        return {'running': platform.release(), 'kernels': []}
    text = CONFIG.read_text()
    selected = default_label(text)
    kernels = []
    for entry in installed():
        error = ''
        try:
            validate_entry(entry, text, hashes=False)
        except (ValueError, OSError) as failure:
            error = str(failure)
        kernels.append({'id': entry['id'], 'name': entry['name'],
                        'release': entry['release'], 'selected': entry['label'] == selected,
                        'available': not error, 'error': error})
    return {'running': platform.release(), 'kernels': kernels}


def atomic_write(path, content):
    descriptor, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(name).unlink(missing_ok=True)


def select(identifier):
    entries = installed()
    target = next((entry for entry in entries if entry['id'] == identifier), None)
    if target is None:
        raise ValueError('未知内核')
    text = CONFIG.read_text()
    previous = default_label(text)
    validate_entry(target, text, hashes=True)
    if previous == target['label']:
        return
    updated = re.sub(r'^(\s*default\s+)\S+(\s*)$',
                     lambda match: match[1] + target['label'] + match[2],
                     text, flags=re.I | re.M)
    if default_label(updated) != target['label']:
        raise ValueError('无法修改默认启动项')
    atomic_write(CONFIG.with_name('extlinux.conf.before-kernel-switch'), text.encode())
    atomic_write(CONFIG, updated.encode())
