#!/usr/bin/env python3
"""Split 7.x JPEG ioctls using one recorded, tightly packed NV12 frame.

Requires exclusive access and a stopped one-kvm-edge service. No capture,
network or GStreamer is involved. Writes a new JSON report and first JPEG;
hashing is outside the individual phase timers but included in wall FPS.
This diagnostic uses the driver's input allocation, not live DMA import.
"""
from array import array
import argparse
import fcntl
import hashlib
import json
import math
import mmap
import os
from pathlib import Path
import select
import statistics
import subprocess
import time


def ioctl(fd, number, payload=0):
    return fcntl.ioctl(fd, 0x40044a00 | number, payload)


def distribution(values):
    ordered = sorted(values)
    return dict(median_ms=statistics.median(ordered),
                p95_ms=ordered[math.ceil(len(ordered) * .95) - 1],
                max_ms=ordered[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclusive', action='store_true', required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--width', type=int, default=3840)
    parser.add_argument('--height', type=int, default=2160)
    parser.add_argument('--quality', type=int, default=80)
    parser.add_argument('--frames', type=int, default=120)
    parser.add_argument('--warmup', type=int, default=10)
    parser.add_argument('--no-copy-output', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not (16 <= args.width <= 4096 and args.width % 32 == 0 and
            16 <= args.height <= 2160 and args.height % 2 == 0 and
            1 <= args.quality <= 100 and 2 <= args.frames <= 1800 and
            1 <= args.warmup <= 120):
        parser.error('Invalid geometry, quality or frame limits; width must align to 32')
    if not os.uname().release.startswith('7.'):
        parser.error('Requires the experimental 7.x kernel')
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'one-kvm-edge']).returncode == 0:
        parser.error('Stop one-kvm-edge before taking exclusive video access')
    source = args.input.read_bytes()
    if len(source) != args.width * args.height * 3 // 2:
        parser.error('Input must contain exactly one tightly packed NV12 frame')
    report = args.output.open('x')
    fd = None
    mapping = None
    try:
        fd = os.open('/dev/jpegenc', os.O_RDWR | os.O_CLOEXEC)
        info = array('I', [0] * 7)
        ioctl(fd, 0, info)
        for offset, size in zip(info[1::2], info[2::2]):
            if offset > info[0] or size > info[0] - offset:
                raise RuntimeError('Driver returned an invalid mapping layout')
        if len(source) > info[2]:
            raise RuntimeError('Recorded input exceeds the driver allocation')
        mapping = mmap.mmap(fd, info[0], flags=mmap.MAP_SHARED,
                            prot=mmap.PROT_READ | mmap.PROT_WRITE)
        mapping[info[1]:info[1] + len(source)] = source
        ioctl(fd, 1)
        command = array('I', [0] * 30)
        command[1:6] = array('I', [3, 4, args.width, args.height, len(source)])
        command[7], command[9] = args.quality, 3
        command[11:15] = array('I', [args.width] * 3 + [args.height])
        poller = select.poll()
        poller.register(fd, select.POLLIN)
        samples = {name: [] for name in ('command', 'wait', 'output_ioctl', 'copy', 'total')}
        hashes = set()
        first_image = None
        wall_start = None
        for index in range(args.warmup + args.frames):
            if index == args.warmup:
                wall_start = time.perf_counter()
            start = time.perf_counter_ns()
            ioctl(fd, 2, command)
            submitted = time.perf_counter_ns()
            events = poller.poll(1000)
            ready = time.perf_counter_ns()
            if not events or not events[0][1] & select.POLLIN:
                raise RuntimeError('JPEG completion timed out or failed')
            sizes = array('I', [0, 0])
            ioctl(fd, 4, sizes)
            finished = time.perf_counter_ns()
            if not (0 < sizes[0] <= info[4] and 0 < sizes[1] <= info[6]):
                raise RuntimeError('Invalid compressed output lengths')
            image = None
            if not args.no_copy_output:
                image = (mapping[info[3]:info[3] + sizes[0]] +
                         mapping[info[5]:info[5] + sizes[1]])
            copied = time.perf_counter_ns()
            if index >= args.warmup:
                for name, duration in zip(samples, (submitted - start, ready - submitted,
                        finished - ready, copied - finished, copied - start)):
                    samples[name].append(duration / 1e6)
                if image is not None:
                    if image[:2] != b'\xff\xd8' or image[-2:] != b'\xff\xd9':
                        raise RuntimeError('Incomplete JPEG')
                    hashes.add(hashlib.sha256(image).hexdigest())
                    if first_image is None:
                        first_image = image
        elapsed = time.perf_counter() - wall_start
        if hashes and len(hashes) != 1:
            raise RuntimeError('Repeated identical input produced different JPEG data')
        result = dict(width=args.width, height=args.height, quality=args.quality,
                      frames=args.frames, warmup=args.warmup, copy_output=not args.no_copy_output,
                      input_sha256=hashlib.sha256(source).hexdigest(),
                      output_sha256=next(iter(hashes), None),
                      wall_fps=args.frames / elapsed,
                      phases={name: distribution(values) for name, values in samples.items()},
                      clock_hz=Path('/sys/kernel/debug/clk/hcodec/clk_rate').read_text().strip(),
                      kernel=os.uname().release)
        if first_image is not None:
            with args.output.with_suffix('.jpg').open('xb') as image_file:
                image_file.write(first_image)
        json.dump(result, report, indent=2)
        report.write('\n')
        print(json.dumps(result))
    finally:
        if mapping is not None:
            mapping.close()
        if fd is not None:
            os.close(fd)
        report.close()


if __name__ == '__main__':
    main()
