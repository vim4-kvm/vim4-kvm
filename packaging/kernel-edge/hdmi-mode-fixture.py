#!/usr/bin/env python3
"""Prepare single-DTD EDIDs offline and qualify actual V4L2 input timings.

CoreGraphics backing dimensions never substitute for receiver measurements.
Only measure opens a device, read-only, using VIDIOC_QUERY_DV_TIMINGS. The caller
must hold the shared board ticket; no EDID write or HPD operation occurs here.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TIMINGS = Path(__file__).with_name('hdmi-modes.json')
BASELINE = ROOT / 'board/edid/rtk-uhd-hdr.bin'
QUERY_DV_TIMINGS = 0x80845663  # _IOR('V', 99, struct v4l2_dv_timings), 132 bytes.


def load_modes():
    return json.loads(TIMINGS.read_text())['modes']


def detailed_timing(mode):
    width, height = mode['width'], mode['height']
    hfront, hsync = mode['hfrontporch'], mode['hsync']
    vfront, vsync = mode['vfrontporch'], mode['vsync']
    hblank = hfront + hsync + mode['hbackporch']
    vblank = vfront + vsync + mode['vbackporch']
    data = bytearray(18)
    data[:2] = round(mode['pixelclock'] / 10000).to_bytes(2, 'little')
    data[2:8] = bytes((width & 255, hblank & 255, (width >> 8) << 4 | hblank >> 8,
                       height & 255, vblank & 255, (height >> 8) << 4 | vblank >> 8))
    data[8:12] = bytes((hfront & 255, hsync & 255, (vfront & 15) << 4 | vsync & 15,
                        (hfront >> 8) << 6 | (hsync >> 8) << 4 |
                        (vfront >> 4) << 2 | vsync >> 4))
    data[12:15] = bytes((0x61, 0x63, 0x21))
    data[17] = 0x18 | int(mode['hsync_positive']) << 1 | int(mode['vsync_positive']) << 2
    return bytes(data)


def single_mode_edid(baseline, mode):
    """Advertise one physical timing, retaining LPCM and HDMI/SCDC capability."""
    from board.vim4vrr import cta_blocks, validate

    validate(baseline)
    if len(baseline) != 256:
        raise ValueError('Expected the qualified two-block RTK EDID')
    data = bytearray(baseline[:128])
    data[12:16] = (0x50303100 + mode['id']).to_bytes(4, 'little')
    data[35:38] = bytes(3)  # Remove established timings.
    data[38:54] = bytes((1, 1)) * 8  # Remove standard timings.
    data[54:72] = detailed_timing(mode)
    data[72:90] = b'\0\0\0\xfc\0RTK UHD HDR\n '
    data[90:108] = b'\0\0\0\xff\0P01-UHD6\n    '
    data[108:126] = bytes.fromhex('000000fd0014780fb43c000a202020202020')
    blocks = bytearray()
    for tag, original in cta_blocks(baseline[128:])[0]:
        payload = bytearray(original)
        # Remove other timings, HDR, Y420 maps and the AMD VRR block.
        if tag == 2 or (tag == 7 and payload[0] in (6, 14, 15)):
            continue
        if tag == 3 and payload[:3] == bytes.fromhex('1a0000'):
            continue
        if tag == 3 and payload[:3] == bytes.fromhex('030c00'):
            payload[5] = 0  # This matrix requests RGB8, without deep colour.
        blocks += bytes(((tag << 5) | len(payload),)) + payload
    cta = bytearray(bytes((2, 3, 4 + len(blocks), 0x40)) + blocks)
    cta.extend(bytes(128 - len(cta)))  # No CTA detailed timings remain.
    data[126] = 1
    data[127] = -sum(data[:127]) % 256
    cta[127] = -sum(cta[:127]) % 256
    result = bytes(data + cta)
    validate(result)
    return result


def decode_timings(raw):
    if len(raw) != 132:
        raise ValueError('Expected a complete V4L2 DV timing structure')
    kind, width, height, interlaced, polarities, clock, *porches = struct.unpack_from(
        '=5IQ6I', raw)
    if kind != 0 or interlaced:
        raise ValueError('Expected progressive BT timings')
    htotal = width + sum(porches[:3])
    vtotal = height + sum(porches[3:])
    if not width or not height or not htotal or not vtotal or not clock:
        raise ValueError('Receiver has no qualified input timing')
    return dict(width=width, height=height, pixelclock=clock,
                hfrontporch=porches[0], hsync=porches[1], hbackporch=porches[2],
                vfrontporch=porches[3], vsync=porches[4], vbackporch=porches[5],
                polarities=polarities, hz=clock / (htotal * vtotal))


def measure(device):
    if sys.platform != 'linux':
        raise ValueError('Actual input timings must be read on the Linux receiver')
    raw = bytearray(132)
    fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    try:
        fcntl.ioctl(fd, QUERY_DV_TIMINGS, raw)
    finally:
        os.close(fd)
    return decode_timings(raw)


def refresh_rate(mode):
    totals = ((mode['width'] + mode['hfrontporch'] + mode['hsync'] + mode['hbackporch']) *
              (mode['height'] + mode['vfrontporch'] + mode['vsync'] + mode['vbackporch']))
    return mode['pixelclock'] / totals


def qualify(mode, measured):
    """Require actual wire geometry and refresh, independently of source scaling."""
    expected = mode['width'], mode['height']
    actual = measured['width'], measured['height']
    hz = refresh_rate(mode)
    if actual != expected or abs(measured['hz'] - hz) > .5:
        raise ValueError(f'HDMI input is {actual}@{measured["hz"]:.3f}, '
                         f'expected {expected}@{hz:.3f}; backing dimensions are insufficient')
    return dict(mode_id=mode['id'], **measured)


def prepare(destination):
    destination.mkdir()
    modes = load_modes()
    baseline = BASELINE.read_bytes()
    manifest = {}
    for mode in modes:
        data = single_mode_edid(baseline, mode)
        name = str(mode['id']) + '.bin'
        (destination / name).write_bytes(data)
        manifest[name] = hashlib.sha256(data).hexdigest()
    (destination / 'modes.json').write_text(json.dumps(modes, indent=2) + '\n')
    (destination / 'sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return dict(modes=len(modes), sha256=manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    build = actions.add_parser('prepare', help='Offline only; create a new fixture directory')
    build.add_argument('destination', type=Path)
    read = actions.add_parser('measure', help='Board only; read actual V4L2 input timings')
    read.add_argument('device')
    verify = actions.add_parser('verify', help='Offline; qualify a measured JSON against one mode')
    verify.add_argument('mode', type=int)
    verify.add_argument('measurement', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'prepare':
            result = prepare(args.destination)
        elif args.action == 'measure':
            result = measure(args.device)
        else:
            mode = next(m for m in load_modes() if m['id'] == args.mode)
            result = qualify(mode, json.loads(args.measurement.read_text()))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
