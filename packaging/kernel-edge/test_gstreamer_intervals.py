#!/usr/bin/env python3
"""Check actual downstream pad caps with the pinned v4l2src and ioctl fixtures."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    plugin = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        shim = Path(tmp) / "capture.so"
        subprocess.run(["cc", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared",
                        Path(__file__).with_name("test-vdin-ioctl.c"), "-o", shim], check=True)
        env = dict(os.environ, GST_REGISTRY=f"{tmp}/registry", GST_PLUGIN_PATH=str(plugin.parent),
                   LD_PRELOAD=str(shim), LC_ALL="C")
        inspect = subprocess.check_output(["gst-inspect-1.0", "v4l2src"], env=env, text=True)
        assert str(plugin) in inspect and "1.24.2" in inspect, inspect
        formats = ["NV12"]
        if "v308" in inspect or "--v308" in sys.argv[2:]:
            formats.append("v308")
        for fmt in formats:
            if fmt == "v308":
                env["TEST_V308"] = "1"
            for ticks, base, fps, maximum in [(1000, 0, "60/1", 0), (1001, 0, "60000/1001", 0),
                                              (1224, 120, "0/1", 120), (1224, 60, "0/1", 60),
                                              (1224, -1, "0/1", 120)]:
                env.update(TEST_TICKS=str(ticks), TEST_VRR_BASE=str(base))
                output = subprocess.check_output(
                    ["gst-launch-1.0", "-v", "v4l2src", "device=/dev/zero", "io-mode=rw",
                     "num-buffers=2", "!", f"video/x-raw,format={fmt}", "!", "fakesink"],
                    env=env, text=True, timeout=10)
                caps = next(line for line in output.splitlines() if "GstFakeSink:" in line and "caps =" in line)
                fields = caps.split(", ")
                assert f"framerate=(fraction){fps}" in fields, caps
                if maximum:
                    assert f"max-framerate=(fraction){maximum}/1" in fields, caps
                else:
                    assert "max-framerate=" not in caps, caps
                print(fmt, ticks, base, caps.split("caps = ")[1])


if __name__ == "__main__":
    main()
