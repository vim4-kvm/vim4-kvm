import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/gpu-diagnose.py'
SPEC = importlib.util.spec_from_file_location('diagnose', SCRIPT)
gpu = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gpu)


class GPUDiagnosticTests(unittest.TestCase):
    def test_overlapping_engine_times_are_not_added(self):
        samples = [{'time': i, 'cpu_stat': None, 'fdinfo': {'1': {
            'drm-engine-fragment': f'{i * 600000000} ns',
            'drm-engine-vertex-tiler': f'{i * 400000000} ns'}}} for i in (1, 2)]
        self.assertEqual(gpu.activity(samples, 100)[0]['engine_busy_estimate_percent'], 60)

    def test_failed_spawn_restores_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = {'available_frequencies': '250 800', 'min_freq': '250',
                       'max_freq': '800', 'device/power/control': 'auto', 'device/profiling': '0'}
            for name, value in entries.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value)
            result = subprocess.run([sys.executable, str(SCRIPT), '--mode', 'system',
                '--devfreq', str(root), '--frequency', '800', '--pm', 'on', '--profiling',
                '--output', str(root / 'report'), '--', '/missing/gpu-probe'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            for name, value in entries.items():
                self.assertEqual((root / name).read_text(), value)
            self.assertTrue(json.loads((root / 'report/result.json').read_text())['error'])

    def test_timeout_retains_output_and_kills_child(self):
        result = gpu.run([sys.executable, '-u', '-c', 'print("map-begin"); import time; time.sleep(30)'],
                         __import__('os').environ.copy(), Path('/nonexistent/devfreq'), .2)
        self.assertIn('map-begin', result['output'])
        self.assertIsNotNone(result['error'])
        self.assertNotEqual(result['exit'], 0)
