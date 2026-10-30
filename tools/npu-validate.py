#!/usr/bin/env python3
"""Local NPU qualification runner; no SSH, installation, services, HID or audio.

run invokes a prebuilt probe and writes a new result directory. compare checks
every output byte before accepting the <=5% paired mean latency threshold.
Each probe runs in its own process group with a bounded termination sequence.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import urllib.request


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def statistics(values):
    if not values or any(not math.isfinite(x) or x <= 0 for x in values):
        raise ValueError('missing or invalid warm timing samples')
    return dict(mean=sum(values) / len(values), p50=percentile(values, .50),
                p99=percentile(values, .99), maximum=max(values))


def bounded_probe(command, cwd, timeout):
    with (cwd / 'probe.log').open('wb') as log:
        process = subprocess.Popen(command, cwd=cwd, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                # Kernel D-state cannot be repaired by userspace. Do not wait forever.
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
            raise
    if code:
        raise ValueError(f'probe failed ({code}); see {cwd / "probe.log"}')


def run(args):
    model, data, probe = [Path(p).resolve(strict=True)
                          for p in (args.model, args.input, args.probe)]
    if digest(model) != args.model_sha256 or digest(data) != args.input_sha256:
        raise ValueError('model/input SHA256 mismatch')
    output = Path(args.output).resolve()
    output.mkdir()  # Never mix with or remove an existing run.
    started = time.time()
    command = [str(probe), str(model), str(data), str(args.iterations)]
    if args.timing:
        command.append('--timing')
    bounded_probe(command, output, args.timeout)
    log = (output / 'probe.log').read_text()
    samples = re.findall(r'iteration=(\d+) elapsed_ms=([\d.]+)',
                         log)
    if [int(i) for i, _ in samples] != list(range(args.iterations)):
        raise ValueError('incomplete iteration sequence')
    files = sorted(output.glob('iteration-*-output-*.f32'))
    counts = [len(list(output.glob(f'iteration-{i:04d}-output-*.f32')))
              for i in range(args.iterations)]
    if not counts[0] or len(set(counts)) != 1:
        raise ValueError('missing output tensors')
    report = dict(model=digest(model), input=digest(data), probe=digest(probe),
                  kernel=os.uname().release, started=started,
                  samples=[float(v) for _, v in samples][1:],
                  outputs={p.name: dict(sha256=digest(p), bytes=p.stat().st_size)
                           for p in files})
    report['statistics_ms'] = statistics(report['samples'])
    if args.timing:
        segments = re.findall(r'^timing_iteration=(\d+) (.+)$', log, re.M)
        if [int(i) for i, _ in segments] != list(range(args.iterations)):
            raise ValueError('missing segmented timings; use a probe supporting --timing')
        report['stage_timings_ms'] = [
            {key: float(value) for key, value in re.findall(r'(\w+)=([\d.]+)', line)}
            for _, line in segments]
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')


def compare(baseline, candidate):
    for key in ('model', 'input', 'probe', 'outputs'):
        if baseline[key] != candidate[key]:
            raise ValueError(f'{key} differs; byte equality qualification failed')
    before, after = statistics(baseline['samples']), statistics(candidate['samples'])
    if len(baseline['samples']) != len(candidate['samples']):
        raise ValueError('different sample counts')
    ratio = after['mean'] / before['mean']
    return dict(baseline_ms=before, candidate_ms=after, mean_ratio=ratio,
                passed=ratio <= 1.05)


def prepare(destination):
    from PIL import Image, __version__ as pillow_version
    import struct

    manifest = json.loads(Path(__file__).with_name('npu-models.json').read_text())
    destination.mkdir()
    for relative, expected in manifest['files'].items():
        url = ('https://raw.githubusercontent.com/khadas/vim4_npu_applications/' +
               manifest['revision'] + '/' + relative)
        payload = urllib.request.urlopen(url, timeout=60).read()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f'download SHA256 mismatch: {relative}')
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    inputs = {}
    for model, picture, size, mode in (
            ('vgg16', 'airplane.jpeg', (32, 32), 'RGB'),
            ('densenet_ctc', 'KhadasTeam.png', (280, 32), 'L'),
            ('yolov8n', 'horses.jpg', (640, 640), 'RGB')):
        image = Image.open(destination / model / 'data' / picture)
        image = image.convert(mode).resize(size, Image.Resampling.BILINEAR)
        # SDK samples consume OpenCV BGR HWC float32, or grayscale float32.
        values = []
        for pixel in image.getdata():
            values.extend([pixel] if mode == 'L' else reversed(pixel))
        target = destination / (model + '.f32')
        target.write_bytes(struct.pack('<' + 'f' * len(values),
                                      *(value / 255 for value in values)))
        inputs[model] = digest(target)
    (destination / 'inputs.json').write_text(json.dumps(
        dict(pillow=pillow_version, inputs=inputs, source=manifest), indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    fetch = sub.add_parser('prepare')
    fetch.add_argument('destination', type=Path)
    trial = sub.add_parser('run')
    trial.add_argument('--timing', action='store_true',
                       help='record probe SDK/external stage timings in probe.log')
    for name in ('probe', 'model', 'input', 'output', 'model-sha256', 'input-sha256'):
        trial.add_argument('--' + name, required=True)
    trial.add_argument('--iterations', type=int, default=101)
    trial.add_argument('--timeout', type=int, default=120)
    diff = sub.add_parser('compare')
    diff.add_argument('baseline', type=Path)
    diff.add_argument('candidate', type=Path)
    args = parser.parse_args()
    if args.action == 'run':
        if not 2 <= args.iterations <= 1000 or not 1 <= args.timeout <= 590:
            parser.error('iterations must be 2..1000; timeout must be 1..590 seconds')
        run(args)
    elif args.action == 'prepare':
        prepare(args.destination)
    else:
        result = compare(json.loads(args.baseline.read_text()),
                         json.loads(args.candidate.read_text()))
        print(json.dumps(result, indent=2))
        if not result['passed']:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
