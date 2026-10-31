#!/usr/bin/env python3
"""Capture experimental HDMI DMA-bufs into H.264/HEVC, or verify that video.

Board (exclusive): capture --exclusive --output NEW.mkv --frames 180
Mac/Linux: verify NEW.mkv --frames 180
Capture requires Python GI/GStreamer and GstAllocators. Software mode uses
OpenH264; Wave5 mode requires the experimental encoder and NV12 capture.
Verify requires ffmpeg/ffprobe. Pad timings do not measure optical latency.
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


def cpu_counters():
    """Read Linux CPU accounting, excluding guest time already counted in user."""
    return {fields[0]: list(map(int, fields[1:9]))
            for line in Path('/proc/stat').read_text().splitlines()
            if (fields := line.split()) and fields[0].startswith('cpu')}


def cpu_usage(before, after):
    usage = {}
    for name in before:
        if name not in after:
            continue
        delta = [b - a for a, b in zip(before[name], after[name])]
        total = sum(delta)
        if total > 0 and min(delta) >= 0:
            usage[name] = 100 * (total - delta[3] - delta[4]) / total
    return usage


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
    gi.require_version('GstVideo', '1.0')
    from gi.repository import GLib, Gst, GstAllocators, GstVideo
    Gst.init(None)
    width, height = map(int, args.size.split('x'))
    payload_size = width * height * 3 // (1 if args.format == 'rgb24' else 2)
    raw_format = 'RGB' if args.format == 'rgb24' else 'NV12'
    if args.encoder == 'wave5':
        if args.format != 'nv12':
            raise ValueError('Wave5 requires NV12 input')
        encoder_description = (f'v4l2{args.codec}enc name=encoder '
                               'output-io-mode=dmabuf-import')
        if args.codec == 'h265':
            encoder_description += ' ! video/x-h265,profile=main,level=(string)5.1'
        # GStreamer's V4L2 encoder chooses NV12M. Share the exported allocation
        # as two plane views; retaining its parent prevents capture-pool reuse.
        bridge_description = (
            'appsink name=bridge emit-signals=true sync=false async=false max-buffers=1 '
            'appsrc name=encoder_source is-live=true format=time block=true max-buffers=2 '
            f'caps="video/x-raw,format=NV12,width={width},height={height},framerate=60/1,'
            f'colorimetry={args.colorimetry},interlace-mode=progressive,pixel-aspect-ratio=1/1" ! ')
    else:
        if args.codec != 'h264':
            raise ValueError('software mode only supports H.264')
        encoder_description = ('videoconvert ! video/x-raw,format=I420 ! '
                               f'openh264enc name=encoder bitrate={args.bitrate} '
                               f'gop-size={args.gop} complexity=low')
        bridge_description = ''
    pipeline_description = (
        'v4l2src name=source io-mode=dmabuf ! '
        f'video/x-raw,format={raw_format},width={width},height={height},framerate=60/1 ! '
        f'identity name=inspect ! {bridge_description}{encoder_description} ! '
        f'{args.codec}parse ! video/x-{args.codec},alignment=au ! '
        'identity name=encoded ! matroskamux ! filesink name=output sync=false async=false')
    try:
        pipeline = Gst.parse_launch(pipeline_description)
    except GLib.Error as error:
        raise ValueError(f'cannot create GStreamer pipeline: {error}') from error
    encoder = pipeline.get_by_name('encoder')
    if args.encoder == 'wave5':
        def capture_allocation(pad, info):
            query = info.get_query()
            if query and query.type == Gst.QueryType.ALLOCATION:
                # The bridge owns its downstream queue. Keep its allocation
                # proposals out of the capture pool and let V4L2 select its
                # native DMA pool from the driver's minimum buffer count.
                return Gst.PadProbeReturn.HANDLED
            return Gst.PadProbeReturn.OK

        pipeline.get_by_name('source').get_static_pad('src').get_peer().add_probe(
            Gst.PadProbeType.QUERY_DOWNSTREAM, capture_allocation)
    if args.encoder == 'wave5':
        encoder_device = Path(encoder.get_property('device'))
        encoder_name = Path('/sys/class/video4linux', encoder_device.name, 'name').read_text().strip()
        if encoder_name != 'C&M Wave5 VPU encoder':
            raise ValueError(f'{encoder_device}: expected Wave5 encoder, got {encoder_name}')
        controls = Gst.Structure.new_empty('controls')
        controls.set_value('video_bitrate', args.bitrate)
        controls.set_value('video_gop_size', args.gop)
        if args.intra_refresh_period:
            controls.set_value('intra_refresh_period', args.intra_refresh_period)
        controls.set_value('frame_level_rate_control_enable', 1)
        controls.set_value('h264_mb_level_rate_control', 1)
        if args.codec == 'h265':
            # V4L2 HEVC level 5.1 (8): 4K60 exceeds level 5's sample rate.
            controls.set_value('hevc_level', 8)
        encoder.set_property('extra-controls', controls)
    pipeline.get_by_name('source').set_property('device', str(device))
    pipeline.get_by_name('source').set_property('num-buffers', args.frames)
    pipeline.get_by_name('output').set_property('location', str(output))
    state = {'frames': 0, 'encoded_frames': 0, 'pts_ns': [], 'exporter': None, 'error': None,
             'keyframes': [], 'keyframe_requests': []}
    pending_keyframes = list(sorted(args.keyframe_at))
    arrivals = {}
    latencies_ms = []
    steady_latencies_ms = []

    if args.encoder == 'wave5':
        encoder_source = pipeline.get_by_name('encoder_source')

        def forward_sample(sink):
            try:
                sample = sink.emit('pull-sample')
                # Preserve the capture transfer rather than relabelling mapped
                # HDR's sRGB samples as BT.709 at the two-plane bridge.
                if 'input_color_caps' not in state:
                    state['input_color_caps'] = sample.get_caps().to_string()
                    encoder_source.set_property('caps', sample.get_caps())
                original = sample.get_buffer()
                view = Gst.Buffer.new()
                memory = original.peek_memory(0)
                luma_size = width * height
                aligned_luma_size = width * ((height + 15) // 16 * 16)
                if aligned_luma_size != luma_size:
                    # Wave5 aligns source capacity to 16 lines, while encoding
                    # the visible height. Only unused plane tails may overlap;
                    # the UV hardware address remains after the active Y rows.
                    original_fd = GstAllocators.dmabuf_memory_get_fd(memory)
                    capacity = os.fstat(original_fd).st_size
                    if capacity < luma_size + aligned_luma_size // 2:
                        raise ValueError('capture allocation lacks encoder tail padding')
                    owned_fd = os.dup(original_fd)
                    try:
                        memory = GstAllocators.DmaBufAllocator.alloc(
                            GstAllocators.DmaBufAllocator.new(), owned_fd, capacity)
                    except Exception:
                        os.close(owned_fd)
                        raise
                    if memory is None:
                        os.close(owned_fd)
                        raise ValueError('cannot create padded DMA plane views')
                view.append_memory(memory.share(0, aligned_luma_size))
                view.append_memory(memory.share(luma_size, aligned_luma_size // 2))
                view.add_parent_buffer_meta(original)
                GstVideo.buffer_add_video_meta_full(
                    view, GstVideo.VideoFrameFlags.NONE, GstVideo.VideoFormat.NV12,
                    width, height, 2, [0, aligned_luma_size, 0, 0], [width, width, 0, 0])
                view.pts, view.dts, view.duration = original.pts, original.dts, original.duration
                return encoder_source.emit('push-buffer', view)
            except Exception as error:
                state['error'] = f'DMA plane bridge: {error}'
                return Gst.FlowReturn.ERROR

        pipeline.get_by_name('bridge').connect('new-sample', forward_sample)
        pipeline.get_by_name('bridge').connect('eos', lambda sink: encoder_source.emit('end-of-stream'))

    def inspect(pad, info, unused):
        try:
            buffer = info.get_buffer()
            if buffer.n_memory() != 1:
                raise ValueError('expected one exported packed plane')
            memory = buffer.peek_memory(0)
            if not GstAllocators.is_dmabuf_memory(memory):
                raise ValueError('source delivered system memory instead of DMA-buf')
            if buffer.get_size() != payload_size:
                raise ValueError(f'wrong raw payload size: {buffer.get_size()}')
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
            arrivals[buffer.pts] = (state['frames'], time.monotonic_ns())
        except Exception as error:
            state['error'] = str(error)
            return Gst.PadProbeReturn.DROP
        return Gst.PadProbeReturn.OK

    def encoded(pad, info, unused):
        buffer = info.get_buffer()
        state['encoded_frames'] += 1
        if not buffer.has_flags(Gst.BufferFlags.DELTA_UNIT):
            state['keyframes'].append(state['encoded_frames'])
        arrival = arrivals.pop(buffer.pts, None)
        if arrival is not None:
            index, started_ns = arrival
            latency = (time.monotonic_ns() - started_ns) / 1e6
            latencies_ms.append(latency)
            if index > 60:
                steady_latencies_ms.append(latency)
        return Gst.PadProbeReturn.OK

    pipeline.get_by_name('inspect').get_static_pad('sink').add_probe(
        Gst.PadProbeType.BUFFER, inspect, None)
    pipeline.get_by_name('encoded').get_static_pad('sink').add_probe(
        Gst.PadProbeType.BUFFER, encoded, None)
    cpu_before = cpu_counters()
    started = time.monotonic()
    try:
        if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise ValueError('pipeline could not enter PLAYING')
        bus = pipeline.get_bus()
        while time.monotonic() - started < args.timeout:
            if state['error']:
                raise ValueError(state['error'])
            if pending_keyframes and state['encoded_frames'] >= pending_keyframes[0]:
                pending_keyframes.pop(0)
                after = state['encoded_frames']
                event = GstVideo.video_event_new_upstream_force_key_unit(Gst.CLOCK_TIME_NONE, True, 0)
                if not encoder.get_static_pad('src').send_event(event):
                    raise ValueError('encoder rejected the force-keyframe event')
                state['keyframe_requests'].append(after)
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
        # Unblock both bridge queues even when negotiation failed before the
        # encoder accepted a frame; EOS drain cannot complete in that state.
        pipeline.send_event(Gst.Event.new_flush_start())
        pipeline.set_state(Gst.State.NULL)
        pipeline.get_state(5 * Gst.SECOND)
    if state['error'] or state['frames'] != args.frames:
        raise ValueError(state['error'] or f'expected {args.frames} frames, got {state["frames"]}')
    if state['encoded_frames'] != args.frames:
        raise ValueError(f'expected {args.frames} encoded frames, got {state["encoded_frames"]}')
    if pending_keyframes or any(not any(after < frame <= after + 30 for frame in state['keyframes'])
                                for after in state['keyframe_requests']):
        raise ValueError('a requested keyframe was not produced within 30 frames: '
                         f'requests={state["keyframe_requests"]}, keyframes={state["keyframes"]}')
    latencies_ms.sort()
    steady_latencies_ms.sort()
    steady_pts = state['pts_ns'][60:]
    system_cpu = cpu_usage(cpu_before, cpu_counters())
    report = {'encoder': args.encoder, 'codec': args.codec, 'size': args.size,
              'format': args.format, 'bitrate': args.bitrate, 'gop': args.gop,
              'intra_refresh_period': args.intra_refresh_period,
              'io_mode': 'dmabuf', 'latency_endpoint': 'source pad to parsed access unit',
              'system_cpu_busy_percent': system_cpu,
              'cpu_scope': 'whole board during capture, includes startup and kernel workers',
              'matched_timings': len(latencies_ms),
              'pad_latency_ms_p50': latencies_ms[len(latencies_ms) // 2] if latencies_ms else None,
              'pad_latency_ms_p99': latencies_ms[min(len(latencies_ms) - 1,
                                                   int(len(latencies_ms) * .99))] if latencies_ms else None,
              'steady_excluded_frames': 60,
              'steady_fps': (len(steady_pts) - 1) * 1e9 / (steady_pts[-1] - steady_pts[0])
                            if len(steady_pts) > 1 else None,
              'steady_max_capture_gap_ms': max(b - a for a, b in zip(steady_pts, steady_pts[1:])) / 1e6
                                           if len(steady_pts) > 1 else None,
              'steady_pad_latency_ms_p50': steady_latencies_ms[len(steady_latencies_ms) // 2]
                                           if steady_latencies_ms else None,
              'steady_pad_latency_ms_p99': steady_latencies_ms[min(len(steady_latencies_ms) - 1,
                                                                  int(len(steady_latencies_ms) * .99))]
                                           if steady_latencies_ms else None,
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
    if args.expect_profile and stream.get('profile') != args.expect_profile:
        raise ValueError(f'expected encoded profile {args.expect_profile}, '
                         f'got {stream.get("profile")}')
    width, height = stream['width'], stream['height']
    if stream['codec_name'] not in ('h264', 'hevc') or (width, height) not in ((1920, 1080), (3840, 2160)):
        raise ValueError('expected H.264/HEVC 1080p or 4K video')
    ids = []
    with tempfile.TemporaryFile() as errors:
        decoder = subprocess.Popen(['ffmpeg', '-v', 'error', '-threads', '2', '-i', str(args.video),
                                    '-map', '0:v:0', '-fps_mode', 'passthrough',
                                    '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'],
                                   stdout=subprocess.PIPE, stderr=errors)
        try:
            while (raw := read_frame(decoder.stdout, width * height * 3)) is not None:
                decoded = frames.decode_frame(raw, width, height)
                if args.check_colors:
                    frames.check_colors(raw, width, height, 'rgb24')
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
    print(json.dumps({'codec': stream['codec_name'], 'width': width, 'height': height,
                      'profile': stream.get('profile'), 'level': stream.get('level'),
                      'frames': len(ids), 'source_ids': ids, 'markers_verified': True,
                      'colors_verified': args.check_colors}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    board = sub.add_parser('capture', help='exclusive board-side encode')
    board.add_argument('--exclusive', action='store_true')
    board.add_argument('--device', type=Path, default=Path('/dev/video0'))
    board.add_argument('--output', type=Path, required=True)
    board.add_argument('--frames', type=int, default=180)
    board.add_argument('--timeout', type=float, default=90)
    board.add_argument('--encoder', choices=('software', 'wave5'), default='software')
    board.add_argument('--codec', choices=('h264', 'h265'), default='h264')
    board.add_argument('--format', choices=('rgb24', 'nv12'), default='rgb24')
    board.add_argument('--colorimetry', choices=('bt709', '2:3:7:1'), default='bt709',
                       help='initial Wave5 bridge caps; actual capture caps remain authoritative')
    board.add_argument('--size', choices=('1920x1080', '3840x2160'), default='1920x1080')
    board.add_argument('--bitrate', type=int, default=20000000)
    board.add_argument('--gop', type=int, default=60)
    board.add_argument('--intra-refresh-period', type=int, default=0,
                       help='Wave5 cyclic refresh period in frames; requires matched driver')
    board.add_argument('--keyframe-at', type=int, action='append', default=[],
                       help='request an IDR after this encoded frame; requires Wave5 and GOP 0 or > frames')
    offline = sub.add_parser('verify', help='offline decode and motion-marker check')
    offline.add_argument('video', type=Path)
    offline.add_argument('--frames', type=int, required=True)
    offline.add_argument('--check-colors', action='store_true')
    offline.add_argument('--expect-profile', help='Reject an actual SPS profile mismatch before decoding')
    args = parser.parse_args()
    if not 2 <= args.frames <= 10000:
        parser.error('frames must be 2..10000')
    if args.action == 'capture' and args.timeout <= 0:
        parser.error('timeout must be positive')
    if args.action == 'capture' and (not 1 <= args.bitrate <= 700000000 or not 0 <= args.gop <= 1000):
        parser.error('bitrate must be 1..700000000 and GOP must be 0..1000')
    if args.action == 'capture':
        if not 0 <= args.intra_refresh_period <= 4096:
            parser.error('intra refresh period must be 0..4096')
        if args.encoder != 'wave5' and (args.gop == 0 or args.intra_refresh_period):
            parser.error('GOP 0 and cyclic intra refresh require Wave5')
    if args.action == 'capture' and args.keyframe_at:
        if args.encoder != 'wave5' or (args.gop != 0 and args.gop <= args.frames):
            parser.error('keyframe requests require Wave5 and GOP 0 or larger than the capture frame count')
        if any(not 1 <= point <= args.frames - 30 for point in args.keyframe_at):
            parser.error('keyframe request points must leave at least 30 output frames')
    try:
        (capture if args.action == 'capture' else verify)(args)
    except (ImportError, OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
