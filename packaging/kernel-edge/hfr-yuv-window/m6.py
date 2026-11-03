"""Invoked in the M6 Terminal via One-KVM. Never run this on the receiver."""
import json
import ctypes as ct
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

root = Path(__file__).resolve().parent
os.chdir(root)
if subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip() != "Apple M6":
    sys.exit("M6 required")
displays = json.loads(subprocess.check_output(["./hdmi-source-mode", "list"]))
if len(displays) != 1 or (displays[0]["vendor"], displays[0]["model"]) != (19083, 6938):
    sys.exit("expected the single RTK UHD HDR display")
display = displays[0]
current = next(m for m in display["modes"] if m["id"] == display["current"])
saved = root / "original.json"
action = sys.argv[1]
print(json.dumps(dict(action=action, display=display["display"], current=current)))
if action == "save":
    if saved.exists() or (current["width"], current["pixelWidth"], current["pixelHeight"]) != (1920, 3840, 2160) or abs(current["hz"] - 60) > .2:
        sys.exit("expected original fixed 4K60 HiDPI")
    saved.write_text(json.dumps(current))
    sys.exit()
original = json.loads(saved.read_text())
pid = root / "source.pid"
if pid.exists():
    previous = int(pid.read_text())
    # Generators exit on their own too. Never signal a recycled PID.
    command = subprocess.run(["ps", "-p", str(previous), "-o", "command="], capture_output=True, text=True).stdout
    if command.startswith(str(root) + "/"):
        os.kill(previous, signal.SIGTERM)
    pid.unlink()
    log = (root / "last-log").read_text()
    print((root / log).read_text())

def start(name, *args, rates=""):
    with (root / (action + ".log")).open("w") as log:
        child = subprocess.Popen([root / name, *args], stdout=log, stderr=log,
                                 env=dict(os.environ, VIM4_HDMI_DISPLAY="RTK", VIM4_VRR_RATES=rates),
                                 stdin=subprocess.DEVNULL, start_new_session=True)
    pid.write_text(str(child.pid))
    (root / "last-log").write_text(action + ".log")

def set_session_mode(display_id, mode_id):
    # CGDisplaySetDisplayMode reverts as its process exits. Commit only to
    # this login session; the saved original mode uses the same restore path.
    cg = ct.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    cf = ct.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    ptr = ct.c_void_p
    key = ptr.in_dll(cg, "kCGDisplayShowDuplicateLowResolutionModes")
    yes = ptr.in_dll(cf, "kCFBooleanTrue")
    cf.CFDictionaryCreate.restype = ptr
    opts = cf.CFDictionaryCreate(None, ct.byref(key), ct.byref(yes), ct.c_long(1), None, None)
    cg.CGDisplayCopyAllDisplayModes.restype = ptr
    modes = ptr(cg.CGDisplayCopyAllDisplayModes(display_id, ptr(opts)))
    cf.CFArrayGetValueAtIndex.restype = ptr
    for i in range(cf.CFArrayGetCount(modes)):
        mode = ptr(cf.CFArrayGetValueAtIndex(modes, ct.c_long(i)))
        if cg.CGDisplayModeGetIODisplayModeID(mode) == mode_id:
            config = ptr()
            if cg.CGBeginDisplayConfiguration(ct.byref(config)):
                sys.exit("cannot begin display configuration")
            if cg.CGConfigureDisplayWithDisplayMode(config, display_id, mode, None):
                cg.CGCancelDisplayConfiguration(config)
                sys.exit("M6 rejected requested display configuration")
            if cg.CGCompleteDisplayConfiguration(config, 1):  # kCGConfigureForSession
                sys.exit("cannot apply requested mode to M6 session")
            return
    sys.exit("mode no longer listed by M6")

if action.startswith("metal"):
    start("metal-vrr", rates="120,80,60,48,120" if action == "metal1080" else "60,48,60")
elif action == "settings":
    subprocess.run(["open", "x-apple.systempreferences:com.apple.Displays-Settings.extension"], check=True)
else:
    target = original
    if action in ("1080", "1440"):
        h = int(action)
        w = {1080: 1920, 1440: 2560}[h]
        choices = [m for m in display["modes"] if m["width"] == m["pixelWidth"] == w
                   and m["pixelHeight"] == h and abs(m["hz"] - 120) <= .25]
        if not choices:
            sys.exit(77)
        target = min(choices, key=lambda m: abs(m["hz"] - 119.88))
    elif action not in ("restore", "pattern", "4k"):
        sys.exit("unknown action")
    if current["id"] != target["id"]:
        set_session_mode(display["display"], target["id"])
    for _ in range(20):
        actual, = json.loads(subprocess.check_output(["./hdmi-source-mode", "list"]))
        if actual["current"] == target["id"]:
            break
        time.sleep(.2)
    else:
        sys.exit(f"M6 mode readback {actual['current']} differs from requested {target}")
    print(json.dumps(dict(confirmed=target)))
    if action in ("1080", "1440"):
        start("latency-source", "--display-link", "--motion", "--verify-coherence", "--no-labels")
    if action == "pattern":
        start("capture-pattern")
