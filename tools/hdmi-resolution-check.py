#!/usr/bin/env python3
"""Compare native UHD monochrome detail with a decoded, unscaled video frame.

Offline only; requires Pillow. Input is the full 3840x2160 canvas image, not a
browser screenshot resized to CSS dimensions. Contrast and correlation check
spatial detail; they do not measure colour accuracy, motion quality or latency.
"""
import argparse
import json
import math

from PIL import Image, ImageStat


def compare(reference, decoded):
    if reference.size != (3840, 2160) or decoded.size != reference.size:
        raise ValueError('Both frames must be unscaled 3840x2160 images')
    reference, decoded = reference.convert('L'), decoded.convert('L')
    tiles = []
    for row, direction in enumerate(('vertical', 'horizontal')):
        for column, pitch in enumerate((1, 2, 4, 8)):
            x, y = 128 + column * 896, 256 + row * 896
            # Exclude tile edges, labels, and any encoder boundary ringing.
            box = (x + 64, y + 64, x + 576, y + 448)
            expected, observed = reference.crop(box), decoded.crop(box)
            a, b = ImageStat.Stat(expected), ImageStat.Stat(observed)
            if a.stddev[0] < 100:
                raise ValueError('Reference lacks the native high-contrast pattern')
            expected_pixels, observed_pixels = expected.tobytes(), observed.tobytes()
            covariance = sum((v - a.mean[0]) * (w - b.mean[0])
                             for v, w in zip(expected_pixels, observed_pixels))
            count = expected.width * expected.height
            denominator = count * a.stddev[0] * b.stddev[0]
            correlation = covariance / denominator if denominator else 0.0
            contrast = b.stddev[0] / a.stddev[0]
            mae = sum(abs(v - w) for v, w in zip(expected_pixels, observed_pixels)) / count
            tiles.append(dict(direction=direction, pitch=pitch, contrast=contrast,
                              correlation=correlation, mean_absolute_error=mae,
                              passed=contrast >= 0.5 and math.fabs(correlation) >= 0.8))
    return dict(size=[3840, 2160], native_single_pixel_detail=all(
        tile['passed'] for tile in tiles if tile['pitch'] == 1), tiles=tiles)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference')
    parser.add_argument('decoded')
    args = parser.parse_args()
    with Image.open(args.reference) as reference, Image.open(args.decoded) as decoded:
        result = compare(reference, decoded)
    print(json.dumps(result, indent=2))
    return 0 if result['native_single_pixel_detail'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
