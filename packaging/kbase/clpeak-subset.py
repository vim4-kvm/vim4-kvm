#!/usr/bin/env python3
"""Run identical, separately bounded clpeak 1.1.2 subsets on either kbase kernel."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--clpeak', type=Path, default=Path('/opt/vim4-mesa-26.2.6/bin/clpeak'))
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
help_text = subprocess.check_output([str(args.clpeak), '--help'], text=True, timeout=5)
tests = (('--kernel-latency', 30), ('--compute-sp', 90))
if any(flag not in help_text for flag, _ in tests):
    parser.error('clpeak lacks the required selective test options')
results = []
for flag, budget in tests:
    command = ['timeout', '-k', '5', str(budget), sys.executable,
               str(Path(__file__).with_name('run.py')), '--graphics', 'icd', '--',
               str(args.clpeak), '--platform', '0', '--device', '0', flag]
    start = time.monotonic()
    with (args.output / (flag[2:] + '.log')).open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    results.append(dict(command=command, exit=result.returncode, seconds=time.monotonic()-start))
(args.output / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
raise SystemExit(int(any(result['exit'] for result in results)))
