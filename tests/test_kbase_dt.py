import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('kbase_build', ROOT / 'packaging/kbase/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


@unittest.skipUnless(all(shutil.which(tool) for tool in ('dtc', 'fdtget', 'fdtput')), 'requires dtc tools')
class CoolingReferencesTest(unittest.TestCase):
    def test_preserves_existing_consumers_and_adds_resolvable_gpu_trip(self):
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / 'board.dts'
                gpu_properties = 'phandle=<0x31>;' if existing else ''
                consumer = 'consumer { cooling-device=<&gpu 0 2>; };' if existing else ''
                source.write_text('/dts-v1/; / { gpu: gpu { #cooling-cells=<2>; ' + gpu_properties +
                                  '}; fan: fan { #cooling-cells=<2>; }; ' + consumer +
                                  ' thermal-zones { gpu-thermal { trips { old: old { phandle=<0x41>; }; };'
                                  ' cooling-maps { mcu { trip=<&old>; cooling-device=<&fan 30 100>; }; }; }; }; };')
                dtb = root / 'board.dtb'
                subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(dtb), str(source)], check=True)
                def get(node, prop):
                    return subprocess.check_output(['fdtget', '-t', 'x', str(dtb), node, prop], text=True).strip()
                mcu = get('/thermal-zones/gpu-thermal/cooling-maps/mcu', 'cooling-device')
                old_gpu = get('/gpu', 'phandle') if existing else None
                build.add_gpu_cooling(dtb, '/gpu', 0x80)
                self.assertEqual(get('/thermal-zones/gpu-thermal/cooling-maps/mcu', 'cooling-device'), mcu)
                gpu = get('/gpu', 'phandle')
                if existing:
                    self.assertEqual(gpu, old_gpu)
                    self.assertEqual(get('/consumer', 'cooling-device').split()[0], gpu)
                new_map = '/thermal-zones/gpu-thermal/cooling-maps/kbase-gpu'
                self.assertEqual(get(new_map, 'cooling-device').split()[0], gpu)
                self.assertEqual(get(new_map, 'trip'), get('/thermal-zones/gpu-thermal/trips/kbase-throttle', 'phandle'))
