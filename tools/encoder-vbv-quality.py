#!/usr/bin/env python3
"""Decode VBV samples and compare matched frames against the deterministic fixture.

Run away from timing windows. Requires ffmpeg; reference is NV12, full 4K.
PSNR/SSIM cover selected frames including transitions, not the whole sequence.
"""
import argparse
import json
import mmap
from pathlib import Path
import re
import subprocess
import tempfile

WIDTH, HEIGHT = 3840, 2160
FRAME_BYTES = WIDTH * HEIGHT * 3 // 2
SAMPLES = [30, 100, 120, 150, 240, 350, 360, 365, 400, 470, 480, 500, 550, 600, 650, 719]


def frame_slot(frame):
    phase = frame % 720
    if phase < 120 or 480 <= phase < 600:
        return 0
    if phase < 360 or phase >= 600:
        return 1 + phase % 30
    return 31 + phase % 33


def fields(line):
    return dict(re.findall(r'(\w+):([^\s()]+)', line))


def aggregate_log(text):
    """Use FFmpeg's pooled-error PSNR, not the mean of per-frame dB values."""
    psnr = fields(next(line for line in reversed(text.splitlines()) if '] PSNR y:' in line))
    ssim = fields(next(line for line in reversed(text.splitlines()) if '] SSIM Y:' in line))
    return dict(sampled_psnr_y_db=float(psnr['y']),
                sampled_psnr_average_db=float(psnr['average']), sampled_ssim_all=float(ssim['All']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    args = parser.parse_args()
    directory = args.directory.resolve()
    windows = json.loads((directory / 'windows.json').read_text())
    results = []
    with tempfile.TemporaryDirectory(prefix='vbv-quality-') as temporary:
        reference = Path(temporary) / 'reference.nv12'
        with args.fixture.open('rb') as source, reference.open('wb') as output:
            with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
                if len(data) != 64 * FRAME_BYTES:
                    raise ValueError('invalid fixture length')
                for frame in SAMPLES:
                    start = frame_slot(frame) * FRAME_BYTES
                    output.write(data[start:start + FRAME_BYTES])
        for window in windows:
            name, codec = window['name'], window['codec']
            if not name.endswith(('a1', 'b500', 'c100')):
                continue
            stream = directory / f'{name}.{codec}'
            psnr, ssim = Path(temporary) / 'psnr.txt', Path(temporary) / 'ssim.txt'
            select = '+'.join(f'eq(n,{frame})' for frame in SAMPLES)
            filters = (f"[0:v]select='{select}',setpts=N/(60*TB),format=yuv420p,split[d1][d2];"
                       '[1:v]format=yuv420p,split[r1][r2];'
                       f'[d1][r1]psnr=stats_file={psnr}:shortest=1[p];'
                       f'[d2][r2]ssim=stats_file={ssim}:shortest=1[s]')
            command = [args.ffmpeg, '-hide_banner', '-nostdin', '-xerror', '-threads', '4',
                       '-err_detect', 'explode', '-i', str(stream), '-f', 'rawvideo',
                       '-pixel_format', 'nv12', '-video_size', '3840x2160', '-framerate', '60',
                       '-i', str(reference), '-filter_complex_threads', '2', '-filter_complex', filters,
                       '-map', '[p]', '-map', '[s]', '-f', 'null', '-']
            print('QUALITY_START', name, flush=True)
            with (directory / f'{name}-quality.log').open('w') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
            p_rows, s_rows = [fields(line) for line in psnr.read_text().splitlines()], [fields(line) for line in ssim.read_text().splitlines()]
            if len(p_rows) != len(SAMPLES) or len(s_rows) != len(SAMPLES):
                raise ValueError(f'{name}: incomplete matched quality frames')
            sample_rows = []
            for index, (p, s) in enumerate(zip(p_rows, s_rows)):
                if int(p['n']) != index + 1 or int(s['n']) != index + 1:
                    raise ValueError('quality sample order mismatch')
                sample_rows.append(dict(frame=SAMPLES[index], psnr_y=float(p['psnr_y']),
                                        psnr_avg=float(p['psnr_avg']), ssim_all=float(s['All'])))
            (directory / f'{name}-quality-psnr.txt').write_text(psnr.read_text())
            (directory / f'{name}-quality-ssim.txt').write_text(ssim.read_text())
            results.append(dict(name=name, samples=sample_rows,
                                **aggregate_log((directory / f'{name}-quality.log').read_text())))
            (directory / 'quality.json').write_text(json.dumps(results, indent=2))
            print('QUALITY_DONE', name, flush=True)


if __name__ == '__main__':
    main()
