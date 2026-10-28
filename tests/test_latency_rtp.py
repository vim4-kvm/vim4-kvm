"""RTP identity avoids assigning a later canvas frame to an earlier callback."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'latency_rtp', Path(__file__).resolve().parents[1] / 'tools/latency-rtp-summary.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RtpLatencyTests(unittest.TestCase):
    def setUp(self):
        self.source = [{'id': 1, 'sourceMs': 1000}, {'id': 2, 'sourceMs': 1017}]
        self.receiver = dict(rtpTimeline=True, before={'ssrc': 9}, after={'ssrc': 9},
            timeline=[dict(rtpTimestamp=9000, presentationWallMs=1070, receiveWallMs=1067,
                           clockUncertaintyMs=1),
                      dict(rtpTimestamp=10500, presentationWallMs=1090, receiveWallMs=1088,
                           clockUncertaintyMs=1)],
            frames=[{'rtpTimestamp': 9000, 'id': 2}])
        self.mapping = dict(ssrc=9, frames=[dict(rtpTimestamp=9000, id=1, valid=True),
                                         dict(rtpTimestamp=10500, id=2, valid=True)])

    def test_uses_rtp_identity_even_when_canvas_has_advanced(self):
        result = module.summarize(self.source, self.receiver, self.mapping)
        self.assertEqual(result['presentationMs']['median'], 71.5)
        self.assertEqual(result['receiveToCompositorMs']['median'], 2.5)
        self.assertEqual(result['pixelReadbackMismatches'], 1)
        self.assertTrue(result['completeAssociation'])
        self.assertFalse(result['p99SampleCountSufficient'])

    def test_missing_association_is_visible_and_cannot_pass_p99(self):
        # Even 1000 successful associations cannot hide a missing slow frame.
        self.source = [{'id': i, 'sourceMs': 1000 + i * 17} for i in range(1001)]
        self.receiver['timeline'] = [dict(rtpTimestamp=i * 1500,
            presentationWallMs=f['sourceMs'] + (5000 if i == 1000 else 70),
            clockUncertaintyMs=1) for i, f in enumerate(self.source)]
        self.receiver['frames'] = []
        self.mapping['frames'] = [dict(rtpTimestamp=i * 1500, id=i, valid=True)
                                  for i in range(1000)]
        result = module.summarize(self.source, self.receiver, self.mapping)
        self.assertEqual(result['matchedCallbacks'], 1000)
        self.assertEqual(result['unmatched'], {'rtp_not_mapped': 1})
        self.assertTrue(result['p99SampleCountSufficient'])
        self.assertFalse(result['completeAssociation'])
        self.assertFalse(result['p99AssociationComplete'])

    def test_rejects_ambiguous_or_unverified_mapping(self):
        for mutate in (
            lambda m: m['frames'].append(copy.deepcopy(m['frames'][0])),
            lambda m: m['frames'][0].update(valid=False),
            lambda m: m.update(ssrc=10),
        ):
            mapping = copy.deepcopy(self.mapping)
            mutate(mapping)
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                module.summarize(self.source, self.receiver, mapping)

    def test_rejects_clock_faults_instead_of_dropping_slow_samples(self):
        for mutate in (
            lambda r: r.update(clockDiscontinuities=1),
            lambda r: r['timeline'][1].update(clockUncertaintyMs=3),
            lambda r: r['timeline'][1].update(presentationWallMs=float('nan')),
            lambda r: r['timeline'][1].update(presentationWallMs=1000),
        ):
            receiver = copy.deepcopy(self.receiver)
            mutate(receiver)
            with self.subTest(receiver=receiver), self.assertRaises(ValueError):
                module.summarize(self.source, receiver, self.mapping)

    def test_rejects_source_wrap_and_repeated_callback(self):
        with self.assertRaises(ValueError):
            module.summarize(self.source + self.source, self.receiver, self.mapping)
        self.receiver['timeline'].append(copy.deepcopy(self.receiver['timeline'][0]))
        with self.assertRaises(ValueError):
            module.summarize(self.source, self.receiver, self.mapping)


if __name__ == '__main__':
    unittest.main()
