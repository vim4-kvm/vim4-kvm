#!/usr/bin/env python3
"""Compare decoded colour patches with measured, pre-matrix 10-bit RX Y/Cb/Cr.

Offline only. Probe JSON must contain 16 source samples from the matching
eight-column, two-row physical HDMI chart. HDR uses PQ/BT.2020 and the
configured capture reference white/peak, not the source application's RGB.
"""
import argparse
import json
from pathlib import Path
from statistics import median


BT2020_TO_BT709 = (
    (1.660491, -.587641, -.072850),
    (-.124550, 1.132900, -.008349),
    (-.018151, -.100579, 1.118730),
)


def pq_nits(value):
    power = max(0, min(1, value)) ** (32 / 2523)
    return (max(0, power - 3424 / 4096) /
            (2413 / 128 - 2392 / 128 * power)) ** (16384 / 2610) * 10000


def srgb(value):
    value = max(0, min(1, value))
    return (12.92 * value if value <= .0031308 else
            1.055 * value ** (1 / 2.4) - .055) * 255


def reference(sample, hdr, white=203, peak=1000):
    if len(sample) != 3 or any(not isinstance(value, int) or not 0 <= value <= 1023 for value in sample):
        raise ValueError('Expected measured 10-bit Y/Cb/Cr')
    if not 160 <= white < peak <= 10000:
        raise ValueError('Invalid capture white or peak')
    luma = (sample[0] - 64) / 876
    cb = (sample[1] - 512) / 896
    cr = (sample[2] - 512) / 896
    red_weight, blue_weight = (.2627, .0593) if hdr else (.2126, .0722)
    red = luma + 2 * (1 - red_weight) * cr
    blue = luma + 2 * (1 - blue_weight) * cb
    green = (luma - red_weight * red - blue_weight * blue) / (1 - red_weight - blue_weight)
    rgb = [red, green, blue]
    if not hdr:
        return [max(0, min(255, value * 255)) for value in rgb]
    linear = [pq_nits(value) for value in rgb]
    mapped = [sum(value * coefficient for value, coefficient in zip(linear, row))
              for row in BT2020_TO_BT709]
    maximum = max(mapped) / white
    gain = 1
    if maximum > .95:
        shoulder = (maximum - .95) / .05
        top = (peak / white - .95) / .05
        compressed = .95 + .05 * shoulder * (1 + shoulder / top ** 2) / (1 + shoulder)
        gain = compressed / maximum
    return [srgb(value / white * gain) for value in mapped]


def measure(image, samples, hdr, white, peak):
    if len(samples) != 16:
        raise ValueError('Expected all 16 matching physical patches')
    results = []
    image = image.convert('RGB')
    for index, sample in enumerate(samples):
        center_x = int(image.width * (index % 8 + .5) / 8)
        center_y = int(image.height * (index // 8 + .5) / 2)
        patch = image.crop((center_x - 8, center_y - 8, center_x + 8, center_y + 8))
        pixels = [patch.getpixel((column, row)) for row in range(16) for column in range(16)]
        actual = [median(pixel[channel] for pixel in pixels) for channel in range(3)]
        expected = reference(sample, hdr, white, peak)
        error = [abs(value - target) for value, target in zip(actual, expected)]
        results.append({'patch': index, 'rxYuv10': sample, 'expected': expected,
                        'actual': actual, 'channelError': error})
    errors = [value for result in results for value in result['channelError']]
    return {'maxChannelError': max(errors), 'meanChannelError': sum(errors) / len(errors),
            'hdr': hdr, 'white': white, 'peak': peak, 'patches': results,
            'note': '10-bit probe quantization and codec error are included; not a panel colour measurement'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--frame', type=Path, required=True)
    parser.add_argument('--hdr', action='store_true')
    parser.add_argument('--white', type=int, default=203)
    parser.add_argument('--peak', type=int, default=1000)
    args = parser.parse_args()
    from PIL import Image
    with Image.open(args.frame) as image:
        print(json.dumps(measure(image, json.loads(args.probe.read_text())['source'],
                                 args.hdr, args.white, args.peak), indent=2))


if __name__ == '__main__':
    main()
