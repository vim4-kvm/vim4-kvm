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
    frames = receiver['frames']
    if any(frame['id'] not in source for frame in frames):
        raise ValueError('Source log does not contain every received marker')
    clocks = [frame['clockOffsetMs'] for frame in frames]
    if not clocks or max(abs(value) for value in clocks) > 2:
        raise ValueError('Browser wall/monotonic clock mapping exceeded 2ms')
    result = {}
    for key in ('readStartMs', 'presentationMs', 'expectedDisplayMs', 'observedMs'):
        values = [frame[key] - source[frame['id']]['sourceMs'] for frame in frames]
        if min(values) < 0:
            raise ValueError('Negative latency: check source/receiver clocks')
        result[key] = distribution(values)
    result['readbackCostMs'] = distribution([
        frame['observedMs'] - frame['readStartMs'] for frame in frames])
    result['sourceDrawCostMs'] = distribution([
        frame['drawEndMs'] - frame['sourceMs'] for frame in source.values()])
    result['clockOffsetMs'] = distribution(clocks)
    result['invalidMarkers'] = receiver['invalidMarkers']
    before, after = receiver['before'], receiver['after']
    seconds = (after['timestamp'] - before['timestamp']) / 1000
    result['decodedFPS'] = (after['framesDecoded'] - before['framesDecoded']) / seconds
    result['receivedMbps'] = (after['bytesReceived'] - before['bytesReceived']) * 8 / seconds / 1e6
    for key in ('framesDropped', 'packetsLost', 'freezeCount', 'keyFramesDecoded'):
        result[key] = after[key] - before[key]
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('receiver')
    args = parser.parse_args()
    print(json.dumps(summarize(args.source, args.receiver), indent=2))
