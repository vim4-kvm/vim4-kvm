"""Documentation stays navigable and cheap to load: tools catalogued, links resolve, entry docs small."""
from pathlib import Path
import re
import subprocess
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPOS = {repo['name'] for repo in tomllib.loads((ROOT / 'workspace.toml').read_text())['repos']}
LINK = re.compile(r'\]\(([^)\s]+)\)')


def tracked(pattern):
    output = subprocess.run(['git', 'ls-files', pattern], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / line for line in output.split()]


def anchor(heading):
    text = heading.strip().lower()
    text = re.sub(r'[^\w\- ]', '', text)
    return text.replace(' ', '-')


def anchors(path):
    return {anchor(line.lstrip('#')) for line in path.read_text().splitlines() if line.startswith('#')}


# The isolated package builder copies sources without .git; the pre-commit run covers these.
@unittest.skipUnless((ROOT / '.git').exists(), 'requires a Git checkout')
class DocsTest(unittest.TestCase):
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

    def test_bringup_entries_are_indexed_and_bounded(self):
        index = (ROOT / 'docs/bringup/README.md').read_text()
        entries = [path for path in tracked('docs/bringup/*.md') if path.name != 'README.md']
        self.assertEqual([p.name for p in entries if not re.fullmatch(r'\d{4}-\d\d-\d\d-[a-z0-9-]+\.md', p.name)], [])
        self.assertEqual([p.name for p in entries if f'({p.name})' not in index], [])
        self.assertEqual([p.name for p in entries if len(p.read_bytes()) > 12000], [])
        self.assertFalse((ROOT / 'docs/bringup-log.md').exists())


if __name__ == '__main__':
    unittest.main()
