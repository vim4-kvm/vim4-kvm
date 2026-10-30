import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gpu_compare', ROOT / 'tools/gpu-compare.py')
gpu = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gpu)


class GPUEnvironmentTests(unittest.TestCase):
    def test_system_does_not_inherit_experimental_driver_selection(self):
        with patch.dict(os.environ, {key: 'contaminated' for key in gpu.GPU_ENV}):
            env = gpu.environment('system', Path('/opt/private'))
        for key in ('LD_PRELOAD', 'VK_DRIVER_FILES', 'VK_ICD_FILENAMES',
                    'RUSTICL_ENABLE', 'PAN_I_WANT_A_BROKEN_VULKAN_DRIVER',
                    'GPU_TIMER_QUERY', 'GPU_UNROLL128'):
            self.assertNotIn(key, env)
        self.assertTrue(env['LD_LIBRARY_PATH'].startswith('/usr/lib/'))

    def test_vendor_refuses_panfrost_kernel(self):
        with patch.object(gpu.platform, 'release', return_value='7.3.0-vim4kvm-uhd1+'):
            with self.assertRaises(ValueError):
                gpu.environment('vendor', Path('/opt/private'))

    def test_private_selection_does_not_change_parent_environment(self):
        before = dict(os.environ)
        env = gpu.environment('private', Path('/opt/private'))
        self.assertEqual(dict(os.environ), before)
        self.assertTrue(env['VK_DRIVER_FILES'].startswith('/opt/private/'))

    def test_failed_tool_is_preserved(self):
        result = gpu.bounded(['/bin/sh', '-c', 'echo rejected; exit 9'], os.environ.copy(), 2)
        self.assertEqual(result['exit'], 9)
        self.assertIn('rejected', result['output'])
