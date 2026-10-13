#!/usr/bin/env python3
"""Summarize input-check logs; same Mac must send browser input and receive USB.

Usage: input-summary.py LOG_PREFIX
Measures WebSocket.send invocation to target app receipt (pointer polling for
movement). Excludes physical input, browser event dispatch, and video return.
"""
import argparse
import json
import statistics
from pathlib import Path


def distribution(values):
    if not values or min(values) < 0:
        raise ValueError('Missing events or negative latency; check matching and clocks')
    return dict(count=len(values), median=statistics.median(values), maximum=max(values))


def pair(sent, received):
    if len(sent) != len(received):
        raise ValueError(f'Unmatched input events: sent {len(sent)}, received {len(received)}')
    return distribution([r['receivedMs'] - s['at'] for s, r in zip(sent, received)])


def summarize(browser, host):
    phases = [r for r in browser if r['kind'] == 'phase']
    reports = [r for r in browser if r['kind'] == 'report']
    if not phases or phases[-1]['name'] != 'done':
        raise ValueError('Input test did not finish')
    if not reports or max(abs(r['clockOffset']) for r in reports) > 2:
        raise ValueError('Browser clock mapping exceeded 2ms or no reports')
    result = {'target': next(r for r in host if r['kind'] == 'ready')}
    for start, end in zip(phases, phases[1:]):
        sent = [r for r in reports if start['at'] <= r['at'] < end['at']]
        received = [r for r in host if start['at'] <= r['receivedMs'] < end['at']]
        name = start['name']
        if name in ('tap', 'hold', 'blur'):
            keys = [r for r in sent if r['bytes'][0] == 1]
            down = [r for r in keys if r['bytes'][3] == 79]
            up = [r for r in keys if not any(r['bytes'][1:])]
            native_down = [r for r in received if r['kind'] == 'keydown' and not r['repeat']]
            native_up = [r for r in received if r['kind'] == 'keyup']
            repeat = [r for r in received if r['kind'] == 'keydown' and r['repeat']]
            # Blur sends redundant neutral states; the host emits only one release.
            if name == 'blur':
                up = up[:1]
            result[name] = dict(down=pair(down, native_down), up=pair(up, native_up),
                                repeated_events=len(repeat))
            if repeat:
                if len(down) != 1 or len(native_up) != 1:
                    raise ValueError('Unexpected repeated-key lifecycle')
                if any(r['receivedMs'] >= native_up[0]['receivedMs'] for r in repeat):
                    raise ValueError('Key repeated after release')
                result[name]['repeat_delay_ms'] = repeat[0]['receivedMs'] - native_down[0]['receivedMs']
                if len(repeat) > 1:
                    result[name]['repeat_interval_ms'] = distribution([
                        b['receivedMs'] - a['receivedMs'] for a, b in zip(repeat, repeat[1:])])
        elif name == 'move':
            result[name] = pair([r for r in sent if r['bytes'][0] == 2],
                                [r for r in received if r['kind'] == 'move'])
        elif name == 'click':
            result[name] = {}
            for kind in ('mousedown', 'mouseup'):
                result[name][kind] = pair([
                    r for r in sent if r['bytes'][0] == 2 and
                    bool(r['bytes'][1]) == (kind == 'mousedown')],
                    [r for r in received if r['kind'] == kind])
        elif name.startswith('wheel-'):
            wheels = [r for r in sent if r['bytes'][0] == 2 and r['bytes'][-1]]
            native = [r for r in received if r['kind'] == 'wheel']
            result[name] = dict(latency=pair(wheels, native),
                                hid=[r['bytes'][-1] if r['bytes'][-1] < 128 else r['bytes'][-1]-256 for r in wheels],
                                native_delta_y=[r['dy'] for r in native],
                                natural_scroll=[r['inverted'] for r in native])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prefix')
    args = parser.parse_args()
    browser = json.loads(Path(args.prefix + '-browser.json').read_text())
    host = [json.loads(line) for line in Path(args.prefix + '-host.jsonl').read_text().splitlines()]
    print(json.dumps(summarize(browser, host), indent=2))
