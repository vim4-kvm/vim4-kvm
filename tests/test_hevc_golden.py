import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'packaging/kernel/hevc-golden/align.py'
SPEC = importlib.util.spec_from_file_location('hevc_golden_align', PATH)
align = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(align)


class GoldenTraceTest(unittest.TestCase):
    def trace(self, writes, mapping=None):
        return align.normalize('HGT p=1 op=E reg=0000 val=00000001\n' + writes +
                               '\nHGT p=7 op=E reg=0000 val=00000007',
                               'custom', 'overrun: 0\ncommit overrun: 0', mapping)

    def test_dma_allocation_changes_do_not_hide_buffer_offsets(self):
        a = self.trace('HGT p=1 op=W reg=3102 val=10000020',
                       {'address_registers': ['0x3102'],
                        'regions': [dict(name='stream', start=0x10000000, size=4096)]})
        b = self.trace('HGT p=1 op=W reg=3102 val=20000020',
                       {'address_registers': ['0x3102'],
                        'regions': [dict(name='stream', start=0x20000000, size=4096)]})
        self.assertTrue(align.compare(a, b)['equal'])
        next(x for x in b[1:] if x['op'] == 'W')['val']['offset'] += 1
        self.assertFalse(align.compare(a, b)['equal'])

    def test_normalization_does_not_mask_non_address_registers(self):
        mapping = {'address_registers': [], 'regions': [dict(name='x', start=0, size=4096)]}
        a = self.trace('HGT p=1 op=W reg=30ce val=00000001', mapping)
        b = self.trace('HGT p=1 op=W reg=30ce val=00000000', mapping)
        self.assertEqual(align.compare(a, b)['first_divergence']['index'], 0)

    def test_reordered_writes_and_missing_phase_are_reported(self):
        a = self.trace('HGT p=1 op=W reg=3102 val=00000000\nHGT p=1 op=W reg=3103 val=00000000')
        b = self.trace('HGT p=1 op=W reg=3103 val=00000000\nHGT p=1 op=W reg=3102 val=00000000')
        self.assertFalse(align.compare(a, b)['equal'])
        b[0]['phases'].append(8)
        a[-3:] = b[-3:]
        self.assertEqual(align.compare(a, b)['first_divergence']['reason'], 'missing phase')

    def test_native_regmap_does_not_duplicate_custom_accesses(self):
        raw = ('HGT p=1 op=E reg=0000 val=00000001\n'
               'HGT p=1 op=W reg=30ce val=00000000\n'
               'regmap_reg_write: fe320000.video-codec reg=c338 val=0\n'
               'regmap_reg_write: unrelated reg=c338 val=1')
        result = align.normalize(raw, 'regmap', 'overrun: 0')
        self.assertEqual([x['reg'] for x in result[1:] if x['op'] == 'W'], [0x30ce])

    def test_loss_and_snapshots_cannot_be_compared(self):
        raw = 'HGT p=1 op=E reg=0000 val=00000001\nHGT p=1 op=W reg=30ce val=00000000'
        good = self.trace('HGT p=1 op=W reg=30ce val=00000000')
        for bad in (align.normalize(raw, 'custom'),
                    align.normalize(raw, 'custom', 'overrun: 2'),
                    align.normalize('CPU:0 [LOST 3 EVENTS]\n' + raw, 'custom', 'overrun: 0'),
                    align.normalize('hevc: timeout wait=00000001', 'snapshot')):
            with self.assertRaises(ValueError):
                align.compare(good, bad)

    def test_stop_at_first_reconstructed_picture(self):
        raw = ('HGT p=1 op=E reg=0000 val=00000001\n'
               'HGT p=5 op=W reg=3301 val=00000001\n'
               'HGT p=7 op=E reg=0000 val=00000007\n'
               'HGT p=8 op=W reg=3301 val=00000000')
        result = align.normalize(raw, 'custom', 'overrun: 0')
        self.assertNotIn(8, result[0]['phases'])

    def test_stream_end_one_past_allocation_needs_explicit_endpoint(self):
        mapping = {'address_registers': ['0x3103'], 'endpoint_registers': ['0x3103'],
                   'regions': [dict(name='stream', start=0x1000, size=0x1000)]}
        self.assertEqual(align.mapped_value(0x3103, 0x2000, mapping),
                         dict(region='stream', offset=0x1000))
        self.assertEqual(align.mapped_value(0x3103, 0x1fff, mapping),
                         dict(region='stream', offset=0xfff))

    def test_volatile_reads_are_preserved_but_optional_in_comparison(self):
        a = self.trace('HGT p=1 op=R reg=3308 val=00000a1d\nHGT p=1 op=W reg=30ce val=00000000')
        b = self.trace('HGT p=1 op=R reg=3308 val=00000a1f\nHGT p=1 op=W reg=30ce val=00000000')
        self.assertTrue(align.compare(a, b)['equal'])
        self.assertFalse(align.compare(a, b, reads=True)['equal'])

    def test_overwritten_ring_buffer_is_rejected(self):
        raw = ('# entries-in-buffer/entries-written: 2/3\n'
               'HGT p=1 op=E reg=0000 val=00000001\nHGT p=1 op=W reg=30ce val=00000000')
        bad = align.normalize(raw, 'custom', 'overrun: 0')
        with self.assertRaises(ValueError):
            align.compare(bad, bad)

    def test_phase_order_difference_is_not_reported_as_equal(self):
        a = self.trace('HGT p=3 op=E reg=0000 val=00000003\n'
                       'HGT p=3 op=W reg=30ce val=00000000\n'
                       'HGT p=4 op=E reg=0000 val=00000004\n'
                       'HGT p=4 op=W reg=3102 val=00000000')
        b = self.trace('HGT p=4 op=E reg=0000 val=00000004\n'
                       'HGT p=4 op=W reg=3102 val=00000000\n'
                       'HGT p=3 op=E reg=0000 val=00000003\n'
                       'HGT p=3 op=W reg=30ce val=00000000')
        self.assertEqual(align.compare(a, b)['first_divergence']['reason'], 'phase order')

    def test_ambiguous_allocation_map_is_rejected(self):
        with self.assertRaises(ValueError):
            align.mapped_value(0x3102, 0x1000, {
                'address_registers': ['0x3102'],
                'regions': [dict(name='stream', start=0x1000, size=0x1000),
                            dict(name='workspace', start=0x1000, size=0x2000)]})

    def test_failed_golden_prefix_is_rejected(self):
        failed = self.trace('HGT p=1 op=W reg=3301 val=00000001')
        failed[0]['phases'].remove(7)
        with self.assertRaises(ValueError):
            align.compare(failed, failed)


if __name__ == '__main__':
    unittest.main()
