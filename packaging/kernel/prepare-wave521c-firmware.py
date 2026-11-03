#!/usr/bin/env python3
"""Extract the tested T7 firmware from a separately obtained licensed header.

This does not download or grant redistribution rights to the firmware. Keep the
header and generated binary outside Git. The output must be a new file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('header', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        source = args.header.read_bytes()
        source_hash = hashlib.sha256(source).hexdigest()
        if source_hash != '5c3d8bb687d95920a6f40fa7373c27312500574ed73f5047ad7498423c55c9da':
            raise ValueError('header differs from the tested firmware source')
        array = re.search(r'bit_code\[(\d+)\]\s*=\s*\{([^}]+)\}', source.decode(), re.S)
        if array is None:
            raise ValueError('firmware array not found')
        words = [int(value, 16) for value in re.findall(r'0x[0-9a-fA-F]+', array[2])]
        if len(words) != int(array[1]) or len(words) != 476096:
            raise ValueError('firmware array length differs from the tested version')
        data = struct.pack('<' + 'H' * len(words), *words)
        digest = hashlib.sha256(data).hexdigest()
        if digest != '873103d7520d5cad737cfe4458a2891c065d566ff556a47ab735e60f27acf031':
            raise ValueError('firmware checksum mismatch')
        with args.output.open('xb') as output:
            output.write(data)
        print(json.dumps({'source_sha256': source_hash, 'firmware_sha256': digest, 'bytes': len(data)}))
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
