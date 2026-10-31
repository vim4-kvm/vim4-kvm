#!/usr/bin/env python3
"""Reject unreviewed checkpatch diagnostics in the external module series."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

packaging = Path(__file__).resolve().parent
failed = False
for name in [*(packaging / 'series').read_text().splitlines(), '0004-dt-candidate.patch']:
    with tempfile.TemporaryDirectory(prefix='kbase-style-') as directory:
        result = subprocess.run([str(Path(sys.argv[1]).resolve()), '--strict', '--no-tree',
                                 '--show-types', str(packaging / name)],
                                cwd=directory, text=True, capture_output=True)
    diagnostics = re.findall(r'^(ERROR|WARNING|CHECK):(\w+): (.*)$', result.stdout, re.M)
    for level, code, message in diagnostics:
        allowed = (
            name in ('0001-kernel-api.patch', '0005-runtime-api.patch') and code == 'LINUX_VERSION_CODE'
            or name == '0001-kernel-api.patch' and code == 'CAMELCASE'
            and message in ('Avoid CamelCase: <__SetPageMovable>',
                            'Avoid CamelCase: <__ClearPageMovable>')
            or name in ('0002-t7-platform.patch', '0004-dt-candidate.patch')
            and code == 'FILE_PATH_CHANGES')
        if level == 'ERROR' or not allowed:
            failed = True
            print(f'{name}: {level}:{code}: {message}')
    if result.returncode not in (0, 1) or (result.returncode and not diagnostics):
        failed = True
        print(result.stdout + result.stderr)
    print(f'{name}: {len(diagnostics)} reviewed diagnostics')
raise SystemExit(1 if failed else 0)
