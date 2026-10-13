#!/usr/bin/env python3
"""Summarize one VIM4_VIDEO_TIMING capture session (times in milliseconds).

Usage: video-timing-summary.py APPLICATION_LOG CAPTURE_LOG
The capture log also needs GST_DEBUG=vfmcapsrc:4. Do not combine restarted
pipelines: PTS and the consumer sequence can restart at zero.
"""
import argparse
import json
import math
import re
import statistics
from pathlib import Path

READ = re.compile(r'timing read pts_ns=(\d+) capture_to_copy_ms=(-?[\d.]+) copy_to_read_ms=([\d.]+) bytes=(\d+) key=(true|false)')
SEND = re.compile(r'timing send pts_ns=(\d+) send_ms=([\d.]+) bytes=(\d+) viewers=(\d+)')
CAPTURE = re.compile(r'delivery_to_dequeue_ms=([\d.]+) sequence=(\d+)')


def distribution(values):
    values = sorted(values)
    if not values:
        return None
    return dict(count=len(values), median=statistics.median(values),
                p99=values[math.ceil(len(values) * .99) - 1], maximum=values[-1])


def summarize(application, capture, warmup_seconds=6, warmup_frames=360):
    reads, samples, sequences, dequeue = {}, [], [], []
    last_pts = -1
    for line in application.splitlines():
        match = READ.search(line)
        if match:
            pts = int(match[1])
            if pts <= last_pts:
                raise ValueError('Repeated/restarted PTS; supply exactly one capture session')
            last_pts = pts
            if pts >= warmup_seconds * 1e9:
                reads[pts] = (float(match[2]), float(match[3]), int(match[4]), match[5] == 'true')
        match = SEND.search(line)
        if match and int(match[1]) in reads and int(match[4]) == 1:
            read = reads.pop(int(match[1]))
            if read[2] != int(match[3]):
                raise ValueError('Read/send byte count mismatch')
            samples.append((*read, float(match[2])))
    if not samples:
        raise ValueError('No matched single-viewer frames after warmup')
    for line in capture.splitlines():
        match = CAPTURE.search(line)
        if match:
            sequence = int(match[2])
            if sequences and sequence <= sequences[-1]:
                raise ValueError('Repeated/restarted sequence; split the capture log')
            sequences.append(sequence)
            if sequence >= warmup_frames:
                dequeue.append(float(match[1]))
    if not dequeue:
        raise ValueError('No capture timing records after warmup')
    return dict(
        source_to_copy_ms=distribution(s[0] for s in samples if s[0] >= 0),
        copy_to_read_ms=distribution(s[1] for s in samples),
        send_key_ms=distribution(s[4] for s in samples if s[3]),
        send_nonkey_ms=distribution(s[4] for s in samples if not s[3]),
        key_bytes=distribution(s[2] for s in samples if s[3]),
        send_key_us_per_KB=distribution(s[4] * 1e6 / s[2] for s in samples if s[3] and s[2]),
        delivery_to_dequeue_ms=distribution(dequeue),
        delivery_sequence_gaps=sum(b - a - 1 for a, b in zip(sequences, sequences[1:])),
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('application', type=Path)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--warmup-seconds', type=float, default=6)
    parser.add_argument('--warmup-frames', type=int, default=360,
                        help='Capture warmup deliveries (360 assumes 60fps)')
    args = parser.parse_args()
    if args.warmup_seconds < 0 or args.warmup_frames < 0:
        parser.error('Warmup values must be nonnegative')
    print(json.dumps(summarize(args.application.read_text(), args.capture.read_text(),
                               args.warmup_seconds, args.warmup_frames), indent=2))
