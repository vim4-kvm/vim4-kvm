#!/usr/bin/env python3
"""Join every browser callback to independently decoded source IDs by RTP timestamp.

The mapping must come from captured access units, not an assumed frame interval:
{"ssrc": 123, "frames": [{"rtpTimestamp": 9000, "id": 42, "valid": true}]}.
Use latency-receiver.mjs --rtp-timeline. Pixel readbacks remain an independent
cross-check; a later canvas frame must not replace the callback's actual frame.
"""
import argparse
from collections import Counter
import json
import math
import statistics


def distribution(values):
    values = sorted(values)
    return dict(count=len(values), min=values[0], median=statistics.median(values),
                p95=values[math.ceil(len(values) * .95) - 1],
                p99=values[math.ceil(len(values) * .99) - 1], max=values[-1])


def summarize(source, receiver, mapping):
    before, after = receiver['before'], receiver['after']
    if (not receiver.get('rtpTimeline') or before['ssrc'] != after['ssrc']
            or mapping['ssrc'] != after['ssrc']):
        raise ValueError('RTP timeline missing or SSRC changed/mismatched')
    if receiver.get('clockDiscontinuities', 0):
        raise ValueError('Browser clock changed abruptly')
    source_by_id = {}
    for frame in source:
        if frame['id'] in source_by_id:
            raise ValueError('Source frame ID wrapped; use a shorter source log')
        source_by_id[frame['id']] = frame
    by_rtp = {}
    for frame in mapping['frames']:
        timestamp = frame['rtpTimestamp']
        if timestamp in by_rtp or not frame.get('valid'):
            raise ValueError('Ambiguous RTP association or invalid decoded marker')
        by_rtp[timestamp] = frame

    values, receive_to_compositor, uncertainties = [], [], []
    missing, seen = Counter(), set()
    for callback in receiver['timeline']:
        timestamp = callback.get('rtpTimestamp')
        if timestamp in seen:
            raise ValueError('Repeated RTP timestamp in callback timeline')
        seen.add(timestamp)
        uncertainty = callback.get('clockUncertaintyMs', math.inf)
        if not math.isfinite(uncertainty) or not 0 <= uncertainty <= 2:
            raise ValueError('Browser clock uncertainty exceeds 2ms')
        frame = by_rtp.get(timestamp)
        if frame is None:
            missing['rtp_not_mapped'] += 1
            continue
        source_frame = source_by_id.get(frame['id'])
        if source_frame is None:
            missing['source_id_missing'] += 1
            continue
        latency = callback['presentationWallMs'] - source_frame['sourceMs']
        if not math.isfinite(latency) or latency < 0:
            raise ValueError('Negative or nonfinite latency; check frame and clock association')
        values.append(latency)
        uncertainties.append(uncertainty)
        if callback.get('receiveWallMs') is not None:
            delta = callback['presentationWallMs'] - callback['receiveWallMs']
            if not math.isfinite(delta) or delta < 0:
                raise ValueError('Invalid browser receive/compositor ordering')
            receive_to_compositor.append(delta)
    if not values:
        raise ValueError('No callbacks matched independently decoded source IDs')
    checked_pixels, mismatched_pixels = 0, 0
    for pixel in receiver['frames']:
        frame = by_rtp.get(pixel.get('rtpTimestamp'))
        if frame is not None:
            checked_pixels += 1
            mismatched_pixels += frame['id'] != pixel['id']
    return dict(
        endpoint='source draw start to browser compositor submission',
        association='independently decoded AU ID and unique RTP timestamp',
        callbacks=len(receiver['timeline']), matchedCallbacks=len(values),
        unmatched=dict(missing), completeAssociation=not missing,
        presentationMs=distribution(values), clockUncertaintyMs=distribution(uncertainties),
        receiveToCompositorMs=distribution(receive_to_compositor) if receive_to_compositor else None,
        checkedPixelReadbacks=checked_pixels, pixelReadbackMismatches=mismatched_pixels,
        p99SampleCountSufficient=len(values) >= 1000,
        # A missing slow callback association must not silently produce a pass.
        p99AssociationComplete=len(values) >= 1000 and not missing,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', help='Source draw JSONL, with unique frame IDs')
    parser.add_argument('receiver', help='Receiver JSON captured with --rtp-timeline')
    parser.add_argument('mapping', help='Verified AU-to-RTP mapping JSON; see module description')
    args = parser.parse_args()
    with open(args.source) as stream:
        source = [json.loads(line) for line in stream]
    with open(args.receiver) as stream:
        receiver = json.load(stream)
    with open(args.mapping) as stream:
        mapping = json.load(stream)
    print(json.dumps(summarize(source, receiver, mapping), indent=2))


if __name__ == '__main__':
    main()
