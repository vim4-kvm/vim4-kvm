#!/usr/bin/env python3
"""Offline scalar-double oracle and GLES compute comparison; no board access.

Run: hdr-check.py PROBE SHADER OUTPUT_DIRECTORY. EGL/driver selection is supplied
by the caller. Output contains saved P010 fixtures, CPU/GPU NV12 and JSON errors.
"""
import importlib.util
import json
import math
from pathlib import Path
import random
import struct
import subprocess
import sys

spec = importlib.util.spec_from_file_location(
    'colour', Path(__file__).resolve().parents[2] / 'tools/hdmi-color-check.py')
colour = importlib.util.module_from_spec(spec)
spec.loader.exec_module(colour)


def rgb(sample):
    y, cb, cr = (sample[0]-64)/876, (sample[1]-512)/896, (sample[2]-512)/896
    r, b = y+1.4746*cr, y+1.8814*cb
    linear = [colour.pq_nits(v) for v in (r, (y-.2627*r-.0593*b)/.678, b)]
    mapped = [sum(a*b for a, b in zip(row, linear))/203
              for row in colour.BT2020_TO_BT709]
    peak = max(mapped)
    gain = 1
    if peak > .95:
        shoulder, top = (peak-.95)/.05, (1000/203-.95)/.05
        gain = (.95+.05*shoulder*(1+shoulder/top**2)/(1+shoulder))/peak
    return [colour.srgb(v*gain)/255 for v in mapped]


def reference(data, iw, ih, ow, oh):
    samples = [v >> 6 for v in struct.unpack('<'+'H'*(len(data)//2), data)]

    def read(x, y, channel):
        width, height = (iw, ih) if channel == 0 else (iw//2, ih//2)
        x, y = max(0, min(width-1, x)), max(0, min(height-1, y))
        index = y*iw+x if channel == 0 else iw*ih+y*iw+2*x+channel-1
        return samples[index]

    def filtered(x, y, channel):
        if channel:
            x, y = (x+.5)/2-.5, (y+.5)/2-.5
        ix, iy = math.floor(x), math.floor(y)
        fx, fy = x-ix, y-iy
        return sum(read(ix+dx, iy+dy, channel) *
                   (fx if dx else 1-fx) * (fy if dy else 1-fy)
                   for dx in (0, 1) for dy in (0, 1))

    pixels = []
    for y in range(oh):
        for x in range(ow):
            at = ((x+.5)*iw/ow-.5, (y+.5)*ih/oh-.5)
            r, g, b = rgb([filtered(*at, c) for c in range(3)])
            luma = .2126*r+.7152*g+.0722*b
            pixels.append((16+219*luma, 128+224*(b-luma)/1.8556,
                           128+224*(r-luma)/1.5748))
    quantize = lambda v: max(0, min(255, math.floor(v+.5)))
    result = bytearray(quantize(p[0]) for p in pixels)
    for y in range(0, oh, 2):
        for x in range(0, ow, 2):
            block = [pixels[(y+dy)*ow+x+dx] for dy in (0, 1) for dx in (0, 1)]
            result.extend(quantize(sum(p[c] for p in block)/4) for c in (1, 2))
    return result


def fixture(width, height, kind):
    rng = random.Random(1023)
    if kind in ('black', 'white'):
        values = [64 if kind == 'black' else 940]*(width*height)+[512]*(width*height//2)
    else:
        values = [rng.randrange(64, 941) for _ in range(width*height)]
        values += [rng.randrange(64, 961) for _ in range(width*height//2)]
    return struct.pack('<'+'H'*len(values), *(v << 6 for v in values))


def main():
    if len(sys.argv) == 6 and sys.argv[1] == '--generate':
        width, height = int(sys.argv[2]), int(sys.argv[3])
        kind = sys.argv[4]
        if not (2 <= width <= 4096 and 2 <= height <= 2160 and
                width % 2 == height % 2 == 0 and kind in ('black', 'white', 'random')):
            raise ValueError('Expected even dimensions and black/white/random fixture')
        Path(sys.argv[5]).write_bytes(fixture(width, height, kind))
        return
    probe, shader, output = sys.argv[1:]
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    reports = []
    for iw, ih, ow, oh, kind in [(64, 32, 64, 32, 'black'), (64, 32, 32, 16, 'white'),
                                (64, 32, 64, 32, 'random'), (48, 32, 32, 16, 'random'),
                                (48, 32, 44, 22, 'random')]:
        name = f'{iw}x{ih}-{ow}x{oh}-{kind}'
        data = fixture(iw, ih, kind)
        source, target = output/(name+'.p010'), output/(name+'.nv12')
        source.write_bytes(data)
        expected = reference(data, iw, ih, ow, oh)
        if kind in ('black', 'white'):
            assert set(expected[:ow*oh]) == ({16} if kind == 'black' else {235})
            assert set(expected[ow*oh:]) == {128}
        (output/(name+'.cpu.nv12')).write_bytes(expected)
        command = [probe, shader, *map(str, (iw, ih, ow, oh)), str(source), str(target)]
        run = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True)
        actual = target.read_bytes()
        assert len(actual) == len(expected)
        errors = [abs(a-b) for a, b in zip(actual, expected)]
        reports.append(dict(case=name, max_error=max(errors), mean_error=sum(errors)/len(errors),
                            log=run.stdout))
        assert max(errors) <= 2, reports[-1]
    # Malformed input must fail before GPU access, never emit a partial frame.
    source.write_bytes(data[:-2])
    bad = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert bad.returncode != 0 and 'size mismatch' in bad.stderr
    source.write_bytes(data)
    malformed = command.copy()
    malformed[4] = '30'
    bad = subprocess.run(malformed, capture_output=True, text=True, timeout=30)
    assert bad.returncode != 0 and 'multiple of 4' in bad.stderr
    (output/'report.json').write_text(json.dumps(reports, indent=2)+'\n')
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
