#!/usr/bin/env python3
"""Assemble Ubuntu component packages without running installation scripts."""
import hashlib
import json
import lzma
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tarfile
import zipfile

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
        if name == 'vim4-onekvm':
            write(stage, 'opt/vim4-onekvm/version', version + '\n')
        # Every installation entry point (including dpkg and the web updater)
        # must flush payloads before reporting success or restarting services.
        postinst = stage / 'DEBIAN/postinst'
        if not postinst.exists():
            write(stage, 'DEBIAN/postinst', '#!/bin/sh\nset -eu\n', 0o755)
        with postinst.open('a') as script:
            script.write('sync\n')
        provides = 'Provides: vim4-media-api-1, vim4-runtime-api-1\n' if name == 'vim4-kvm-board' else ''
        if name == 'vim4-amlvenc':
            provides = 'Provides: vim4-wave5-api-1\n'
        if name == 'vim4-manager':
            provides = 'Provides: vim4-nas-api-1\n'
        write(stage, 'DEBIAN/control', f'Package: {name}\nVersion: {version}\nArchitecture: arm64\n'
              'Maintainer: VIM4 KVM <318096335+localhost-copilot@users.noreply.github.com>\n'
              f'Section: misc\nPriority: optional\nDepends: {depends}\n{provides}'
              f'Description: VIM4 Ubuntu {name} component\n')
        configs = sorted('/' + str(p.relative_to(stage)) for p in (stage / 'etc').rglob('*') if p.is_file())
        if configs:
            write(stage, 'DEBIAN/conffiles', '\n'.join(configs) + '\n')
        copy('/out/sources.json', stage, f'usr/share/doc/{name}/sources.json')
        # dpkg --verify needs checksums for every independently updated app.
        sums = [f'{hashlib.md5(path.read_bytes()).hexdigest()}  {path.relative_to(stage)}'
                for path in sorted(stage.rglob('*'))
                if path.is_file() and not path.is_symlink() and path.relative_to(stage).parts[0] != 'DEBIAN']
        write(stage, 'DEBIAN/md5sums', '\n'.join(sums) + '\n')
        # dpkg-deb clamps archive timestamps to SOURCE_DATE_EPOCH.
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage),
                        str(output / f'{name}_{version}_arm64.deb')], check=True)


def board(stage):
    copy(ROOT / 'board/60-vim4-panic.conf', stage,
         'usr/lib/sysctl.d/60-vim4-panic.conf')
    copy(ROOT / 'board/60-vim4-watchdog.conf', stage,
         'usr/lib/systemd/system.conf.d/60-vim4-watchdog.conf')
    copy(ROOT / 'board/60-vim4-journal.conf', stage,
         'usr/lib/systemd/journald.conf.d/60-vim4-journal.conf')
    copy(ROOT / 'board/vim4-logging', stage, 'usr/libexec/vim4-logging', 0o755)
    write(stage, 'DEBIAN/postinst', '''#!/bin/sh
set -eu
if [ "${1:-}" = configure ]; then /usr/libexec/vim4-logging; fi
''', 0o755)
    copy(ROOT / 'board/edid/1080p60-sdr8.bin', stage, 'usr/share/vim4-kvm/edid/1080p60-sdr8.bin', 0o644)
    copy(ROOT / 'board/vim4media.py', stage, 'usr/lib/vim4-kvm/python/vim4media.py', 0o644)
    copy(ROOT / 'board/vim4video.py', stage, 'usr/lib/vim4-kvm/python/vim4video.py', 0o644)
    copy(ROOT / 'board/vim4boot.py', stage, 'usr/lib/vim4-kvm/python/vim4boot.py', 0o644)
    copy(ROOT / 'board/vim4pd.py', stage, 'usr/lib/vim4-kvm/python/vim4pd.py', 0o644)
    copy(ROOT / 'board/vim4-wave5-monitor.py', stage, 'usr/libexec/vim4-wave5-monitor', 0o755)
    copy(ROOT / 'board/vim4-wave5-monitor.conf', stage, 'etc/default/vim4-wave5-monitor', 0o644)
    for name in ('vim4-board-runtime', 'vim4-kvm-run'):
        copy(ROOT / 'board' / name, stage, 'usr/libexec/' + name, 0o755)
    copy(ROOT / 'packaging/kernel-edge/one-kvm-edge-prepare', stage, 'usr/libexec/vim4-mainline-prepare', 0o755)
    copy(ROOT / 'packaging/kernel-edge/one-kvm-edge-usb-prepare', stage, 'usr/libexec/vim4-mainline-gadget-prepare', 0o755)
    copy(ROOT / 'tools/rootfs-policy.py', stage, 'usr/sbin/vim4-rootfs-policy', 0o755)
    copy(ROOT / 'build/usb-pd-init', stage, 'usr/sbin/usb-pd-init', 0o755)
    for name in ('hdmi-setup.sh', 'kvm-gadget.sh'):
        copy(ROOT / 'tools' / name, stage, 'usr/sbin/' + name, 0o755)
    # hdmi-setup.sh calls it from its own directory; vim4-manager-helper too.
    copy(ROOT / 'tools/hdr-curve.sh', stage, 'usr/sbin/vim4-hdr-curve', 0o755)
    for file in (ROOT / 'board').glob('*.service'):
        write(stage, 'usr/lib/systemd/system/' + file.name,
              file.read_text().replace('/usr/local/sbin/', '/usr/sbin/'))
    copy(ROOT / 'board/99-vfm-cap.rules', stage, 'usr/lib/udev/rules.d/99-vfm-cap.rules')
    copy(ROOT / 'board/90-vim4-encoder.conf', stage, 'etc/modprobe.d/90-vim4-encoder.conf')
    copy(ROOT / 'LICENSE', stage, 'usr/share/doc/vim4-kvm-board/copyright')


