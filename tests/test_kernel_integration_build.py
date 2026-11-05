"""Offline checks for the integration configuration gate; never invoke make."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'integration_build', ROOT / 'packaging/kernel/build-integration.py')
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class IntegrationConfigTests(unittest.TestCase):
    def test_generated_gate_rejects_stale_debug_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / '.config'
            generated = Path(directory) / 'auto.conf'
            config.write_text('CONFIG_MODULES=y\n# CONFIG_KASAN is not set\n')
            generated.write_text('CONFIG_MODULES=y\nCONFIG_KASAN=y\n')
            with self.assertRaisesRegex(ValueError, 'CONFIG_KASAN'):
                BUILD.check_generated_config(config, generated)

    def test_generated_gate_accepts_omitted_disabled_options(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / '.config'
            generated = Path(directory) / 'auto.conf'
            config.write_text('CONFIG_MODULES=y\nCONFIG_TYPEC=m\nCONFIG_CC_VERSION_TEXT="gcc test"\n# CONFIG_KASAN is not set\n')
            generated.write_text('CONFIG_MODULES=y\nCONFIG_TYPEC=m\nCONFIG_CC_VERSION_TEXT=gcc test\n')
            BUILD.check_generated_config(config, generated)

    def test_production_rejects_changed_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / '.config'
            config.write_bytes((BUILD.RECIPE / 'kernel.config').read_bytes())
            BUILD.check_config(config, 'production')
            config.write_text(config.read_text().replace(
                '# CONFIG_FUNCTION_ERROR_INJECTION is not set',
                'CONFIG_FUNCTION_ERROR_INJECTION=y'))
            with self.assertRaisesRegex(ValueError, 'CONFIG_FUNCTION_ERROR_INJECTION'):
                BUILD.check_config(config, 'production')

    def test_debug_rejects_unfulfilled_fragment(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / '.config'
            config.write_bytes((BUILD.RECIPE / 'kernel.config').read_bytes())
            with self.assertRaisesRegex(ValueError, 'CONFIG_KASAN'):
                BUILD.check_config(config, 'debug')

    def test_debug_allows_selected_dependencies_but_rejects_kunit(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / '.config'
            values = BUILD.config_values(BUILD.RECIPE / 'kernel.config')
            values.update(BUILD.config_values(BUILD.RECIPE / 'vdec-debug.config'))
            values['CONFIG_DEBUG_LOCK_ALLOC'] = 'y'
            config.write_text('\n'.join(f'{key}={value}' for key, value in values.items()))
            BUILD.check_config(config, 'debug')
            values['CONFIG_KUNIT'] = 'y'
            config.write_text('\n'.join(f'{key}={value}' for key, value in values.items()))
            with self.assertRaisesRegex(ValueError, 'CONFIG_KUNIT'):
                BUILD.check_config(config, 'debug')
