#!/usr/bin/env python3
"""Normalize CPU-visible HEVC traces; report the first phase-local divergence.

Register addresses are DOS word indices. Allocation values are normalized only
for registers and regions explicitly declared in each capture's address map.
Snapshots can exercise parsing but cannot stand in for an access trace.
"""
import argparse
import json
from pathlib import Path
import re

HGT = re.compile(r'HGT p=(\d+) op=([RWEIFL]) reg=([0-9a-fA-F]+) val=([0-9a-fA-F]+)')
REGMAP = re.compile(r'regmap_reg_(read|write):\s+(\S+) reg=([0-9a-fA-F]+) val=([0-9a-fA-F]+)')
PHASES = {'before-reset': 5, 'after-reset': 5, 'after-start': 5, 'timeout': 5}
SNAP_REGS = {'reset': 0x3f34, 'mpsr': 0x3301, 'cpsr': 0x3321,
             'pc': 0x3308, 'status': 0x30c0, 'mask': 0x3072,
             'rd': 0x3105, 'wr': 0x3104, 'control': 0x3101, 'fifo': 0x3107,
             'wait': 0x30ce, 'size': 0x30d7, 'shift': 0x310d,
             'shift_status': 0x310b, 'parser_irq': 0x3120,
             'mode': 0x30d3, 'mode_or_nal': 0x30d3, 'search': 0x30d2}


def number(value):
    return int(value, 0) if isinstance(value, str) else value


def mapped_value(reg, value, mapping):
    if reg not in {number(x) for x in mapping.get('address_registers', [])}:
        return value
    matches = []
    for region in mapping.get('regions', []):
        base, size = number(region['start']), number(region['size'])
        endpoint = reg in {number(x) for x in mapping.get('endpoint_registers', [])}
        if base <= value < base + size or (endpoint and value == base + size):
            matches.append({'region': region['name'], 'offset': value - base})
    if len(matches) > 1:
        raise ValueError('overlapping allocation regions for address value')
    if matches:
        return matches[0]
    return value


def normalize(raw, source, stats=None, mapping=None):
    mapping = mapping or {}
    lost = bool(re.search(r'LOST\s+\d+\s+EVENTS', raw))
    counters = re.findall(r'^\s*(?:commit )?overrun:\s*(\d+)', stats or '', re.M)
    if stats is not None and not counters:
        raise ValueError('stats must contain per-CPU overrun counters')
    lost |= any(int(x) for x in counters)
    header = re.search(r'entries-in-buffer/entries-written:\s*(\d+)/(\d+)', raw)
    lost |= bool(header and int(header[2]) > int(header[1]))
    events, phases = [], []
    phase = 0
    for line_number, line in enumerate(raw.splitlines(), 1):
        if source == 'snapshot':
            if line.startswith('{'):
                line = json.loads(line).get('MESSAGE', '')
            found = re.search(r'hevc: (before-reset|after-reset|after-start|timeout) ', line)
            if not found:
                continue
            for key, val in re.findall(r'([a-z_]+)=([0-9a-fA-F]{8})\b', line):
                if key in SNAP_REGS:
                    events.append(dict(p=PHASES[found[1]], op='S', reg=SNAP_REGS[key],
                                       val=int(val, 16), line=line_number))
            continue
        found = HGT.search(line)
        if found:
            p, op, reg, value = found.groups()
            phase, reg, value = int(p), int(reg, 16), int(value, 16)
            if op == 'E':
                if not phases or phases[-1] != phase:
                    phases.append(phase)
            if source == 'regmap' and op in 'RW':
                continue  # Native regmap events cover MMIO, including update_bits.
        else:
            found = REGMAP.search(line) if source == 'regmap' else None
            if not found:
                continue
            operation, device, reg, value = found.groups()
            if device != 'fe320000.video-codec':
                continue
            reg, value = int(reg, 16), int(value, 16)
            if reg % 4:
                raise ValueError('unaligned DOS byte offset')
            reg >>= 2
            if not (0x3000 <= reg < 0x3f00 or 0x3f33 <= reg <= 0x3f35):
                continue
            op = 'R' if operation == 'read' else 'W'
        if not phases or phases[-1] != phase:
            phases.append(phase)
        events.append(dict(p=phase, op=op, reg=reg,
                           val=mapped_value(reg, value, mapping), line=line_number))
        if op == 'E' and phase == 7:
            break
    if not events:
        raise ValueError('no matching HEVC records')
    meta = dict(kind='meta', source=source, loss_checked=stats is not None,
                lost=lost, phases=phases, snapshot=source == 'snapshot')
    return [meta, *events]


def compare(left, right, reads=False):
    for records in (left, right):
        meta = records[0]
        if meta.get('kind') != 'meta' or meta.get('snapshot'):
            raise ValueError('comparison requires access traces, not snapshots')
        if not meta.get('loss_checked') or meta.get('lost'):
            raise ValueError('missing loss counters or dropped/overwritten events')
        if 1 not in meta['phases']:
            raise ValueError('capture does not include power phase')
    if 7 not in left[0]['phases']:
        raise ValueError('golden capture does not reach first picture completion')
    operations = 'RWIFL' if reads else 'WIFL'
    order = list(dict.fromkeys(left[0]['phases'] + right[0]['phases']))
    report = dict(equal=True, phase_order_left=left[0]['phases'],
                  phase_order_right=right[0]['phases'], first_divergence=None,
                  compared_reads=reads,
                  phase_order_differs=left[0]['phases'] != right[0]['phases'])
    count = 0
    for phase in order:
        streams = [[x for x in data[1:] if x['p'] == phase and x['op'] in operations]
                   for data in (left, right)]
        if (phase in left[0]['phases']) != (phase in right[0]['phases']):
            report.update(equal=False, first_divergence=dict(phase=phase, reason='missing phase'))
            return report
        for index in range(max(map(len, streams))):
            a, b = (s[index] if index < len(s) else None for s in streams)
            if (None if a is None else (a['op'], a['reg'], a['val'])) != \
               (None if b is None else (b['op'], b['reg'], b['val'])):
                report.update(equal=False, first_divergence=dict(phase=phase, index=index,
                              left=a, right=b, reason='value or access order'))
                return report
            count += 1
    if not count:
        raise ValueError('no comparable writes, firmware results or IRQ events')
    report['compared_events'] = count
    if report['phase_order_differs']:
        report.update(equal=False, first_divergence=dict(reason='phase order'))
    return report


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    normal = commands.add_parser('normalize')
    normal.add_argument('input', type=Path)
    normal.add_argument('output', type=Path)
    normal.add_argument('--source', choices=['custom', 'regmap', 'snapshot'], required=True)
    normal.add_argument('--stats', type=Path)
    normal.add_argument('--address-map', type=Path)
    diff = commands.add_parser('compare')
    diff.add_argument('golden')
    diff.add_argument('candidate')
    diff.add_argument('--reads', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'normalize':
            records = normalize(args.input.read_text(), args.source,
                                args.stats.read_text() if args.stats else None,
                                json.loads(args.address_map.read_text()) if args.address_map else None)
            args.output.write_text(''.join(json.dumps(x) + '\n' for x in records))
            return 0
        result = compare(read_jsonl(args.golden), read_jsonl(args.candidate), args.reads)
        print(json.dumps(result, indent=2))
        return 0 if result['equal'] else 1
    except (ValueError, KeyError, OSError) as error:
        parser.exit(2, f'{error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
