#!/bin/bash
# On-board upgrade of verified Ubuntu component packages. Does not flash/reboot.
set -euo pipefail
[[ $# == 2 && $1 == --exclusive ]] || { echo 'Usage: sudo bash install-components.sh --exclusive PACKAGE_DIRECTORY' >&2; exit 2; }
[[ $EUID == 0 && $(uname -m) == aarch64 ]] || { echo 'Requires root on VIM4 ARM64' >&2; exit 1; }
grep -qi 'Khadas VIM4' /proc/device-tree/model
exec 9>/run/lock/vim4-component-install.lock
flock -n 9
cd "${2:?}"
sha256sum -c SHA256SUMS
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
packages=()
version=
components=(vim4-kvm-board vim4-vfmcap vim4-amlvenc vim4-nanokvm vim4-jetkvm vim4-onekvm vim4-manager)
component=$(python3 -c 'import json; print(json.load(open("sources.json")).get("component", "all"))')
case "$component" in
    all) ;;
    pikvm) components=(vim4-pikvm vim4-manager) ;;
    pikvm-app) components=(vim4-pikvm) ;;
    manager) components=(vim4-manager) ;;
    onekvm) components=(vim4-onekvm) ;;
    onekvm-board) components=(vim4-kvm-board vim4-onekvm) ;;
    nanokvm) components=(vim4-nanokvm) ;;
    jetkvm) components=(vim4-jetkvm) ;;
    platform) components=(vim4-kvm-board vim4-vfmcap vim4-amlvenc) ;;
    capture) components=(vim4-vfmcap) ;;
    encoder) components=(vim4-amlvenc) ;;
    *) echo 'Unknown package component set' >&2; exit 1 ;;
