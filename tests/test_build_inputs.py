"""Pinned downloads must never turn changed upstream bytes into accepted inputs."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('fetch', Path(__file__).resolve().parents[1] / 'packaging/ubuntu/fetch.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class DownloadTests(unittest.TestCase):
    def test_verified_download_and_changed_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'input'
            source.write_bytes(b'expected bytes')
            entry = dict(name='sdk.deb', url=source.as_uri(), sha256=hashlib.sha256(source.read_bytes()).hexdigest())
            fetch.fetch([entry], root / 'cache')
            source.write_bytes(b'changed upstream bytes')
            with self.assertRaises(ValueError):
                fetch.fetch([entry], root / 'cache')
            self.assertEqual((root / 'cache/sdk.deb').read_bytes(), b'expected bytes')

    def test_download_cannot_escape_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                fetch.fetch([dict(name='../outside', url='unused', sha256='unused')], Path(directory))


if __name__ == '__main__':
    unittest.main()
