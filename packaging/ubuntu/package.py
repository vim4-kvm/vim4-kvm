#!/usr/bin/env python3
"""Assemble Ubuntu component packages without running installation scripts."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path('/work')


def copy(source, stage, destination, mode=0o644):
    target = stage / destination.lstrip('/')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(mode)
    return target


def write(stage, destination, content, mode=0o644):
    target = stage / destination.lstrip('/')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    target.chmod(mode)


def package(name, version, output, populate, depends):
    with tempfile.TemporaryDirectory(prefix=name) as directory:
        stage = Path(directory)
        populate(stage)
        if name == 'vim4-nanokvm':
            write(stage, 'opt/vim4-nanokvm/version', version + '\n')
        # Every installation entry point (including dpkg and the web updater)
        # must flush payloads before reporting success or restarting services.
        postinst = stage / 'DEBIAN/postinst'
        if not postinst.exists():
            write(stage, 'DEBIAN/postinst', '#!/bin/sh\nset -eu\n', 0o755)
        with postinst.open('a') as script:
            script.write('sync\n')
        write(stage, 'DEBIAN/control', f'Package: {name}\nVersion: {version}\nArchitecture: arm64\n'
              'Maintainer: VIM4 KVM <318096335+localhost-copilot@users.noreply.github.com>\n'
              f'Section: misc\nPriority: optional\nDepends: {depends}\n'
              f'Description: VIM4 Ubuntu {name} component\n')
        configs = sorted('/' + str(p.relative_to(stage)) for p in (stage / 'etc').rglob('*') if p.is_file())
        if configs:
            write(stage, 'DEBIAN/conffiles', '\n'.join(configs) + '\n')
        copy('/out/sources.json', stage, f'usr/share/doc/{name}/sources.json')
        # dpkg-deb clamps archive timestamps to SOURCE_DATE_EPOCH.
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage),
                        str(output / f'{name}_{version}_arm64.deb')], check=True)


def board(stage):
    copy(ROOT / 'tools/rootfs-policy.py', stage, 'usr/sbin/vim4-rootfs-policy', 0o755)
    copy(ROOT / 'build/usb-pd-init', stage, 'usr/sbin/usb-pd-init', 0o755)
    for name in ('hdmi-setup.sh', 'kvm-gadget.sh'):
        copy(ROOT / 'tools' / name, stage, 'usr/sbin/' + name, 0o755)
    for file in (ROOT / 'board').glob('*.service'):
        write(stage, 'usr/lib/systemd/system/' + file.name,
              file.read_text().replace('/usr/local/sbin/', '/usr/sbin/'))
    copy(ROOT / 'board/99-vfm-cap.rules', stage, 'usr/lib/udev/rules.d/99-vfm-cap.rules')
    copy(ROOT / 'board/90-vim4-encoder.conf', stage, 'etc/modprobe.d/90-vim4-encoder.conf')


def capture(stage):
    copy(ROOT / 'gst-plugin-vfmcap/build/libgstvfmcap.so', stage,
         'usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgstvfmcap.so', 0o644)
    copy(ROOT / 'gst-plugin-vfmcap/README.md', stage, 'usr/share/doc/vim4-vfmcap/README.md')
    copy(ROOT / 'gst-plugin-vfmcap/src/gstvfmcapsrc.c', stage, 'usr/share/doc/vim4-vfmcap/gstvfmcapsrc.c')
    copy('/usr/share/common-licenses/LGPL-2.1', stage, 'usr/share/doc/vim4-vfmcap/copyright')


def encoder(stage):
    copy(ROOT / 'gst-plugin-venc/amlvenc/libgstamlvenc.so', stage,
         'usr/lib/vim4-kvm/gstreamer-1.0/libgstamlvenc.so', 0o644)
    write(stage, 'usr/lib/systemd/system/nanokvm.service.d/encoder.conf',
          '[Service]\nEnvironment=GST_PLUGIN_PATH=/usr/lib/vim4-kvm/gstreamer-1.0\n')
    for source in (ROOT / 'gst-plugin-venc/amlvenc').glob('*.[ch]'):
        copy(source, stage, 'usr/share/doc/vim4-amlvenc/source/' + source.name)


def application(stage):
    deploy = ROOT / 'NanoKVM/deploy/vim4'
    copy(ROOT / 'build/NanoKVM-Server', stage, 'opt/vim4-nanokvm/NanoKVM-Server', 0o755)
    shutil.copytree(ROOT / 'NanoKVM/web/dist', stage / 'opt/vim4-nanokvm/web')
    shutil.copytree(ROOT / 'NanoKVM/support/assistant', stage / 'opt/vim4-nanokvm/assistant',
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT / 'NanoKVM/kvmapp/picoclaw', stage / 'opt/vim4-nanokvm/picoclaw',
                    ignore=shutil.ignore_patterns('__pycache__'))
    copy(deploy / 'picoclaw', stage, 'usr/libexec/vim4-picoclaw', 0o755)
    copy(ROOT / 'NanoKVM/LICENSE', stage, 'usr/share/doc/vim4-nanokvm/copyright')
    for name in ('vim4-video', 'vim4-media', 'vim4-system', 'vim4-update', 'vim4-edid', 'vim4-tailscale'):
        copy(deploy / name, stage, 'usr/libexec/' + name, 0o755)
        copy(deploy / (name + '.sudoers'), stage, 'etc/sudoers.d/' + name, 0o440)
    for name in ('nanokvm.service', 'vim4-kvm-cpufreq.service'):
        copy(deploy / name, stage, 'usr/lib/systemd/system/' + name)
    copy(deploy / '99-vim4-kvm-hid.rules', stage, 'usr/lib/udev/rules.d/99-vim4-kvm-hid.rules')
    copy(deploy / 'server.yaml', stage, 'usr/share/vim4-nanokvm/server.yaml')
    # Preserve application-managed settings and credentials on upgrade.
    write(stage, 'DEBIAN/postinst', '''#!/bin/sh
set -eu
if [ "$1" = configure ]; then
    getent passwd khadas >/dev/null || { echo 'Requires the Khadas Ubuntu base account' >&2; exit 1; }
    install -d -o khadas -g khadas -m 0755 /etc/kvm /var/lib/vim4-kvm/images
    install -d -o khadas -g khadas -m 0700 /var/lib/kvm/update-jobs /var/lib/vim4-kvm/update-cache
    install -d -o khadas -g khadas -m 0700 /var/lib/vim4-kvm/picoclaw
    if [ ! -e /etc/kvm/server.yaml ]; then
        install -o khadas -g khadas -m 0600 /usr/share/vim4-nanokvm/server.yaml /etc/kvm/server.yaml
    fi
    for name in vim4-video vim4-media vim4-system vim4-update vim4-edid vim4-tailscale; do
        test -s /usr/libexec/$name
        test -x /usr/libexec/$name
        test -s /etc/sudoers.d/$name
        visudo -cf /etc/sudoers.d/$name
    done
    if [ -d /run/systemd/system ]; then systemctl daemon-reload; fi
fi
''', 0o755)


def jetkvm(stage):
    copy(ROOT / 'build/jetkvm', stage, 'opt/vim4-jetkvm/jetkvm', 0o755)
    copy(ROOT / 'kvm/deploy/vim4/vim4-kvm.service', stage, 'usr/lib/systemd/system/vim4-kvm.service')
    copy(ROOT / 'kvm/LICENSE', stage, 'usr/share/doc/vim4-jetkvm/copyright')
    # Not enabled here: vim4-manager selects the application that boots.
    write(stage, 'DEBIAN/postinst', '''#!/bin/sh
set -eu
if [ "$1" = configure ] && [ -d /run/systemd/system ]; then systemctl daemon-reload; fi
''', 0o755)


def manager(stage):
    deploy = ROOT / 'vim4-manager/deploy'
    copy(ROOT / 'build/vim4-manager', stage, 'opt/vim4-manager/vim4-manager', 0o755)
    copy(deploy / 'vim4-manager-helper', stage, 'usr/libexec/vim4-manager-helper', 0o755)
    copy(deploy / 'vim4-manager-helper.sudoers', stage, 'etc/sudoers.d/vim4-manager-helper', 0o440)
    copy(deploy / 'vim4-manager.service', stage, 'usr/lib/systemd/system/vim4-manager.service')
    copy(ROOT / 'vim4-manager/LICENSE', stage, 'usr/share/doc/vim4-manager/copyright')
    write(stage, 'DEBIAN/postinst', '''#!/bin/sh
set -eu
if [ "$1" = configure ]; then
    getent passwd khadas >/dev/null || { echo 'Requires the Khadas Ubuntu base account' >&2; exit 1; }
    test -s /etc/sudoers.d/vim4-manager-helper
    visudo -cf /etc/sudoers.d/vim4-manager-helper
    if [ -d /run/systemd/system ]; then systemctl daemon-reload; fi
fi
''', 0o755)


def main():
    version, output = sys.argv[1], Path(sys.argv[2])
    subprocess.run(['dpkg', '--validate-version', version], check=True)
    gst = 'libc6 (>= 2.38), libglib2.0-0t64, libgstreamer1.0-0 (>= 1.24), libgstreamer-plugins-base1.0-0 (>= 1.24)'
    for name, populate, depends in [
        ('vim4-kvm-board', board, 'libc6 (>= 2.38), python3, systemd, udev, kmod, psmisc, iproute2, alsa-utils, hdmiin-demo (= 0.8-202305~noble)'),
        ('vim4-vfmcap', capture, gst),
        ('vim4-amlvenc', encoder, gst + ', libamvenc (= 0.2-202406~noble), libge2d (= 0.4-202406), gst-aml-drmbufferpool-plugins (= 0.2-202311)'),
        ('vim4-nanokvm', application, gst + ', libopus0, sudo, python3, curl, ca-certificates, picocom, network-manager, avahi-daemon, openssh-server, chrony, alsa-utils, gstreamer1.0-alsa, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good, gstreamer1.0-plugins-bad, gstreamer1.0-libav, vim4-kvm-board (>= 1.0.3+vim4.20261013.18), vim4-vfmcap, vim4-amlvenc (>= 1.0.3+vim4.20261013.18)'),
        ('vim4-jetkvm', jetkvm, 'libc6 (>= 2.38), libglib2.0-0t64, libgstreamer1.0-0 (>= 1.24), '
         'libgstreamer-plugins-base1.0-0 (>= 1.24), gstreamer1.0-plugins-bad, '
         f'vim4-kvm-board (>= {version}), vim4-vfmcap (>= {version}), vim4-amlvenc (>= {version}), '
         # The NanoKVM package owns the shared HID udev rule. Lower bounds only:
         # the NanoKVM web updater replaces that one package by itself.
         f'vim4-nanokvm (>= {version})'),
        ('vim4-manager', manager, f'libc6 (>= 2.38), python3, sudo, systemd, vim4-nanokvm (>= {version})')]:
        package(name, version, output, populate, depends)
    shutil.copy('/opt/build-inputs/ubuntu-packages.txt', output)
    shutil.copy('/opt/build-inputs/downloads.lock.json', output)
    checksums = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != 'SHA256SUMS':
            checksums.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name)
    (output / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')


if __name__ == '__main__':
    main()
