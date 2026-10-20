#!/usr/bin/env python3
"""Check 1080p RGB24 snapshots of latency-source.swift --verify-coherence.

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


def decode_frame(raw):
    if len(raw) != FRAME_BYTES:
        raise ValueError(f'expected {FRAME_BYTES} RGB24 bytes, got {len(raw)}')
    words = []
    ids = []
    for y in (85, 540, 995):
        word = 0
        for bit in range(32):
            x = int(20 + (bit + .5) * 1880 / 32)
            offset = (y * WIDTH + x) * 3
            pixel = raw[offset:offset + 3]
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


def check_advance(previous, current):
    delta = (current - previous) & 0xffff
    if delta == 0 or delta >= 0x8000:
        raise ValueError(f'frame ID did not advance: {previous} -> {current}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frames', type=Path, nargs='+', help='RGB24 files in capture order')
    args = parser.parse_args()
    previous = None
    for path in args.frames:
        try:
            result = decode_frame(path.read_bytes())
            if previous is not None:
                check_advance(previous, result['id'])
        except (OSError, ValueError) as error:
            parser.exit(1, f'{path}: {error}\n')
        previous = result['id']
        print(json.dumps({'file': str(path), **result}))


if __name__ == '__main__':
    main()
