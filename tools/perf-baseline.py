#!/usr/bin/env python3
"""Offline performance plans and paired-result gates; never contacts the board.

Commands in plans are templates for a separately reserved board/heavy window.
See docs/performance-baseline.md for endpoints, prerequisites and validity gates.
"""
import argparse
import json
import math
from pathlib import Path
import statistics


def plan(backend):
    env = ('GST_PLUGIN_PATH=/usr/lib/vim4-kvm/gstreamer-1.0 '
           'LD_LIBRARY_PATH=/opt/vim4-onekvm/lib' if backend == 'stock' else
           'GST_PLUGIN_PATH=/usr/lib/vim4-kvm/mainline-gstreamer-1.0')
    cases = []
    for codec in ('capture', 'h264', 'h265', 'jpeg'):
        cases.append(dict(id=codec, location='board, khadas', seconds=120,
                          command=f'env {env} GST_REGISTRY=$OUT/registry.bin '
                          f'timeout -k 5 240 /var/tmp/vim4-driver-bench --exclusive '
                          f'--backend={backend} --codec={codec} --warmup=900 --frames=7200 '
                          '--width=$WIDTH --height=$HEIGHT --bitrate=$BITRATE --gop=60 '
                          '--quality=80 --timeout=230 --output=$OUT/driver.json',
                          note='7200 frames: >=120s at 60Hz; timeout is failure, not a sample'))
    for name, location, seconds, command in (
        ('video-latency', 'Mac', 120,
         'node tools/latency-receiver.mjs "$URL" 120 --verify-coherence > "$OUT/receiver.json"'),
        ('video-cadence', 'Mac', 120,
         'node tools/latency-receiver.mjs "$URL" 120 --no-pixels > "$OUT/cadence.json"'),
        ('audio-skew', 'Mac', 180,
         'node tools/one-kvm-av-sync-check.mjs --exclusive --seconds=180 --mode=$CODEC > "$OUT/av.jsonl"'),
        ('hid', 'Mac', 40,
         'node tools/input-check.mjs /tmp/vim4-input-target "$OUT/input" "$URL"'),
        ('cpu-single', 'board', 120,
         'taskset -c $CPU sysbench cpu --threads=1 --time=120 --cpu-max-prime=20000 run'),
        ('cpu-all', 'board', 120,
         'sysbench cpu --threads=8 --time=120 --cpu-max-prime=20000 run'),
        ('memory', 'board', 120,
         'sysbench memory --threads=1 --time=120 --memory-block-size=256M '
         '--memory-total-size=1000000G --memory-oper=read --memory-access-mode=seq run'),
        ('storage-read', 'board', 120,
         'fio --name=read --filename="$SCRATCH" --readonly --rw=read --bs=1M '
         '--direct=1 --ioengine=libaio --iodepth=16 --size=2G --time_based=1 '
         '--runtime=120 --ramp_time=15 --output-format=json'),
        ('storage-write', 'board', 120,
         'fio --name=write --filename="$SCRATCH" --rw=write --bs=1M '
         '--direct=1 --ioengine=libaio --iodepth=16 --size=2G --time_based=1 '
         '--runtime=120 --ramp_time=15 --end_fsync=1 --output-format=json'),
        ('network', 'board', 120,
         'iperf3 -c "$PEER" -B "$LOCAL_IP" -t 120 -O 15 -P 1 -J'),
        ('gpu-offscreen', 'board', 120,
         'glmark2-es2-drm --off-screen --size 1920x1080 --benchmark "shading:duration=120"'),
        ('gpu-scanout', 'board', 120,
         'glmark2-es2-drm --size 1920x1080 --benchmark "shading:duration=120"'),
        ('gpu-kms', 'board', 120, 'timeout -s INT -k 5 120 kmscube'),
        ('decode', 'board', 120,
         'timeout -k 5 180 gst-launch-1.0 -e filesrc location="$CLIP" ! '
         '$DEMUX ! $PARSER ! $HW_DECODER ! fpsdisplaysink video-sink=fakesink '
         'text-overlay=false sync=false'),
        ('boot', 'board', 0, 'systemd-analyze time; systemd-analyze critical-chain'),
        ('idle', 'board', 300, 'python3 tools/perf-sensors.py --seconds=300 --output="$OUT/idle.jsonl"'),
        ('load', 'board', 600,
         'stress-ng --cpu 8 --cpu-method matrixprod --timeout 600s --metrics-brief'),
    ):
        cases.append(dict(id=name, location=location, seconds=seconds, command=command))
    return dict(schema=1, backend=backend, execution='plan-only', status='待测',
                locks=['/tmp/vim4-board.lock', '/tmp/vim4-heavy.lock'],
                repetitions='three A/B/A groups, A=5.15 B=7.3', cases=cases)


