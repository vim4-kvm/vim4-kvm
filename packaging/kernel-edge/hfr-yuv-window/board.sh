#!/bin/bash
# Called by window.py in a private /tmp directory with a live board lease.
set -eu -o pipefail
cd "$(dirname "$0")"
unit=one-kvm
rx=/sys/kernel/debug/fe398000.hdmi-receiver
plugins=/opt/vim4-kvm/hdr10-r14e/gstreamer-1.0
app=/opt/vim4-kvm/one-kvm-usb-ffc6130/one-kvm
export GST_PLUGIN_PATH=$plugins
export GST_REGISTRY=$PWD/registry.bin
manager=/usr/libexec/vim4-manager-helper
active=/var/lib/vim4-kvm/edid/active.bin
v4l2-ctl() { LD_LIBRARY_PATH="$PWD" ./v4l2-ctl "$@"; }
private_directory() {
    local target=$1 upper=$2
    chown --reference="$target" "$upper"
    chmod --reference="$target" "$upper"
    mkdir "$upper.lower" "$upper.work"
    mount --bind "$target" "$upper.lower"
    mount -t overlay overlay -o "lowerdir=$PWD/$upper.lower,upperdir=$PWD/$upper,workdir=$PWD/$upper.work" "$target"
}
device() {
    local found=()
    for name in /sys/class/video4linux/video*/name; do
        if [[ $(cat "$name") == t7-vdin-test ]]; then
            local dir=${name%/name}
            found+=("/dev/${dir##*/}")
        fi
    done
    test "${#found[@]}" = 1
    dev=${found[0]}
}
proof() {
    systemctl is-active --quiet "$unit"
    timeout 12 bash -c 'until [[ /proc/$(systemctl show -p MainPID --value one-kvm)/exe -ef "$1" ]]; do sleep .2; done' _ "$app"
    sha256sum "$app" "$plugins"/{libgstvideo4linux2,libgstvim4wave5,libgstvim4hevc10}.so \
        /sys/module/{wave5,t7_hdmirx,t7_vdin_test}/notes/.note.gnu.build-id "$active" "$rx/edid"
    "$manager" edid-status
}
case "$1" in
preflight)
    proof
    sha256sum -c SHA256SUMS
    v4l2-ctl --version
    grep -Eiq '^default[[:space:]]+FullKvm[[:space:]]*$' /boot/extlinux/extlinux.conf
    test "$(uname -r)" = 7.3.0-vim4kvm-uhd7+
    cmp "$active" /usr/share/vim4-manager/edid/rtk-uhd-hdr.bin
    cmp "$active" "$rx/edid"
    test "$(cat /var/lib/vim4-kvm/edid/active.name)" = RTK-CONTROL
    test -d /sys/module/mali_kbase
    test "$(cat /sys/module/t7_vdin_test/parameters/direct_dma)" = Y ;;
