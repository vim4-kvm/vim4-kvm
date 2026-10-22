"""Reject ambiguous package selection before starting Docker or a VM."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class BuildCliTests(unittest.TestCase):
    def test_package_consumers_require_an_explicit_version(self):
        root = Path(__file__).resolve().parents[1]
        for tool, action, flag in [('ubuntu-build', 'verify', '--version'),
                                   ('ubuntu-image', 'assemble', '--components')]:
            with self.subTest(tool=tool, action=action):
                spec = importlib.util.spec_from_file_location(tool, root / 'tools' / (tool + '.py'))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                errors = io.StringIO()
                with patch('sys.argv', [tool, action]), contextlib.redirect_stderr(errors), \
                     patch.object(module.subprocess, 'run', side_effect=AssertionError('external work started')), \
                     patch.object(module.subprocess, 'check_output', side_effect=AssertionError('external work started')):
                    with self.assertRaises(SystemExit) as exc:
                        module.main()
                self.assertEqual(exc.exception.code, 2)
                self.assertIn(flag, errors.getvalue())


class VersionTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('ubuntu_build', root / 'tools' / 'ubuntu-build.py')
        self.build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.build)

    def test_development_versions_number_after_their_base_release(self):
        base = '2.5.1+vim4.20261016.1020'
        existing = [base + '.dev.2.gabcdef0', '2.5.1+vim4.20261016.1018.dev.9.gabcdef0', '2.5.1+vim4.20261016.116']
        self.assertEqual(self.build.development_version(base, '49c45f25a29b', True, existing), base + '.dev.3.g49c45f2.dirty')
        self.assertEqual(self.build.development_version(base, '49c45f25a29b', False, []), base + '.dev.1.g49c45f2')

    def test_release_and_development_formats_do_not_overlap(self):
        self.assertTrue(self.build.RELEASE.fullmatch('2.5.1+vim4.20261016.1020'))
        self.assertFalse(self.build.RELEASE.fullmatch('2.5.1+vim4.20261016.1020.dev.1.g49c45f2'))
        self.assertTrue(self.build.DEVELOPMENT.fullmatch('2.5.1+vim4.20261016.1020.dev.1.g49c45f2.dirty'))
        self.assertFalse(self.build.DEVELOPMENT.fullmatch('2.5.1+vim4.20261016.1020.dev.1'))

    def test_latest_release_orders_numerically(self):
        tags = '2.5.1+vim4.20261016.998\n2.5.1+vim4.20261016.1020\n2.5.1+vim4.20261015.2000\nv1.0\n'
        with patch.object(self.build.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)), patch.object(self.build, 'output', return_value=tags):
            self.assertEqual(self.build.latest_release('vim4-manager'), '2.5.1+vim4.20261016.1020')
        with patch.object(self.build.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)), patch.object(self.build, 'output', return_value=''):
            self.assertEqual(self.build.latest_release('vim4-manager'), self.build.NO_RELEASE)

    def test_offline_development_uses_cached_tags_but_ci_refuses(self):
        with patch.object(self.build.subprocess, 'run', side_effect=subprocess.TimeoutExpired('git', 30)), \
             patch.object(self.build, 'output', return_value='2.5.1+vim4.20261016.1020'), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.build.latest_release('vim4-manager'), '2.5.1+vim4.20261016.1020')
            with self.assertRaisesRegex(ValueError, 'refusing'):
                self.build.latest_release('vim4-manager', allow_cached=False)

    def test_ci_numbers_do_not_regress_during_migration_or_reruns(self):
        choose = self.build.release_version
        self.assertEqual(choose('20261016', 11, '2.5.1+vim4.20261016.1020'), '2.5.1+vim4.20261016.1022')
        self.assertEqual(choose('20261016', 11, '2.5.1+vim4.20261016.1022'), '2.5.1+vim4.20261016.1024')
        self.assertEqual(choose('20261017', 12, '2.5.1+vim4.20261016.1024'), '2.5.1+vim4.20261017.24')
        self.assertEqual(choose('20261016', 11, '2.5.1+vim4.20261016.1020', pikvm=True), '2.5.1+vim4.20261016.1021')
        with self.assertRaisesRegex(ValueError, 'earlier'):
            choose('20261015', 12, '2.5.1+vim4.20261016.1020')

    def test_combined_development_starts_after_all_included_releases(self):
        tags = {'.': '2.5.1+vim4.20261016.1002', 'vim4-manager': '2.5.1+vim4.20261016.1020'}
        with patch.object(self.build, 'latest_release', side_effect=lambda repo, **kwargs: tags.get(repo, self.build.NO_RELEASE)):
            self.assertEqual(self.build.latest_component_release('all'), tags['vim4-manager'])
            self.assertEqual(self.build.latest_component_release('platform'), tags['vim4-manager'])
            self.assertEqual(self.build.latest_component_release('pikvm'), tags['vim4-manager'])

    def test_dirty_release_fails_before_docker_and_auto_development_records_its_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath('vim4-manager').mkdir()
            def output(*args):
                if '--show-toplevel' in args:
                    return str(Path(args[2]).resolve())
                if '--porcelain' in args:
                    return ' M source.py'
                if 'diff' in args:
                    return 'changed source'
                if '--format=%ct' in args:
                    return '1'
                return '49c45f25a29b'
            with patch.object(self.build, 'ROOT', root), patch.object(self.build, 'output', side_effect=output), \
                 patch.object(self.build.subprocess, 'check_output', return_value=b''), \
                 patch.object(self.build.subprocess, 'run') as docker, \
                 patch.object(self.build, 'latest_component_release', return_value='2.5.1+vim4.20261016.1020'), \
                 contextlib.redirect_stdout(io.StringIO()):
                with patch('sys.argv', ['build', 'package', '--component', 'manager', '--version', '2.5.1+vim4.20261016.1022']):
                    with self.assertRaisesRegex(ValueError, 'committed sources'):
                        self.build.main()
                docker.assert_not_called()
                with patch('sys.argv', ['build', 'package', '--component', 'manager']):
                    self.build.main()
                    self.build.main()
                metadata = json.loads(next(root.glob('build/packages/*.dev.2.*/sources.json')).read_text())
                self.assertTrue(metadata['development'])
                self.assertEqual(metadata['version'], '2.5.1+vim4.20261016.1020.dev.2.g49c45f2.dirty')
                self.assertIn('PACKAGE_VERSION=' + metadata['version'], docker.call_args.args[0])

    @unittest.skipUnless(shutil.which('dpkg'), 'dpkg is available in the Ubuntu builder')
    def test_generated_development_versions_sort_between_releases_in_dpkg(self):
        base = '2.5.1+vim4.20261016.1020'
        dev = self.build.development_version(base, '49c45f25a29b', True, [])
        dev10 = self.build.development_version(base, 'abcdef012345', False, [base + '.dev.9.g49c45f2'])
        for earlier, later in [(base, dev), (dev, dev10), (dev10, '2.5.1+vim4.20261016.1022'),
                               (dev10, '2.5.1+vim4.20261017.1')]:
            result = subprocess.run(['dpkg', '--compare-versions', later, 'gt', earlier], capture_output=True)
            self.assertEqual(result.returncode, 0, f'{later} must sort after {earlier}: {result.stderr}')
