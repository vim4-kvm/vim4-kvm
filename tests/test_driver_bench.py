"""Compile native timing/ownership regressions when GStreamer development libs exist."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('gstreamer-app-1.0', 'gstreamer-allocators-1.0', 'gstreamer-video-1.0')


def has_dependencies():
    return bool(shutil.which('cc') and shutil.which('pkg-config') and
                subprocess.run(['pkg-config', '--exists', *PACKAGES], check=False).returncode == 0)


@unittest.skipUnless(has_dependencies(), 'requires native GStreamer development libraries')
class DriverBenchmarkTest(unittest.TestCase):
    def test_native_timing_and_capture_lease(self):
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', *PACKAGES], text=True))
        plugin_dir = Path(subprocess.check_output(
            ['pkg-config', '--variable=pluginsdir', 'gstreamer-1.0'], text=True).strip())
        with tempfile.TemporaryDirectory(prefix='vim4-driver-bench-') as directory:
            folder = Path(directory)
            binary = folder / 'test-bench'
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-function', str(ROOT / 'tests/test_driver_bench.c'),
                            '-o', str(binary), *flags], check=True, capture_output=True, text=True)
            # Only load appsrc/appsink: a software test must never probe V4L2.
            plugins = folder / 'plugins'
            plugins.mkdir()
            candidates = list(plugin_dir.glob('libgstapp.*'))
            self.assertTrue(candidates, f'missing app plugin in {plugin_dir}')
            for plugin in candidates:
                (plugins / plugin.name).symlink_to(plugin)
            environment = dict(os.environ, GST_PLUGIN_PATH='', GST_PLUGIN_PATH_1_0='',
                               GST_PLUGIN_SYSTEM_PATH=str(plugins),
                               GST_PLUGIN_SYSTEM_PATH_1_0=str(plugins),
                               GST_REGISTRY=str(folder / 'registry.bin'))
            result = subprocess.run([str(binary)], env=environment, capture_output=True,
                                    text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
