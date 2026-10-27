"""Package PiKVM and its private runtime without enabling board services."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from package import copy, write, package, manager

ROOT = Path('/work')


def pikvm(stage):
    deploy = ROOT / 'kvmd/deploy/vim4'
    shutil.copytree('/opt/vim4-pikvm/python', stage / 'opt/vim4-pikvm/python', symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__'))
    copy('/usr/sbin/nginx', stage, 'opt/vim4-pikvm/bin/nginx', 0o755)
    copy('/usr/share/doc/nginx/copyright', stage, 'usr/share/doc/vim4-pikvm/nginx-copyright')
    copy('/usr/bin/janus', stage, 'usr/bin/janus', 0o755)
    shutil.copytree('/usr/lib/janus', stage / 'usr/lib/janus', symlinks=True)
    shutil.copytree('/usr/share/janus/javascript', stage / 'usr/share/janus/javascript')
    copy(ROOT / 'janus/COPYING', stage, 'usr/share/doc/vim4-pikvm/janus-COPYING')
    copy(ROOT / 'ustreamer/src/ustreamer.bin', stage, 'usr/bin/ustreamer', 0o755)
    copy(ROOT / 'ustreamer/janus/libjanus_ustreamer.so', stage,
         'usr/lib/ustreamer/janus/libjanus_ustreamer.so', 0o755)
    for source in ('kvmd', 'ustreamer'):
        copy(ROOT / source / 'LICENSE', stage, f'usr/share/doc/vim4-pikvm/{source}-LICENSE')
    shutil.copytree(ROOT / 'kvmd/web', stage / 'usr/share/kvmd/web',
                    ignore=shutil.ignore_patterns('*.pug'))
    shutil.copytree(ROOT / 'kvmd/contrib/keymaps', stage / 'usr/share/kvmd/keymaps')
    (stage / 'usr/share/kvmd/extras').mkdir()
    copy(deploy / 'main.yaml', stage, 'usr/lib/kvmd/main.yaml')
    write(stage, 'usr/lib/kvmd/platform', 'PIKVM_MODEL=VIM4\nPIKVM_VIDEO=HDMI\nPIKVM_BOARD=Khadas VIM4\n')
    for source in (ROOT / 'kvmd/configs/nginx').glob('*.conf'):
        copy(source, stage, 'etc/kvmd/nginx/' + source.name)
    copy('/etc/nginx/mime.types', stage, 'etc/kvmd/nginx/mime.types')
    copy(deploy / 'nginx.conf', stage, 'etc/kvmd/nginx/vim4.conf')
    copy(ROOT / 'kvmd/configs/janus/janus.transport.websockets.jcfg', stage,
         'etc/kvmd/janus/janus.transport.websockets.jcfg')
    for name in ('janus.jcfg', 'janus.plugin.ustreamer.jcfg'):
        copy(deploy / name, stage, 'etc/kvmd/janus/' + name)
    for name in ('meta.yaml', 'web.css'):
        copy(ROOT / 'kvmd/configs/kvmd' / name, stage, 'etc/kvmd/' + name)
    for name in ('htpasswd', 'totp.secret'):
        copy(ROOT / 'kvmd/configs/kvmd' / name, stage, 'usr/share/vim4-pikvm/defaults/' + name, 0o600)
    copy(deploy / 'override.yaml', stage, 'usr/share/vim4-pikvm/defaults/override.yaml', 0o600)
    copy(ROOT / 'packaging/ubuntu/manager-config.py', stage, 'usr/share/vim4-pikvm/manager-config.py')
    copy(deploy / 'vim4-pikvm.service', stage, 'usr/lib/systemd/system/vim4-pikvm.service')
    for name in ('vim4-pikvm-media', 'vim4-pikvm-run'):
        copy(deploy / name, stage, 'usr/libexec/' + name, 0o755)
    copy(deploy / 'vim4-pikvm-media.sudoers', stage, 'etc/sudoers.d/vim4-pikvm-media', 0o440)
    write(stage, 'DEBIAN/postinst', '''#!/bin/sh
set -eu
if [ "$1" = configure ]; then
    getent passwd khadas >/dev/null
    install -d -o khadas -g khadas -m 0700 /var/lib/kvmd /var/lib/kvmd/msd /etc/kvmd/override.d
    for name in htpasswd override.yaml totp.secret; do
        if [ ! -e "/etc/kvmd/$name" ]; then
            install -o khadas -g khadas -m 0600 "/usr/share/vim4-pikvm/defaults/$name" "/etc/kvmd/$name"
        fi
    done
    /opt/vim4-pikvm/python/bin/python3.14 /usr/share/vim4-pikvm/manager-config.py pikvm /etc/kvmd/override.yaml
    visudo -cf /etc/sudoers.d/vim4-pikvm-media
    if [ -d /run/systemd/system ]; then systemctl daemon-reload; fi
fi
''', 0o755)


def main():
    version, output = sys.argv[1], Path(sys.argv[2])
    subprocess.run(['dpkg', '--validate-version', version], check=True)
    depends = ('libc6 (>= 2.38), libglib2.0-0t64, libgstreamer1.0-0, libgstreamer-plugins-base1.0-0, '
               'libjansson4, libconfig9, libwebsockets19t64, libnice10, libsrtp2-1, libssl3t64, '
               'libopus0, libasound2t64, libspeexdsp1, libatomic1, libevent-2.1-7t64, '
               'libevent-pthreads-2.1-7t64, libbsd0, libjpeg-turbo8, libbz2-1.0, liblzma5, '
               'libsqlite3-0, libreadline8t64, libffi8, libsystemd0, libxkbcommon0, libfreetype6, '
               'libpcre2-8-0, libcrypt1, zlib1g, python3, sudo, util-linux, ca-certificates, '
               'gstreamer1.0-plugins-base, gstreamer1.0-plugins-good, gstreamer1.0-plugins-bad, '
               'vim4-kvm-board (>= 2.5.1+vim4.20261014.24), vim4-media-api-1, vim4-runtime-api-1, vim4-wave5-api-1, vim4-vfmcap (>= 2.5.1+vim4.20261014.24), '
               'vim4-amlvenc (>= 2.5.1+vim4.20261014.24), vim4-vdin1-api-1, vim4-hevc-hdr-api-1, vim4-nanokvm')
    package('vim4-pikvm', version, output, pikvm, depends)
    if len(sys.argv) < 4 or sys.argv[3] == 'pikvm':
        package('vim4-manager', version, output, manager, 'libc6 (>= 2.38), python3, sudo, systemd, vim4-media-api-1, vim4-runtime-api-1, vim4-nanokvm')
    for name in ('ubuntu-packages.txt', 'pikvm-downloads.lock.json', 'bootstrap.lock'):
        shutil.copy('/opt/build-inputs/' + name, output)
    shutil.copy(ROOT / 'packaging/ubuntu/pikvm/requirements.lock', output)
    subprocess.run([sys.executable, str(ROOT / 'packaging/ubuntu/feeds.py'), str(output), version], check=True)
    entries = [f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}'
               for path in sorted(output.iterdir()) if path.is_file() and path.name != 'SHA256SUMS']
    (output / 'SHA256SUMS').write_text('\n'.join(entries) + '\n')


if __name__ == '__main__':
    main()
