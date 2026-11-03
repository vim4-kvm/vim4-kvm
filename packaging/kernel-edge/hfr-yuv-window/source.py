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
        self.mcp.call(name, args, deadline=time.monotonic() + 12)

    def shell(self, command, timeout=25):
        ticket = secrets.token_hex(8)
        self.acks[ticket] = None
        log = "/tmp/hfr-receipt-" + ticket
        command = (f' ({command}) >{log} 2>&1; r=$?; curl -fsS --max-time 8 '
                   f'--data-binary @{log} {self.url}/done/{ticket}/$r; rm -f {log}')
        self.call("type", text=command)
        self.call("key", text="Return")
        end = time.monotonic() + timeout
        while self.acks[ticket] is None:
            if time.monotonic() >= end:
                raise TimeoutError("M6 did not acknowledge the MCP command")
            time.sleep(.2)
        return self.acks.pop(ticket)

    def open_terminal(self):
        for name, text in [("key", "Escape"), ("key", "super+alt+space"),
                           ("key", "super+shift+g"), ("type", "/System/Applications/Utilities/Terminal.app"),
                           ("key", "Return"), ("key", "super+o")]:
            self.call(name, text=text)
            time.sleep(.6)
        self.call("key", text="super+n")
        time.sleep(.7)
        if not any(r["label"] == "Terminal" for r in self.labels()):
            raise RuntimeError("MCP screenshot did not identify Terminal")

    def bootstrap(self, sha, gadget_ids):
        # The cable assignment is M6. Cross-check the receiving Mac's USB
        # tree before even the first Finder shortcut, while HID is still idle.
        vendor, product = (int(value, 16) for value in gadget_ids.split())
        nodes = plistlib.loads(subprocess.check_output(["ioreg", "-a", "-p", "IOUSB", "-l"], timeout=8))
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
        if self.shell(cmd + " waitpid=$!"):
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
        return json.loads(subprocess.check_output([self.build / "labels", path], timeout=8))

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
