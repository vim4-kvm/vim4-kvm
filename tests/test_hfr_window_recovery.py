"""A partial insmod/bind failure must still reboot and verify the old runtime."""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / "packaging/kernel-edge/hfr-yuv-window"


class OverlayRecoveryTest(unittest.TestCase):
    def test_partial_activation(self):
        with patch.object(sys, "path", [str(SCRIPTS), *sys.path]):
            run = runpy.run_path(str(SCRIPTS / "window.py"))["run"]
        state = run.__globals__
        inventory = json.loads((SCRIPTS.parent / "uhd7-module-inventory.json").read_text())
        def identity(host, files):
            digests = dict.fromkeys(files, "installed")
            for mod in ("t7-hdmirx", "t7-vdin-test", "wave5"):
                entry, = [v for k, v in inventory.items() if k.endswith("/" + mod + ".ko.xz")]
                note = bytes.fromhex("040000001400000003000000474e5500" + entry["build_id"])
                digests[f"/sys/module/{mod.replace('-', '_')}/notes/.note.gnu.build-id"] = hashlib.sha256(note).hexdigest()
            return dict(release=state["RELEASE"], build_id="d6f9c685802759c85cba6bd92bce90396d1cf6ec",
                        files=digests, cmdline="reboot_mode=normal")

        def ssh(host, cmd, **kwargs):
            if "credentials.json" in cmd:
                return '{"api_key":"mock"}'
            if "mktemp" in cmd:
                return "/tmp/hfr-yuv.12345678"
            if cmd.startswith("sha256sum"):
                return "installed  /proc/123/exe"
            return "unchanged"

        def child(args, **kwargs):
            if " activate" in str(args[-1]):
                raise subprocess.CalledProcessError(1, args)
            metrics = dict(fps=60, samples=[dict(frameWidth=3840, frameHeight=2160)])
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps(metrics))

        queue = MagicMock()
        queue.read.return_value = dict(started=time.time(), who="hfr-yuv-window", seconds=1800)
        queue.status.return_value = []
        board = dict(state["BW"], require_board=lambda: (queue, "lease"), source_hdr=lambda host: False,
                     identity=identity, ssh=MagicMock(side_effect=ssh), ready=MagicMock(), sha=lambda path: "mock")
        tunnel = MagicMock()
        tunnel.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "logs").mkdir()
            with patch.dict(state, ROOT=root, BW=board, Source=MagicMock(),
                            api=lambda path: {"mode": "h265", "status": {"connection_count": 0, "sessions": []}}), \
                 patch("subprocess.Popen", return_value=tunnel), patch("subprocess.run", side_effect=child), \
                 patch("subprocess.check_output", return_value="192.0.2.1"), patch("time.sleep"), \
                 patch("signal.signal"), patch("signal.alarm"), self.assertRaises(subprocess.CalledProcessError):
                run()
            evidence, = (root / "logs").iterdir()
            self.assertTrue((evidence / "restored-4k-receiver.json").is_file())
        reboots = [c for c in board["ssh"].call_args_list if "systemctl reboot" in c.args[1]]
        self.assertEqual(len(reboots), 1)
        board["ready"].assert_called_once_with("vim4", expected=state["RELEASE"], old_boot="unchanged", timeout=90)
        queue.sampling.assert_called_with("lease", False)
