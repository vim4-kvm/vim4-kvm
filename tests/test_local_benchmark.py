"""Reject misleading comparisons across hardware, memory models or workloads."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'bench', Path(__file__).resolve().parents[1] / 'tools/onekvm-local-bench.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def report():
    return dict(schema=1, workload='buffers-v1', memory_model='file-backed', arch='aarch64',
                gstreamer='1.24.2', dma_heaps=None, samples=3, batch_ms=100,
                environment=dict(target='builder', image='same-image'),
                cases=[dict(name='copy', payload_bytes=16, copied_bytes_per_op=16,
                            ns_per_op=[9, 10, 11], median_ns=10, p95_ns=11)])


class BenchmarkTests(unittest.TestCase):
    def test_comparison_allows_new_source_but_reports_regression(self):
        old = report()
        new = copy.deepcopy(old)
        new['source'] = dict(revision='new-optimized-source')
        new['cases'][0].update(median_ns=12, p95_ns=22, ns_per_op=[10, 12, 22])
        result = bench.compare(new, old)[0]
        self.assertAlmostEqual(result['median_change_pct'], 20)
        self.assertAlmostEqual(result['p95_change_pct'], 100)

    def test_mismatched_targets_and_missing_work_are_rejected(self):
        old = report()
        for key, value in [('arch', 'x86_64'), ('memory_model', 'real DMA'),
                           ('environment', dict(target='vim4')), ('cases', [])]:
            new = copy.deepcopy(old)
            new[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                bench.compare(new, old)
        new = copy.deepcopy(old)
        new['cases'][0]['payload_bytes'] = 8
        with self.assertRaises(ValueError):
            bench.compare(new, old)

    def test_failed_or_partial_runs_cannot_produce_successful_results(self):
        good = report()
        text = 'test some::name ... ' + bench.MARKER + json.dumps(good) + '\nok\n'
        self.assertEqual(bench.parse_result(text), good)
        for output in ['', text + text]:
            with self.subTest(output=output), self.assertRaises(ValueError):
                bench.parse_result(output)
        for incomplete in [None, {}, dict(schema=1, cases=[{}], samples=3)]:
            with self.subTest(incomplete=incomplete), self.assertRaises(ValueError):
                bench.parse_result(bench.MARKER + json.dumps(incomplete))
        for values in ([1, 2], [0, 10, 11], [float('nan'), 10, 11]):
            broken = report()
            broken['cases'][0]['ns_per_op'] = values
            with self.subTest(values=values), self.assertRaises(ValueError):
                bench.parse_result(bench.MARKER + json.dumps(broken))
        broken = report()
        broken['cases'][0]['median_ns'] = 0
        with self.assertRaises(ValueError):
            bench.compare(good, broken)


if __name__ == '__main__':
    unittest.main()
