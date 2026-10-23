"""Reject misleading performance passes and persistent/unsafe boot selections."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


perf = module('perf-baseline')
boot = module('vendor-boot-plan')
sensors = module('perf-sensors')


class PerformanceGateTest(unittest.TestCase):
    def report(self):
        run = dict(valid=True, evidence='raw/run.json', config_sha256='a' * 64, value=100)
        return dict(status='ok', direction='higher', policy='throughput', groups=[
            {key: copy.deepcopy(run) for key in ('before', 'candidate', 'after')}
            for _ in range(3)])

    def test_regression_in_one_pair_cannot_be_hidden_by_average(self):
        report = self.report()
        report['groups'][0]['candidate']['value'] = 90
        report['groups'][1]['candidate']['value'] = 200
        self.assertEqual(perf.compare(report)['status'], '性能回退')

    def test_missing_is_not_zero_or_pass(self):
        self.assertEqual(perf.compare({'status': '能力缺失'})['status'], '能力缺失')
        report = self.report()
        report['groups'].pop()
        self.assertEqual(perf.compare(report)['status'], '待测')

    def test_drift_and_mismatched_configuration_invalidate(self):
        report = self.report()
        report['groups'][0]['after']['value'] = 120
        self.assertEqual(perf.compare(report)['status'], '受干扰')
        report = self.report()
        report['groups'][0]['candidate']['config_sha256'] = 'b' * 64
        self.assertEqual(perf.compare(report)['status'], '受干扰')

    def test_nan_and_missing_evidence_never_pass(self):
        report = self.report()
        report['groups'][0]['candidate']['value'] = float('nan')
        with self.assertRaises(ValueError):
            perf.compare(report)
        report['groups'][0]['candidate']['evidence'] = ''
        self.assertEqual(perf.compare(report)['status'], '受干扰')

    def test_latency_floor_and_zero_errors(self):
        report = self.report()
        report.update(direction='lower', policy='latency-ms')
        for group in report['groups']:
            for run in group.values():
                run['value'] = 1
            group['candidate']['value'] = 3
        self.assertEqual(perf.compare(report)['status'], '通过')
        report.update(direction='zero', policy='errors')
        self.assertEqual(perf.compare(report)['status'], '性能回退')

    def test_configuration_cannot_change_between_groups(self):
        report = self.report()
        for run in report['groups'][2].values():
            run['config_sha256'] = 'b' * 64
        self.assertEqual(perf.compare(report)['status'], '受干扰')

    def test_missing_and_unreadable_sensors_are_not_zero(self):
        with patch.object(sensors, 'PATTERNS', ('missing', 'unreadable')), \
                patch.object(sensors.glob, 'glob', side_effect=[[], ['/sensor/power']]), \
                patch.object(sensors.Path, 'read_text', side_effect=PermissionError('denied')):
            result = sensors.snapshot()
        self.assertEqual(result['values'], {})
        self.assertIn('/sensor/power', result['errors'])


CONFIG = '''DEFAULT FullKvm
LABEL FullKvm
 LINUX /edge/Image
 FDT /edge/vim4.dtb
 APPEND root=PARTUUID=test edge_only=1
LABEL Vendor
 LINUX /vmlinuz-5.15.137-vim4kvm
 INITRD /initrd.img-5.15.137-vim4kvm
 FDT /dtb-5.15.137-vim4kvm/amlogic/kvim4n.dtb
 APPEND root=PARTUUID=test console=ttyAML0,921600 cma=512M panic=5
'''


class VendorBootPlanTest(unittest.TestCase):
    def test_resolved_profile_handles_historical_links_without_expanding_variables(self):
        historical = CONFIG.replace('/vmlinuz-5.15.137-vim4kvm', '/Image')
        historical = historical.replace('root=PARTUUID=test console=', '${rootdev} console=')
        _, entries = boot.parse_config(CONFIG)
        result = boot.generate(historical, 'Vendor', entries['Vendor'])
        self.assertIn('/vmlinuz-5.15.137-vim4kvm', result['config'])
        with self.assertRaises(ValueError):
            boot.generate(historical, 'Vendor')

    def test_uses_vendor_initrd_and_arguments_without_default_mutation(self):
        result = boot.generate(CONFIG, 'Vendor')
        self.assertIn('INITRD /initrd.img-5.15.137-vim4kvm', result['config'])
        self.assertIn('cma=512M oops=panic panic=20', result['config'])
        self.assertNotIn('edge_only', result['config'])
        self.assertNotIn('saveenv', result['serial_command'])
        self.assertTrue(result['serial_command'].endswith('; reset'))

    def test_rejects_wrong_default_and_unversioned_artifacts(self):
        for text in (CONFIG.replace('DEFAULT FullKvm', 'DEFAULT Vendor'),
                     CONFIG.replace('/vmlinuz-5.15.137-vim4kvm', '/Image'),
                     CONFIG.replace('INITRD ', '#INITRD ')):
            with self.assertRaises(ValueError):
                boot.generate(text, 'Vendor')

    def test_rejects_injected_commands_and_ambiguous_snapshot(self):
        for suffix in (' init=/evil', ' ; reset', ' ${bootargs}'):
            with self.assertRaises(ValueError):
                boot.generate(CONFIG.rstrip() + suffix, 'Vendor')
        with self.assertRaises(ValueError):
            boot.generate(CONFIG + 'LABEL Vendor\n', 'Vendor')
        with self.assertRaises(ValueError):
            boot.generate(CONFIG.replace('/dtb-5.15', '/../dtb-5.15'), 'Vendor')


if __name__ == '__main__':
    unittest.main()