def capture(stage):
    copy(ROOT / 'gst-plugin-vfmcap/build/libgstvfmcap.so', stage,
         'usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgstvfmcap.so', 0o644)
    copy(ROOT / 'gst-plugin-vfmcap/README.md', stage, 'usr/share/doc/vim4-vfmcap/README.md')
    copy(ROOT / 'gst-plugin-vfmcap/src/gstvfmcapsrc.c', stage, 'usr/share/doc/vim4-vfmcap/gstvfmcapsrc.c')
    copy('/usr/share/common-licenses/LGPL-2.1', stage, 'usr/share/doc/vim4-vfmcap/copyright')


def encoder(stage):
    mainline = 'usr/lib/vim4-kvm/mainline-gstreamer-1.0/'
    copy(ROOT / 'gst-plugin-venc/wave5/libgstvim4wave5.so', stage, mainline + 'libgstvim4wave5.so', 0o644)
    copy(ROOT / 'build/mainline-gstreamer/libgstvideo4linux2.so', stage, mainline + 'libgstvideo4linux2.so', 0o644)
    copy(ROOT / 'gst-plugin-venc/jpeg/vim4/libgstvim4jpegenc.so', stage, mainline + 'libgstvim4jpegenc.so', 0o644)
    copy(ROOT / 'gst-plugin-venc/jpeg/vim4/libgstvim4jpegenc.so', stage,
         'usr/lib/vim4-kvm/gstreamer-1.0/libgstvim4jpegenc.so', 0o644)
    copy(ROOT / 'gst-plugin-venc/jpeg/vim4/gstvim4jpegenc.c', stage,
         'usr/share/doc/vim4-amlvenc/source/gstvim4jpegenc.c')
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
    shutil.copytree(ROOT / 'NanoKVM/kvmapp/picoclaw', stage / 'opt/vim4-nanokvm/picoclaw',
                    ignore=shutil.ignore_patterns('__pycache__'))
    copy(deploy / 'picoclaw', stage, 'usr/libexec/vim4-picoclaw', 0o755)
    copy(deploy / 'remove-legacy-assistant', stage, 'usr/libexec/vim4-remove-legacy-assistant', 0o755)
    copy(ROOT / 'NanoKVM/LICENSE', stage, 'usr/share/doc/vim4-nanokvm/copyright')
    for name in ('vim4-video', 'vim4-media', 'vim4-system', 'vim4-update', 'vim4-edid'):
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
    /usr/libexec/vim4-remove-legacy-assistant
    # dpkg retains obsolete conffiles; revoke the old application's access.
    rm -f /etc/sudoers.d/vim4-tailscale /usr/libexec/vim4-tailscale
    install -d -o khadas -g khadas -m 0755 /etc/kvm /var/lib/vim4-kvm/images
    install -d -o khadas -g khadas -m 0700 /var/lib/kvm/update-jobs /var/lib/vim4-kvm/update-cache
    install -d -o khadas -g khadas -m 0700 /var/lib/vim4-kvm/picoclaw
    if [ ! -e /etc/kvm/server.yaml ]; then
        install -o khadas -g khadas -m 0600 /usr/share/vim4-nanokvm/server.yaml /etc/kvm/server.yaml
    fi
    for name in vim4-video vim4-media vim4-system vim4-update vim4-edid; do
        test -s /usr/libexec/$name
        test -x /usr/libexec/$name
        test -s /etc/sudoers.d/$name
        visudo -cf /etc/sudoers.d/$name
    done
    if [ -d /run/systemd/system ]; then systemctl daemon-reload; fi
