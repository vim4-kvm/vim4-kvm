#!/usr/bin/env python3
"""Exclusive 7.3 Wave5/GStreamer EOS teardown regression on the board.

Stop all video applications first. Uses a generated pattern, not HDMI; successful
teardown does not establish capture correctness or browser playback performance.
Select the private patched V4L2 plugin with GST_PLUGIN_PATH before launching.
"""
import argparse
import gc
import json
import os
from pathlib import Path
import sys


def video_fds():
    result = []
    for path in Path('/proc/self/fd').iterdir():
        try:
            target = str(path.readlink())
        except OSError:
            continue
        if target.startswith('/dev/video'):
            result.append(target)
    return sorted(result)


def cma_free_kb():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('CmaFree:'):
            return int(line.split()[1])
    raise ValueError('CMA accounting is unavailable')


def run(args, report):
    if not args.exclusive or os.uname().release not in (
            '7.3.0-rc7-vim4kvm-uhd1+', '7.3.0-vim4kvm-uhd1+'):
        raise ValueError('requires --exclusive and the matched experimental 7.3 kernel')
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
    baseline_fds = video_fds()
    baseline_cma = cma_free_kb()
    if baseline_fds or baseline_cma < 400000:
        raise ValueError('video devices are already open or CMA is below the idle test budget')
    report.update(kernel=os.uname().release, gstreamer=Gst.version_string(),
                  baseline_cma_free_kb=baseline_cma)
    for cycle in range(args.cycles):
        for codec in args.codecs:
            pipeline = Gst.parse_launch(
                f'videotestsrc num-buffers={args.frames} ! '
                'video/x-raw,format=NV12,width=1920,height=1080,framerate=60/1 ! '
                f'v4l2{codec}enc name=encoder ! {codec}parse ! '
                'fakesink sync=false enable-last-sample=false')
            try:
                encoder = pipeline.get_by_name('encoder')
                device = Path(encoder.get_property('device'))
                name = Path('/sys/class/video4linux', device.name, 'name').read_text().strip()
                if name != 'C&M Wave5 VPU encoder':
                    raise ValueError(f'{device}: expected Wave5, got {name}')
                del encoder
                if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                    raise ValueError('encoder failed to start')
                bus = pipeline.get_bus()
                message = bus.timed_pop_filtered(args.timeout * Gst.SECOND,
                                                Gst.MessageType.EOS | Gst.MessageType.ERROR)
                if message is None:
                    raise ValueError('encoder EOS timed out')
                if message.type == Gst.MessageType.ERROR:
                    error, debug = message.parse_error()
                    raise ValueError(f'{error}: {debug}')
                del message, bus
            finally:
                pipeline.send_event(Gst.Event.new_flush_start())
                pipeline.set_state(Gst.State.NULL)
                changed, current, _ = pipeline.get_state(5 * Gst.SECOND)
                if changed == Gst.StateChangeReturn.FAILURE or current != Gst.State.NULL:
                    raise ValueError('encoder teardown did not reach NULL')
                del pipeline
                gc.collect()
            fds, free = video_fds(), cma_free_kb()
            report['runs'].append(dict(cycle=cycle, codec=codec, frames=args.frames,
                                       video_fds=fds, cma_free_kb=free))
            # Stop at the first leak, before another iteration can exhaust CMA.
            if fds != baseline_fds or free < baseline_cma - 4096:
                raise ValueError('encoder teardown retained a video fd or more than 4 MiB CMA')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclusive', action='store_true')
    parser.add_argument('--cycles', type=int, default=3)
    parser.add_argument('--frames', type=int, default=120)
    parser.add_argument('--codecs', choices=['h264', 'h265'], nargs='+', default=['h264', 'h265'])
    parser.add_argument('--timeout', type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 100 or not 60 <= args.frames <= 1000 or args.timeout <= 0:
        parser.error('cycles must be 1..100, frames 60..1000 and timeout positive')
    report = dict(runs=[], passed=False)
    try:
        run(args, report)
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
