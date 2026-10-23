#!/usr/bin/env python3
"""Offline kernel patch inventory/export and isolated forward-port measurement.

Run in Linux against an existing kernel repository. No fetch, installation or
hardware access is performed. Fetch the desired upstream ref explicitly first.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()


def topic(path):
    if path.startswith(('arch/arm64/boot/dts/', 'include/dt-bindings/')):
        return 'dt'
    if '/bindings/' in path:
        return 'dt-bindings'
    for name, patterns in (
        ('clk', ('drivers/clk/',)),
        ('pinctrl', ('drivers/pinctrl/',)),
        ('pwrc', ('drivers/pmdomain/',)),
        ('hdmirx-vdin', ('/t7-hdmirx/',)),
        ('wave5', ('/wave5/',)),
        ('drm', ('drivers/gpu/drm/', 'include/drm/')),
        ('asoc', ('sound/',)),
        ('iio', ('drivers/iio/',)),
        ('usb', ('drivers/usb/',)),
        ('network', ('drivers/net/',)),
        ('media-other', ('drivers/media/',)),
        ('thermal-mcu', ('drivers/thermal/', 'drivers/mfd/', 'include/linux/mfd/')),
    ):
        if any(pattern in path for pattern in patterns):
            return name
    return 'platform-other'


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def inventory(args):
    source = args.source.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    head = git(source, 'rev-parse', args.head + '^{commit}')
    base = git(source, 'rev-parse', args.base + '^{commit}')
    floor = git(source, 'rev-parse', args.floor + '^{commit}')
    commits = git(source, 'rev-list', '--reverse', '--topo-order', f'{floor}..{head}').splitlines()
    upstream = set(git(source, 'rev-list', base).splitlines())
    rows, series = [], []
    patch_count = 0
    for number, commit in enumerate(commits, 1):
        parents = git(source, 'show', '-s', '--format=%P', commit).split()
        subject = git(source, 'show', '-s', '--format=%s', commit)
        files = git(source, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', commit).splitlines()
        topics = sorted({topic(path) for path in files})
        row = {'commit': commit, 'subject': subject, 'topics': topics,
               'files': files, 'kind': 'merge' if len(parents) > 1 else 'patch'}
        if commit in upstream:
            row['disposition'] = 'already-upstream'
        elif len(parents) > 1:
            row['disposition'] = 'merge-review'
        else:
            patch = subprocess.check_output(['git', '-C', str(source), 'format-patch',
                                             '-1', '--stdout', '--no-signature', commit])
            patch_count += 1
            primary = next((name for name in topics if name not in ('dt', 'dt-bindings', 'platform-other')), topics[0] if topics else 'platform-other')
            relative = Path(primary) / f'{patch_count:04d}-{commit[:12]}.patch'
            destination = output / relative
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(patch)
            series.append(str(relative))
            checked = subprocess.run([str(source / 'scripts/checkpatch.pl'), '--strict',
                                      '--no-tree', str(destination)], cwd=output,
                                     capture_output=True, text=True)
            (output / (str(relative) + '.checkpatch')).write_text(checked.stdout + checked.stderr)
            totals = re.search(r'total: (\d+) errors, (\d+) warnings, (\d+) checks', checked.stdout)
            row['checkpatch'] = dict(zip(('errors', 'warnings', 'checks'), map(int, totals.groups()))) if totals else {'exit': checked.returncode}
            # These markers require review; a clean style check alone never
            # establishes hardware correctness or upstream acceptance.
            flags = []
            added = '\n'.join(line[1:] for line in patch.decode().splitlines() if line.startswith('+') and not line.startswith('+++'))
            for label, pattern in (
                ('private-sysfs', r'DEVICE_ATTR'),
                ('module-parameter', r'module_param'),
                ('debug-interface', r'debugfs_create'),
                ('temporary-policy', r'(?i)experiment|bring.up|\bhack\b|keep.*(?:clock|domain).*on|force.*on|fixup!|FROMLIST'),
            ):
                if re.search(pattern, added + '\n' + subject):
                    flags.append(label)
            row['flags'] = flags
            row['disposition'] = ('private-temporary' if flags else
                                  'upstream-candidate' if checked.returncode == 0 else 'needs-cleanup')
            row['patch'] = str(relative)
            row['sha256'] = hashlib.sha256(patch).hexdigest()
        rows.append(row)
        if number % 50 == 0:
            print(f'inventoried {number}/{len(commits)}', flush=True)
    (output / 'series').write_text('\n'.join(series) + '\n')
    # A merge may contain a resolution absent from format-patch. Prove that
    # flattening preserves the complete source tree before calling it replayable.
    with tempfile.TemporaryDirectory(prefix='vim4-series-') as temporary:
        environment = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'))
        subprocess.run(['git', '-C', str(source), 'read-tree', base], env=environment, check=True)
        replay_exit = 0
        with (output / 'replay.log').open('w') as stream:
            for relative in series:
                replay = subprocess.run(['git', '-C', str(source), 'apply', '--cached', '--3way',
                                         str(output / relative)], env=environment,
                                        stdout=stream, stderr=subprocess.STDOUT)
                if replay.returncode:
                    replay_exit = replay.returncode
                    break
        tree = subprocess.check_output(['git', '-C', str(source), 'write-tree'], env=environment, text=True).strip() if not replay_exit else None
    replayable = tree == git(source, 'rev-parse', head + '^{tree}')
    write_json(output / 'inventory.json', {'base': base, 'floor': floor, 'head': head, 'commits': rows})
    with (output / 'inventory.tsv').open('w') as stream:
        writer = csv.writer(stream, delimiter='\t')
        writer.writerow(('commit', 'kind', 'topics', 'disposition', 'checkpatch', 'flags', 'subject'))
        for row in rows:
            writer.writerow((row['commit'], row['kind'], ','.join(row['topics']), row['disposition'],
                             json.dumps(row.get('checkpatch', {})), ','.join(row.get('flags', [])), row['subject']))
    summary = {'base': base, 'head': head, 'floor': floor, 'total': len(rows),
               'dispositions': dict(Counter(row['disposition'] for row in rows)),
               'patches': patch_count,
               'replay_tree': tree, 'replay_matches_source': replayable,
               'topics_overlapping': dict(Counter(name for row in rows if row['commit'] not in upstream and row['kind'] == 'patch' for name in row['topics']))}
    write_json(output / 'summary.json', summary)
    print(json.dumps(summary, indent=2))
    return int(not replayable)


def forward(args):
    source = args.source.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    head = git(source, 'rev-parse', args.head + '^{commit}')
    target = git(source, 'rev-parse', args.target + '^{commit}')
    base = git(source, 'rev-parse', args.base + '^{commit}')
    if args.branch == 'vim4-kvm-7.3':
        raise SystemExit('Use a new maintenance branch')
    # Check before allocating a worktree. The caller may supply the existing
    # identity through Git's environment; never write repository/global config.
    git(source, 'var', 'GIT_COMMITTER_IDENT')
    worktree = args.worktree.resolve()
    subprocess.run(['git', '-C', str(source), 'worktree', 'add', '-b', args.branch,
                    str(worktree), head], check=True)
    started = time.monotonic()
    with (output / 'rebase.log').open('w') as stream:
        result = subprocess.run(['git', '-C', str(worktree), '-c', 'rerere.enabled=false',
                                 'rebase', '--onto', target, base], stdout=stream, stderr=subprocess.STDOUT)
    conflicts = git(worktree, 'diff', '--name-only', '--diff-filter=U').splitlines()
    stopped = subprocess.run(['git', '-C', str(worktree), 'rev-parse', '--verify', 'REBASE_HEAD'], capture_output=True, text=True)
    report = {'source': head, 'base': base, 'target': target, 'branch': args.branch,
              'worktree': str(worktree), 'exit': result.returncode,
              'seconds': round(time.monotonic() - started, 2),
              'first_conflict_commit': stopped.stdout.strip() if stopped.returncode == 0 else None,
              'conflict_files': conflicts,
              'complete': result.returncode == 0,
              'note': 'Conflict list is the first stop, not the total forward-port cost. Resolve and continue in this worktree; do not skip patches to claim a build.'}
    write_json(output / 'rebase.json', report)
    print(json.dumps(report, indent=2))
    return result.returncode


def verify(args):
    source = args.source.resolve()
    output = args.output.resolve()
    revision = git(source, 'rev-parse', 'HEAD')
    if git(source, 'ls-files', '-u'):
        raise SystemExit('Resolve all conflicts before validation')
    if output.is_relative_to(source):
        raise SystemExit('Output must be outside source')
    output.mkdir(parents=True, exist_ok=False)
    build = output / 'build'
    build.mkdir()
    (build / '.config').write_bytes(args.config.read_bytes())
    make = ['make', '-C', str(source), 'O=' + str(build), 'ARCH=arm64', '-j' + str(args.jobs)]
    files = git(source, 'diff', '--name-only', args.base, 'HEAD').splitlines()
    schemas = [path.removeprefix('Documentation/devicetree/bindings/')
               for path in files if '/bindings/' in path and path.endswith('.yaml')]
    dtbs = sorted({Path(path).name.replace('.dts', '.dtb') for path in files
                   if path.startswith('arch/arm64/boot/dts/amlogic/') and path.endswith('.dts')})
    commands = [('config', make + ['olddefconfig']),
                ('host-tests', ['python3', str(source / 'scripts/vim4/offline-tests.py'),
                                '--output', str(output / 'host-tests')]),
                ('checkpatch', [str(source / 'scripts/checkpatch.pl'), '--strict', '--no-tree',
                                '-g', args.base + '..HEAD'])]
    if args.kunit_config:
        commands[1][1].extend(['--kunit-config', str(args.kunit_config.resolve()),
                               '--kunit-arch', args.kunit_arch])
    if schemas:
        selection = 'DT_SCHEMA_FILES=' + ':'.join(schemas)
        commands += [('bindings', make + [selection, 'dt_binding_check']),
                     ('dtbs', make + [selection, 'CHECK_DTBS=y'] + ['amlogic/' + dtb for dtb in dtbs])]
    if args.build:
        commands.append(('build', make + ['Image', 'dtbs', 'modules']))
    results = []
    for name, command in commands:
        started = time.monotonic()
        with (output / (name + '.log')).open('w') as stream:
            result = subprocess.run(command, cwd=source, stdout=stream, stderr=subprocess.STDOUT)
        log = (output / (name + '.log')).read_text(errors='replace')
        # Kbuild can exit zero after reporting dt-schema validation failures.
        diagnostics = [line for line in log.splitlines() if re.search(
            r'\.dtb:|\.yaml:.*(?:error|warning)|Error:|Warning \(|ignoring, error in schema', line)] if name in ('bindings', 'dtbs') else []
        results.append({'stage': name, 'command': command, 'exit': result.returncode,
                        'seconds': round(time.monotonic() - started, 2),
                        'schema_diagnostics': diagnostics})
        print(f'{name}: exit={result.returncode} diagnostics={len(diagnostics)}', flush=True)
        if name == 'config' and result.returncode:
            break
    write_json(output / 'verify.json', {
        'revision': revision, 'final_revision': git(source, 'rev-parse', 'HEAD'),
        'base': git(source, 'rev-parse', args.base + '^{commit}'),
        'config_sha256': hashlib.sha256(args.config.read_bytes()).hexdigest(),
        'effective_config_sha256': hashlib.sha256((build / '.config').read_bytes()).hexdigest(),
        'build_requested': args.build, 'hardware_tested': False, 'results': results})
    return int(any(row['exit'] or row['schema_diagnostics'] for row in results))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('verify')
    check.add_argument('--source', type=Path, required=True)
    check.add_argument('--base', default='v7.3')
    check.add_argument('--config', type=Path, required=True)
    check.add_argument('--output', type=Path, required=True)
    check.add_argument('--jobs', type=int, default=4)
    check.add_argument('--build', action='store_true', help='Also build Image, all DTBs and modules')
    check.add_argument('--kunit-config', type=Path)
    check.add_argument('--kunit-arch', default='arm64')
    check.set_defaults(function=verify)
    for name, function in (('inventory', inventory), ('forward', forward)):
        command = sub.add_parser(name)
        command.add_argument('--source', type=Path, required=True)
        command.add_argument('--head', required=True, help='Pinned source commit')
        command.add_argument('--base', default='v7.3')
        command.add_argument('--output', type=Path, required=True, help='New report directory')
        command.set_defaults(function=function)
        if name == 'inventory':
            command.add_argument('--floor', default='v7.3-rc7', help='Also account for already upstream history')
        else:
            command.add_argument('--target', required=True, help='Already fetched ref; no network access')
            command.add_argument('--branch', required=True)
            command.add_argument('--worktree', type=Path, required=True)
    args = parser.parse_args()
    return args.function(args)


if __name__ == '__main__':
    raise SystemExit(main())
