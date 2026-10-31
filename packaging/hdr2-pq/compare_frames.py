#!/usr/bin/env python3
"""Compare visible NV21/NV12 samples, excluding per-frame tail padding."""
import argparse
import json
from pathlib import Path


def compare(vendor, candidate, width, height, vendor_block, candidate_block,
            exclude_top=0, vendor_format='nv21', candidate_format='nv12'):
    if width % 2 or height % 2 or min(width, height) <= 0:
        raise ValueError('Even positive dimensions required')
    luma = width * height
    visible = luma * 3 // 2
    if exclude_top % 2 or not 0 <= exclude_top < height:
        raise ValueError('Excluded top rows must be even and smaller than height')
    if vendor_format not in ('nv12', 'nv21') or candidate_format not in ('nv12', 'nv21'):
        raise ValueError('Expected NV12 or NV21')
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
        au, bu = int(vendor_format == 'nv21'), int(candidate_format == 'nv21')
        for name, x, y in [('Y', a[exclude_top * width:luma], b[exclude_top * width:luma]),
                           ('U', a[luma + exclude_top * width // 2 + au::2],
                            b[luma + exclude_top * width // 2 + bu::2]),
                           ('V', a[luma + exclude_top * width // 2 + 1 - au::2],
                            b[luma + exclude_top * width // 2 + 1 - bu::2])]:
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
    parser.add_argument('--exclude-top', type=int, default=0,
                        help='analysis only: exclude an even number of top rows; full-frame gate stays separate')
    parser.add_argument('--vendor-format', choices=('nv12', 'nv21'), default='nv21')
    parser.add_argument('--candidate-format', choices=('nv12', 'nv21'), default='nv12')
    args = parser.parse_args()
    print(json.dumps(compare(args.vendor.read_bytes(), args.candidate.read_bytes(),
                             args.width, args.height, args.vendor_block,
                             args.candidate_block, args.exclude_top,
                             args.vendor_format, args.candidate_format), indent=2))
