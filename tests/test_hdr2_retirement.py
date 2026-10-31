import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('retirement', Path(__file__).resolve().parents[1] /
                                             'packaging/hdr2-pq/check_retirement.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def capture(phase, gen=1, ticket=1):
    return f't7_vdin_buffer: gen={gen} ticket={ticket} index=0 allocator=abcd phys=1048576 phase={phase}'


def encoder(phase):
    return f'wave5_buffers_buffer: allocator=abcd phys=1048576 phase={phase}'


class RetirementTest(unittest.TestCase):
    def test_distinct_exports_same_allocator_and_mapping(self):
        events = [capture(6), capture(0)+' ino=105', capture(1)+' ino=105',
                  encoder(0)+' ino=109', encoder(1)+' ino=109', capture(3), capture(7)]
        self.assertEqual(module.check(events)['encoder_submissions'], 1)
        for address in ('0', '2097152'):
            changed = [line.replace('phys=1048576', 'phys='+address)
                       if 'wave5_buffers' in line else line for line in events]
            with self.assertRaises(ValueError):
                module.check(changed)

    def test_retired_epoch_then_next_epoch(self):
        events = [capture(6), capture(0), capture(1), encoder(0), encoder(1),
                  capture(8), capture(3), capture(7), capture(6, 2, 0), capture(7, 2, 0)]
        result = module.check(events)
        self.assertEqual(result['outstanding'], 0)
        self.assertEqual(result['epochs'][0], dict(generation=1, armed=1,
                                                 completed=1, retired=1, encoded=1))

    def test_stale_encoder_input_and_early_recycle(self):
        prefix = [capture(6), capture(0), capture(1)]
        for suffix in [[capture(8), encoder(0)], [encoder(0), capture(3)],
                       [capture(7), capture(6, 2, 0)], [capture(5)],
                       [encoder(1)], [capture(0)], [capture(3), capture(1)]]:
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                module.check(prefix + suffix)

    def test_capture_reference_release_keeps_imported_dma_outstanding(self):
        prefix = [capture(6), capture(0), capture(1), encoder(0), capture(8), capture(4)]
        result = module.check(prefix + [encoder(1), capture(7)])
        self.assertEqual(result['outstanding'], 0)
        self.assertEqual(result['epochs'][0]['retired'], 1)
        # Neither source cleanup nor an epoch marker substitutes for completion.
        for suffix in [[capture(7)], [capture(6, 2, 0), encoder(1), capture(7)],
                       [capture(0, 1, 2)], [encoder(0)]]:
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                module.check(prefix + suffix)

    def test_incomplete_and_lost_trace(self):
        for events in [[], [capture(6)], ['CPU:0 LOST 4 EVENTS'],
                       [capture(6), capture(7)],
                       ['overrun: 1'], ['commit overrun: 3'], ['dropped events: 7'],
                       ['# entries-in-buffer/entries-written: 20/90']]:
            with self.assertRaises(ValueError):
                module.check(events)
