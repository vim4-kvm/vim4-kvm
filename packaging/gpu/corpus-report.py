#!/usr/bin/env python3
"""Compare named shader-db variants without counting stderr's duplicate stats."""
from collections import Counter
import json
from pathlib import Path
import re
import sys


def parse(text):
    variants = {}
    counts = Counter()
    for line in text.splitlines():
        match = re.match(r'(.+shader_test) - (MESA_SHADER_\w+) shader: (.*)', line)
        if not match:
            continue
        path, stage, body = match.groups()
        index = counts[path, stage]
        counts[path, stage] += 1
        patterns = {'bytes': r'(\d+) code size', 'instrs': r'(\d+) instrs',
                    'cycles': r'([\d.]+) cycles',
                    'loops': r'(\d+) loops', 'regs': r'(\d+) registers used',
                    'spills': r'(\d+):\d+ spills', 'fills': r'\d+:(\d+) spills'}
        variants[path, stage, index] = {
            name: (float if name == 'cycles' else int)(re.search(pattern, body)[1])
            for name, pattern in patterns.items()}
    return variants


def compare(before, after):
    keys = sorted(before.keys() & after.keys())
    if not keys:
        raise ValueError('No common shader variants')
    return {
        'counts': [len(before), len(after)], 'common': len(keys),
        'programs': len({key[0] for key in keys}),
        'only_baseline': len(before.keys() - after.keys()),
        'only_candidate': len(after.keys() - before.keys()),
        'total': [{name: sum(variants[key][name] for key in keys)
                   for name in ('bytes', 'instrs', 'cycles', 'loops', 'spills', 'fills')}
                  for variants in (before, after)],
        'max_registers': [max(variants[key]['regs'] for key in keys)
                          for variants in (before, after)],
        'register_increases': sum(after[key]['regs'] > before[key]['regs'] for key in keys),
        'changes': [{'key': key, 'before': before[key], 'after': after[key]}
                    for key in keys if before[key] != after[key]],
    }


if __name__ == '__main__':
    result = compare(*(parse(Path(path).read_text()) for path in sys.argv[1:3]))
    print(json.dumps(result, indent=2))
