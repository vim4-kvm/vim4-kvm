#!/usr/bin/env python3
"""Generate an experimental VRR EDID offline; never load it or pulse HPD."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'board'))
from vim4vrr import Range, capabilities, rewrite, select_range


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('--receiver', nargs=2, type=int, required=True, metavar=('MIN', 'MAX'),
                        help='explicit candidate receiver range; not inferred from fixed timings')
    parser.add_argument('--request', nargs=2, type=int, required=True, metavar=('MIN', 'MAX'))
    parser.add_argument('--protocol', choices=('hdmi-forum', 'amd-freesync'), required=True,
                        help='Forum requires minimum <=48 and explicit maximum >=100 Hz; '
                             'mode-dependent VRRmax=0 is not generated')
    parser.add_argument('--mode', choices=('remote', 'local'), required=True)
    parser.add_argument('--sink', type=Path, help='raw HDMI OUT EDID; required for local mode')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (args.mode == 'local') != (args.sink is not None):
        parser.error('local requires --sink; remote must not depend on an HDMI OUT EDID')
    try:
        selected = select_range(Range(*args.receiver), Range(*args.request), args.protocol,
                                args.sink.read_bytes() if args.sink else None)
        data = rewrite(args.baseline.read_bytes(), args.protocol, selected)
        # Refuse to overwrite the baseline or any previous candidate.
        with args.output.open('xb') as output:
            output.write(data)
        print(json.dumps({'mode': args.mode, 'experimental': True,
                          'ranges': {key: [value.minimum, value.maximum]
                                     for key, value in capabilities(data).items()}}, sort_keys=True))
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
