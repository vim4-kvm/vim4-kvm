import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'mali_runtime', Path(__file__).resolve().parents[1] / 'tools/mali-runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class MaliFetchTest(unittest.TestCase):
    def test_bad_download_is_not_published_and_can_be_retried(self):
        payload = b'verified driver artifact'
        with tempfile.TemporaryDirectory() as directory, patch.object(
                runtime, 'SHA256', hashlib.sha256(payload).hexdigest()):
            destination = Path(directory)
            with patch.object(runtime.urllib.request, 'urlopen', return_value=io.BytesIO(b'truncated')):
                with self.assertRaisesRegex(ValueError, 'SHA-256'):
                    runtime.fetch(destination)
            self.assertEqual(list(destination.iterdir()), [])
            with patch.object(runtime.urllib.request, 'urlopen', return_value=io.BytesIO(payload)):
                runtime.fetch(destination)
            self.assertEqual((destination / 'libMali.so').read_bytes(), payload)
            with patch.object(runtime.urllib.request, 'urlopen') as download:
                runtime.fetch(destination)
                download.assert_not_called()

    def test_existing_corrupt_artifact_fails_without_installing(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'libMali.so').write_bytes(b'corrupt')
            with patch.object(runtime, 'DESTINATION', source / 'installed'):
                with self.assertRaisesRegex(ValueError, 'SHA-256'):
                    runtime.install(source)
            self.assertFalse((source / 'installed').exists())

    def test_mainline_kernel_cannot_install_vendor_runtime(self):
        payload = b'verified driver artifact'
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'libMali.so').write_bytes(payload)
            with (patch.object(runtime, 'SHA256', hashlib.sha256(payload).hexdigest()),
                  patch.object(runtime, 'DESTINATION', source / 'installed'),
                  patch.object(runtime.os, 'geteuid', return_value=0),
                  patch.object(runtime.platform, 'machine', return_value='aarch64'),
                  patch.object(runtime.platform, 'release', return_value='7.3.0-vim4kvm')):
                with self.assertRaisesRegex(ValueError, 'vendor 5.15'):
                    runtime.install(source)
            self.assertFalse((source / 'installed').exists())


if __name__ == '__main__':
    unittest.main()