fi
''', 0o755)


def jetkvm(stage):
    deploy = ROOT / 'kvm/deploy/vim4'
    copy(ROOT / 'build/jetkvm', stage, 'opt/vim4-jetkvm/jetkvm', 0o755)
    copy(deploy / 'vim4-kvm.service', stage, 'usr/lib/systemd/system/vim4-kvm.service')
    copy(deploy / 'vim4-jetkvm', stage, 'usr/libexec/vim4-jetkvm', 0o755)
    copy(deploy / 'vim4-jetkvm.sudoers', stage, 'etc/sudoers.d/vim4-jetkvm', 0o440)
    copy(ROOT / 'kvm/LICENSE', stage, 'usr/share/doc/vim4-jetkvm/copyright')
    copy(ROOT / 'packaging/ubuntu/manager-config.py', stage, 'usr/share/vim4-jetkvm/manager-config.py')
    # Not enabled here: vim4-manager selects the application that boots.
    write(stage, 'DEBIAN/postinst', '''#!/bin/sh
set -eu
if [ "$1" = configure ]; then
    if [ -e /var/lib/jetkvm/config.json ]; then
        python3 /usr/share/vim4-jetkvm/manager-config.py jetkvm /var/lib/jetkvm/config.json
    fi
    test -s /usr/libexec/vim4-jetkvm
    test -x /usr/libexec/vim4-jetkvm
    test -s /etc/sudoers.d/vim4-jetkvm
    visudo -cf /etc/sudoers.d/vim4-jetkvm
    if [ -d /run/systemd/system ]; then systemctl daemon-reload; fi