def compare(report):
    """Gate one metric/config; callers retain raw evidence for every A/B/A run."""
    status = report.get('status')
    if status in ('能力缺失', '待测', '测量缺失', '受干扰', '失败'):
        return dict(status=status)
    if status != 'ok':
        raise ValueError('explicit measurement status required')
    direction = report['direction']
    if direction not in ('higher', 'lower', 'zero'):
        raise ValueError('unknown direction')
    # Named policies keep callers from choosing an arbitrary passing tolerance.
    policies = {'throughput': (0.05, 0), 'latency-ms': (0.05, 2),
                'power-w': (0.05, 0), 'temperature-c': (0, 2),
                'boot-s': (0.05, 1), 'errors': (0, 0)}
    relative, absolute = policies[report['policy']]
    expected_direction = ('higher' if report['policy'] == 'throughput' else
                          'zero' if report['policy'] == 'errors' else 'lower')
    if direction != expected_direction:
        raise ValueError('direction disagrees with metric policy')
    if (report['policy'] == 'errors') != (direction == 'zero'):
        raise ValueError('error counts require zero policy/direction')
    groups = report['groups']
    if len(groups) < 3:
        return dict(status='待测', reason='at least three A/B/A groups required')
    changes = []
    verdicts = []
    configuration = None
    for group in groups:
        runs = [group[key] for key in ('before', 'candidate', 'after')]
        if any(run.get('valid') is not True or not run.get('evidence') for run in runs):
            return dict(status='受干扰', reason='invalid run or missing raw evidence')
        if len({run['config_sha256'] for run in runs}) != 1:
            return dict(status='受干扰', reason='workload/userspace configuration mismatch')
        fingerprint = runs[0]['config_sha256']
        if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(
                char not in '0123456789abcdef' for char in fingerprint):
            raise ValueError('config_sha256 must be a SHA256 hex digest')
        if configuration is not None and fingerprint != configuration:
            return dict(status='受干扰', reason='configuration changed between groups')
        configuration = fingerprint
        values = [run['value'] for run in runs]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
               not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('values must be finite nonnegative numbers')
        before, candidate, after = values
        baseline = (before + after) / 2
        tolerance = max(relative * baseline, absolute)
        if abs(before - after) > tolerance:
            return dict(status='受干扰', reason='baseline drift exceeds tolerance')
        delta = candidate - baseline
        changes.append(delta)
        verdicts.append(candidate == before == after == 0 if direction == 'zero' else
                        delta >= -tolerance if direction == 'higher' else delta <= tolerance)
    return dict(status='通过' if all(verdicts) else '性能回退',
                paired_deltas=changes, median_delta=statistics.median(changes),
                note='per metric only; all metrics and validity gates must pass')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('plan').add_argument('--backend', choices=('stock', 'edge'), required=True)
    commands.add_parser('compare').add_argument('report', type=Path)
    args = parser.parse_args()
    result = plan(args.backend) if args.action == 'plan' else compare(json.loads(args.report.read_text()))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.action == 'compare' and result['status'] != '通过':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
