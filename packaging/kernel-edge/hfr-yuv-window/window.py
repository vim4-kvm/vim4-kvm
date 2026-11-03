"""Single uhd7 overlay window. With no arguments only validate local artifacts."""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shlex
import signal
import subprocess
import sys
import time
import tomllib
import urllib.request

from source import Source

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT / "build/hfr-yuv-window"
PAYLOAD = BUILD / "payload"
BW = runpy.run_path(str(ROOT / "tools/board-window"))
RX = "/sys/kernel/debug/fe398000.hdmi-receiver/status"
PLUGINS = "/opt/vim4-kvm/hdr10-r14e/gstreamer-1.0"
URL = "http://127.0.0.1:18081"
APP = "/opt/vim4-kvm/one-kvm-usb-ffc6130/one-kvm"
RELEASE = "7.3.0-vim4kvm-uhd7+"
PHASES = [(0, "admission"), (3, "fixed-4k"), (6, "fixed-1080"), (10, "fixed-1440"),
          (14, "raw444"), (17, "vrr1080"), (21, "vrr4k"), (24, "loss"), (25, "restore")]


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate():
    recipe = tomllib.loads((HERE.parent / "sources.toml").read_text())["gstreamer"]
    check(BW["sha"](PAYLOAD / "libgstvideo4linux2.so") == recipe["candidate_plugin_sha256"], "v4l2 plugin lock mismatch")
    subprocess.run(["shasum", "-a", "256", "-c", "SHA256SUMS"], cwd=PAYLOAD, check=True)
    for name in ("labels", "source.tar"):
        check((BUILD / name).is_file(), f"missing {name}")
    playwright = ROOT / "kvm/ui/node_modules/playwright/index.mjs"
    if not playwright.exists():
        playwright = ROOT.parent / "vim4-kvm/kvm/ui/node_modules/playwright/index.mjs"
    check(playwright.is_file(), "missing Playwright")
    os.environ["PLAYWRIGHT_MODULE"] = str(playwright)