esac
for name in "${components[@]}"; do
    candidates=("${name}"_*_arm64.deb)
    [[ ${#candidates[@]} == 1 && -f ${candidates[0]} ]]
    package=${candidates[0]}
    [[ $(dpkg-deb -f "$package" Package) == "$name" && $(dpkg-deb -f "$package" Architecture) == arm64 ]]
    current=$(dpkg-deb -f "$package" Version)
    [[ -z $version || $version == "$current" ]]
    version=$current
    # Verify selected packages are actually covered by the manifest.
    grep -Fqx "$(sha256sum "$package")" SHA256SUMS
    if installed=$(dpkg-query -W -f='${Version}' "$name" 2>/dev/null); then
        dpkg --compare-versions "$current" ge "$installed"
    fi
    dpkg-deb -x "$package" "$stage"
    packages+=("$PWD/$package")
done
# Only migrate exact known manual-install equivalents. Keep administrator
# overrides (including rtp-lan.conf) and reject unknown conflicting units.
python3 - "$stage" > "$stage/migrate" <<'PY'
from pathlib import Path
import hashlib
import subprocess
import sys
stage = Path(sys.argv[1])

def unchanged_packaged_sudoers(path):
    # Package-owned conffiles legitimately change across releases. Only accept
    # the previous shipped bytes; administrator edits remain an explicit error.
    if path.parent != Path('/etc/sudoers.d') or path.is_symlink():
        return False
    owner = subprocess.run(['dpkg-query', '-S', str(path)], capture_output=True, text=True)
    if owner.returncode or len(owner.stdout.splitlines()) != 1:
        return False
    package, separator, filename = owner.stdout.strip().partition(': ')
    if not separator or filename != str(path):
        return False
    installed = subprocess.run(['dpkg-query', '-W', '-f=${Conffiles}', package],
                               capture_output=True, text=True)
    if installed.returncode:
        return False
    digest = hashlib.md5(path.read_bytes()).hexdigest()
    return any(fields == [str(path), digest]
               for fields in (line.split() for line in installed.stdout.splitlines()))

pairs = [(p, Path('/etc/systemd/system') / p.relative_to(stage / 'usr/lib/systemd/system'))
         for p in (stage / 'usr/lib/systemd/system').rglob('*') if p.is_file()]
pairs += [(p, Path('/etc/udev/rules.d') / p.name)
          for p in (stage / 'usr/lib/udev/rules.d').glob('*') if p.is_file()]
pairs += [(p, Path('/etc/sudoers.d') / p.name)
          for p in (stage / 'etc/sudoers.d').glob('*') if p.is_file()]
for source, installed in pairs:
    if not installed.exists() and not installed.is_symlink():
        continue
    expected = source.read_bytes()
    legacy = expected.replace(b'/usr/sbin/', b'/usr/local/sbin/').replace(b'/usr/lib/vim4-kvm/', b'/usr/local/lib/vim4-kvm/').replace(b'/usr/libexec/', b'/usr/local/libexec/')
    if installed.is_symlink() or (installed.read_bytes() not in (expected, legacy)
                                  and not unchanged_packaged_sudoers(installed)):
        raise SystemExit(f'Unrecognized override; review before installing: {installed}')
    print(installed)
PY
for file in "$stage"/etc/sudoers.d/*; do
    [[ -f $file ]] || continue
    visudo -cf "$file"
done
apt-get -s --no-remove install "${packages[@]}"
# A dashboard-only update must preserve capture and display failure evidence.
# Share the helper lock so an in-flight user operation finishes before upgrade.
if [[ $component == manager ]]; then
    exec 8>/run/lock/vim4-manager.lock
    flock -n 8
    systemctl stop vim4-manager.service
    DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get -y --no-remove -o Dpkg::Options::=--force-confold install "${packages[@]}"
    while IFS= read -r file; do
        case "$file" in
            /etc/sudoers.d/*) install -m 0440 "$stage$file" "$file" ;;
            *) rm -f -- "$file" ;;
        esac
    done < "$stage/migrate"
    systemctl daemon-reload
    sync
    systemctl start vim4-manager.service
    systemctl is-active vim4-manager.service
    dpkg-query -W -f='${Package} ${Version}\n' vim4-manager
    exit 0
fi
# Keep the application selected in vim4-manager. NanoKVM is the default when
# no alternative is enabled (first installation).
app=nanokvm.service
for unit in vim4-kvm.service one-kvm.service vim4-pikvm.service; do
    if systemctl is-enabled --quiet "$unit" 2>/dev/null; then app=$unit; fi
done
# Wait for every installed application to release the shared hardware.
for unit in nanokvm.service vim4-kvm.service one-kvm.service vim4-pikvm.service; do
    if [[ $(systemctl show --property=LoadState --value "$unit") == loaded ]]; then
        systemctl stop "$unit"
    fi
done
# If installation fails, leave the service stopped: do not launch a mixed install.
DEBIAN_FRONTEND=noninteractive apt-get -y --no-remove -o Dpkg::Options::=--force-confold install "${packages[@]}"
while IFS= read -r file; do
    case "$file" in
        /etc/sudoers.d/*) install -m 0440 "$stage$file" "$file" ;;
        *) rm -f -- "$file" ;;
    esac
done < "$stage/migrate"
# The root filesystem uses data=writeback: flush new files (sudoers included)
# before restarting. This does not make an interrupted installation atomic.
sync
if [[ -x /usr/sbin/vim4-rootfs-policy ]]; then /usr/sbin/vim4-rootfs-policy /; fi
systemctl daemon-reload
# Manual installations enabled units using absolute /etc paths. Recreate those
# links against the packaged units so the next boot does not silently skip KVM.
systemctl reenable --force "$app" vim4-manager.service vim4-kvm-hdmi.service vim4-kvm-gadget.service \
    vim4-kvm-pd.service vim4-kvm-cpufreq.service
for unit in "$app" vim4-manager.service vim4-kvm-hdmi.service vim4-kvm-gadget.service vim4-kvm-pd.service \
    vim4-kvm-cpufreq.service; do
    readlink -e "/etc/systemd/system/multi-user.target.wants/$unit" >/dev/null
done
udevadm control --reload-rules
systemctl restart "$app" vim4-manager.service
if systemctl cat vim4-wave5-monitor.service >/dev/null 2>&1; then
    systemctl enable --now vim4-wave5-monitor.service
fi
systemctl is-active "$app" vim4-manager.service
dpkg-query -W -f='${Package} ${Version}\n' "${components[@]}"
for file in "$stage"/etc/sudoers.d/*; do
    [[ -f $file ]] || continue
    installed=/etc/sudoers.d/$(basename "$file")
    cmp "$file" "$installed"
    visudo -cf "$installed"
done
# Include newly created service enablement links in the durability boundary.
sync
echo 'Installed. Run tools/board.py check on the host, then exercise a video session.'
