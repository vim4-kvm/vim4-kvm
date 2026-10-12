#!/usr/bin/env python3
"""Capture the VIM4 serial console to a file (and stdout) without sending anything.

Usage: tools/uart-log.py [-d /dev/cu.usbserial-100] [-t seconds] [-o logs/uart0.log] [--send 'reboot']
"""
import argparse, os, select, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
uart_run = __import__("uart-run")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-d", "--device", default="/dev/cu.usbserial-100")
    p.add_argument("-b", "--baud", type=int, default=921600)
    p.add_argument("-t", "--timeout", type=float, default=0, help="stop after N seconds (0 = forever)")
    p.add_argument("-o", "--output", default="logs/uart0.log")
    p.add_argument("--send", help="line to send once the port is open, e.g. 'sync; reboot'")
    p.add_argument("-q", "--quiet", action="store_true", help="do not echo to stdout")
    args = p.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    fd = uart_run.open_port(args.device, args.baud)
    if args.send:
        os.write(fd, f"\n{args.send}\n".encode())
    end = time.time() + args.timeout if args.timeout else None
    with open(args.output, "ab") as f:
        try:
            while end is None or time.time() < end:
                if select.select([fd], [], [], 0.5)[0]:
                    try:
                        data = os.read(fd, 65536)
                    except BlockingIOError:
                        continue
                    f.write(data)
                    f.flush()
                    if not args.quiet:
                        sys.stdout.buffer.write(data)
                        sys.stdout.flush()
        except KeyboardInterrupt:
            pass
    os.close(fd)


if __name__ == "__main__":
    main()
