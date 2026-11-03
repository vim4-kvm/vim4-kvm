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

    def window_report(self):
        report = self.report()
        report['schema'] = 2
        for index, group in enumerate(report['groups']):
            for side, backend in [('before', 'stock'), ('candidate', 'edge'), ('after', 'stock')]:
                group[side].update(run_id=f'{index}-{side}', backend=backend,
                                   epoch='frozen-build', day='2026-10-31', source_sha256='b' * 64)
        return report

    def test_build_between_windows_and_reused_candidates_invalidate(self):
        report = self.window_report()
        self.assertEqual(perf.compare(report)['status'], '通过')
        report['groups'][0]['after']['epoch'] = 'new-build'
        self.assertEqual(perf.compare(report)['status'], '受干扰')
        report = self.window_report()
        report['groups'][1]['candidate']['run_id'] = report['groups'][0]['candidate']['run_id']
        self.assertEqual(perf.compare(report)['status'], '受干扰')

    def test_cross_day_source_change_and_wrong_backend_invalidate(self):
        for field, value in [('day', '2026-11-01'), ('source_sha256', 'c' * 64), ('backend', 'stock')]:
            with self.subTest(field=field):
                report = self.window_report()
                report['groups'][0]['candidate'][field] = value
                self.assertEqual(perf.compare(report)['status'], '受干扰')

    def test_matrix_includes_recovery_and_obeys_lease_limit(self):
        result = perf.matrix()
        self.assertGreater(result['board_seconds'], 3 * 3600)
        self.assertTrue(all(s['budget_s'] <= 1800 for s in result['segments']))
        self.assertEqual(result['board_seconds'], 7 * sum(
            s['count'] * s['timeout_s'] + s['overhead_s'] for s in result['segments']))

    def test_missing_and_unreadable_sensors_are_not_zero(self):
        with patch.object(sensors, 'PATTERNS', ('missing', 'unreadable')), \
                patch.object(sensors.glob, 'glob', side_effect=[[], ['/sensor/power']]), \
                patch.object(sensors.Path, 'read_text', side_effect=PermissionError('denied')):
            result = sensors.snapshot()
        self.assertEqual(result['values'], {})
        self.assertIn('/sensor/power', result['errors'])

    def test_stock_receiver_checks_lock_after_reading_cached_yuv420_timing(self):
        info = 'Hactive: 1920\nVactive: 2160\nColor Space: 3-YUV420\nFrame Rate: 5994\nInterlace: 0'
        for final_lock in ('10000', '00000'):
            with patch.object(Path, 'read_text', side_effect=['10000', info, final_lock]):
                state = sensors.receiver_state('stock')
            if final_lock == '10000':
                self.assertEqual((state['width'], state['height'], state['refreshHz']), (3840, 2160, 59.94))
            else:
                self.assertFalse(state['signal'])

    def test_phase_state_separates_uu_desktop_peers_from_webrtc_clients(self):
        api = {'stream/status': {'clients': 0}, 'webrtc/status': {'session_count': 0},
               'config/uu-remote': {'status': {'sessions': [{'id': 'private-peer'}]}},
               'config/vnc/status': {'connection_count': 2}, 'recording': {'recording': True},
               'config/rtsp/status': {'service_status': 'running'}}
        with patch.object(sensors, 'api_status', side_effect=api.__getitem__), \
                patch.object(sensors, 'receiver_state', return_value={'signal': True}), \
                patch.object(sensors.subprocess, 'check_output', return_value='active'):
            state = sensors.phase_state('edge')
        self.assertEqual(state['uu_desktop_sessions'], 1)
        self.assertEqual(state['webrtc_sessions'], 0)
        self.assertEqual((state['vnc_connections'], state['recording'], state['rtsp_service']),
                         (2, True, 'running'))
        self.assertEqual(state['rtsp_connections'], '未核实')
        self.assertEqual(state['external_subscriber_count'], '未核实')
        self.assertNotIn('private-peer', repr(state))


CONFIG = '''DEFAULT Mainline
LABEL Mainline
 LINUX /kernels/7.3.1-vim4kvm-uhd7+/Image
 FDT /kernels/7.3.1-vim4kvm-uhd7+/vim4.dtb
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
        for text in (CONFIG.replace('DEFAULT Mainline', 'DEFAULT Vendor'),
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
