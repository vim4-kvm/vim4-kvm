"""Reject ambiguous package selection before starting Docker or a VM."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch


class BuildCliTests(unittest.TestCase):
    def test_package_consumers_require_an_explicit_version(self):
        root = Path(__file__).resolve().parents[1]
        for tool, action, flag in [('ubuntu-build', 'package', '--version'),
                                   ('ubuntu-build', 'verify', '--version'),
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
