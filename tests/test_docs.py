"""Documentation stays navigable and cheap to load: tools catalogued, links resolve, entry docs small."""
from pathlib import Path
import re
import subprocess
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPOS = {repo['name'] for repo in tomllib.loads((ROOT / 'workspace.toml').read_text())['repos']}
LINK = re.compile(r'\]\(([^)\s]+)\)')
PYTHON_SCRIPT = re.compile(r"\bpython3[ \t]+((?:tools|packaging)/[^\s`'\";)]+)")
DATE_INDEX = '以下保留完整日期索引。'


def literal_python_scripts(text):
    # Only literal root-relative commands; no shell expansion or execution.
    for number, line in enumerate(text.splitlines(), 1):
        for match in PYTHON_SCRIPT.finditer(line):
            path = match[1].rstrip('.,')
            if any(char in path for char in '<>{}$*…') or '...' in path:
                continue
            yield number, path


def date_index_errors(text, records):
    date = None
    seen = set()
    errors = []
    for line in text.split(DATE_INDEX, 1)[1].splitlines():
        heading = re.fullmatch(r'## (\d{4}-\d{2}-\d{2})', line)
        if heading:
            date = heading[1]
        for target in LINK.findall(line):
            name = target.split('#', 1)[0]
            record = re.fullmatch(r'(\d{4}-\d{2}-\d{2})-[\w-]+\.md', name)
            if not record:
                continue
            if record[1] != date:
                errors.append(f'{name}: under {date}, expected {record[1]}')
            if name in seen:
                errors.append(f'{name}: duplicate date entry')
            seen.add(name)
    for name in sorted(set(records) - seen):
        errors.append(f'{name}: missing date entry')
    return errors


class DocsChecksTest(unittest.TestCase):
    def test_literal_commands_keep_missing_paths_but_skip_placeholders(self):
        text = '''python3 tools/missing.py --dry-run
`python3 packaging/kernel/missing.py`
python3 tools/<script>.py
python3 tools/${SCRIPT}.py
python3 packaging/.../script.py
python3 tools/…
python3 -m unittest
'''
        self.assertEqual(list(literal_python_scripts(text)), [
            (1, 'tools/missing.py'), (2, 'packaging/kernel/missing.py')])

    def test_date_index_ignores_shortcuts_but_rejects_misfiled_duplicates(self):
        record = '[record](2026-10-30-sample.md)'
        records = ['2026-10-30-sample.md']
        text = f'{record}\n{DATE_INDEX}\n## 2026-10-30\n{record}\n'
        self.assertEqual(date_index_errors(text, records), [])
        self.assertEqual(date_index_errors(f'{record}\n{DATE_INDEX}\n', records),
                         ['2026-10-30-sample.md: missing date entry'])
        errors = date_index_errors(text + f'## 2026-10-31\n{record}\n', records)
        self.assertEqual(len(errors), 2)
        self.assertIn('expected 2026-10-30', errors[0])
        self.assertIn('duplicate', errors[1])


def tracked(pattern):
    # Validate moves before staging too: include new files and omit removed paths.
    output = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', pattern], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted({ROOT / line for line in output.splitlines() if (ROOT / line).is_file()})


def anchor(heading):
    text = heading.strip().lower()
    text = re.sub(r'[^\w\- ]', '', text)
    return text.replace(' ', '-')


def anchors(path):
    return {anchor(line.lstrip('#')) for line in path.read_text().splitlines() if line.startswith('#')}


