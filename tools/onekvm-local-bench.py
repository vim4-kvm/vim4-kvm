#!/usr/bin/env python3
"""Benchmark Wave5 buffer helpers without opening capture/encoder devices.

Default: build/run in the existing Linux builder. --board uploads only a temporary
test executable and runs it on that board's current kernel; no service changes.
See docs/local-video-benchmark.md for interpretation and kernel regression gates.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FILTER = 'video::pipeline::shared::vim4::wave5::benchmark::local_buffer_paths'
MARKER = 'VIM4_BENCH_JSON '


def command(argv, **kwargs):
    return subprocess.run(argv, check=True, text=True, capture_output=True, **kwargs).stdout.strip()


def parse_result(output):
    records = [json.loads(line.partition(MARKER)[2]) for line in output.splitlines() if MARKER in line]
    if len(records) != 1:
        raise ValueError('Expected exactly one successful benchmark record')
    result = records[0]
    fields = {'schema', 'cases', 'samples', 'workload', 'memory_model', 'arch', 'gstreamer', 'dma_heaps', 'batch_ms'}
    if (not isinstance(result, dict) or not fields <= result.keys() or result.get('schema') != 1 or
            not isinstance(result.get('cases'), list) or not result['cases'] or
            type(result.get('samples')) is not int or result['samples'] < 3):
        raise ValueError('Unsupported or empty benchmark result')
    required = {'name', 'payload_bytes', 'copied_bytes_per_op', 'ns_per_op', 'median_ns', 'p95_ns'}
    if any(not isinstance(case, dict) or not required <= case.keys() or
           not isinstance(case['name'], str) or not case['name'] for case in result['cases']):
        raise ValueError('Incomplete benchmark case')
    names = [case['name'] for case in result['cases']]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate benchmark cases')
    for case in result['cases']:
        values = case['ns_per_op']
        if (not isinstance(values, list) or len(values) != result['samples'] or
                any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                    for v in values + [case['median_ns'], case['p95_ns']])):
            raise ValueError('Invalid or incomplete timing samples')
    return result


def compare(current, baseline):
    # Reports may come from interrupted/manual runs; reject invalid timing data
    # before computing ratios rather than silently accepting NaN/zero baselines.
    parse_result(MARKER + json.dumps(baseline))
    for key in ('schema', 'workload', 'memory_model', 'arch', 'gstreamer', 'dma_heaps',
                'samples', 'batch_ms', 'environment'):
        if key not in current or key not in baseline or current[key] != baseline[key]:
            raise ValueError(f'Incompatible baseline: {key} differs')
    old = {case['name']: case for case in baseline['cases']}
    if set(old) != {case['name'] for case in current['cases']}:
        raise ValueError('Incompatible baseline: case set differs')
    comparisons = []
    for case in current['cases']:
        previous = old[case['name']]
        for key in ('payload_bytes', 'copied_bytes_per_op'):
            if case[key] != previous[key]:
                raise ValueError(f'Incompatible workload for {case["name"]}: {key}')
        comparisons.append(dict(name=case['name'],
                                median_change_pct=(case['median_ns'] / previous['median_ns'] - 1) * 100,
                                p95_change_pct=(case['p95_ns'] / previous['p95_ns'] - 1) * 100))
    return comparisons


def source_state(repository):
    status = command(['git', '-C', str(repository), 'status', '--porcelain'])
    files = ['Cargo.lock', 'src/video/pipeline/shared/vim4/wave5.rs',
             'src/video/pipeline/shared/vim4/wave5_bench.rs']
    return dict(revision=command(['git', '-C', str(repository), 'rev-parse', 'HEAD']),
                dirty=bool(status), files_sha256={name: hashlib.sha256((repository / name).read_bytes()).hexdigest()
                                                for name in files})


def builder(container, repository):
    mounts = json.loads(command(['docker', 'inspect', '--format', '{{json .Mounts}}', container]))
    if not any(m['Destination'] == '/work' and Path(m['Source']).resolve() == repository for m in mounts):
        raise ValueError('Builder /work must bind the current One-KVM checkout')
    print('Building release benchmark (no application installation)...', file=sys.stderr, flush=True)
    output = command(['docker', 'exec', '-w', '/work', container, 'cargo', 'test', '--locked',
                      '--release', '--features', 'vim4', '--lib', '--no-run', '--message-format=json'])
    executables = []
    for line in output.splitlines():
        artifact = json.loads(line)
        if artifact.get('reason') == 'compiler-artifact' and artifact.get('executable'):
            executables.append(artifact['executable'])
    if len(executables) != 1:
        raise ValueError('Expected exactly one library test executable')
    return executables[0]


def run_benchmark(args, executable):
    env = [f'VIM4_BENCH_SAMPLES={args.samples}', f'VIM4_BENCH_BATCH_MS={args.batch_ms}',
           'GST_PLUGIN_SYSTEM_PATH=', 'GST_PLUGIN_SYSTEM_PATH_1_0=',
           'GST_PLUGIN_PATH=', 'GST_PLUGIN_PATH_1_0=']
    test = [FILTER, '--exact', '--ignored', '--nocapture', '--test-threads=1']
    if not args.board:
        scratch = command(['docker', 'exec', args.container, 'mktemp', '-d', '/tmp/vim4-buffer-bench.XXXXXXXX'])
        if not scratch.startswith('/tmp/vim4-buffer-bench.') or '/' in scratch.removeprefix('/tmp/'):
            raise ValueError('Unexpected builder temporary directory')
        try:
            output = command(['docker', 'exec', '-w', '/work', args.container, 'env', *env,
                              f'GST_REGISTRY={scratch}/registry.bin', executable, *test])
        finally:
            command(['docker', 'exec', args.container, 'rm', '-rf', '--', scratch])
        environment = dict(target='builder', host=platform.node(),
                           image=command(['docker', 'inspect', '--format', '{{.Image}}', args.container]),
                           limits=json.loads(command(['docker', 'inspect', '--format',
                               '{"cpuset":{{json .HostConfig.CpusetCpus}},"nanocpus":{{.HostConfig.NanoCpus}},'
                               '"memory":{{.HostConfig.Memory}}}', args.container])),
                           kernel=command(['docker', 'exec', args.container, 'uname', '-r']))
        return parse_result(output), environment

    ssh = ['ssh', '-o', 'BatchMode=yes', args.board]
    # Isolated test artifact only: no /boot, /opt, module or systemd writes.
    remote = command([*ssh, 'mktemp -d /var/tmp/vim4-buffer-bench.XXXXXXXX'])
    if not remote.startswith('/var/tmp/vim4-buffer-bench.') or '/' in remote.removeprefix('/var/tmp/'):
        raise ValueError('Unexpected remote temporary directory')
    try:
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'bench'
            command(['docker', 'cp', f'{args.container}:{executable}', str(binary)])
            digest = hashlib.sha256(binary.read_bytes()).hexdigest()
            command(['scp', '-q', '-o', 'BatchMode=yes', str(binary), f'{args.board}:{remote}/bench'])
        remote_hash = command([*ssh, shlex.join(['sha256sum', f'{remote}/bench'])]).split()[0]
        if remote_hash != digest:
            raise ValueError('Remote executable hash mismatch')
        if args.dma_heaps:
            env.append(f'VIM4_BENCH_DMA_HEAPS={args.dma_heaps}')
        # GstDmaBufMemory/VideoMeta are library APIs. No plugins are needed;
        # an isolated registry also prevents V4L2 discovery during gst_init.
        env.append(f'GST_REGISTRY={remote}/registry.bin')
        metadata = command([*ssh, "uname -r; uname -v; uname -m; cat /sys/devices/system/cpu/online; "
                            "cat /sys/devices/system/cpu/cpufreq/policy*/scaling_governor; "
                            "systemctl is-active one-kvm.service one-kvm-edge.service || true"])
        run = ['sudo', '-n', 'flock', '-n', '/run/lock/vim4-buffer-bench.lock',
               'taskset', '-c', str(args.cpu), 'env', *env, f'{remote}/bench', *test]
        output = command([*ssh, shlex.join(run)])
        result = parse_result(output)
        result['executable_sha256'] = digest
        result['load_after'] = command([*ssh, 'uptime; ps -C one-kvm -o pid,pcpu,nlwp || true'])
        environment = dict(target=args.board, cpu=args.cpu, system=metadata)
        return result, environment
    finally:
        command([*ssh, shlex.join(['rm', '-rf', '--', remote])])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', default='vim4-wave5-build')
    parser.add_argument('--board', help='SSH target; runs on its current kernel without rebooting')
    parser.add_argument('--cpu', type=int, default=0, help='Board benchmark CPU only (default A73 CPU0)')
    parser.add_argument('--dma-heaps', help='Board only: comma-separated /dev/dma_heap paths; allocates private buffers')
    parser.add_argument('--kernel-source', type=Path, help='Also run local C ownership/offset/rollback regression gates')
    parser.add_argument('--samples', type=int, default=9)
    parser.add_argument('--batch-ms', type=int, default=100)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--max-regression-pct', type=float, help='Fail if any case median exceeds baseline by this percent')
    parser.add_argument('--output', required=True, type=Path, help='New JSON path; never overwrites a report')
    args = parser.parse_args()
    if not 3 <= args.samples <= 100 or not 10 <= args.batch_ms <= 1000 or args.cpu < 0:
        parser.error('samples=3..100, batch-ms=10..1000 and cpu>=0 required')
    if args.dma_heaps and (not args.board or any(not p.startswith('/dev/dma_heap/') for p in args.dma_heaps.split(','))):
        parser.error('--dma-heaps requires --board and /dev/dma_heap paths')
    if args.max_regression_pct is not None and (not args.baseline or not math.isfinite(args.max_regression_pct) or args.max_regression_pct < 0):
        parser.error('--max-regression-pct requires --baseline and a finite nonnegative percentage')
    if args.output.exists():
        parser.error('Output exists; choose a new report path')
    baseline = None
    if args.baseline:
        baseline = json.loads(args.baseline.read_text())
        parse_result(MARKER + json.dumps(baseline))
    repository = (ROOT / 'One-KVM').resolve()
    source = source_state(repository)
    regressions = []
    if args.kernel_source:
        kernel = args.kernel_source.resolve()
        for relative in ('amlogic/t7-hdmirx/test_stream.py', 'chips-media/wave5/test_buffers.py',
                         'chips-media/wave5/test_encoder_cleanup.py'):
            script = kernel / 'drivers/media/platform' / relative
            result = command([sys.executable, str(script)])
            print(result, file=sys.stderr)
            regressions.append(dict(test=relative, output=result))
    executable = builder(args.container, repository)
    if source_state(repository) != source:
        raise ValueError('One-KVM sources changed during the benchmark build; rerun with stable sources')
    result, environment = run_benchmark(args, executable)
    result.update(source=source, environment=environment, kernel_regressions=regressions,
                  measured_at=datetime.now(timezone.utc).isoformat())
    if args.kernel_source:
        result['kernel_source'] = dict(revision=command(['git', '-C', str(kernel), 'rev-parse', 'HEAD']),
                                       dirty=bool(command(['git', '-C', str(kernel), 'status', '--porcelain'])))
    if baseline is not None:
        result['comparison'] = compare(result, baseline)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as report:
        json.dump(result, report, indent=2, allow_nan=False)
        report.write('\n')
    for case in result['cases']:
        print(f'{case["name"]}: median {case["median_ns"] / 1000:.2f} us; p95 {case["p95_ns"] / 1000:.2f} us')
    print(f'Report: {args.output}')
    if args.max_regression_pct is not None and any(
            case['median_change_pct'] > args.max_regression_pct for case in result['comparison']):
        return 2
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print((error.stdout or '')[-12000:], file=sys.stderr)
            print((error.stderr or '')[-12000:], file=sys.stderr)
        sys.exit(1)
