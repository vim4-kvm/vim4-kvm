#!/usr/bin/env python3
"""Download pinned build inputs, refusing content with a different SHA256."""
import hashlib
import json
from pathlib import Path
import sys
import urllib.request


def fetch(entries, directory):
    directory.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        name = entry['name']
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('Download name must be a basename')
        target = directory / name
        with urllib.request.urlopen(entry['url'], timeout=120) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError(f'Checksum mismatch: {name}')
        target.write_bytes(data)


if __name__ == '__main__':
    fetch(json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]))