# The isolated package builder copies sources without .git; the pre-commit run covers these.
@unittest.skipUnless((ROOT / '.git').exists(), 'requires a Git checkout')
class DocsTest(unittest.TestCase):
    def test_documented_python_scripts_exist(self):
        documents = [path for path in tracked('*.md')
                     if not path.relative_to(ROOT).as_posix().startswith(('docs/bringup/', 'docs/archive/'))]
        missing = []
        for document in documents:
            # tools/ and packaging/ commands refer to the main workspace root.
            for number, script in literal_python_scripts(document.read_text()):
                if not (ROOT / script).is_file():
                    missing.append(f'{document.relative_to(ROOT)}:{number}: {script}')
        self.assertEqual(missing, [])

    def test_existing_one_kvm_integration_commands(self):
        integration = ROOT / 'One-KVM/VIM4.md'
        if not integration.is_file():
            self.skipTest('One-KVM checkout absent')
        missing = [f'{number}: {script}' for number, script in literal_python_scripts(integration.read_text())
                   if not (ROOT / script).is_file()]
        self.assertEqual(missing, [])

    def test_bringup_date_entries_are_unique_and_under_matching_date(self):
        index = (ROOT / 'docs/bringup/README.md').read_text()
        self.assertIn(DATE_INDEX, index)
        records = [path.name for path in tracked('docs/bringup/*.md') if path.name != 'README.md']
        self.assertEqual(date_index_errors(index, records), [])

    def test_every_tool_is_catalogued(self):
        catalog = (ROOT / 'docs/tools.md').read_text()
        missing = [path.name for path in tracked('tools/*') if path.name not in catalog]
        self.assertEqual(missing, [])

    def test_catalogued_tools_exist(self):
        catalog = (ROOT / 'docs/tools.md').read_text()
        names = set(re.findall(r'tools/([\w.-]+\.(?:py|mjs|sh|swift|c))', catalog))
        self.assertEqual(sorted(name for name in names if not (ROOT / 'tools' / name).exists()), [])

    def test_local_links_resolve(self):
        broken = []
        for doc in tracked('*.md'):
            for target in LINK.findall(doc.read_text()):
                if re.match(r'[a-z]+:', target):
                    continue
                path, _, fragment = target.partition('#')
                resolved = (doc.parent / path).resolve() if path else doc
                if not resolved.exists():
                    # Sub-repositories are separate checkouts and may be absent.
                    if not resolved.is_relative_to(ROOT) or resolved.relative_to(ROOT).parts[0] not in REPOS:
                        broken.append(f'{doc.relative_to(ROOT)}: {target}')
                elif fragment and resolved.suffix == '.md' and fragment not in anchors(resolved):
                    broken.append(f'{doc.relative_to(ROOT)}: {target}')
        self.assertEqual(broken, [])

    # Loaded into every agent session; subsystem detail belongs in docs/subsystems/.
    def test_always_loaded_docs_stay_small(self):
        sizes = {name: len((ROOT / name).read_bytes()) for name in ('CLAUDE.md', 'AGENTS.md', 'LESSONS.md')}
        self.assertLessEqual(sum(sizes.values()), 6000, sizes)

    def test_subsystem_entries_stay_small(self):
        oversized = {p.name: p.stat().st_size for p in (ROOT / 'docs/subsystems').glob('*.md')
                     if p.stat().st_size > 14000}
        self.assertEqual(oversized, {})

    def test_archive_snapshots_are_labelled_and_indexed(self):
        archive = ROOT / 'docs/archive'
        index = archive / 'README.md'
        indexed = {(index.parent / target.split('#')[0]).resolve()
                   for target in LINK.findall(index.read_text()) if not re.match(r'[a-z]+:', target)}
        for doc in archive.rglob('*.md'):
            if doc.name == 'README.md':
                continue
            with self.subTest(doc=doc.relative_to(ROOT)):
                self.assertRegex(doc.read_text(), r'\A# [^\n]+\n\n> 归档快照（\d{4}-\d{2}-\d{2}）：[^\n]+')
                self.assertIn(doc.resolve(), indexed)

    def test_task_routes_do_not_link_directly_to_evidence(self):
        for target in LINK.findall((ROOT / 'AGENTS.md').read_text()):
            path = target.split('#')[0]
            if path.startswith(('docs/archive/', 'docs/bringup/')):
                self.assertEqual(path.rsplit('/', 1)[-1], 'README.md', target)

    def test_bringup_entries_are_indexed_and_bounded(self):
        index = (ROOT / 'docs/bringup/README.md').read_text()
        entries = [path for path in tracked('docs/bringup/*.md') if path.name != 'README.md']
        self.assertEqual([p.name for p in entries if not re.fullmatch(r'\d{4}-\d\d-\d\d-[a-z0-9-]+\.md', p.name)], [])
        self.assertEqual([p.name for p in entries if f'({p.name})' not in index], [])
        self.assertEqual([p.name for p in entries if len(p.read_bytes()) > 12000], [])
        self.assertFalse((ROOT / 'docs/bringup-log.md').exists())


if __name__ == '__main__':
    unittest.main()
