#!/usr/bin/env python3
"""Summarize fixed-input VBV experiments; FIFO results are a model, not network measurements."""
import argparse
import csv
import json
import math
from pathlib import Path


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def peak_mbps(sizes, frame_count, fps=60):
    """Largest complete frame-aligned window; do not divide a partial window by its full width."""
    if len(sizes) < frame_count or frame_count <= 0:
        raise ValueError('insufficient frames for a complete window')
    total = sum(sizes[:frame_count])
    peak = total
    for index in range(frame_count, len(sizes)):
        total += sizes[index] - sizes[index - frame_count]
        peak = max(peak, total)
    return peak * 8 * fps / frame_count / 1e6


def fifo_tail_ms(rows, capacity_bps):
    """Instantaneous AU arrival at media PTS, constant-rate FIFO, no overhead or loss.

    Return arrival-to-last-byte service completion, including the current AU's
    own serialization. This deliberately does not use offline execution speed.
    """
    if capacity_bps <= 0:
        raise ValueError('capacity must be positive')
    end = 0.0
    delays = []
    for row in rows:
        arrival = row['pts_ns'] / 1e9
        end = max(end, arrival) + row['bytes'] * 8 / capacity_bps
        delays.append((end - arrival) * 1000)
    return delays


def load_rows(path, expected_frames=720):
    with path.open() as stream:
        rows = [{key: int(value) for key, value in row.items()} for row in csv.DictReader(stream)]
    if len(rows) != expected_frames:
        raise ValueError(f'{path}: incomplete frame count')
    for index, row in enumerate(rows):
        if row['frame'] != index or row['bytes'] <= 0 or row['encoder_us'] <= 0:
            raise ValueError(f'{path}: invalid frame {index}')
        if row['finished_us'] - row['entered_us'] != row['encoder_us']:
            raise ValueError(f'{path}: unmatched timing')
        if index and row['pts_ns'] - rows[index - 1]['pts_ns'] not in (16666666, 16666667):
            raise ValueError(f'{path}: unexpected media cadence')
    return rows


def summarize(rows, target_kbps, warmup=30):
    measured = rows[warmup:]
    sizes = [row['bytes'] for row in measured]
    durations = [row['encoder_us'] / 1000 for row in measured]
    delays = fifo_tail_ms(rows, target_kbps * 1000 * 1.2)[warmup:]
    return {
        'frames': len(rows), 'measured_frames': len(measured),
        'initial_au_bytes': rows[0]['bytes'],
        'mean_mbps': sum(sizes) * 8 * 60 / len(sizes) / 1e6,
        'au_bytes_p50': percentile(sizes, .5), 'au_bytes_p99': percentile(sizes, .99),
        'au_bytes_max': max(sizes),
        'peak_100ms_mbps': peak_mbps(sizes, 6),
        'peak_500ms_mbps': peak_mbps(sizes, 30),
        'peak_1s_mbps': peak_mbps(sizes, 60),
        'encoder_ms_p50': percentile(durations, .5),
        'encoder_ms_p99': percentile(durations, .99),
        'fifo_model_capacity_mbps': target_kbps * 1.2 / 1000,
        'fifo_model_tail_ms_p99': percentile(delays, .99),
        'fifo_model_tail_ms_max': max(delays),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    windows = json.loads((args.directory / 'windows.json').read_text())
    output = []
    for window in windows:
        name = window['name']
        rows = load_rows(args.directory / (name + '.csv'))
        result = {**window, **summarize(rows, window['bitrate_kbps'])}
        result['scenes'] = {
            label: summarize(rows[start:end], window['bitrate_kbps'], warmup=0)
            for label, start, end in [('static', 30, 120), ('motion', 120, 360),
                                      ('stress', 360, 480), ('static_return', 480, 600),
                                      ('motion_return', 600, 720)]
        }
        temperatures = (args.directory / (name + '.temperature')).read_text().split()
        result['temperature_c'] = [int(value) / 1000 for value in temperatures]
        output.append(result)
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