activate)
    # Reuse the running uhd7 parameters for all three replacements.
    for mod in wave5 t7_vdin_test t7_hdmirx; do
        for param in /sys/module/"$mod"/parameters/*; do
            printf '%s=%s\n' "${param##*/}" "$(cat "$param")"
        done > "$mod.params"
    done
    systemctl stop "$unit" vim4-kvm-hdmi
    # One-KVM saves output FPS/codec and the GStreamer registry in its data
    # directory. Keep those writes private until the normal recovery boot.
    mkdir data-upper
    private_directory /var/lib/one-kvm data-upper
    rmmod wave5 t7_vdin_test t7_hdmirx
    for name in t7-hdmirx t7-vdin-test wave5; do
        mapfile -t parameters < "${name//-/_}.params"
        insmod "./$name.ko" "${parameters[@]}"
        localid=$(readelf -n "$name.ko" | awk '/Build ID:/ {print $3}')
        test -n "$localid"
        note=/sys/module/${name//-/_}/notes/.note.gnu.build-id
        test "$(tail -c 20 "$note" | od -An -tx1 | tr -d ' \n')" = "$localid"
    done
    mount --bind "$PWD/one-kvm" "$app"
    # A new factory (vim4ptsrate) has no installed file to bind over.
    mkdir plugin-upper
    install -m 0644 ./*.so plugin-upper/
    private_directory "$plugins" plugin-upper
    for p in *.so; do cmp "$p" "$plugins/$p"; done
    gst-inspect-1.0 vim4ptsrate
    systemctl start vim4-kvm-hdmi
    "$manager" edid-select RTK-CONTROL
    cmp "$active" "$rx/edid"
    systemctl start "$unit"
    proof ;;
sample)
    device
    cat "$rx/status"
    grep Cma /proc/meminfo
    cat /proc/sys/kernel/tainted
    v4l2-ctl -d "$dev" --query-dv-timings --get-parm --get-ctrl=gaming_vrr_base_rate --list-formats ;;
bench|raw444|rgb|caps|pts|loss)
    device
    systemctl stop "$unit"
    trap 'systemctl start "$unit"' EXIT
    case "$1" in
    caps)
        timeout 8 gst-launch-1.0 -v vim4v4l2src num-buffers=12 ! fakesink ;;
    rgb)
        result=0
        timeout 8 gst-launch-1.0 -v v4l2src device="$dev" num-buffers=4 ! video/x-raw,format=v308 ! fakesink || result=$?
        test "$result" = 1
        timeout 8 gst-launch-1.0 -v v4l2src device="$dev" num-buffers=4 ! 'video/x-raw,format=(string){v308,RGB}' ! fakesink ;;
    pts)
        # The source runs 120/80/60/48/120 at seven seconds per phase.
        # Keep the buffer PTS through the final slow-to-fast transition.
        result=0
        LD_LIBRARY_PATH="$PWD" timeout 36 stdbuf -oL ./v4l2-ctl -d "$dev" --poll-for-event=source_change=0 > events.txt &
        events=$!
        timeout -s INT -k 2 36 gst-launch-1.0 -e -v vim4v4l2src max-fps=60 ! \
            identity silent=false ! fakesink sync=false > output-pts.txt || result=$?
        test "$result" = 124
        status=0
        wait "$events" || status=$?
        test "$status" = 124
        cat events.txt
        grep 'pts:' output-pts.txt ;;
    bench)
        shift
        width=$1 height=$2 fps=$3
        shift 3
        for codec in "$@"; do
            stream=()
            if [[ $codec != capture ]]; then stream=(--save-bitstream="$PWD/$width.$codec"); fi
            runuser -u khadas -- env GST_PLUGIN_PATH="$plugins" GST_REGISTRY="$PWD/user-registry" \
                ./vim4-driver-bench --device="$dev" --exclusive --backend=edge --codec="$codec" \
                --width="$width" --height="$height" --fps="$fps" --warmup=60 --frames=600 --timeout=25 \
                --output="$PWD/$width-$codec.json" "${stream[@]}"
        done ;;
    raw444)
        timeout 90 ./capture-integrity --v4l2 "$dev" 3600 "$PWD/last.raw"
        grep Cma /proc/meminfo
        timeout 12 ./raw-pool "$dev"
        grep Cma /proc/meminfo
        gst-launch-1.0 -v v4l2src device="$dev" num-buffers=12 ! video/x-raw,format=NV12 ! fakesink ;;
    loss)
        trap '/usr/libexec/vim4-edid restore; systemctl start "$unit"' EXIT
        v4l2-ctl -d "$dev" --get-fmt-video > before-loss.fmt
        v4l2-ctl -d "$dev" --clear-edid 0
        timeout 10 bash -c 'until grep -qx "link_ready: 0" "$1/status"; do sleep .2; done' _ "$rx"
        cat "$rx/status"
        v4l2-ctl -d "$dev" --get-fmt-video > lost.fmt
        diff -u before-loss.fmt lost.fmt
        v4l2-ctl -d "$dev" --get-ctrl=gaming_vrr_base_rate
        /usr/libexec/vim4-edid restore
        cmp "$active" "$rx/edid" ;;
    esac ;;
*) exit 2 ;;
esac
