"""A case-folding shared volume must not silently lose kernel modules."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'final_package', Path(__file__).resolve().parents[1] / 'packaging/kernel-edge/package-final.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class ModuleInventoryTest(unittest.TestCase):
    def test_case_collision_is_an_incomplete_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = root / 'modules'
            target = modules / 'kernel/net/netfilter/xt_dscp.ko.xz'
            target.parent.mkdir(parents=True)
            target.touch()
            order = root / 'modules.order'
            order.write_text('net/netfilter/xt_dscp.o\nnet/netfilter/xt_DSCP.o\n')
            with self.assertRaisesRegex(RuntimeError, 'missing=.*xt_DSCP.ko'):
                package.verify_modules(modules, order)

    def test_complete_compressed_inventory_accepts_build_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = root / 'modules'
            modules.mkdir()
            (modules / 'kernel').mkdir()
            (modules / 'kernel/encoder.ko.xz').touch()
            (modules / 'kernel/capture.ko.xz').touch()
            order = root / 'modules.order'
            order.write_text('encoder.o\ncapture.o\n')
            package.verify_modules(modules, order)


class DisplayProfileTest(unittest.TestCase):
    def test_m1_without_driver_is_refused_before_reading_dtb(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / '.config').write_text('# CONFIG_DRM_MESON_T7_HANDOFF is not set\n')
            with patch.object(package, 'run') as read_dtb:
                with self.assertRaisesRegex(RuntimeError, 'built-in T7 handoff'):
                    package.verify_display_profile(output, 'amlogic-t7-a311d2-khadas-vim4-display-m1.dtb')
                read_dtb.assert_not_called()

    def test_m1_rejects_concurrent_framebuffer_or_vpu_and_experimental_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / '.config').write_text('CONFIG_DRM_MESON_T7_HANDOFF=y\n')
            for framebuffer, vpu, compatible, error in (
                ('okay', 'disabled', 'amlogic,t7-display-handoff', 'framebuffer'),
                ('disabled', 'okay', 'amlogic,t7-display-handoff', 'vpu'),
                ('disabled', 'disabled', 'amlogic,t7-display-linear', 'qualified handoff'),
                ('disabled', 'disabled', 'amlogic,t7-display-handoff', None),
            ):
                with self.subTest(framebuffer=framebuffer, vpu=vpu, compatible=compatible):
                    with patch.object(package, 'run', side_effect=[framebuffer, vpu, compatible]):
                        if error:
                            with self.assertRaisesRegex(RuntimeError, error):
                                package.verify_display_profile(output, 'amlogic-t7-a311d2-khadas-vim4-display-m1.dtb')
                        else:
                            package.verify_display_profile(output, 'amlogic-t7-a311d2-khadas-vim4-display-m1.dtb')
