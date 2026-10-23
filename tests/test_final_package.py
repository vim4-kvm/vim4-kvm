"""A case-folding shared volume must not silently lose kernel modules."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

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
