#!/usr/bin/env python3
"""Bounded AMLY→GPU→P010 measurement inside an exclusive board window.

Use the candidate's private GStreamer and explicit Vulkan ICD environment.
Stop capture consumers first. No service changes, HID, CPU pixel mapping,
encoder, network or browser are involved. Requires Python GI/GStreamer.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import time


def metrics(timestamps):
    intervals = sorted((b - a) / 1e6 for a, b in zip(timestamps, timestamps[1:]))
    if not intervals or intervals[0] <= 0:
        raise ValueError('Need at least two strictly increasing frame timestamps')
    return dict(frames=len(timestamps),
                fps=(len(timestamps) - 1) * 1e9 / (timestamps[-1] - timestamps[0]),
                p99_ms=intervals[math.ceil(len(intervals) * .99) - 1],
                max_ms=intervals[-1])


def gpu_counters():
    # Own-process DRM fdinfo is the standard per-client counter interface.
    # Preserve raw fields: drivers differ in exposed engines/time units, and
    # multiple fds can share one drm-client-id. Missing counters are not zero.
    clients = []
    for path in Path('/proc/self/fdinfo').iterdir():
        try:
            fields = [line for line in path.read_text().splitlines() if line.startswith('drm-')]
        except FileNotFoundError:
            continue
        if fields:
            clients.append(dict(fd=path.name, fields=fields))
    frequency = Path('/sys/class/devfreq/fe400000.gpu/cur_freq')
    return dict(time_ns=time.monotonic_ns(), clients=clients,
                frequency_hz=int(frequency.read_text()) if frequency.exists() else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--frames', type=int, default=300)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.execute or not 2 <= args.frames <= 600:
        parser.error('Requires --execute inside a board window, 2–600 frames')
    if args.output.exists():
        parser.error('Use a new output file')
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'one-kvm']).returncode == 0:
        parser.error('Stop One-KVM and other capture consumers first')
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
    pipeline = Gst.parse_launch(
        f'vim4amlysrc name=source num-buffers={args.frames} ! fakesink sync=false')
    timestamps, counters = [], []

    def frame(pad, info):
        now = time.monotonic_ns()
        timestamps.append(now)
        if not counters or now - counters[-1]['time_ns'] >= 1_000_000_000:
            counters.append(gpu_counters())
        return Gst.PadProbeReturn.OK

    pipeline.get_by_name('source').get_static_pad('src').add_probe(Gst.PadProbeType.BUFFER, frame)
    result = dict(endpoint='GPU P010 source pad', timestamps_ns=timestamps, gpu_counters=counters)
    try:
        pipeline.set_state(Gst.State.PLAYING)
        message = pipeline.get_bus().timed_pop_filtered(
            30 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
        if message is None:
            raise RuntimeError('GPU source timed out after 30 seconds')
        if message.type == Gst.MessageType.ERROR:
            raise RuntimeError(str(message.parse_error()))
        if len(timestamps) != args.frames:
            raise RuntimeError('GPU source returned an incomplete frame count')
        result.update(metrics(timestamps))
        result['complete'] = True
    finally:
        pipeline.set_state(Gst.State.NULL)
        args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
