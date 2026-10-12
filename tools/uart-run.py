#!/usr/bin/env python3
"""Run a shell command on VIM4 over the serial console and print its output.

Usage: tools/uart-run.py [-d /dev/cu.usbserial-100] [-t seconds] 'command'
"""
import argparse, fcntl, os, select, struct, termios, time, uuid

IOSSIOSPEED = 0x80045402


def open_port(dev, baud):
    fd = os.open(dev, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    a = termios.tcgetattr(fd)
    a[0] = a[1] = a[3] = 0
    a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    termios.tcsetattr(fd, termios.TCSANOW, a)
    fcntl.ioctl(fd, IOSSIOSPEED, struct.pack("L", baud))
    return fd


def read_until(fd, marker, timeout):
    buf, end = b"", time.time() + timeout
    while time.time() < end and marker not in buf:
        if select.select([fd], [], [], 0.2)[0]:
            try:
                buf += os.read(fd, 65536)
            except BlockingIOError:
                pass
    return buf


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
    cmd = f"stty -echo 2>/dev/null; echo {begin}; ( {args.command} ) 2>&1; echo {done}; stty echo 2>/dev/null\n"
    os.write(fd, cmd.encode())
    out = read_until(fd, done.encode() + b"\r\n", args.timeout).decode("utf-8", "replace")
    os.close(fd)
    start = out.rfind(begin + "\r\n")
    stop = out.rfind(done)
    print(out[start + len(begin) + 2 : stop if stop > start else None].replace("\r\n", "\n").rstrip())


if __name__ == "__main__":
    main()