def api(path, method="GET", data=None):
    req = urllib.request.Request(URL + "/api/" + path, method=method,
                                 data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json", "Origin": URL})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def poll(check_state, seconds):
    deadline = time.monotonic() + seconds
    while not check_state():
        if time.monotonic() >= deadline:
            raise TimeoutError("state deadline")
        time.sleep(.5)


def run():
    queue, ticket = BW["require_board"]()
    lease = queue.read(ticket)
    check(lease["who"] == "hfr-yuv-window" and lease["seconds"] <= 1800, "wrong lease")
    end = lease["started"] + lease["seconds"]
    name = "hfr-yuv-" + str(int(lease["started"]))
    out = ROOT / "logs" / name
    out.mkdir()
    ip = subprocess.check_output(["ipconfig", "getifaddr", "en0"], text=True).strip()
    tunnel = None
    source = None
    activated = saved = False

    def ssh(cmd, timeout=20):
        BW["require_board"]()
        return BW["ssh"]("vim4", cmd, timeout=timeout)

    def save(label, value):
        (out / label).write_text(value if isinstance(value, str) else json.dumps(value, indent=2))
        return value

    def board(label, args, timeout=45):
        BW["require_board"]()
        cmd = f"sudo -n timeout -k 3 {timeout} bash {remote}/board.sh " + shlex.join(args)
        with (out / label).open("w") as stream:
            subprocess.run(["ssh", "-n", "-oBatchMode=yes", "-oConnectTimeout=5", "vim4", cmd],
                           stdout=stream, stderr=subprocess.STDOUT, timeout=timeout + 8, check=True)

    def connect():
        proc = subprocess.Popen(["ssh", "-N", "-oExitOnForwardFailure=yes", "-oBatchMode=yes",
                                 "-L", "18081:127.0.0.1:8081", "vim4"], stdin=subprocess.DEVNULL)
        time.sleep(.8)
        check(proc.poll() is None, "SSH forward failed")
        return proc

    def receive(label, seconds, minimum=0, size=None, codec=None, maximum=None):
        directory = name + "/" + label
        args = [ROOT / "tools/board-window", "--window", directory.replace("/", "-"), "receiver",
                "--url", URL, "--seconds", str(seconds), "--local-ip", ip]
        result = subprocess.run(args, stdout=subprocess.PIPE, text=True, timeout=seconds + 45, check=True)
        save(label + "-receiver.json", result.stdout)
        metrics = json.loads(result.stdout)
        check(metrics["fps"] >= minimum, f"{label} receiver {metrics['fps']:.2f} fps")
        if maximum is not None:
            check(metrics["fps"] <= maximum, f"{label} exceeded {maximum} fps")
        stat = metrics["samples"][-1]
        if size:
            check((stat["frameWidth"], stat["frameHeight"]) == size, "unexpected decoded dimensions")
        if codec:
            check(stat["codec"].lower().endswith(codec), "unexpected negotiated codec")
        queue.sampling(ticket, True)  # receiver releases its sampling interval
        return metrics

    def configure(codec, fps):
        response = api("config/video", "PATCH", {"output": {"height": 0, "fps": fps}})
        check(response["output"]["fps"] == fps, "One-KVM output limit mismatch")
        api("stream/mode", "POST", {"mode": codec})
        check(api("stream/mode")["mode"].lower() == codec, "One-KVM codec constrained")

    def status():
        return dict(line.split(": ", 1) for line in ssh("sudo -n cat " + RX).splitlines() if ": " in line)

    def wire(label, width, height, base=0):
        def ready():
            s = status()
            # COR reports half the horizontal pixels for a YCbCr420 link.
            avi = bytes.fromhex(s.get("avi_packet", ""))
            scale = 2 if len(avi) > 4 and avi[4] >> 5 == 3 else 1
            ticks = int(s.get("frame_ticks", "0"))
            expected = 60 if height == 2160 else 120
            return (int(s.get("width", 0)) * scale, s.get("height"), s.get("link_ready"),
                    s.get("vrr_base_hz")) == (width, str(height), "1", str(base)) and (
                        base or (ticks and abs(166666664 / ticks - expected) < 1))
        poll(ready, 15)
        board(label + "-input.txt", ["sample"])
        board(label + "-caps.txt", ["caps"], 15)
        check(not BW["source_hdr"]("vim4"), "expected SDR")

    files = [APP, *(PLUGINS + "/" + p.name for p in PAYLOAD.glob("*.so")),
             "/boot/extlinux/extlinux.conf", "/etc/vim4-kvm/runtime-build.json",
             "/var/lib/vim4-kvm/edid/active.bin", "/var/lib/vim4-kvm/edid/active.name",
             "/sys/kernel/debug/fe398000.hdmi-receiver/edid",
             *[f"/sys/module/{m}/notes/.note.gnu.build-id" for m in ("t7_vdin_test", "t7_hdmirx", "wave5")]]
    def alarm(*_):
        raise TimeoutError("reserved recovery time reached")
    signal.signal(signal.SIGALRM, alarm)
    signal.signal(signal.SIGTERM, alarm)
    try:
        signal.alarm(max(1, int(end - time.time() - 300)))
        check(not any(i["heavy"] and i["state"] == "held" for i in queue.status()), "heavy build still running")
        queue.sampling(ticket, True)
        baseline = save("baseline.json", BW["identity"]("vim4", files))
        check(baseline["build_id"] == "d6f9c685802759c85cba6bd92bce90396d1cf6ec" and
              baseline["release"] == RELEASE, "unexpected baseline")
        inventory = json.loads((HERE.parent / "uhd7-module-inventory.json").read_text())
        for mod in ("t7-hdmirx", "t7-vdin-test", "wave5"):
            build_id, = [v["build_id"] for k, v in inventory.items() if k.endswith("/" + mod + ".ko.xz")]
            note = bytes.fromhex("040000001400000003000000474e5500" + build_id)
            path = "/sys/module/" + mod.replace("-", "_") + "/notes/.note.gnu.build-id"
            check(baseline["files"][path] == hashlib.sha256(note).hexdigest(), f"unexpected baseline {mod}")
        ssh("systemctl is-active --quiet one-kvm && systemctl is-active --quiet vim4-kvm-hdmi && "
            "grep -Eiq '^default[[:space:]]+FullKvm[[:space:]]*$' /boot/extlinux/extlinux.conf && "
            "test -z \"$(sudo -n cat /sys/kernel/config/usb_gadget/kvm/functions/mass_storage.disk0/lun.0/file)\"")
        oldboot = ssh("cat /proc/sys/kernel/random/boot_id").strip()
        save("dmesg-before", ssh("sudo -n dmesg"))
        tunnel = connect()
        save("initial-config.json", api("config/video"))
        save("initial-mode.json", api("stream/mode"))
        uu = api("config/uu-remote")["status"]
        check(not uu["connection_count"] and not uu["sessions"], "UU session is active")
        check(not BW["source_hdr"]("vim4"), "initial source must be SDR")
        remote = ssh("mktemp -d /tmp/hfr-yuv.XXXXXXXX").strip()
        check(re.fullmatch(r"/tmp/hfr-yuv\.[A-Za-z0-9]{8}", remote), "unexpected staging directory")
        subprocess.run(["scp", *PAYLOAD.glob("*"), HERE / "board.sh", "vim4:" + remote + "/"], timeout=60, check=True)
        board("original.txt", ["preflight"])
        key = json.loads(ssh("sudo -n cat /var/lib/one-kvm/mcp/credentials.json"))["api_key"]
        source = Source(BW["MCP"](URL + "/api/mcp", key), BUILD, out, ip)
        source.bootstrap(BW["sha"](BUILD / "source.tar"))
        saved = True
        reference = receive("baseline", 10, 55, (3840, 2160))
        activated = True
        board("candidate.txt", ["activate"], 65)
        wire("fixed-4k", 3840, 2160)
        metrics = receive("candidate-4k", 10, reference["fps"] - 2, (3840, 2160))
        for counter in ("freezeCount", "framesDropped", "packetsLost"):
            for sample in (reference, metrics):
                check(counter in sample["samples"][0], "missing receiver counter " + counter)
            def delta(sample):
                return sample["samples"][-1][counter] - sample["samples"][0][counter]
            check(delta(metrics) <= delta(reference), "4K60 regression in " + counter)

        for height, width, codec in [(1080, 1920, "h264"), (1440, 2560, "h265")]:
            if not source.action(str(height)):
                save(f"skip-{height}", "M6 lacks native 119.88/120 mode")
                continue
            label = f"fixed-{height}"
            wire(label, width, height)
            try:
                board(label + "-bench.log", ["bench", str(width), str(height), "120", "capture",
                                              *(["h264", "h265"] if height == 1080 else ["h265"])], 105)
            finally:
                subprocess.run(["scp", f"vim4:{remote}/{width}-*.json", out], timeout=20, check=True)
            subprocess.run(["scp", f"vim4:{remote}/{width}.h26*", out], timeout=30, check=True)
            for path in out.glob(f"{width}-*.json"):
                data = json.loads(path.read_text())
                check(data["success"] and data["wall_fps"] >= 110, f"short HFR bench: {path.name}")
            configure(codec, 120)
            receive(label, 12, 110, (width, height), codec)
            if height == 1440:
                configure("h264", 120)
                receive("qhd-avc-limited", 10, 50, (width, height), "h264", maximum=61)
        source.action("pattern")
        wire("444", 3840, 2160)
        state = status()
        if bytes.fromhex(state["avi_packet"])[4] >> 5 == 2 and int(state["color_depth_code"], 0) in (0, 4):
            board("444-integrity.log", ["raw444"], 100)
            subprocess.run(["scp", f"vim4:{remote}/last.raw", out], timeout=25, check=True)
        else:
            save("skip-444", "source did not supply YCbCr444/8")
            if bytes.fromhex(state["avi_packet"])[4] >> 5 == 0:
                board("rgb-fallback.txt", ["rgb"])

        for mode, width, height, base in [("1080", 1920, 1080, 120), ("4k", 3840, 2160, 60)]:
            if end - time.time() < 480:
                save("skip-tail", "recovery reserve")
                break
            if not source.action(mode) or not source.variable():
                save("skip-vrr-" + mode, "source mode/Variable unavailable")
                continue
            if base == 120:
                source.action("metal1080")
                board("vrr-output-pts.txt", ["pts"], 45)
            for codec in ("h264", "h265"):
                label = f"vrr-{mode}-{codec}"
                configure(codec, 60)
                source.action("metal" + mode)
                wire(label, width, height, base)
                source.action("metal" + mode)
                with (out / (label + "-cadence.txt")).open("w") as log:
                    monitor = subprocess.Popen(["ssh", "vim4", f"for i in $(seq 1 75); do date +%s.%N; "
                                                f"sudo -n grep -E '^(vrr_|frame_ticks|vtotal|link_ready)' {RX}; sleep .5; done"],
                                               stdout=log)
                    try:
                        receive(label, 32 if base == 120 else 20, size=(width, height), codec=codec)
                    finally:
                        monitor.terminate()
                        monitor.wait(timeout=5)
        source.action("restore")
        wire("fixed-again", 3840, 2160)
        if end - time.time() > 365:
            board("loss.log", ["loss"])
            wire("relocked", 3840, 2160)
            receive("relocked", 5, 50)
    finally:
        signal.alarm(max(1, int(end - time.time() - 5)))
        try:
            if saved:
                source.restore()
        finally:
            if source:
                source.server.shutdown()
            if tunnel:
                tunnel.terminate()
                tunnel.wait(timeout=5)
            try:
                if activated:
                    try:
                        save("dmesg-candidate", ssh("sudo -n dmesg"))
                    except subprocess.SubprocessError as error:
                        save("candidate-log-unavailable", str(error))
                    try:
                        if ssh("cat /proc/sys/kernel/random/boot_id").strip() == oldboot:
                            ssh("sudo -n systemctl reboot --no-block")
                    except subprocess.SubprocessError as error:
                        # SSH can drop after systemd has accepted the reboot.
                        # The new boot ID below decides whether recovery succeeded.
                        save("reboot-transport", str(error))
                    BW["ready"]("vim4", expected=RELEASE, old_boot=oldboot, timeout=90)
                    BW["verify_baseline"](baseline, save("restored.json", BW["identity"]("vim4", files)))
                    ssh("systemctl is-active one-kvm vim4-kvm-hdmi vim4-manager vim4-kvm-gadget")
                    save("restored-exe", ssh("sha256sum /proc/$(systemctl show -p MainPID --value one-kvm)/exe"))
                    check((out / "restored-exe").read_text().split()[0] == baseline["files"][APP], "restored process mismatch")
                    save("dmesg-restored", ssh("sudo -n dmesg"))
                    ssh(f"sudo -n rm -rf -- {remote}")
                    tunnel = connect()
                    try:
                        check(api("config/video") == json.loads((out / "initial-config.json").read_text()), "video config changed")
                        check(api("stream/mode")["mode"] == json.loads((out / "initial-mode.json").read_text())["mode"], "codec changed")
                        receive("restored-4k", 6, 55, (3840, 2160))
                    finally:
                        tunnel.terminate()
                        tunnel.wait(timeout=5)
            finally:
                queue.sampling(ticket, False)
                signal.alarm(0)


if __name__ == "__main__":
    validate()
    if sys.argv[1:] == ["--execute"]:
        run()
    elif sys.argv[1:]:
        sys.exit("usage: window.py [--execute]")
    else:
        print(PHASES)
