#!/usr/bin/env python3
"""Run a shell command on VIM4 over the serial console and print its output.

Usage: tools/uart-run.py [-d /dev/cu.usbserial-100] [-t seconds] 'command'
"""
import argparse, fcntl, os, re, select, struct, sys, termios, time, uuid

IOSSIOSPEED = 0x80045402


def open_port(dev, baud):
    fd = os.open(dev, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    # All project UART tools share this advisory lock. External terminals must close.
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    a = termios.tcgetattr(fd)
    a[0] = a[1] = a[3] = 0
    a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    termios.tcsetattr(fd, termios.TCSANOW, a)
    if sys.platform == "darwin":
        fcntl.ioctl(fd, IOSSIOSPEED, struct.pack("L", baud))
    else:
        speed = getattr(termios, f"B{baud}")
        a[4] = a[5] = speed
        termios.tcsetattr(fd, termios.TCSANOW, a)
    return fd


def read_until(fd, marker, timeout):
    buf, end = b"", time.monotonic() + timeout
    while time.monotonic() < end and marker not in buf:
        if select.select([fd], [], [], 0.2)[0]:
            try:
                buf += os.read(fd, 65536)
            except BlockingIOError:
                pass
    return buf


def read_result(fd, done, timeout):
    buf, end = b"", time.monotonic() + timeout
    pattern = re.compile(rb"\n" + done.encode() + rb":\d+\r?\n")
    while time.monotonic() < end and not pattern.search(buf):
        if select.select([fd], [], [], 0.2)[0]:
            try:
                buf += os.read(fd, 65536)
            except BlockingIOError:
                pass
    return buf


def parse_result(out, begin, done):
    out = out.replace("\r\n", "\n")
    start = out.find(begin + "\n")
    match = re.search(r"(?:^|\n)" + re.escape(done) + r":(\d+)\n", out)
    if start < 0 or match is None:
        raise TimeoutError("UART command completion unknown; do not retry or send another command until the console is idle")
    return out[start + len(begin) + 1:match.start()].rstrip(), int(match[1])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-d", "--device", default="/dev/cu.usbserial-100")
    p.add_argument("-b", "--baud", type=int, default=921600)
    p.add_argument("-t", "--timeout", type=float, default=15)
    p.add_argument("command")
    args = p.parse_args()

    fd = open_port(args.device, args.baud)
    tag = uuid.uuid4().hex[:8]
    begin, done = f"__B{tag}__", f"__E{tag}__"
    read_until(fd, b"\x00", 0.3)
    cmd = f"stty -echo 2>/dev/null; echo {begin}; ( {args.command} ) 2>&1; printf '\\n{done}:%s\\n' $?; stty echo 2>/dev/null\n"
    os.write(fd, cmd.encode())
    # Read through the status line, not the echoed command containing the marker.
    out = read_result(fd, done, args.timeout)
    out = out.decode("utf-8", "replace")
    os.close(fd)
    try:
        output, status = parse_result(out, begin, done)
    except TimeoutError as exc:
        print(out, file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 124
    print(output)
    return status


if __name__ == "__main__":
    sys.exit(main())
