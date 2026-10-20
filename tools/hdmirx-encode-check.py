#!/usr/bin/env python3
"""Capture experimental HDMI DMA-bufs into software H.264, or verify that video.

Board (exclusive): capture --exclusive --output NEW.mkv --frames 180
Mac/Linux: verify NEW.mkv --frames 180
Capture requires Python GI/GStreamer, GstAllocators and OpenH264. Verify requires
ffmpeg/ffprobe. This does not exercise the T7 hardware encoder or measure latency.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def read_frame(stream, size):
    """Return a complete raw frame, None at clean EOF, or reject a truncated one."""
    parts = []
    remaining = size
    while remaining:
        part = stream.read(remaining)
        if not part:
            if not parts:
                return None
            raise ValueError(f'truncated decoded frame: missing {remaining} bytes')
        parts.append(part)
        remaining -= len(part)
    return b''.join(parts)


def capture(args):
    if not args.exclusive:
        raise ValueError('capture requires --exclusive and an idle experimental board')
    device = args.device.resolve()
    name = Path('/sys/class/video4linux', device.name, 'name').read_text().strip()
    if name != 't7-vdin-test':
        raise ValueError(f'{device}: expected t7-vdin-test, got {name}')
    output = args.output.resolve()
    report_path = output.with_suffix(output.suffix + '.json')
    if output.exists() or report_path.exists() or not output.parent.is_dir():
        raise ValueError('output and report must be new files in an existing directory')

    import gi
    gi.require_version('Gst', '1.0')
    gi.require_version('GstAllocators', '1.0')
    from gi.repository import Gst, GstAllocators
    Gst.init(None)
    pipeline = Gst.parse_launch(
        'v4l2src name=source io-mode=dmabuf ! '
        'video/x-raw,format=RGB,width=1920,height=1080,framerate=60/1 ! '
        'identity name=inspect ! videoconvert ! video/x-raw,format=I420 ! '
        'openh264enc name=encoder bitrate=20000000 gop-size=60 complexity=low ! '
        'h264parse ! matroskamux ! filesink name=output sync=false')
    pipeline.get_by_name('source').set_property('device', str(device))
    pipeline.get_by_name('source').set_property('num-buffers', args.frames)
    pipeline.get_by_name('output').set_property('location', str(output))
    state = {'frames': 0, 'pts_ns': [], 'exporter': None, 'error': None}

    def inspect(pad, info, unused):
        try:
            buffer = info.get_buffer()
            if buffer.n_memory() != 1:
                raise ValueError('expected one exported RGB24 plane')
            memory = buffer.peek_memory(0)
            if not GstAllocators.is_dmabuf_memory(memory):
                raise ValueError('source delivered system memory instead of DMA-buf')
            if buffer.get_size() != 1920 * 1080 * 3:
                raise ValueError(f'wrong RGB24 payload size: {buffer.get_size()}')
            if state['exporter'] is None:
                fd = GstAllocators.dmabuf_memory_get_fd(memory)
                fields = dict(line.split(':', 1) for line in
                              Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines() if ':' in line)
                state['exporter'] = fields.get('exp_name', '').strip()
                if state['exporter'] != 'videobuf2_dma_contig':
                    raise ValueError(f'unexpected DMA-buf exporter: {state["exporter"]}')
            if buffer.pts == Gst.CLOCK_TIME_NONE:
                raise ValueError('missing capture timestamp')
            if state['pts_ns'] and buffer.pts <= state['pts_ns'][-1]:
                raise ValueError('capture timestamps did not advance')
            state['pts_ns'].append(buffer.pts)
            state['frames'] += 1
        except Exception as error:
            state['error'] = str(error)
            return Gst.PadProbeReturn.DROP
        return Gst.PadProbeReturn.OK

    pipeline.get_by_name('inspect').get_static_pad('sink').add_probe(
        Gst.PadProbeType.BUFFER, inspect, None)
    started = time.monotonic()
    try:
        if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise ValueError('pipeline could not enter PLAYING')
        bus = pipeline.get_bus()
        while time.monotonic() - started < args.timeout:
            if state['error']:
                raise ValueError(state['error'])
            message = bus.timed_pop_filtered(100 * Gst.MSECOND,
                                            Gst.MessageType.ERROR | Gst.MessageType.EOS)
            if message is None:
                continue
            if message.type == Gst.MessageType.ERROR:
                error, debug = message.parse_error()
                raise ValueError(f'{error}: {debug}')
            break
        else:
            raise ValueError('capture/encode pipeline timed out')
    finally:
        pipeline.set_state(Gst.State.NULL)
        pipeline.get_state(5 * Gst.SECOND)
    if state['error'] or state['frames'] != args.frames:
        raise ValueError(state['error'] or f'expected {args.frames} frames, got {state["frames"]}')
    report = {'software_encoder': 'openh264enc', 'io_mode': 'dmabuf',
              'kernel': os.uname().release, 'gstreamer': Gst.version_string(),
              'elapsed_seconds': time.monotonic() - started, **state,
              'encoded_bytes': output.stat().st_size}
    if not report['encoded_bytes']:
        raise ValueError('empty encoded video')
    with report_path.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: value for key, value in report.items() if key not in ('pts_ns', 'error')}))


def verify(args):
    spec = importlib.util.spec_from_file_location('hdmirx_frames',
                                                Path(__file__).with_name('hdmirx-frame-check.py'))
    frames = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frames)
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                             '-show_streams', '-of', 'json', str(args.video)],
                            check=True, capture_output=True, text=True)
    streams = json.loads(result.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('expected one video stream')
    stream = streams[0]
    if (stream['codec_name'], stream['width'], stream['height']) != ('h264', 1920, 1080):
        raise ValueError('expected H.264 1920x1080 video')
    ids = []
    with tempfile.TemporaryFile() as errors:
        decoder = subprocess.Popen(['ffmpeg', '-v', 'error', '-threads', '2', '-i', str(args.video),
                                    '-map', '0:v:0', '-fps_mode', 'passthrough',
                                    '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'],
                                   stdout=subprocess.PIPE, stderr=errors)
        try:
            while (raw := read_frame(decoder.stdout, frames.FRAME_BYTES)) is not None:
                decoded = frames.decode_frame(raw)
                if ids:
                    frames.check_advance(ids[-1], decoded['id'])
                ids.append(decoded['id'])
            if decoder.wait() != 0:
                errors.seek(0)
                raise ValueError(f'ffmpeg failed: {errors.read().decode(errors="replace")}')
        finally:
            decoder.stdout.close()
            if decoder.poll() is None:
                decoder.kill()
                decoder.wait()
    if len(ids) != args.frames:
        raise ValueError(f'expected {args.frames} decoded frames, got {len(ids)}')
    print(json.dumps({'codec': 'h264', 'width': 1920, 'height': 1080,
                      'frames': len(ids), 'source_ids': ids, 'markers_verified': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    board = sub.add_parser('capture', help='exclusive board-side software encode')
    board.add_argument('--exclusive', action='store_true')
    board.add_argument('--device', type=Path, default=Path('/dev/video0'))
    board.add_argument('--output', type=Path, required=True)
    board.add_argument('--frames', type=int, default=180)
    board.add_argument('--timeout', type=float, default=90)
    offline = sub.add_parser('verify', help='offline H.264 decode and motion-marker check')
    offline.add_argument('video', type=Path)
    offline.add_argument('--frames', type=int, required=True)
    args = parser.parse_args()
    if not 2 <= args.frames <= 10000:
        parser.error('frames must be 2..10000')
    if args.action == 'capture' and args.timeout <= 0:
        parser.error('timeout must be positive')
    try:
        (capture if args.action == 'capture' else verify)(args)
    except (ImportError, OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
