#!/usr/bin/env python3
"""Exclusive bounded DMA comparison; private trace instance, no service changes.

Run as root with --output NEW_DIR and --probe/--shader pointing to the same
ARM64 binaries on each kernel. Only requested named heaps are allocated.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def append_probe(path, definition):
    # Older tracefs rejects the seek-to-end performed by Python append mode.
    fd = os.open(path, os.O_WRONLY | os.O_APPEND)
    try:
        os.write(fd, definition.encode())
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--probe', required=True, type=Path)
    parser.add_argument('--shader', required=True, type=Path)
    parser.add_argument('--heap', action='append', required=True)
    parser.add_argument('--frequency', type=Path)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False, parents=True)
    tracing = Path('/sys/kernel/tracing')
    instance = tracing / 'instances/vim4_kbase_r6'
    instance.mkdir(exist_ok=False)
    events = []
    controls = []
    probes = []
    report = {'kernel': os.uname().release, 'runs': []}
    try:
        (instance / 'buffer_size_kb').write_text('32768')
        (instance / 'trace_clock').write_text('mono')
        # Current kernels provide the complete SG lengths in DMA tracepoints.
        for name in ('dma_sync_sg_for_cpu', 'dma_sync_sg_for_device',
                     'dma_sync_single_for_cpu', 'dma_sync_single_for_device'):
            event = instance / 'events/dma' / name / 'enable'
            if event.exists():
                controls.append(event); events.append(str(event.relative_to(instance)))
        if not events:
            symbols = {line.split()[-1] for line in Path('/proc/kallsyms').read_text().splitlines()}
            for name in ('dma_sync_sg_for_cpu', 'dma_sync_sg_for_device'):
                if name not in symbols:
                    continue
                label = 'vim4_r6_' + name
                # ARM64 scatterlist.length offset is 12; valid total only for
                # nents=1. Preserve raw events rather than multiplying lengths.
                definition = (f'p:vim4_r6/{label} {name} device=%x0:x64 nents=%x2:u32 '
                              'first_address=+16(%x1):x64 first_length=+12(%x1):u32\n')
                append_probe(tracing / 'kprobe_events', definition)
                probes.append(label)
                controls.append(instance / 'events/vim4_r6' / label / 'enable')
                events.append(label)
        # Architecture operations count actual cache maintenance bytes, even
        # when a DMA API tracepoint reports a coherent no-op request.
        symbols = {line.split()[-1] for line in Path('/proc/kallsyms').read_text().splitlines()}
        for name in ('arch_sync_dma_for_cpu', 'arch_sync_dma_for_device'):
            if name not in symbols:
                continue
            label = 'vim4_r6_' + name
            append_probe(tracing / 'kprobe_events', f'p:vim4_r6/{label} {name} address=%x0:x64 bytes=%x1:u64\n')
            probes.append(label)
            controls.append(instance / 'events/vim4_r6' / label / 'enable')
            events.append(label)
        if not events:
            raise RuntimeError('No supported named DMA sync events; counts unavailable')
        for name in ('clk_set_rate', 'clk_enable', 'clk_disable'):
            event = instance / 'events/clk' / name / 'enable'
            if event.exists():
                controls.append(event); events.append(str(event.relative_to(instance)))
        report['events'] = events
        report['architectureScope'] = 'All devices; correlate addresses with Mali SG events before attributing bytes'
        clocks = Path('/sys/kernel/debug/clk/clk_summary')
        if clocks.exists():
            report['gpuClocksBefore'] = [line for line in clocks.read_text().splitlines()
                                         if 'gpu' in line.lower() or 'mali' in line.lower()]
        for heap in args.heap:
            for traced in (False, True):
                name = Path(heap).name + ('-trace' if traced else '-plain')
                env = dict(os.environ)
                for key in ('GPU_TRACE_MARKER', 'GPU_TIMESTAMP', 'GPU_FREQ_PATH'):
                    env.pop(key, None)
                # tracing_on=0 alone leaves kprobe traps installed. Remove
                # event activation as well for an uninstrumented comparison.
                for control in controls:
                    control.write_text('1' if traced else '0')
                if args.frequency:
                    env['GPU_FREQ_PATH'] = str(args.frequency)
                if traced:
                    (instance / 'trace').write_text('')
                    (instance / 'tracing_on').write_text('1')
                    env['GPU_TRACE_MARKER'] = str(instance / 'trace_marker')
                    env['GPU_TIMESTAMP'] = '1'
                else:
                    (instance / 'tracing_on').write_text('0')
                command = ['python3', str(Path(__file__).with_name('run.py')), '--',
                           str(args.probe), str(args.shader), heap, '10']
                before = subprocess.check_output(['dmesg'], text=True)
                with (args.output / (name + '.txt')).open('w') as output:
                    process = subprocess.Popen(command, env=env, stdout=output,
                                               stderr=subprocess.STDOUT, start_new_session=True)
                    deadline = time.monotonic() + 40
                    stopped = None
                    while process.poll() is None:
                        current = subprocess.check_output(['dmesg'], text=True)
                        delta = current[len(before):] if current.startswith(before) else current
                        if any(token in delta for token in ('WARNING:', 'BUG:', 'Oops:',
                               'GPU Fault ', 'Unhandled Page fault', 'GPU fault 0x')):
                            stopped = 'kernel/GPU fault'
                        if time.monotonic() > deadline:
                            stopped = 'timeout'
                        if stopped:
                            os.killpg(process.pid, signal.SIGTERM)
                            try:
                                process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=3)
                            break
                        time.sleep(.1)
                (instance / 'tracing_on').write_text('0')
                if traced:
                    (args.output / (name + '.trace')).write_text((instance / 'trace').read_text())
                    stats = {str(p.relative_to(instance)): p.read_text()
                             for p in instance.glob('per_cpu/cpu*/stats')}
                    (args.output / (name + '-stats.json')).write_text(json.dumps(stats, indent=2))
                final_log = subprocess.check_output(['dmesg'], text=True)
                (args.output / (name + '-dmesg.txt')).write_text(final_log)
                delta = final_log[len(before):] if final_log.startswith(before) else final_log
                if any(token in delta for token in ('WARNING:', 'BUG:', 'Oops:',
                       'GPU Fault ', 'Unhandled Page fault', 'GPU fault 0x')):
                    stopped = 'kernel/GPU fault'
                report['runs'].append({'heap': heap, 'trace': traced, 'exit': process.returncode, 'stop': stopped})
                if stopped or process.returncode:
                    raise RuntimeError(f'{name}: {stopped or process.returncode}')
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        clocks = Path('/sys/kernel/debug/clk/clk_summary')
        if clocks.exists():
            report['gpuClocksAfter'] = [line for line in clocks.read_text().splitlines()
                                        if 'gpu' in line.lower() or 'mali' in line.lower()]
        cleanup_errors = []
        try:
            (instance / 'tracing_on').write_text('0')
            for event in instance.glob('events/*/*/enable'):
                if event.read_text().strip() == '1': event.write_text('0')
            instance.rmdir()
        except OSError as error:
            cleanup_errors.append(str(error))
        for label in probes:
            try:
                append_probe(tracing / 'kprobe_events', f'-:vim4_r6/{label}\n')
            except OSError as error:
                cleanup_errors.append(str(error))
        if cleanup_errors:
            report['cleanupErrors'] = cleanup_errors
        (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        if cleanup_errors:
            raise RuntimeError('Trace cleanup failed: ' + '; '.join(cleanup_errors))


if __name__ == '__main__':
    main()
