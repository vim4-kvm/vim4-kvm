"""Numerical self-loop analysis: layout padding, range and bad measurements."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('display_color', ROOT / 'tools/display-color.py')
COLOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COLOR)


def avi(fmt=0, quantization=2):
    packet = bytearray([0x82, 2, 13, 0, fmt << 5, 2 << 6,
                        quantization << 2 if fmt == 0 else 0, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    packet[3] = -sum(packet) & 255
    return packet


def fixture():
    width, height, stride, padded = 1920, 130, 1952, 144
    _, layout = COLOR.chart(width, height)
    raw = bytearray([73]) * (stride * padded * 3 // 2)
    # Independent BT.709 equations populate each patch, with deliberately
    # non-image padding. Quantization/clipping happens before subsampling.
    for block in layout['blocks']:
        r, g, b = block['rgb']
        yuv = [round(16 + (0.182586 * r + 0.614231 * g + 0.062007 * b)),
               round(128 - 0.100644 * r - 0.338572 * g + 0.439216 * b),
               round(128 + 0.439216 * r - 0.398942 * g - 0.040274 * b)]
        x0, y0, x1, y1 = block['rect']
        for y in range(y0, y1):
            raw[y * stride + x0:y * stride + x1] = bytes([yuv[0]]) * (x1 - x0)
        for y in range((y0 + 1) // 2, y1 // 2):
            for x in range((x0 + 1) & ~1, x1 - 1, 2):
                offset = stride * padded + y * stride + x
                raw[offset:offset + 2] = bytes(yuv[1:])
    meta = dict(width=width, height=height, stride=stride, uv_offset=stride * padded,
                format='NV12', colorspace=3, ycbcr_enc=2, quantization=2)
    return layout, meta, raw


class DisplayColorTest(unittest.TestCase):
    def test_cta_420_map_is_extension_local_and_rejects_bad_references(self):
        base = bytearray(128)
        base[126] = 2
        base[127] = -sum(base) & 255
        def extension(vic, bitmap):
            block = bytearray(128)
            payload = bytes([0x41, vic, 0xe2, 15, bitmap])
            block[:4] = bytes([2, 3, 4 + len(payload), 0])
            block[4:4 + len(payload)] = payload
            block[-1] = -sum(block) & 255
            return block
        edid = base + extension(97, 1) + extension(16, 0)
        self.assertEqual(COLOR.y420_vics(edid), {97})
        with self.assertRaises(ValueError):
            COLOR.y420_vics(base + extension(97, 1) + extension(16, 2))

    def test_padded_native_frames_and_all_greys(self):
        layout, meta, raw = fixture()
        result = COLOR.analyze(layout, meta, [raw] * 3, COLOR.avi_decode(avi()))
        self.assertTrue(result['passed'], [b for b in result['blocks'] if not b['passed']][:2])
        self.assertEqual(len([b for b in result['blocks'] if b['name'].startswith('ramp-')]), 256)

    def test_single_frame_corruption_and_swapped_chroma_fail(self):
        layout, meta, raw = fixture()
        corrupted = bytearray(raw)
        # Red patch centre, first of the three observations only.
        y, x = 16, 600
        for yy in range(y - 4, y + 4, 2):
            corrupted[yy * meta['stride'] + x] += 8
        result = COLOR.analyze(layout, meta, [corrupted, raw, raw], COLOR.avi_decode(avi()))
        self.assertFalse(result['passed'])
        swapped = bytearray(raw)
        for offset in range(meta['uv_offset'], len(raw), 2):
            swapped[offset], swapped[offset + 1] = swapped[offset + 1], swapped[offset]
        self.assertFalse(COLOR.analyze(layout, meta, [swapped] * 3,
                                       COLOR.avi_decode(avi()))['passed'])

    def test_avi_integrity_and_range_endpoints(self):
        bad = avi()
        bad[-1] = 1
        with self.assertRaises(ValueError):
            COLOR.avi_decode(bad)
        for quant in (1, 2):
            decoded = COLOR.avi_decode(avi(quantization=quant))
            for rgb, wire, yuv in [((0, 0, 0), 16 if quant == 1 else 0, 16),
                                   ((255, 255, 255), 235 if quant == 1 else 255, 235)]:
                expected_wire, expected_nv12 = COLOR.reference(rgb, decoded)
                self.assertEqual(expected_wire, [wire] * 3)
                self.assertEqual(expected_nv12, [yuv, 128, 128])

    def test_truncation_and_wrong_capture_contract_rejected(self):
        layout, meta, raw = fixture()
        with self.assertRaises(ValueError):
            COLOR.analyze(layout, meta, [raw[:100]] * 3, COLOR.avi_decode(avi()))
        meta['quantization'] = 1
        with self.assertRaises(ValueError):
            COLOR.analyze(layout, meta, [raw] * 3, COLOR.avi_decode(avi()))


if __name__ == '__main__':
    unittest.main()
