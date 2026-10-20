#!/usr/bin/env python3
"""Check RGB24 or limited-range BT.709 NV12 HDMI motion-marker snapshots.

Offline only. Pass snapshots in capture order; repeated or backwards IDs fail.
This checks the three frame markers, not frame rate, latency or every pixel.
"""
import argparse
import hashlib
import json
from pathlib import Path

WIDTH = 1920
HEIGHT = 1080
FRAME_BYTES = WIDTH * HEIGHT * 3


def rgb_at(raw, x, y, width, height, pixel_format):
    if pixel_format == 'rgb24':
        offset = (y * width + x) * 3
        return list(raw[offset:offset + 3])
    luma = raw[y * width + x] - 16
    chroma = width * height + (y // 2) * width + (x // 2) * 2
    u, v = raw[chroma] - 128, raw[chroma + 1] - 128
    return [max(0, min(255, round(value))) for value in (
        1.164384 * luma + 1.792741 * v,
        1.164384 * luma - .213249 * u - .532909 * v,
        1.164384 * luma + 2.112402 * u)]


def decode_frame(raw, width=WIDTH, height=HEIGHT, pixel_format='rgb24'):
    if pixel_format not in ('rgb24', 'nv12') or width <= 0 or height <= 0:
        raise ValueError('expected RGB24 or NV12 with positive dimensions')
    if pixel_format == 'nv12' and (width % 2 or height % 2):
        raise ValueError('NV12 requires even dimensions')
    expected = width * height * 3 if pixel_format == 'rgb24' else width * height * 3 // 2
    if len(raw) != expected:
        raise ValueError(f'expected {expected} {pixel_format} bytes, got {len(raw)}')
    words = []
    ids = []
    for marker_y in (85, 540, 995):
        y = marker_y * height // 1080
        word = 0
        for bit in range(32):
            x = int((20 + (bit + .5) * 1880 / 32) * width / 1920)
            if pixel_format == 'nv12':
                luma = raw[y * width + x]
                chroma = width * height + (y // 2) * width + (x // 2) * 2
                if (any(abs(value - 128) > 6 for value in raw[chroma:chroma + 2]) or
                        not (8 <= luma <= 24 or 227 <= luma <= 243)):
                    raise ValueError(f'corrupt black/white NV12 marker at ({x}, {y})')
            pixel = rgb_at(raw, x, y, width, height, pixel_format)
            mean = sum(pixel) / 3
            # A valid ID alone missed the initial single-channel corruption.
            if max(pixel) - min(pixel) > 12 or 16 < mean < 239:
                raise ValueError(f'corrupt black/white marker at ({x}, {y}): {list(pixel)}')
            word = (word << 1) | int(mean >= 239)
        frame_id = (word >> 8) & 0xffff
        checksum = (frame_id >> 8) ^ (frame_id & 255) ^ 0xa5
        if word >> 24 != 0xa5 or word & 255 != checksum:
            raise ValueError(f'invalid marker at y={y}: {word:#010x}')
        words.append(f'{word:#010x}')
        ids.append(frame_id)
    if len(set(ids)) != 1:
        raise ValueError(f'frame markers disagree: {ids}')
    return {'id': ids[0], 'markers': words, 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def check_colors(raw, width, height, pixel_format):
    """Check the three primary-colour patches drawn by the coherence source."""
    samples = [rgb_at(raw, x * width // 1920, 800 * height // 1080,
                      width, height, pixel_format) for x in (240, 720, 1200)]
    for channel, pixel in enumerate(samples):
        if pixel[channel] < 180 or any(value > 60 for i, value in enumerate(pixel) if i != channel):
            raise ValueError(f'incorrect primary colour {channel}: {pixel}')
    return samples


def check_advance(previous, current):
    delta = (current - previous) & 0xffff
    if delta == 0 or delta >= 0x8000:
        raise ValueError(f'frame ID did not advance: {previous} -> {current}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frames', type=Path, nargs='+', help='RGB24 files in capture order')
    parser.add_argument('--size', choices=('1920x1080', '3840x2160'), default='1920x1080')
    parser.add_argument('--format', choices=('rgb24', 'nv12'), default='rgb24')
    parser.add_argument('--check-colors', action='store_true')
    args = parser.parse_args()
    width, height = map(int, args.size.split('x'))
    previous = None
    for path in args.frames:
        try:
            raw = path.read_bytes()
            result = decode_frame(raw, width, height, args.format)
            if args.check_colors:
                result['primary_colors'] = check_colors(raw, width, height, args.format)
            if previous is not None:
                check_advance(previous, result['id'])
        except (OSError, ValueError) as error:
            parser.exit(1, f'{path}: {error}\n')
        previous = result['id']
        print(json.dumps({'file': str(path), **result}))


if __name__ == '__main__':
    main()
