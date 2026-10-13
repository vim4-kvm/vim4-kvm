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
for name in vim4-kvm-board vim4-vfmcap vim4-amlvenc vim4-nanokvm; do
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
import sys
stage = Path(sys.argv[1])
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
    if installed.is_symlink() or installed.read_bytes() not in (expected, legacy):
        raise SystemExit(f'Unrecognized override; review before installing: {installed}')
    print(installed)
PY
for file in "$stage"/etc/sudoers.d/*; do visudo -cf "$file"; done
apt-get -s --no-remove install "${packages[@]}"
systemctl stop nanokvm.service
# If installation fails, leave the service stopped: do not launch a mixed install.
DEBIAN_FRONTEND=noninteractive apt-get -y --no-remove -o Dpkg::Options::=--force-confold install "${packages[@]}"
while IFS= read -r file; do
    case "$file" in
        /etc/sudoers.d/*) install -m 0440 "$stage$file" "$file" ;;
        *) rm -f -- "$file" ;;
    esac
done < "$stage/migrate"
systemctl daemon-reload
# Manual installations enabled units using absolute /etc paths. Recreate those
# links against the packaged units so the next boot does not silently skip KVM.
systemctl reenable --force nanokvm.service vim4-kvm-hdmi.service vim4-kvm-gadget.service \
    vim4-kvm-pd.service vim4-kvm-cpufreq.service
for unit in nanokvm vim4-kvm-hdmi vim4-kvm-gadget vim4-kvm-pd vim4-kvm-cpufreq; do
    readlink -e "/etc/systemd/system/multi-user.target.wants/$unit.service" >/dev/null
done
udevadm control --reload-rules
systemctl restart nanokvm.service
systemctl is-active nanokvm.service
dpkg-query -W -f='${Package} ${Version}\n' vim4-kvm-board vim4-vfmcap vim4-amlvenc vim4-nanokvm
echo 'Installed. Run tools/board.py check on the host, then exercise a video session.'
