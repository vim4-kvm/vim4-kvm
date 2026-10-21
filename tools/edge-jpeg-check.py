#!/usr/bin/env python3
"""Exclusive 7.x board check: VDIN scaling, DMA JPEG and repeated teardown.

Stop one-kvm-edge first, select its private plugins with GST_PLUGIN_PATH, then
run with --exclusive. Saves first/last JPEGs; a separate moving HDMI source is
needed to verify scene coverage/content progression. This measures the Python
observer pipeline, not an isolated encoder throughput benchmark.
"""
import argparse
import gc
import json
import os
from pathlib import Path
import subprocess
import time


def resources():
    dma = Path('/sys/kernel/debug/dma_buf/bufinfo').read_text().splitlines()
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    irqs = [line.split(':', 1)[1].split() for line in Path('/proc/interrupts').read_text().splitlines()
            if line.endswith('t7-jpeg')]
    count = sum(int(value) for row in irqs for value in row if value.isdecimal())
    return dict(cma_free_kib=int(memory['CmaFree'].split()[0]),
                dma_summary=dma[-1], jpeg_irqs=count,
                taint=int(Path('/proc/sys/kernel/tainted').read_text()))


def measure(Gst, device, width, height, quality, frames, directory):
    pipeline = Gst.parse_launch(
        f'v4l2src name=source io-mode=dmabuf ! '
        f'video/x-raw,format=NV12,width={width},height={height},framerate=60/1 ! '
        f'vim4jpegenc quality={quality} ! '
        'appsink name=frames sync=false max-buffers=1 drop=true enable-last-sample=false')
    pipeline.get_by_name('source').set_property('device', str(device))
    sink = pipeline.get_by_name('frames')
    times, sizes = [], []
    before = resources()
    sample = buffer = None
    try:
        if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError('Cannot start capture/JPEG pipeline')
        for index in range(frames):
            sample = sink.try_pull_sample(3 * Gst.SECOND)
            if sample is None:
                message = pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR)
                raise RuntimeError(str(message.parse_error()) if message else 'No hardware JPEG frame')
            buffer = sample.get_buffer()
            jpeg = buffer.extract_dup(0, buffer.get_size())
            assert jpeg[:2] == b'\xff\xd8' and jpeg[-2:] == b'\xff\xd9', 'Incomplete JPEG'
            caps = sample.get_caps().get_structure(0)
            assert caps.get_value('width') == width and caps.get_value('height') == height
            times.append(time.monotonic())
            sizes.append(len(jpeg))
            if index in (0, frames - 1):
                (directory / f'{width}x{height}-q{quality}-{index}.jpg').write_bytes(jpeg)
            sample = buffer = None
    finally:
        sample = buffer = None
        pipeline.set_state(Gst.State.NULL)
        pipeline.get_state(3 * Gst.SECOND)
        sink = pipeline = None
        gc.collect()
    after = resources()
    assert after['taint'] == before['taint'] == 0
    assert after['dma_summary'] == before['dma_summary'] == 'Total 0 objects, 0 bytes'
    assert after['cma_free_kib'] >= before['cma_free_kib'] - 1024, 'CMA did not return after teardown'
    assert after['jpeg_irqs'] - before['jpeg_irqs'] >= frames, 'JPEG hardware IRQs did not advance'
    elapsed = times[-1] - times[10]
    row = dict(width=width, height=height, quality=quality, frames=frames,
               fps=(len(times) - 11) / elapsed,
               average_jpeg_bytes=sum(sizes[11:]) / len(sizes[11:]),
               max_gap_ms=max(b - a for a, b in zip(times[10:], times[11:])) * 1000,
               before=before, after=after)
    print(json.dumps(row), flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclusive', action='store_true', required=True)
    parser.add_argument('--frames', type=int, default=180)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.frames < 30 or args.frames > 1800:
        parser.error('frames must be 30..1800')
    assert os.uname().release.startswith('7.'), 'Requires the experimental kernel'
    assert subprocess.run(['systemctl', 'is-active', '--quiet', 'one-kvm-edge']).returncode != 0, \
        'Stop one-kvm-edge before taking exclusive video access'
    devices = [path.parent for path in Path('/sys/class/video4linux').glob('*/name')
               if path.read_text().strip() == 't7-vdin-test']
    assert len(devices) == 1 and Path('/dev/jpegenc').exists()
    args.output.mkdir(parents=True, exist_ok=False)
    import gi
    gi.require_version('Gst', '1.0')
    gi.require_version('GstApp', '1.0')
    from gi.repository import Gst, GstApp  # noqa: F401; installs AppSink Python methods
    Gst.init(None)
    rows = []
    for width, height, quality in [(3840, 2160, 50), (3840, 2160, 80), (3840, 2160, 100),
                                   (1920, 1080, 80), (1280, 720, 80), (3840, 2160, 80)]:
        rows.append(measure(Gst, Path('/dev') / devices[0].name, width, height, quality,
                            args.frames, args.output))
    for image in args.output.glob('*.jpg'):
        subprocess.run(['gst-launch-1.0', '-q', 'filesrc', f'location={image}', '!',
                        'jpegdec', '!', 'fakesink'], check=True, timeout=5)
    (args.output / 'metrics.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps(dict(passed=True, decoded_saved_frames=True, cycles=len(rows))), flush=True)


if __name__ == '__main__':
    main()