fi
''', 0o755)


def onekvm(stage):
    deploy = ROOT / 'One-KVM/deploy/vim4'
    copy(ROOT / 'build/onekvm', stage, 'opt/vim4-onekvm/one-kvm', 0o755)
    copy(ROOT / 'One-KVM/target/vim4/libgst-aml-dma-allocator.so', stage,
         'opt/vim4-onekvm/lib/libgst-aml-dma-allocator.so', 0o755)
    copy(deploy / 'one-kvm.service', stage, 'usr/lib/systemd/system/one-kvm.service')
    copy(deploy / 'vim4-onekvm', stage, 'usr/libexec/vim4-onekvm', 0o755)
    copy(deploy / 'vim4-onekvm-update', stage, 'usr/libexec/vim4-onekvm-update', 0o755)
    copy(deploy / 'vim4-onekvm.sudoers', stage, 'etc/sudoers.d/vim4-onekvm', 0o440)
    copy(deploy / '71-onekvm-hid.rules', stage, 'usr/lib/udev/rules.d/71-onekvm-hid.rules')
    copy(ROOT / 'One-KVM/LICENSE', stage, 'usr/share/doc/vim4-onekvm/copyright')
    # Ship only the terminal executable: depending on ttyd also enables its
    # standalone daemon, while One-KVM owns the authenticated Unix socket.
    copy('/usr/bin/ttyd', stage, 'opt/vim4-onekvm/bin/ttyd', 0o755)
    copy('/usr/share/doc/ttyd/copyright', stage, 'usr/share/doc/vim4-onekvm/ttyd-copyright')
    copy(deploy / '71-onekvm-watchdog.rules', stage, 'usr/lib/udev/rules.d/71-onekvm-watchdog.rules')
    extensions = Path('/opt/one-kvm-extensions')
    for archive, member, destination in (
        ('gostc.tar.gz', 'gostc', 'opt/vim4-onekvm/bin/gostc'),
        ('gostc.tar.gz', 'LICENSE', 'usr/share/doc/vim4-onekvm/gostc-LICENSE'),
        ('frp.tar.gz', 'frp_0.71.0_linux_arm64/frpc', 'opt/vim4-onekvm/bin/frpc'),
        ('frp.tar.gz', 'frp_0.71.0_linux_arm64/LICENSE', 'usr/share/doc/vim4-onekvm/frp-LICENSE'),
    ):
        with tarfile.open(extensions / archive) as source:
            target = stage / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as incoming, target.open('wb') as output:
                shutil.copyfileobj(incoming, output)
            target.chmod(0o755 if '/bin/' in destination else 0o644)
    with zipfile.ZipFile(extensions / 'easytier.zip') as source:
        target = stage / 'opt/vim4-onekvm/bin/easytier-core'
        with source.open('easytier-linux-aarch64/easytier-core') as incoming, target.open('wb') as output:
            shutil.copyfileobj(incoming, output)
        target.chmod(0o755)
    copy(extensions / 'easytier-LICENSE', stage, 'usr/share/doc/vim4-onekvm/easytier-LICENSE')
    copy(ROOT / 'packaging/ubuntu/extensions.lock.json', stage, 'usr/share/doc/vim4-onekvm/extensions.lock.json')
    resources = ROOT / 'One-KVM/libs/ventoy-img-rs/resources'
    destination = 'usr/share/vim4-onekvm/ventoy'
    copy(resources / 'boot.img', stage, f'{destination}/boot.img')
    for name in ('core.img', 'ventoy.disk.img'):
        target = stage / destination / name
        with lzma.open(resources / f'{name}.xz', 'rb') as source, target.open('wb') as output:
            shutil.copyfileobj(source, output)
        target.chmod(0o644)
    # Also constrain previously installed versions of the other two units.
    for unit in ('nanokvm.service', 'vim4-kvm.service'):
        write(stage, f'usr/lib/systemd/system/{unit}.d/onekvm.conf',
              '[Unit]\nConflicts=one-kvm.service\n')
    write(stage, 'DEBIAN/postinst', '''#!/bin/sh
set -eu
if [ "$1" = configure ]; then
    getent passwd khadas >/dev/null
    getent group vim4-watchdog >/dev/null || groupadd --system vim4-watchdog
    setcap cap_net_admin=ep /opt/vim4-onekvm/bin/easytier-core
    test -s /usr/libexec/vim4-onekvm
    test -s /opt/vim4-onekvm/lib/libgst-aml-dma-allocator.so
    for name in boot.img core.img ventoy.disk.img; do
        test -s "/usr/share/vim4-onekvm/ventoy/$name"
    done
    test -x /usr/libexec/vim4-onekvm
    test -s /etc/sudoers.d/vim4-onekvm
    visudo -cf /etc/sudoers.d/vim4-onekvm
    if [ -d /run/systemd/system ]; then
        systemctl daemon-reload
        udevadm control --reload-rules
        udevadm trigger --subsystem-match=watchdog
    fi
