"""Keep repeated variants and unmatched coverage visible in corpus comparisons."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('corpus', Path(__file__).resolve().parents[1] /
                                               'packaging/gpu/corpus-report.py')
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)


class CorpusTest(unittest.TestCase):
    def test_repeated_stage_is_not_overwritten(self):
        line = ('x.shader_test - MESA_SHADER_FRAGMENT shader: 4 instrs, 1.0 cycles, 32 code size, '
                '1 loops, 0:0 spills:fills, 7 registers used\n')
        before = corpus.parse(line + line)
        after = corpus.parse(line + line.replace('32 code', '64 code'))
        result = corpus.compare(before, after)
        self.assertEqual(result['common'], 2)
        self.assertEqual(result['total'][0]['bytes'], 64)
        self.assertEqual(result['total'][1]['bytes'], 96)
        self.assertEqual(len(result['changes']), 1)

    def test_missing_variant_is_not_a_code_size_improvement(self):
        line = ('x.shader_test - MESA_SHADER_VERTEX shader: 4 instrs, 1.0 cycles, 32 code size, '
                '0 loops, 0:0 spills:fills, 7 registers used\n')
        result = corpus.compare(corpus.parse(line + line), corpus.parse(line))
        self.assertEqual(result['only_baseline'], 1)
        self.assertEqual(result['total'][0], result['total'][1])
        with self.assertRaises(ValueError):
            corpus.compare({}, {})
