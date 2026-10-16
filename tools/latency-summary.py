#!/usr/bin/env python3
"""Match HDMI pixel IDs using source and browser timestamps from the same Mac."""
import argparse
import json
import math
import statistics


def distribution(values):
    values = sorted(values)
    if not values:
        raise ValueError('No matching frames')
    return dict(count=len(values), min=values[0], median=statistics.median(values),
                p95=values[math.ceil(len(values) * .95) - 1],
                p99=values[math.ceil(len(values) * .99) - 1], max=values[-1])


def cadence(receiver):
    """Include silent tails; percentiles alone hide a stalled final frame."""
    start, end = receiver['startedMs'], receiver['endedMs']
    if end <= start:
        raise ValueError('Invalid measurement window')
    timeline = receiver['timeline']
    if not timeline:
        return {'callbacks': 0, 'maxNoCallbackMs': end - start,
                'presentedFPS': 0, 'missedCallbacks': 0}
    gaps, missed = [], 0
    for previous, current in zip(timeline, timeline[1:]):
        gap = current['presentationMs'] - previous['presentationMs']
        frames = current['presentedFrames'] - previous['presentedFrames']
        if gap <= 0 or frames <= 0:
            raise ValueError('Presentation timeline reset or did not advance')
        gaps.append(gap)
        missed += frames - 1
    callback_times = [start] + [f['callbackMs'] for f in timeline] + [end]
    callback_gaps = [max(0, b - a) for a, b in zip(callback_times, callback_times[1:])]
    span = timeline[-1]['presentationMs'] - timeline[0]['presentationMs']
    return {
        'callbacks': len(timeline),
        'intervalMs': distribution(gaps) if gaps else None,
        'intervalsOverMs': {str(limit): sum(gap > limit for gap in gaps)
                            for limit in (50, 100, 250)},
        'maxNoCallbackMs': max(callback_gaps),
        'trailingNoCallbackMs': callback_gaps[-1],
        # Active-span FPS and whole-window progress are both needed: a stream
        # can run at 60fps briefly, then stop for the rest of the observation.
        'activePresentedFPS': ((timeline[-1]['presentedFrames'] - timeline[0]['presentedFrames'])
                               * 1000 / span) if span else 0,
        'presentedFPS': (timeline[-1]['presentedFrames'] - timeline[0]['presentedFrames'])
                        * 1000 / (end - start),
        'missedCallbacks': missed,
    }


def summarize(source_path, receiver_path):
    source = {}
    with open(source_path) as stream:
        for line in stream:
            frame = json.loads(line)
            if frame['id'] in source:
                raise ValueError('Source frame ID wrapped; use a shorter run')
            source[frame['id']] = frame
    with open(receiver_path) as stream:
        receiver = json.load(stream)
    before, after = receiver['before'], receiver['after']
    if not before or not after:
        raise ValueError('Missing inbound video statistics')
    seconds = (after['timestamp'] - before['timestamp']) / 1000
    if seconds <= 0 or before.get('ssrc') != after.get('ssrc') or after['framesDecoded'] < before['framesDecoded']:
        raise ValueError('Video statistics reset or measurement duration is invalid')
    result = {}
    if 'timeline' in receiver:
        result['cadence'] = cadence(receiver)
    result['decodedFPS'] = (after['framesDecoded'] - before['framesDecoded']) / seconds
    result['receivedMbps'] = (after['bytesReceived'] - before['bytesReceived']) * 8 / seconds / 1e6
    for key in ('framesDropped', 'packetsLost', 'freezeCount', 'keyFramesDecoded'):
        result[key] = after[key] - before[key]
    for total, count, name in (
        ('jitterBufferDelay', 'jitterBufferEmittedCount', 'actualJitterBufferMs'),
        ('totalDecodeTime', 'framesDecoded', 'meanDecodeMs'),
    ):
        emitted = after.get(count, 0) - before.get(count, 0)
        result[name] = (1000 * (after[total] - before[total]) / emitted
                        if emitted > 0 and total in before and total in after else None)
    if receiver.get('noPixels'):
        return result
    frames = receiver['frames']
    if any(frame['id'] not in source for frame in frames):
        raise ValueError('Source log does not contain every received marker')
    clocks = [frame['clockOffsetMs'] for frame in frames]
    if not clocks or max(abs(value) for value in clocks) > 2:
        raise ValueError('Browser wall/monotonic clock mapping exceeded 2ms')
    for key in ('readStartMs', 'presentationMs', 'expectedDisplayMs', 'observedMs'):
        values = [frame[key] - source[frame['id']]['sourceMs'] for frame in frames]
        if min(values) < 0:
            raise ValueError('Negative latency: check source/receiver clocks')
        result[key] = distribution(values)
    result['readbackCostMs'] = distribution([
        frame['observedMs'] - frame['readStartMs'] for frame in frames])
    result['sourceDrawCostMs'] = distribution([
        frame['drawEndMs'] - frame['sourceMs'] for frame in source.values()])
    first_source = min(source[frame['id']]['sourceMs'] for frame in frames)
    last_source = max(source[frame['id']]['sourceMs'] for frame in frames)
    source_frames = [frame for frame in source.values()
                     if first_source <= frame['sourceMs'] <= last_source]
    result['sourceFPS'] = ((len(source_frames) - 1) * 1000 / (last_source - first_source)
                           if last_source > first_source else 0)
    result['clockOffsetMs'] = distribution(clocks)
    result['invalidMarkers'] = receiver['invalidMarkers']
    result['p99SampleCountSufficient'] = len(frames) >= 1000
    result['markersValid'] = not receiver['invalidMarkers'] and not receiver.get('incoherentMarkers', 0)
    if receiver.get('verifyCoherence'):
        result['incoherentMarkers'] = receiver['incoherentMarkers']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('receiver')
    args = parser.parse_args()
    print(json.dumps(summarize(args.source, args.receiver), indent=2))
