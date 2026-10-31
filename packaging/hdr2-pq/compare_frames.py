#!/usr/bin/env python3
"""Compare visible NV21/NV12 samples, excluding per-frame tail padding."""
import argparse
import json
from pathlib import Path


def compare(vendor, candidate, width, height, vendor_block, candidate_block):
    if width % 2 or height % 2 or min(width, height) <= 0:
        raise ValueError('Even positive dimensions required')
    luma = width * height
    visible = luma * 3 // 2
    if min(vendor_block, candidate_block) < visible:
        raise ValueError('Frame block smaller than visible payload')
    if len(vendor) % vendor_block or len(candidate) % candidate_block:
        raise ValueError('Partial frame block')
    count = len(vendor) // vendor_block
    if not count or len(candidate) // candidate_block != count:
        raise ValueError('Equal nonzero frame counts required')
    result = []
    for frame in range(count):
        a = vendor[frame * vendor_block:frame * vendor_block + visible]
        b = candidate[frame * candidate_block:frame * candidate_block + visible]
        report = {}
        for name, x, y in [('Y', a[:luma], b[:luma]),
                           ('U', a[luma + 1::2], b[luma::2]),
                           ('V', a[luma::2], b[luma + 1::2])]:
            hist = [0] * 256
            for left, right in zip(x, y):
                hist[abs(left - right)] += 1
            cumulative = 0
            quantiles = {}
            for value, samples in enumerate(hist):
                cumulative += samples
                for percentile in (50, 99):
                    if percentile not in quantiles and cumulative * 100 >= len(x) * percentile:
                        quantiles[percentile] = value
            report[name] = {'p50': quantiles[50], 'p99': quantiles[99],
                            'max': max(i for i, n in enumerate(hist) if n),
                            'mean': sum(i * n for i, n in enumerate(hist)) / len(x)}
        result.append(report)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vendor', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--width', type=int, default=3840)
    parser.add_argument('--height', type=int, default=2160)
    parser.add_argument('--vendor-block', type=int, default=12443648)
    parser.add_argument('--candidate-block', type=int, default=12441600)
    args = parser.parse_args()
    print(json.dumps(compare(args.vendor.read_bytes(), args.candidate.read_bytes(),
                             args.width, args.height, args.vendor_block,
                             args.candidate_block), indent=2))