fi
''', 0o755)


def manager(stage):
    deploy = ROOT / 'vim4-manager/deploy'
    copy(ROOT / 'build/vim4-manager', stage, 'opt/vim4-manager/vim4-manager', 0o755)
    copy(deploy / 'vim4-manager-helper', stage, 'usr/libexec/vim4-manager-helper', 0o755)
    copy(deploy / 'vim4-manager-helper.sudoers', stage, 'etc/sudoers.d/vim4-manager-helper', 0o440)
    copy(deploy / 'vim4-manager.service', stage, 'usr/lib/systemd/system/vim4-manager.service')
    copy(ROOT / 'build/vim4-nasdisk', stage, 'usr/libexec/vim4-nasdisk', 0o755)
    copy(deploy / 'vim4-nasdisk.service', stage, 'usr/lib/systemd/system/vim4-nasdisk.service')
    for file in (deploy / 'edid').iterdir():
        copy(file, stage, 'usr/share/vim4-manager/edid/' + file.name)
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


GST = 'libc6 (>= 2.38), libglib2.0-0t64, libgstreamer1.0-0 (>= 1.24), libgstreamer-plugins-base1.0-0 (>= 1.24)'
# Applications state lower bounds only: their web updaters replace one package
# and refuse any plan that would also upgrade the platform.
PLATFORM = ('vim4-kvm-board (>= 1.0.3+vim4.20261013.18), vim4-media-api-1, vim4-runtime-api-1, vim4-wave5-api-1, vim4-vfmcap, '
            'vim4-amlvenc (>= 1.0.3+vim4.20261013.18)')
PACKAGES = {
    'platform': [
        ('vim4-kvm-board', board, 'libc6 (>= 2.38), python3, mtools, dosfstools, systemd, udev, kmod, psmisc, iproute2, alsa-utils, hdmiin-demo (= 0.8-202305~noble)'),
        ('vim4-vfmcap', capture, GST),
        ('vim4-amlvenc', encoder, GST + ', libamvenc (= 0.2-202406~noble), libge2d (= 0.4-202406), gst-aml-drmbufferpool-plugins (= 0.2-202311)')],
    'nanokvm': [
        ('vim4-nanokvm', application, GST + ', libopus0, sudo, python3, dosfstools, curl, ca-certificates, picocom, network-manager, avahi-daemon, openssh-server, chrony, alsa-utils, gstreamer1.0-alsa, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good, gstreamer1.0-plugins-bad, gstreamer1.0-libav, ' + PLATFORM)],
    'jetkvm': [
        ('vim4-jetkvm', jetkvm, 'libc6 (>= 2.38), libglib2.0-0t64, libgstreamer1.0-0 (>= 1.24), '
         'libgstreamer-plugins-base1.0-0 (>= 1.24), gstreamer1.0-plugins-bad, ' + PLATFORM + ', '
         # The NanoKVM package owns the shared HID udev rule.
         'vim4-nanokvm (>= 1.0.3+vim4.20261013.18), sudo, python3, network-manager, avahi-daemon')],
    'onekvm': [
        ('vim4-onekvm', onekvm, GST + ', libavcodec60, libavutil58, libdrm2, libyuv0, '
         'libasound2t64, libudev1, libdbus-1-3, libopus0, libstdc++6, '
         'gstreamer1.0-plugins-good, gstreamer1.0-plugins-bad, gstreamer-aml (= 0.6-202406), sudo, python3, libcap2-bin, '
         'libjson-c5, libuv1t64, libssl3t64, libcap2, zlib1g, libwebsockets-evlib-uv, '
         'network-manager, dnsmasq-base, openssh-client, ' + PLATFORM + ', vim4-nanokvm (>= 1.0.3+vim4.20261013.18), '
         'vim4-manager (>= 2.5.1+vim4.20261014.4)')],
    'manager': [
        ('vim4-manager', manager, 'libc6 (>= 2.38), python3, sudo, systemd, fuse3, cifs-utils, nfs-common, vim4-media-api-1, vim4-runtime-api-1, vim4-nanokvm (>= 1.0.3+vim4.20261013.18)')],
}
PACKAGES['all'] = [entry for name in ('platform', 'nanokvm', 'jetkvm', 'onekvm', 'manager') for entry in PACKAGES[name]]
PACKAGES['capture'] = [PACKAGES['platform'][1]]
PACKAGES['encoder'] = [PACKAGES['platform'][2]]


def main():
    version, output = sys.argv[1], Path(sys.argv[2])
    component = sys.argv[3] if len(sys.argv) > 3 else 'all'
    subprocess.run(['dpkg', '--validate-version', version], check=True)
    for name, populate, depends in PACKAGES[component]:
        package(name, version, output, populate, depends)
    shutil.copy('/opt/build-inputs/ubuntu-packages.txt', output)
    shutil.copy('/opt/build-inputs/downloads.lock.json', output)
    if component in ('all', 'onekvm'):
        shutil.copy('/opt/build-inputs/extensions.lock.json', output)
    subprocess.run([sys.executable, str(ROOT / 'packaging/ubuntu/feeds.py'), str(output), version], check=True)
    checksums = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != 'SHA256SUMS':
            checksums.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name)
    (output / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')

if __name__ == '__main__':
    main()
