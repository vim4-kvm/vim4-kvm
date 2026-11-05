#!/usr/bin/env python3
"""Prepare locked Fluster inputs on the host; never connect to the board.

Default: validate the existing source and print the selected suites offline.
--download uses upstream Fluster to download and check the published checksums,
then records SHA256 for the extracted inputs. A failed download can be resumed;
cached archives are rechecked and inputs re-extracted before sealing a manifest.
--archive exports only manifest-listed files, excluding the host download cache.
--seal-cached is offline: seal only checksum-verified cached inputs and retain
every unavailable vector with its reason. It never turns missing data into a pass.
No decoder is run and no board-side downloader is provided here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tomllib
from urllib.parse import urlparse


def digest(path, algorithm='sha256'):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def selected_suites(source, lock, names):
    known = {item['name'] for item in lock['suites']}
    if set(names) - known:
        raise ValueError('Unknown suites: ' + ', '.join(sorted(set(names) - known)))
    selected = []
    for spec in lock['suites']:
        if names and spec['name'] not in names:
            continue
        path = source / spec['path']
        if digest(path) != spec['sha256']:
            raise ValueError('Suite differs from lock: ' + spec['name'])
        suite = json.loads(path.read_text())
        if suite['name'] != spec['name']:
            raise ValueError('Suite name differs from lock')
        if spec.get('profiles'):
            suite['test_vectors'] = [v for v in suite['test_vectors']
                                     if v.get('profile') in spec['profiles']]
        if len(suite['test_vectors']) != spec['vectors']:
            raise ValueError('Selected vector count differs from lock: ' + spec['name'])
        for vector in suite['test_vectors']:
            if len(vector['source_checksum']) != 32:
                raise ValueError('Published checksum is required: ' + vector['name'])
            for name in (vector['name'], vector['input_file']):
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise ValueError('Invalid input path: ' + name)
        selected.append((spec, suite))
    return selected


def prepare(args, lock, suites):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    proof = output / 'bundle-manifest.json'
    if proof.exists():
        raise ValueError('Bundle already sealed; use its manifest or a new output directory')
    source_files = subprocess.check_output(
        ['git', '-C', str(args.source), 'ls-files', '-z'], text=True).split('\0')
    files = {}
    for name in filter(None, source_files):
        original = args.source / name
        target = output / 'fluster' / name
        if not original.is_file() or original.is_symlink():
            raise ValueError('Unexpected Fluster source entry: ' + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
        files[str(target.relative_to(output))] = digest(target)
    shutil.copyfile(args.lock, output / 'vdec-fluster.toml')
    files['vdec-fluster.toml'] = digest(output / 'vdec-fluster.toml')
    suite_dir = output / 'suites'
    suite_dir.mkdir(exist_ok=True)
    # A resumed download must not trust an already extracted file merely because
    # it exists (upstream skips those). Keep the cache, recheck and re-extract.
    wanted = {spec['name'] + '.json' for spec, _ in suites}
    for old in suite_dir.glob('*.json'):
        if old.name not in wanted:
            raise ValueError('Resume must use the same suite selection')
    for spec, suite in suites:
        write_json(suite_dir / (spec['name'] + '.json'), suite)
        for vector in suite['test_vectors']:
            for relative in (Path(spec['name']) / vector['name'] / vector['input_file'],
                             Path(spec['name']) / vector['input_file']):
                path = output / 'resources' / relative
                # A suite-root filename can equal the per-vector directory.
                if path.is_file():
                    path.unlink()
    command = [sys.executable, str(output / 'fluster/fluster.py'), '-ne',
               '-tsd', str(suite_dir), '-r', str(output / 'resources'),
               'download', '-j', str(args.jobs), '-k', '-r', '2',
               *(spec['name'] for spec, _ in suites)]
    if args.download:
        with (output / 'download.log').open('a') as log:
            log.write(shlex_command(command) + '\n')
            log.flush()
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    # Use the pinned upstream extractor, including its archive-member naming
    # rules. Re-extract verified cache entries so partial output from a failed
    # download is never mistaken for a complete input file.
    sys.path.insert(0, str(args.source))
    from fluster.utils import extract_archive, is_extractable
    manifest = {'schema': 1, 'fluster_revision': lock['revision'],
                'lock_sha256': digest(args.lock), 'suites': [], 'files': files}
    for spec, suite in suites:
        suite_path = 'suites/' + spec['name'] + '.json'
        files[suite_path] = digest(output / suite_path)
        record = dict(spec, suite_file=suite_path, test_method=suite.get('test_method', 'md5'),
                      codec=suite['codec'], vectors=[])
        for vector in suite['test_vectors']:
            url = vector['source']
            cached = (output / 'resources/.cache' / hashlib.md5(url.encode()).hexdigest()
                      / Path(urlparse(url).path).name)
            if not cached.is_file() or digest(cached, 'md5') != vector['source_checksum']:
                if not args.seal_cached:
                    raise ValueError('Downloaded source checksum differs: ' + url)
                record['vectors'].append(dict(vector, availability='unavailable',
                    reason='source archive absent or published checksum differs',
                    received_sha256=digest(cached) if cached.is_file() else None))
                continue
            relative = Path('resources') / spec['name'] / vector['name'] / vector['input_file']
            destination = output / 'resources' / spec['name'] / vector['name']
            destination.mkdir(parents=True, exist_ok=True)
            if is_extractable(cached.name):
                missing = extract_archive(str(cached), [(vector['input_file'], str(destination))])
                if missing:
                    raise ValueError('Input missing from checked archive: ' + vector['name'])
            else:
                shutil.copyfile(cached, output / relative)
            files[str(relative)] = digest(output / relative)
            record['vectors'].append(dict(vector, input_path=str(relative),
                                          availability='available', source_sha256=digest(cached)))
        manifest['suites'].append(record)
    if digest(args.lock) != files['vdec-fluster.toml']:
        raise ValueError('Lock changed during download; repeat preparation with the cached sources')
    write_json(proof, manifest)
    if args.archive:
        with tarfile.open(args.archive, 'x:gz') as archive:
            for name in ['bundle-manifest.json', *sorted(files)]:
                archive.add(output / name, arcname=name, recursive=False)
    print(json.dumps({'manifest': str(proof), 'sha256': digest(proof),
                      'suites': {s['name']: {'total': len(s['vectors']),
                          'available': sum(v['availability'] == 'available' for v in s['vectors'])}
                          for s in manifest['suites']}}, indent=2))


def shlex_command(command):
    import shlex
    return shlex.join(command)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Existing clean locked Fluster checkout')
    parser.add_argument('--lock', type=Path, default=Path(__file__).with_name('vdec-fluster.toml'))
    parser.add_argument('--suite', action='append', default=[], help='Repeat to prepare a subset')
    parser.add_argument('--output', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--download', action='store_true')
    mode.add_argument('--seal-cached', action='store_true', help='Offline seal with unavailable vectors recorded')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    args.source = args.source.resolve()
    lock = tomllib.loads(args.lock.read_text())
    head = subprocess.check_output(['git', '-C', str(args.source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(args.source), 'status', '--porcelain'], text=True).strip()
    if head != lock['revision'] or dirty:
        raise ValueError('Fluster checkout must be clean and match the locked commit')
    suites = selected_suites(args.source, lock, args.suite)
    if not args.download and not args.seal_cached:
        print(json.dumps({'offline': True, 'revision': head,
                          'suites': {s['name']: len(data['test_vectors']) for s, data in suites}}, indent=2))
        return
    if args.output is None or not 1 <= args.jobs <= 8:
        parser.error('Preparation requires --output and 1..8 jobs')
    prepare(args, lock, suites)


if __name__ == '__main__':
    main()
