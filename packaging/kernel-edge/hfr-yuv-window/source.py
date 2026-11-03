"""M6 actions go exclusively through the board's One-KVM MCP session."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import plistlib
import re
import secrets
import shlex
import subprocess
import threading
import time


class Source:
    def __init__(self, mcp, build, evidence, ip):
        self.mcp = mcp
        self.build = build
        self.evidence = evidence
        self.root = "/tmp/hfr-" + secrets.token_hex(8)
        self.acks = {}
        self.input_switched = False
        self.fallback = threading.Event()
        fallback = self.fallback
        self.fallback_path = "/restore-" + secrets.token_hex(8)
        fallback_path = self.fallback_path
        receipts = self.acks

        class Handler(SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == fallback_path:
                    self.send_response(200 if fallback.is_set() else 409)
                    self.end_headers()
                    return
                if self.path == "/source.tar":
                    return super().do_GET()
                self.send_error(404)

            def do_POST(self):
                match = re.fullmatch(r"/done/([0-9a-f]{16})/(\d+)", self.path)
                length = int(self.headers.get("Content-Length", "0"))
                if match and match[1] in receipts and 0 <= length <= 2_000_000:
                    (evidence / ("m6-" + match[1] + ".log")).write_bytes(self.rfile.read(length))
                    receipts[match[1]] = int(match[2])
                    self.send_response(204)
                    self.end_headers()
                else:
                    self.send_error(404)

        self.server = ThreadingHTTPServer((ip, 0), functools.partial(Handler, directory=build))
        self.url = f"http://{ip}:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def call(self, name, **args):
        self.mcp.call(name, args, deadline=time.monotonic() + (45 if name == "type" else 12))

    def shell(self, command, timeout=25):
        ticket = secrets.token_hex(8)
        self.acks[ticket] = None
        log = "/tmp/hfr-receipt-" + ticket
        command = (f' ({command}) >{log} 2>&1; r=$?; curl -fsS --max-time 8 '
                   f'--data-binary @{log} "{self.url}/done/{ticket}/$r" ; rm -f {log}')
        self.call("type", text=command)
        self.call("key", text="Return")
        end = time.monotonic() + timeout
        while self.acks[ticket] is None:
            if time.monotonic() >= end:
                raise TimeoutError("M6 did not acknowledge the MCP command")
            time.sleep(.2)
        return self.acks.pop(ticket)

    def open_terminal(self):
        # M6 fixed 4K60: MCP's 1920x1080 image shows Terminal in the Dock.
        # Confirm the hover label before clicking and the menu before typing.
        icon = [1205, 1044]
        self.call("mouse_move", coordinate=icon)
        time.sleep(1)
        if not any("Terminal" in r["label"] and abs(r["x"] - icon[0]) < 90 and
                   930 < r["y"] < icon[1] for r in self.labels()):
            raise RuntimeError("M6 Terminal Dock tooltip not identified")
        self.call("left_click", coordinate=icon)
        time.sleep(.7)
        if not any("Terminal" in r["label"] and r["y"] < 25 and r["x"] < 160 for r in self.labels()):
            raise RuntimeError("MCP screenshot did not identify Terminal")
        self.call("key", text="super+n")
        time.sleep(.7)

    def english_input(self):
        # Probe in our own blank Terminal without submitting a shell command.
        # A prior Terminal may still be visible behind ours. Its prompt or
        # shell-history suggestions are not evidence for the active input.
        marker = "vanilla keyboard " + str(100000 + secrets.randbelow(900000))
        self.call("type", text=marker + " ")
        time.sleep(.4)
        try:
            return any(marker in r["label"].lower() for r in self.labels())
        finally:
            # Cancel the entire unsubmitted line, including any composed text
            # left by the M6 input method before switching to English.
            self.call("key", text="ctrl+c")

    def bootstrap(self, sha, gadget_ids):
        # The cable assignment is M6. Cross-check the receiving Mac's USB
        # tree before even the first Finder shortcut, while HID is still idle.
        vendor, product = (int(value, 16) for value in gadget_ids.split())
        tree = plistlib.loads(subprocess.check_output(["ioreg", "-a", "-p", "IOUSB", "-l"], timeout=8))
        nodes = [tree] if isinstance(tree, dict) else tree
        devices = []
        while nodes:
            node = nodes.pop()
            nodes.extend(node.get("IORegistryEntryChildren", []))
            if "idVendor" in node:
                devices.append((node["idVendor"], node.get("idProduct")))
        if not devices or (vendor, product) in devices:
            raise RuntimeError("unable to exclude the receiving Mac as the USB HID target")
        if not self.mcp.idle(self.evidence)["idle"]:
            raise RuntimeError("M6 screen is active, deferring HID")
        self.open_terminal()
        if not self.english_input():
            self.call("key", text="ctrl+space")
            self.input_switched = True
            time.sleep(.7)
            if not self.english_input():
                raise RuntimeError("M6 English input could not be verified")
        r = self.root
        command = (f'test "$(sysctl -n machdep.cpu.brand_string)" = "Apple M6" && '
                   f'umask 077 && mkdir {r} && cd {r} && curl -fsS {self.url}/source.tar -o s.tar && '
                   f'echo "{sha}  s.tar" | shasum -a 256 -c - && tar xf s.tar && python3 m6.py save')
        if self.shell(command):
            raise RuntimeError("M6 model, display or initial mode mismatch")
        # Independent fallback if video/HID disappears while changing modes.
        guard = (f'cd {r} || exit 1; end=$(($(date +%s)+1420)); '
                 f'while test ! -e done && test $(date +%s) -lt $end; do '
                 f'curl -fs --max-time 2 {self.url}{self.fallback_path} && break; sleep 2; done; '
                 'test -e done || python3 m6.py restore')
        cmd = f'nohup sh -c {shlex.quote(guard)} </dev/null >{r}/guard.log 2>&1 &'
        if self.shell(cmd):
            raise RuntimeError("M6 fallback did not start")

    def action(self, action):
        result = self.shell(f'cd {self.root} && python3 m6.py {shlex.quote(action)}')
        if result == 77:
            return False
        if result:
            raise RuntimeError(f"M6 {action} exited {result}")
        return True

    def labels(self):
        path = self.evidence / f"mcp-{time.time_ns()}.jpg"
        self.mcp.screenshot(path, deadline=time.monotonic() + 12)
        return json.loads(subprocess.check_output([self.build / "labels", path], timeout=30))

    def variable(self):
        self.action("settings")
        time.sleep(1)
        rows = self.labels()
        try:
            if not any("RTK" in row["label"] for row in rows):
                raise RuntimeError("cannot identify the RTK display in Settings")
            rate = next((r for r in rows if r["label"].lower() == "refresh rate"), None)
            if not rate:
                display = next(r for r in rows if "RTK" in r["label"])
                self.call("scroll", scroll_direction="down", scroll_amount=7,
                          coordinate=[display["x"], display["y"]])
                time.sleep(.5)
                rows = self.labels()
                rate = next((r for r in rows if r["label"].lower() == "refresh rate"), None)
                if not rate:
                    raise RuntimeError("refresh rate selector not visible")
            values = [r for r in rows if abs(r["y"] - rate["y"]) < 15 and r["x"] > rate["x"]
                      and re.search(r"hertz|\bhz\b", r["label"], re.I)]
            if len(values) != 1:
                raise RuntimeError("ambiguous refresh rate selector")
            self.call("left_click", coordinate=[values[0]["x"], values[0]["y"]])
            time.sleep(.5)
            menu = self.labels()
            variable = next((r for r in menu if "variable" in r["label"].lower()), None)
            if not variable:
                self.call("key", text="Escape")
                return False
            self.call("left_click", coordinate=[variable["x"], variable["y"]])
            time.sleep(1)
            if not any("variable" in r["label"].lower() for r in self.labels()):
                raise RuntimeError("Variable selection not visible after click")
            return True
        finally:
            self.call("key", text="super+h")

    def restore(self):
        try:
            if not self.action("restore") or self.shell(f"touch {self.root}/done"):
                raise RuntimeError("M6 restoration failed")
        except Exception:
            self.fallback.set()
            time.sleep(4)
            raise
